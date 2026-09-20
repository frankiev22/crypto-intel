# RULE_V3 result and win verification, 2026-09-20

The evidence behind `PRECOMMIT_paper_v3.md` §11. Run from this folder.

| file | what |
|---|---|
| `verify_wins.py` | puts every v3 exit at ≥ 2.0x through `journal.verify_win`, with quote-side depth and swap direction measured **at the exit moment from the pool's own vaults** and authorities read from the mint account |
| `win_verdicts.json` | the per-token output: depth, sells/buys, authorities, and which of the nine checks each claim passed |

**The verdict is a FAILURE of the rule and a PASS for five of its wins.** Both
are in §11; neither may be quoted without the other.

## ⚠️ Two mistakes the first attempt made, recorded because they are easy to repeat

1. It passed `usd_out` (the ~$217 taken out) as `exit_depth`, which the gate
   tests against an $8,000 **pool quote-side depth** floor. Every claim failed
   `depth_floor` for a reason that had nothing to do with the claims.
2. It judged the `alive` check from **today's** Jupiter quote rather than from
   the moment the position closed. A token dying a day after a completed exit
   says nothing about whether that exit was obtainable.

Both produced "all six FAIL", which looked like a clean negative result and was
a broken harness. ⭐ **A gate written for one pricing model does not transfer to
another without checking what each input means** — the depth floor was written
for outcome rows priced off a pool, where `exit_depth` is the pool's quote side.

## Cost

~350 Helius RPC calls, plus one Jupiter round trip per token. Nothing executed;
both legs of every quote are quotes.
