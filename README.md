# SEC File No. 4-927: Verifiable On-Chain Evidence for Tokenized Securities Venues

Open-source tooling that reads and independently verifies Uniswap V3 pool state for
tokenized U.S. equities (for example TSLAx), so that public comments in the SEC's
File No. 4-927 rulemaking can rest on evidence anyone can reproduce.

## The rulemaking

The SEC is proposing a five-year pilot program (File No. 4-927) that would grant temporary
exemptions to Tokenized Securities Venues (TSVs). Under the proposal, TSVs could trade
tokenized U.S. equities, such as TSLAx or AAPLx, through blockchain-based Automated Market
Makers (AMMs) without registering as traditional national securities exchanges.

This project supports advocating for a record built on checkable facts. It is intended to
help ordinary investors and the public, who bear the risk when market structure changes,
see how these AMM pools actually behave. The proposal is still open for comment; nothing here
assumes its outcome.

## What the tool does

`extract_pools.py` reads pool state from Ethereum through **two independent RPC providers**
pinned to one block, and writes data only if every check passes:

- both providers return the same block hash and timestamp;
- every value read is identical on both providers;
- all initialized ticks are scanned over the full tick range (-887272 to 887272);
- `liquidityNet` sums to zero over all ticks;
- `liquidityNet` at ticks at or below the current tick equals active liquidity.

Outputs: `real_pool_state.csv`, `tick_liquidity_net.csv`, `run_metadata.json` (with SHA-256
of both CSVs).

## Quick start

```bash
pip install -r requirements.txt
python3 test_extract_pools.py          # offline tests against a fake node
python3 extract_pools.py --block 26112406 --rpc-a URL_A --rpc-b URL_B
```

Re-reading an old block needs RPC providers that serve historical (archive) state.
Without `--block` the script reads the latest finalized block, which changes over time.
`--pools FILE` reads other pool addresses; `--discover` uses the DexScreener public search
API only to propose candidate addresses.

## Example data (`data/`)

`data/real_pool_state.csv` and `data/tick_liquidity_net.csv` are the pool data filed as
Attachment E (Figure 3D) for Ethereum mainnet block 26112406: TSLAx/USDC 0.30%, MSTRx/USDC
0.30% and MSTRx/USDC 1.00%.

> **Provenance note:** these files were produced by an earlier version of the extraction
> script. Version 2.1 in this repository has been tested only against an offline fake node,
> and has not yet been used to re-read block 26112406 from live archive RPCs. Treat
> re-verification under version 2.1 as pending until that run is published.

## Limits

The offline tests check the script's logic, not live RPC behavior. The script covers
Uniswap V3 pools only.

## License

MIT. See `LICENSE`.

Shawn SN. Dedicated to protecting the rights of the voiceless and underrepresented as the
modern landscape evolves.
