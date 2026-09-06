# The forward-recorded paper log

Started **2026-09-06**, per instruction, with the simplest defensible rule
rather than a good one. The point is the log's integrity, not the rule's
quality. `data/paper/ledger.jsonl`, `paper.py`.

## Why this and not more analysis

Three findings in this repo have now died the same death:

| finding | apparent lift | what it actually was |
|---|---:|---|
| liquidity trajectory | 14.5x | 11 of 11 out-of-sample wins were already >=2x at the decision point |
| score discrimination | 5.4x | reversed itself out of sample (10.77% train -> 2.70% test) |
| graduation prediction | 16.1x | median first-sight FDV $34,290 against a $69,000 threshold — already half way |

Every one looked like a forecast and was a restatement of progress already made.
The defect is not carelessness, it is **ordering**: the feature and the outcome
were measured from the same historical record, and history has no ordering we
can trust. No amount of care with retrospective data fixes that.

A forward log does, because a row is written **before the outcome exists**. That
is the only property this file protects, and it protects it strictly.

## Integrity

- **Append-only.** `_append()` is the only writer in the module.
- **Hash-chained.** Every record carries `prev`, the SHA-256 of the previous
  record's canonical JSON. Editing any earlier row breaks every hash after it.
  `paper.py verify` reports the first index where the chain parts. This does not
  make editing impossible; it makes **silent** editing impossible, which is the
  achievable guarantee.
- **Nothing is deleted.** A row entered in error is closed with a `void` record
  giving the reason. The original stays on the chain.
- **An exit is written once.** Re-closing an entry raises.
- **Exit rule declared at entry.** An exit rule invented after the fact is the
  same leakage in a new costume.
- **Open positions are never dropped from a denominator.** Survivorship in the
  denominator is exactly how the 227x filter got mistaken for an edge.
- **One open position per contract**, keyed on contract address, never ticker.

Verified 2026-09-06 against a scratch ledger — all six behaviours hold,
including tamper detection:

    row 0 edited in place  ->  verify() returns False at index 0,
                               "content does not match its own hash"

## RULE_V1

    venue_type == "amm"       curve tokens are 0.01% >=2x (2 wins in 14,802);
                              AMM tokens 2.27% [1.75, 2.93]. A FILTER, not an
                              edge — it says a position is possible, not good.
    exit_depth_usd >= $1,000  quote side, computed from reserves. The only
                              measure here that has never been retracted.
                              Reported liquidity is unusable: five measured
                              pools overstated it 125.6–125.8x.
    70 <= score <= 99         within the AMM population, 4.55% [2.62, 7.78]
                              against 1.20% [0.64, 2.27] at score 100.

Exit rule, declared now: **first of 2.0x on quote-side depth, or 24h elapsed.**
Notional $100, bookkeeping only — nothing is sized, sent or signed.

Expected hit rate is therefore about 4.5%, so **n will be small for a long
time.** `MIN_N = 30` closed entries is stated in the module before any data
exists, so it cannot be moved to meet a result. `summary()` returns
`WITHHELD - <k> closed, need 30` until then, and it will keep saying that for
weeks. That is correct behaviour, not a fault.

## Live

Wired into `scanner.scan()` inside the enrichment loop, before any outcome
exists. First entries, 2026-09-06T11:57Z:

| symbol | contract | venue | entry | exit depth | score |
|---|---|---|---:|---:|---:|
| `$1` | XWTjthD4kjEssQovbyAL… | pumpswap | $0.026 | $218,729 | 85 |
| WWR | oQCz7rb2UAA7F2R1HrDm… | amm | $0.006646 | $109,655 | — |
| BILL | 5jccNMLQFdUurCo8WDbJ… | amm | $2.528e-06 | $2,252 | — |
| KYIRAD | 9pSqJkymLHcwa5EyVTJR… | amm | $0.02308 | $53,316 | — |

## Not a recommendation

A simulation ledger. It sizes nothing, sends nothing, signs nothing, and no
capital is at risk or implied.

## Open

- Closing is manual (`python paper.py close <hash> <price> <depth>`). Automatic
  closing on the declared exit rule is the obvious next step and is deliberately
  not built yet — an automatic closer that reads a price is another place
  leakage can enter, and it needs its own review.
