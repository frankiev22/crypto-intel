# Is the product fraud detection rather than prediction?

2026-09-07. **Yes. And for the first time in this project, that is a measured
claim rather than an opinion.**

## The argument is an asymmetry in what can be verified

Prediction and fraud detection are not two products of equal difficulty here.
They differ in whether the thing being claimed is *checkable*.

| | prediction | fraud detection |
|---|---|---|
| the claim | this token will run | this pool cannot be exited at its reported size |
| evidence needed | an outcome, measured later | reserves, measured **now** |
| where it comes from | a source that drops 79% of pairs before the outcome lands | the pair object already in hand |
| verifiable after the fact? | **no** — the pool is delisted | **yes** — and it was verifiable at the time |
| track record | 4 findings, 4 evaporated | see below |

The four that died — the 718x, the liquidity-trajectory gradient, the low-score
inversion, and half the win record — all died the same way: the evidence for
them was gone by the time anyone looked. **Zero of 165 all-time wins are
verifiable.** Not disproven; *unverifiable*, which is worse, because it cannot
be argued either way.

Fraud is different in kind. A one-sided pool announces itself in reserves that
we already fetch, at the moment we fetch them. Nothing has to survive for a week
in someone else's index.

## The first validated detector in this repo

Standing rule 10 says nothing filters until it reports precision and recall with
counts against a labelled set built from reserves. **That is now done.**

**Labelled set: n=826 observations** carrying both a measured `exit_depth_usd`
and a reported `liq`, ground truth = `depth/liq`:

    depth/liq   p05 0.0347   p25 0.4966   median 0.5003   p75 0.5112   p95 0.5640

A healthy constant-product pool sits at 0.50, as the arithmetic requires.
**49 of 826 (5.93%) sit below 0.10** — the one-sided population.

**The detector uses only non-reserve fields** — `liq`, `fdv`, `buys_h1`,
`sells_h1` — so it is not scored against its own inputs:

| rule | flagged | TP | FP | FN | precision | recall |
|---|---:|---:|---:|---:|---|---|
| `liq/fdv >= 0.95` | 181 | 41 | 140 | 8 | 22.65% [17.2, 29.3] | 83.67% [71.0, 91.5] |
| `sells==0 & buys>=10` | 30 | 23 | 7 | 26 | 76.67% [59.1, 88.2] | 46.94% [33.7, 60.6] |
| **both together** | **23** | **23** | **0** | 26 | **100.00% [85.7, 100.0]** | 46.94% [33.7, 60.6] |
| either | 188 | 41 | 147 | 8 | 21.81% [16.5, 28.2] | 83.67% [71.0, 91.5] |

**Zero false positives in 23 flags.** The honest claim is **precision ≥ 85.7% at
95% confidence** — not "100%", because n=23.

And the interaction is the whole thing, exactly as `plausibility.py` said it
was: `liq/fdv` alone throws 140 false positives, silence alone throws 7,
**together they throw none.** Neither term is the detector; the conjunction is.

## The honest limitation: recall

**It catches 46.94% [33.7, 60.6] of one-sided pools. It misses half.**

That is the number to attack next, and it must not be attacked by loosening the
conjunction — the "either" row shows what that costs: recall rises to 83.67% and
precision collapses to 21.81%, which is 147 real tokens wrongly flagged.

## False-positive cost, stated plainly

At 0 FPs in 23 the measured cost is zero, but the bound matters more than the
point estimate. At the 85.7% lower bound, roughly 1 in 7 flags could be a real
token.

**The operational cost of that is near zero, for a specific reason:** every
token this detector flags is *already rejected by the scanner on other grounds*
— maximum score 50, most commonly `vol/liq 0.00 - liquidity parked, nothing
trading`. No template observation has ever passed the filter. So flagging them
does not discard anything we would otherwise have acted on.

**Where it does cost something is the record**, and that is where the value is:
these pools supplied 85 of 165 realizable 3x+ "wins" (51.5%). The damage was
never to entries; it was to the yardstick we measured ourselves against.

## The lens, generalised

**A depth floor cannot catch a pool nobody has ever sold into.** $10,045 of real
quote side clears a $100 exit floor honestly. What disqualifies those pools is
that no counterparty has ever existed — the price was set by a curve with nobody
on the other side of it.

So every remaining check asks the counterparty question *before* the magnitude
question:

    has anyone ever sold?            -> sells_h1 == 0 with buys_h1 >= 10
    can the deployer print supply?   -> mint authority live
    can the deployer stop the sale?  -> freeze authority live
    is there a second side at all?   -> exit_depth vs liq

The first three are now hard disqualifiers in `paper.qualifies()` and none of
them is a statistic. They are facts about what the contract permits and what has
actually happened, checked before any number is weighed.

## What the product is, end to end

**A gate that says "you cannot get out of this pool", with a measured error
rate.** Concretely, what exists today:

1. **`journal.verify_win()`** — eight checks at write time, each recorded by
   name: pair identity, depth measured, depth floor, sell side, source
   agreement, plausibility, elapsed recorded, alive.
2. **`plausibility.assess()`** — the validated template fingerprint above.
3. **`onchain.authorities()`** — mint and freeze, one free RPC call, run on
   every row we would act on.
4. **`paper.qualifies()`** — the capability disqualifiers, applied before entry.
5. **`resolve.exit_depth_usd()`** — the quote side, from reserves, the only
   measure here that has never been retracted.

**What it still needs**, in order:

- **Recall.** 46.94% is half the population. The 26 false negatives are the next
  labelled-set question: what do one-sided pools that *do* show sells look like?
- **A bigger labelled set.** n=826 grows every pass now that reserves are stored
  forward. Re-run this table weekly; the precision interval tightens on its own.
- **Holder concentration**, which is the one causal feature still unmeasured.
  Priced at **$0/month** — see `ONCHAIN_COST.md`; it needs a free Helius key,
  not money.

## What I am not claiming

That the scanner should stop scoring. The score is not the product, but it is
how rows get prioritised, and killing it would be a change with no measurement
behind it — the exact mistake this document exists to avoid.

That fraud detection makes money. It does not. It makes the *record* honest,
which is the precondition for ever knowing whether anything else does.

That prediction is impossible. Only that **four attempts have failed, zero wins
are verifiable, and the measurement infrastructure supports one of these two
products and not the other.**
