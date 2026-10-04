#!/usr/bin/env python3
"""extract_pools.py (version 2.1): read and verify Uniswap V3 pool state from Ethereum.

Writes real_pool_state.csv, tick_liquidity_net.csv and run_metadata.json.

Reproduce the filed run:
    pip install web3 requests
    python3 extract_pools.py --block 26112406 --rpc-a URL_A --rpc-b URL_B
Re-reading an old block needs RPC providers that serve historical (archive) state.
Without --block the script reads the latest finalized block, which changes over time.

How it works
  * The pools to read are fixed (DEFAULT_POOLS, or --pools FILE, one address per line).
    DexScreener is used only with --discover, to propose candidate addresses.
  * All state is read from two independent RPC providers at one block number. Both
    must return the same block hash, and every value read must match exactly.
  * All initialized ticks are scanned over the full tick range. Two exact checks
    must pass for every pool: liquidityNet sums to zero over all ticks, and the sum
    of liquidityNet at ticks at or below the current tick equals active liquidity.
  * Nothing is written unless every pool passes every check.
"""
import argparse
import csv
import hashlib
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timezone
from importlib import metadata

from web3 import Web3

SCRIPT_VERSION = "2.1"
CHAINS = {
    "ethereum": {"chain_id": 1, "rpcs": ["https://ethereum-rpc.publicnode.com",
                                         "https://eth.drpc.org"]},
    "arbitrum": {"chain_id": 42161, "rpcs": ["https://arbitrum-one-rpc.publicnode.com",
                                             "https://arb1.arbitrum.io/rpc"]},
}
DEFAULT_CHAIN = "ethereum"
DEFAULT_POOLS = [
    "0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6",  # TSLAx/USDC, 0.30% fee
    "0xEC32103fC313A4719960961Ef99EddcBbb4816DF",  # MSTRx/USDC, 0.30% fee
    "0xde9A4FF448252248D7Bc4F21FD20975FFd5290D2",  # MSTRx/USDC, 1.00% fee
]
DISCOVERY_QUERIES = ["xStock", "TSLAx", "NVDAx", "AAPLx", "SPYx", "MSFTx", "GOOGLx",
                     "AMZNx", "METAx", "COINx", "MSTRx", "CRCLx", "HOODx", "QQQx"]
STABLES = {"USDC", "USDT", "DAI", "USDC.E"}
STOCK_RE = re.compile(r"^[A-Z]{1,5}x$")      # xStocks symbol convention, e.g. TSLAx
ALLOWED_FEES = {100, 500, 3000, 10000}       # 0.01, 0.05, 0.30, 1.00 percent
MIN_TICK, MAX_TICK = -887272, 887272
RETRIES, RETRY_DELAY = 3, 1.0

CSV_COLUMNS = ["pool_address", "token_symbol", "paired_asset", "reserve_token",
               "reserve_paired", "fee_tier", "current_tick", "active_liquidity",
               "block_number",
               # added in version 2, after the original nine columns
               "fee_pct", "sqrt_price_x96", "token_address", "paired_address",
               "token0_is_stock", "block_hash", "block_timestamp_utc"]
TICK_COLUMNS = ["pool_address", "block_number", "tick", "liquidity_net"]

POOL_ABI = [
    {"name": "slot0", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"name": n, "type": t} for n, t in [
         ("sqrtPriceX96", "uint160"), ("tick", "int24"), ("observationIndex", "uint16"),
         ("observationCardinality", "uint16"), ("observationCardinalityNext", "uint16"),
         ("feeProtocol", "uint8"), ("unlocked", "bool")]]},
    {"name": "liquidity", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "uint128"}]},
    {"name": "fee", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "uint24"}]},
    {"name": "tickSpacing", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "int24"}]},
    {"name": "token0", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "address"}]},
    {"name": "token1", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "address"}]},
    {"name": "tickBitmap", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "int16"}], "outputs": [{"type": "uint256"}]},
    {"name": "ticks", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "int24"}],
     "outputs": [{"name": "liquidityGross", "type": "uint128"},
                 {"name": "liquidityNet", "type": "int128"},
                 {"type": "uint256"}, {"type": "uint256"}, {"type": "int56"},
                 {"type": "uint160"}, {"type": "uint32"}, {"type": "bool"}]},
]
ERC20_ABI = [
    {"name": "symbol", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "string"}]},
    {"name": "decimals", "type": "function", "stateMutability": "view", "inputs": [],
     "outputs": [{"type": "uint8"}]},
    {"name": "balanceOf", "type": "function", "stateMutability": "view",
     "inputs": [{"type": "address"}], "outputs": [{"type": "uint256"}]},
]


class ExtractError(Exception):
    """A check failed. Nothing is written."""


def retry(fn):
    for attempt in range(RETRIES):
        try:
            return fn()
        except Exception:
            if attempt == RETRIES - 1:
                raise
            time.sleep(RETRY_DELAY * (2 ** attempt))


def call(contract_fn, block):
    return retry(lambda: contract_fn.call(block_identifier=block))


def connect(urls, chain_id):
    good = []
    for url in urls:
        try:
            w3 = Web3(Web3.HTTPProvider(url, request_kwargs={"timeout": 30}))
            if w3.eth.chain_id != chain_id:
                print("  skipping %s: chain id %s, expected %s" % (url, w3.eth.chain_id, chain_id))
                continue
            good.append(w3)
        except Exception as exc:
            print("  RPC unavailable %s: %s" % (url, exc))
    if len(good) < 2:
        raise ExtractError("need two working RPC providers for the cross-check")
    return good[0], good[1]


def utc(ts):
    return datetime.fromtimestamp(int(ts), tz=timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def pick_block(wa, wb, target):
    if target is None:
        # use the older of the two finalized blocks so both providers have it
        number = min(wa.eth.get_block("finalized")["number"],
                     wb.eth.get_block("finalized")["number"])
    else:
        number = int(target)
    blk_a, blk_b = wa.eth.get_block(number), wb.eth.get_block(number)
    hash_a, hash_b = Web3.to_hex(blk_a["hash"]), Web3.to_hex(blk_b["hash"])
    if hash_a != hash_b:
        raise ExtractError("the two RPC providers disagree on the hash of block %d" % number)
    if blk_a["timestamp"] != blk_b["timestamp"]:
        raise ExtractError("the two RPC providers disagree on the timestamp of block %d" % number)
    return {"number": number, "hash": hash_a, "timestamp": int(blk_a["timestamp"])}


def scan_ticks(pool, spacing, block, workers):
    """Return sorted (tick, liquidityGross, liquidityNet) for every initialized tick."""
    first_word = (MIN_TICK // spacing) >> 8
    last_word = (MAX_TICK // spacing) >> 8

    def read_word(word):
        return word, call(pool.functions.tickBitmap(word), block)

    with ThreadPoolExecutor(max_workers=workers) as ex:
        words = list(ex.map(read_word, range(first_word, last_word + 1)))
    ticks = []
    for word, bitmap in words:
        for bit in range(256):
            if (bitmap >> bit) & 1:
                ticks.append(((word << 8) + bit) * spacing)

    def read_tick(tick):
        info = call(pool.functions.ticks(tick), block)
        return tick, int(info[0]), int(info[1])

    with ThreadPoolExecutor(max_workers=workers) as ex:
        return sorted(ex.map(read_tick, ticks))


def read_pool(w3, address, block_number, workers):
    address = Web3.to_checksum_address(address)
    pool = w3.eth.contract(address=address, abi=POOL_ABI)
    slot0 = call(pool.functions.slot0(), block_number)
    tokens = []
    for getter in (pool.functions.token0(), pool.functions.token1()):
        addr = call(getter, block_number)
        erc20 = w3.eth.contract(address=addr, abi=ERC20_ABI)
        try:
            symbol = call(erc20.functions.symbol(), block_number)
        except Exception:
            symbol = "?"
        tokens.append({"address": addr, "symbol": symbol,
                       "decimals": int(call(erc20.functions.decimals(), block_number)),
                       "balance": int(call(erc20.functions.balanceOf(address), block_number))})
    state = {"address": address, "sqrt_price_x96": int(slot0[0]), "tick": int(slot0[1]),
             "liquidity": int(call(pool.functions.liquidity(), block_number)),
             "fee": int(call(pool.functions.fee(), block_number)),
             "spacing": int(call(pool.functions.tickSpacing(), block_number)),
             "tokens": tokens}
    state["ticks"] = scan_ticks(pool, state["spacing"], block_number, workers)
    return state


def check_state(st):
    name = st["address"]
    if st["fee"] not in ALLOWED_FEES:
        raise ExtractError("%s: unexpected fee %s" % (name, st["fee"]))
    if st["spacing"] <= 0:
        raise ExtractError("%s: bad tick spacing %s" % (name, st["spacing"]))
    if min(t["balance"] for t in st["tokens"]) <= 0:
        raise ExtractError("%s: a token balance is zero" % name)
    if not st["ticks"]:
        raise ExtractError("%s: no initialized ticks found" % name)
    for tick, gross, net in st["ticks"]:
        if gross < abs(net):
            raise ExtractError("%s: liquidityGross < |liquidityNet| at tick %d" % (name, tick))
    total = sum(net for _, _, net in st["ticks"])
    if total != 0:
        raise ExtractError("%s: liquidityNet sums to %d, not 0 (incomplete scan?)" % (name, total))
    below = sum(net for tick, _, net in st["ticks"] if tick <= st["tick"])
    if below != st["liquidity"]:
        raise ExtractError("%s: liquidityNet at or below the current tick is %d, but active "
                           "liquidity is %d" % (name, below, st["liquidity"]))


def stock_index(st):
    found = [i for i, t in enumerate(st["tokens"]) if STOCK_RE.match(t["symbol"])]
    if len(found) != 1:
        raise ExtractError("%s: cannot tell which token is the stock (%s)" % (
            st["address"], [t["symbol"] for t in st["tokens"]]))
    return found[0]


def implied_price(st):
    """Price of the stock in units of the paired token, from sqrtPriceX96."""
    i = stock_index(st)
    t0, t1 = st["tokens"]
    raw_price = (st["sqrt_price_x96"] / 2 ** 96) ** 2
    token1_per_token0 = raw_price * 10 ** (t0["decimals"] - t1["decimals"])
    return token1_per_token0 if i == 0 else 1 / token1_per_token0


def make_row(st, block):
    i = stock_index(st)
    stock, paired = st["tokens"][i], st["tokens"][1 - i]
    return {"pool_address": st["address"], "token_symbol": stock["symbol"],
            "paired_asset": paired["symbol"],
            "reserve_token": stock["balance"] / 10 ** stock["decimals"],
            "reserve_paired": paired["balance"] / 10 ** paired["decimals"],
            "fee_tier": st["fee"] / 1e6, "current_tick": st["tick"],
            "active_liquidity": st["liquidity"], "block_number": block["number"],
            "fee_pct": "%.2f" % (st["fee"] / 1e4), "sqrt_price_x96": st["sqrt_price_x96"],
            "token_address": stock["address"], "paired_address": paired["address"],
            "token0_is_stock": str(i == 0), "block_hash": block["hash"],
            "block_timestamp_utc": utc(block["timestamp"])}


def discover(chain):
    import requests
    found = []
    for query in DISCOVERY_QUERIES:
        resp = requests.get("https://api.dexscreener.com/latest/dex/search",
                            params={"q": query}, timeout=30).json()
        for p in resp.get("pairs") or []:
            if (p.get("chainId") == chain and p.get("dexId") == "uniswap"
                    and "v3" in (p.get("labels") or [])
                    and STOCK_RE.match(p["baseToken"]["symbol"])
                    and p["quoteToken"]["symbol"].upper() in STABLES
                    and p["pairAddress"] not in found):
                found.append(p["pairAddress"])
    return found


def dexscreener_price(chain, address):
    import requests
    try:
        url = "https://api.dexscreener.com/latest/dex/pairs/%s/%s" % (chain, address)
        pairs = requests.get(url, timeout=30).json().get("pairs") or []
        return float(pairs[0]["priceUsd"]) if pairs and pairs[0].get("priceUsd") else None
    except Exception:
        return None


def sha256(path):
    h = hashlib.sha256()
    with open(path, "rb") as f:
        h.update(f.read())
    return h.hexdigest()


def write_outputs(outdir, rows, tick_rows, meta):
    os.makedirs(outdir, exist_ok=True)
    paths = {"state": os.path.join(outdir, "real_pool_state.csv"),
             "ticks": os.path.join(outdir, "tick_liquidity_net.csv"),
             "meta": os.path.join(outdir, "run_metadata.json")}
    with open(paths["state"], "w", newline="") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    with open(paths["ticks"], "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(TICK_COLUMNS)
        writer.writerows(tick_rows)
    meta["sha256"] = {"real_pool_state.csv": sha256(paths["state"]),
                      "tick_liquidity_net.csv": sha256(paths["ticks"])}
    with open(paths["meta"], "w") as f:
        json.dump(meta, f, indent=2, sort_keys=True)
        f.write("\n")
    return paths


def parse_args(argv):
    ap = argparse.ArgumentParser(description="Read and verify Uniswap V3 pool state.")
    ap.add_argument("--block", type=int, help="block number to read (default: latest finalized)")
    ap.add_argument("--chain", default=DEFAULT_CHAIN, choices=sorted(CHAINS))
    ap.add_argument("--pools", help="file with one pool address per line")
    ap.add_argument("--discover", action="store_true", help="use DexScreener to find pools")
    ap.add_argument("--price-check", action="store_true", help="compare with DexScreener price")
    ap.add_argument("--rpc-a", help="first RPC URL")
    ap.add_argument("--rpc-b", help="second RPC URL (use a different provider from --rpc-a)")
    ap.add_argument("--outdir", default=".")
    ap.add_argument("--workers", type=int, default=6)
    return ap.parse_args(argv)


def main(argv=None):
    args = parse_args(argv)
    chain = CHAINS[args.chain]
    if args.discover:
        addresses = discover(args.chain)
    elif args.pools:
        with open(args.pools) as f:
            addresses = [ln.strip() for ln in f if ln.strip() and not ln.startswith("#")]
    else:
        addresses = list(DEFAULT_POOLS)
    if not addresses:
        raise ExtractError("no pools to read")
    urls = [args.rpc_a, args.rpc_b] if args.rpc_a and args.rpc_b else chain["rpcs"]
    wa, wb = connect(urls, chain["chain_id"])
    block = pick_block(wa, wb, args.block)
    print("chain=%s block=%d hash=%s time=%s" % (args.chain, block["number"], block["hash"],
                                                 utc(block["timestamp"])))
    if args.block is None:
        print("WARNING: no --block given; this run reads the latest finalized block and "
              "cannot be repeated later.")
    rows, tick_rows, pool_meta = [], [], []
    for address in addresses:
        sa = read_pool(wa, address, block["number"], args.workers)
        sb = read_pool(wb, address, block["number"], args.workers)
        if sa != sb:
            keys = [k for k in sa if sa[k] != sb.get(k)]
            raise ExtractError("%s: the two RPC providers returned different %s" % (address, keys))
        check_state(sa)
        row = make_row(sa, block)
        rows.append(row)
        tick_rows.extend([[sa["address"], block["number"], t, n] for t, _, n in sa["ticks"]])
        price = implied_price(sa)
        entry = {"pool": sa["address"], "implied_price": price, "ticks_scanned": len(sa["ticks"])}
        if args.price_check and sa["tokens"][1 - stock_index(sa)]["symbol"].upper() in STABLES:
            ref = dexscreener_price(args.chain, sa["address"])
            entry["dexscreener_price_usd"] = ref
            if ref and abs(price - ref) / ref > 0.05:
                print("WARNING: %s implied price %.4f differs from DexScreener %.4f"
                      % (sa["address"], price, ref))
        pool_meta.append(entry)
        print("OK %s %s/%s fee=%s%% ticks=%d price=%.4f" % (
            sa["address"], row["token_symbol"], row["paired_asset"], row["fee_pct"],
            len(sa["ticks"]), price))
    meta = {"script_version": SCRIPT_VERSION, "run_utc": utc(time.time()), "chain": args.chain,
            "chain_id": chain["chain_id"], "block_number": block["number"],
            "block_hash": block["hash"], "block_timestamp_unix": block["timestamp"],
            "block_timestamp_utc": utc(block["timestamp"]),
            "rpc_a": getattr(wa.provider, "endpoint_uri", "?"),
            "rpc_b": getattr(wb.provider, "endpoint_uri", "?"),
            "client_a": str(wa.client_version), "client_b": str(wb.client_version),
            "web3_version": metadata.version("web3"), "python": sys.version.split()[0],
            "checks_passed": ["identical block hash on both RPCs",
                              "all values identical on both RPCs",
                              "liquidityNet sums to zero over all ticks",
                              "liquidityNet at or below current tick equals active liquidity"],
            "pools": pool_meta}
    paths = write_outputs(args.outdir, rows, tick_rows, meta)
    print("wrote " + ", ".join(sorted(paths.values())))
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except ExtractError as exc:
        sys.exit("ERROR: %s" % exc)
