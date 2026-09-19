# Cluster-rule test and degentape re-derivation, 2026-09-19

The code and per-token outputs behind the results in `PRECOMMIT_cluster_rule.md`
("Result") and `docs/EXISTING_TOOLS.md` §4a. Run from this folder.

| file | what |
|---|---|
| `cluster_sample.json` | the pre-committed sample: 409 distinct tokens from the 493 AMM rows, 09-12 → 09-18, first sighting each, with the pool's program |
| `cluster_auth.json` | mint/freeze authority at entry per token: `revoked` / `live` / `unknown`, and how it was known |
| `cluster_chain.py` | price and quote depth at a moment, from the pool's own vaults; seeks a pool's history by time via a signature from the block at that time |
| `run_arm.py` | prices an arm: entry after T, outcomes at +6h / +24h |
| `armB_final.jsonl` | arm B (every sample token from its first sighting), 409 rows: 364 priced, 45 unpriced with the reason |
| `armD_input.json`, `armD.jsonl` | arm D: the 7 sample tokens whose first degentape cluster fire fell in [sighting, +2h], and their pricing |
| `cluster_fires.py` | computes arm D's fires from degentape's tape |
| `cluster_eval.py` | scores an arm under the pre-commit, all four reporting variants, Wilson intervals |
| `dt_pull.py` | pulls degentape's public Solana tape (AGGREGATE, read-only, 1 req/s) |
| `dt_positions.py` | rebuilds degentape's closed positions from their own fills; their definition and ours |

⚠️ **degentape's tape itself is not in this repo.** It is their dataset (281,000
rows, 172 MB, pulled 2026-09-19 18:57–19:20Z, 09-11 20:56Z onward); publishing it
here would republish someone else's data. `dt_pull.py` re-pulls it into
`degentape/tape_sol_0912.jsonl`. Their fills were verified on chain on a sample
(182/182, `docs/EXISTING_TOOLS.md` §4a); everything priced in this folder was
priced from chain, never from their fields.

Chain cost of the whole run: ~17,200 Helius RPC calls (arm B 15,690 + reruns 961
+ arm D 508), about 1.7% of the free tier's month.
