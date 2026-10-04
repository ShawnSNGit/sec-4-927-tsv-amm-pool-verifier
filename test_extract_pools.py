"""Offline tests for extract_pools.py. Uses a fake web3 module built from the filed CSVs.
Run: python3 test_extract_pools.py

If real_pool_state.csv and tick_liquidity_net.csv are next to this file (or in the folder
named by the NCF_DATA environment variable) they are used. Otherwise a built-in copy of
Attachment E (block 26112406) is written to a temporary folder and used.
These tests check the script's logic. They do not test a live RPC connection."""
import collections
import csv
import json
import math
import os
import sys
import tempfile
import types
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
BLOCK, HASH_A, TS = 26112406, bytes.fromhex("ab" * 32), 1790000000

BUILTIN_STATE = """pool_address,token_symbol,paired_asset,reserve_token,reserve_paired,fee_tier,current_tick,active_liquidity,block_number
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,TSLAx,USDC,0.257134411735595,134.606681,0.003,-216076,668915148720368,26112406
0xEC32103fC313A4719960961Ef99EddcBbb4816DF,MSTRx,USDC,0.33095242097586997,48.228251,0.003,226566,3783315540927,26112406
0xde9A4FF448252248D7Bc4F21FD20975FFd5290D2,MSTRx,USDC,0.008685508536482782,0.283012,0.01,226348,236323508041,26112406
"""
BUILTIN_TICKS = """pool_address,block_number,tick,liquidity_net
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,-887220,2579178483806
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,-219300,10099418942072
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,-216120,656236551294490
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,-216060,-656236551294490
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,-214140,-10099418942072
0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6,26112406,887220,-2579178483806
0xEC32103fC313A4719960961Ef99EddcBbb4816DF,26112406,-887220,3783315540927
0xEC32103fC313A4719960961Ef99EddcBbb4816DF,26112406,887220,-3783315540927
0xde9A4FF448252248D7Bc4F21FD20975FFd5290D2,26112406,225000,236323508041
0xde9A4FF448252248D7Bc4F21FD20975FFd5290D2,26112406,228400,-236323508041
"""


def find_data_dir():
    for d in (os.environ.get("NCF_DATA"), HERE):
        if d and os.path.exists(os.path.join(d, "real_pool_state.csv")) \
                and os.path.exists(os.path.join(d, "tick_liquidity_net.csv")):
            return d
    d = tempfile.mkdtemp(prefix="ncf_data_")
    for name, text in (("real_pool_state.csv", BUILTIN_STATE),
                       ("tick_liquidity_net.csv", BUILTIN_TICKS)):
        with open(os.path.join(d, name), "w", newline="") as f:
            f.write(text)
    return d


DATA = find_data_dir()


def read_text(path):
    with open(path, newline="") as f:
        return f.read()


def read_rows(path):
    with open(path, newline="") as f:
        return list(csv.DictReader(f))


def load():
    state = {r["pool_address"]: r for r in read_rows(os.path.join(DATA, "real_pool_state.csv"))}
    ticks = collections.defaultdict(list)
    for r in read_rows(os.path.join(DATA, "tick_liquidity_net.csv")):
        ticks[r["pool_address"]].append((int(r["tick"]), int(r["liquidity_net"])))
    return state, ticks


STATE, TICKS = load()
if not STATE or not TICKS:
    sys.exit("ERROR: the CSV files in %s contain no data rows" % DATA)
STOCK_FIRST = {"0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6"}   # TSLAx is token0 in this pool


class Fn:
    def __init__(self, chain, name, args):
        self.chain, self.name, self.args = chain, name, args

    def call(self, block_identifier=None):
        return self.chain.answer(self.name, self.args, block_identifier)


class Contract:
    def __init__(self, chain, address):
        self.chain, self.address = chain, address
        self.functions = types.SimpleNamespace()
        for n in ("slot0", "liquidity", "fee", "tickSpacing", "token0", "token1", "tickBitmap",
                  "ticks", "symbol", "decimals", "balanceOf"):
            setattr(self.functions, n, (lambda n: lambda *a: Fn(self, n, a))(n))

    def answer(self, name, args, block):
        return self.chain.answer(name, args, block, self.address)


class Chain:
    """One fake RPC provider. `tweak` lets a test alter what this provider returns."""
    def __init__(self, url, tweak=None, block_hash=HASH_A):
        self.url, self.tweak, self.block_hash = url, tweak or {}, block_hash
        self.calls = 0

    def answer(self, name, args, block, address=None):
        self.calls += 1
        if block != BLOCK:
            raise RuntimeError("fake node has no state for block %r" % (block,))
        row = STATE.get(address)
        stock_first = address in STOCK_FIRST
        if name == "slot0":
            tick = int(row["current_tick"])
            sqrt = int(math.sqrt(1.0001 ** tick) * 2 ** 96)
            return [sqrt, tick, 0, 1, 1, 0, True]
        if name == "liquidity":
            return int(row["active_liquidity"]) + self.tweak.get("liquidity", 0)
        if name == "fee":
            return int(round(float(row["fee_tier"]) * 1e6))
        if name == "tickSpacing":
            return {3000: 60, 10000: 200}[int(round(float(row["fee_tier"]) * 1e6))]
        if name in ("token0", "token1"):
            first = name == "token0"
            stock = (stock_first == first)
            return "0xSTOCK%s" % address[-4:] if stock else "0xUSDC"
        sp = {3000: 60, 10000: 200}[int(round(float(row["fee_tier"]) * 1e6))]
        ticks = [t for t in TICKS[address] if t[0] not in self.tweak.get("drop_ticks", ())]
        if name == "tickBitmap":
            word, bm = args[0], 0
            for t, _ in ticks:
                comp = t // sp
                if comp >> 8 == word:
                    bm |= 1 << (comp & 255)
            return bm
        if name == "ticks":
            net = dict(ticks)[args[0]]
            return (abs(net), net, 0, 0, 0, 0, 0, True)
        raise AssertionError(name)


class TokenContract(Contract):
    def answer(self, name, args, block):
        if block != BLOCK:
            raise RuntimeError("no state")
        addr = self.address
        if addr == "0xUSDC":
            if name == "symbol":
                return "USDC"
            if name == "decimals":
                return 6
            return int(round(float(STATE[args[0]]["reserve_paired"]) * 10 ** 6))
        pool = next(p for p in STATE if p[-4:] == addr[-4:])
        row = STATE[pool]
        if name == "symbol":
            return row["token_symbol"]
        if name == "decimals":
            return 18
        return int(round(float(row["reserve_token"]) * 10 ** 18))


class Eth:
    def __init__(self, chain, chain_id=1):
        self.chain, self.chain_id = chain, chain_id

    def get_block(self, ident):
        n = BLOCK if ident == "finalized" else ident
        return {"number": n, "hash": self.chain.block_hash, "timestamp": TS}

    def contract(self, address, abi):
        if address.startswith("0xSTOCK") or address == "0xUSDC":
            return TokenContract(self.chain, address)
        return Contract(self.chain, address)


class FakeWeb3:
    CHAINS = {}

    class HTTPProvider:
        def __init__(self, url, request_kwargs=None):
            self.endpoint_uri = url

    def __init__(self, provider):
        self.provider = provider
        self.eth = Eth(FakeWeb3.CHAINS[provider.endpoint_uri])
        self.client_version = "FakeNode/1.0"

    @staticmethod
    def to_checksum_address(a):
        return a

    @staticmethod
    def to_hex(b):
        return "0x" + bytes(b).hex()


web3_stub = types.ModuleType("web3")
web3_stub.Web3 = FakeWeb3
sys.modules["web3"] = web3_stub
import importlib.metadata as _md  # noqa: E402
_md.version = lambda name: "stub"
sys.path.insert(0, HERE)
import extract_pools as ep  # noqa: E402
ep.RETRY_DELAY = 0.0


def run(tmp, a_tweak=None, b_tweak=None, hash_b=HASH_A, extra=(), block_args=True):
    FakeWeb3.CHAINS = {"http://a": Chain("http://a", a_tweak),
                       "http://b": Chain("http://b", b_tweak, hash_b)}
    args = ["--block", str(BLOCK)] if block_args else []
    return ep.main(args + ["--rpc-a", "http://a", "--rpc-b", "http://b",
                           "--outdir", tmp] + list(extra))


class Tests(unittest.TestCase):
    def test_happy_path_reproduces_filed_data(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(tmp), 0)
            got = read_rows(os.path.join(tmp, "real_pool_state.csv"))
            self.assertEqual([r["pool_address"] for r in got], list(STATE))
            for r in got:
                f = STATE[r["pool_address"]]
                for col in ("token_symbol", "paired_asset", "fee_tier", "current_tick",
                            "active_liquidity", "block_number"):
                    self.assertEqual(r[col], f[col], col)
                for col in ("reserve_token", "reserve_paired"):
                    self.assertAlmostEqual(float(r[col]) / float(f[col]), 1.0, places=9)
            self.assertEqual([r["fee_pct"] for r in got], ["0.30", "0.30", "1.00"])
            self.assertEqual([r["token0_is_stock"] for r in got], ["True", "False", "False"])
            a = read_text(os.path.join(tmp, "tick_liquidity_net.csv"))
            b = read_text(os.path.join(DATA, "tick_liquidity_net.csv"))
            self.assertEqual(a.replace("\r\n", "\n"), b.replace("\r\n", "\n"))
            with open(os.path.join(tmp, "run_metadata.json")) as f:
                meta = json.load(f)
            self.assertEqual(meta["block_hash"], "0x" + HASH_A.hex())
            self.assertEqual(meta["block_number"], BLOCK)
            self.assertEqual(len(meta["sha256"]), 2)

    def test_latest_finalized_mode_works(self):
        with tempfile.TemporaryDirectory() as tmp:
            self.assertEqual(run(tmp, block_args=False), 0)

    def test_rpc_disagreement_fails_and_writes_nothing(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ep.ExtractError):
                run(tmp, b_tweak={"liquidity": 1})
            self.assertEqual(os.listdir(tmp), [])

    def test_block_hash_mismatch_fails(self):
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ep.ExtractError):
                run(tmp, hash_b=bytes.fromhex("cd" * 32))

    def test_incomplete_tick_data_fails(self):
        drop = (TICKS["0xA7fd774E0aD54A6D2CeAfB4103615f473E589cC6"][0][0],)
        with tempfile.TemporaryDirectory() as tmp:
            with self.assertRaises(ep.ExtractError) as cm:
                run(tmp, a_tweak={"drop_ticks": drop}, b_tweak={"drop_ticks": drop})
            self.assertIn("liquidityNet", str(cm.exception))
            self.assertEqual(os.listdir(tmp), [])

    def test_wrong_block_is_an_error_not_a_silent_fallback(self):
        with self.assertRaises(SystemExit):
            ep.main(["--block", "26112406x"])


if __name__ == "__main__":
    unittest.main(verbosity=2)
