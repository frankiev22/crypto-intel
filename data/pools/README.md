# data/pools/

| file | what it is |
|---|---|
| `offsets.json` | the MEASURED mint offset per venue, with the pool each was measured on. ⛔ A venue absent here is never queried, because a guessed offset returns zero rows and zero rows reads as "no pool". |
| `state.jsonl` | the measured pool state per contract under `PRECOMMIT_pool_state.md` **v2**, the §3a amendment. Append-only sidecar, keyed on `token`. ⛔ It does not overwrite any outcome row's `status`. |
| `state_v1_superseded.jsonl` | ⛔ **33 rows measured under the ORIGINAL `pool_closed` rule, which was too loose.** Kept because nothing is deleted (standing rule 8). ⚠️ **Any figure quoted from this file must say it is superseded.** The defect: a pump.fun bonding-curve PDA can be derived for a mint that never launched on pump.fun, and its non-existence was scored `pool_closed` when it means the token was never on that venue. See `PRECOMMIT_pool_state.md` §3a. |

⛔ **No state in either file claims a token is sellable.** A pool holding $41.07
of WSOL returned NO_SELL_ROUTE from Jupiter, measured. The exit is
`chainfields.round_trip()` and only that.

## ⚠️ `state.jsonl` holds MORE THAN ONE ROW for some contracts, on purpose

The file is append-only (standing rule 8). When a reader fix landed mid-day, the
affected contracts were **re-measured and appended**, never edited. So:

- ⭐ **The current answer for a contract is its LAST row**, which is what
  `already_done()` returns and what every tally in `backfill.py` uses.
- ⛔ An earlier row for the same contract is a **superseded measurement**, kept
  as the record of what we said and when. `supersedes_earlier_row: true` marks a
  row that replaced one.
- ⚠️ So **never count rows; count distinct contracts.** The tally prints both.

Fixes that forced a re-measure on 2026-09-23, all in `PRECOMMIT_pool_state.md`:
§3a (`pool_closed` needed evidence the pool once existed), §3b (native SOL on a
bonding curve; vaults read out of the pool's own bytes; an unread quote side is
not $0; the struct scan keeps one authority group), plus `raydium_cpmm` and
`fluxbeam` gaining measured offsets so they are queried at all.
