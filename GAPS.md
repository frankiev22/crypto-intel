# What stands between this system and risking real money

2026-09-07. Written because Frank wants to trade. **Nothing here is softened.**

The one-line answer: **this system has never had a profitable entry rule, and the
one forward-recorded strategy it does have is currently losing money — median
outcome 0.40x on 7 closed positions.** The fraud detector works and answers a
different question.

---

## Part 1 — The walls. These may never close.

A wall is a hole where the honest read is that the base rate for success is low
and we have evidence, not just absence of success.

### W1. Entry prediction. Five attempts, five retractions.

| attempt | how it died |
|---|---|
| the 718x | contaminated — priced off a pool we did not hold |
| liquidity-trajectory gradient | leakage — feature at 1h, outcome from entry; 11/11 wins were already ≥2x before the decision point |
| low-score reversal | leakage, same shape |
| graduation predictor | leakage, retracted in the same report it was found |
| age-keyed magnitude gate | `age_hours` is PAIR age; a new pool for an old token looks like a new token. Withdrawn same day |

**0 for 5.** Every one looked like a real result first. The pattern is not bad
luck: retrospective analysis on a dataset where survivors are the only rows that
persist will keep producing them, and this dataset loses non-survivors by
construction (Dexscreener stops indexing: 1h 99.9%, 6h 99.9%, 24h 36.8%,
168h 5.2%).

**What would count as passing:** a rule specified in writing *before* the data
it is scored on exists, holding a precision interval clear of the base rate at
n≥200 forward closes. That is the only design that has ever survived here — it
is why D1 held when four retrospective findings did not.

**This is a wall, not a task.** Do not put it on a schedule.

### W2. Coverage is 1.9% of the launch stream.

Measured: median discovery window 234s/pass, ~7 passes/day = **1.9% of a 24h
stream**. Raising it is bounded by GeckoTerminal's page-10 ceiling and a
~30/min budget that is already saturated.

**Why it is nearly a wall:** it is not fixable with free tools, and more
importantly *it does not matter for trading*. If there is no edge, seeing more
launches produces more losing trades. Coverage matters for research, not for
Frank's money. **Deprioritised deliberately.**

---

## Part 2 — The work. These close with measurable effort.

### G1. The paper log has no usable n. *(engineering + time only)*

7 closed. Hit rate 14.3% **[2.6, 51.3]** — an interval so wide it excludes
nothing. See Part 3 for the date arithmetic.

**Passing:** n≥200 closes, interval width ≤10pp. **~2026-09-14.**

### G2. 43% of closes could not be priced at all. *(open question, then work)*

Of 7 closes: 1 target hit, 3 expiry, **3 unpriceable — the source dropped the
pair before exit.**

This is the single most important unresolved item, because it is **ambiguous
between two opposite realities**:

- *the index lost it* — the pool is fine, we simply cannot see it (Dexscreener
  drops 63% of pairs by 24h, which is measured and expected), **or**
- *the pool drained* — a real holder could not have sold either.

For paper accounting they are the same non-event. **For Frank's money they are
the difference between a position and a total loss.** Nothing in the current
stack can tell them apart, because both look identical from a single source.

**Passing:** an independent on-chain reserve read at exit that resolves ≥90% of
unpriceable closes into drained/alive. **Unblocked 2026-09-07 — the key was already in `.env`.** ~108 calls.

### G3. Ground truth is single-source. *(engineering, blocked on the key)*

`exit_depth_usd` comes from Dexscreener's reserve split. Every label D1 is
scored against derives from it. **If that field is ever wrong, D1 is
unfalsifiable** — the detector and its report card share one source.

The features are non-reserve fields, so there is no circularity in the
*inputs*. The exposure is entirely in the *labels*.

**Passing:** re-derive reserves on chain for all 54 flagged rows and confirm the
one-sided classification. **~108 RPC calls = 0.011% of Helius's free tier.**

### G4. Holder concentration and deployer history are unmeasured. *(blocked)*

~~Blocked~~ **LIVE as of 2026-09-07.** `getTokenLargestAccounts` returns 429 on
the *public* endpoint at any spacing, but returns in **94–193ms through Helius**,
whose key was in `.env` all along. Concentration now runs.
These are the two causal features most likely to catch what D1's 50% recall
misses.

**Passing:** measured on ≥200 labelled rows, reported with an interval, kept only
if it is a distinct mechanism from D1 (zero-overlap test, as D2 passed).

### G5. D2 is in-sample and unquotable. *(time only)*

Derived 2026-09-07 from the rows it is scored on. 100% [80.6, 100] means
nothing yet.

**Passing:** scored only on rows observed after 2026-09-07, n≥30 flagged.

---

## Part 3 — The paper log, and the date

| | |
|---|---|
| entries | 31 |
| closed | **7** |
| open | 24 (all close within 24h) |
| wins | **1** (WOFI, 2.02x, on $462,501 of quote depth) |
| expiry | 3 — at **0.000x, 0.024x, 0.779x** |
| unpriceable | **3** |
| **median multiple** | **0.4015x** |
| p25 / p75 | 0.00028x / 0.779x |
| hit rate | 14.3% **[2.6, 51.3]** — withheld, n<30 |

**The median position lost 60%.** One position went to 0.000x. That is the
strategy the system currently expresses, recorded forward, and it is losing.

Sustainable entry rate, measured: **28 qualifying pools/day** (0.94% of 2,983
daily observations pass `qualifies()`).

| n closed | date | interval at today's 14.3% | width |
|---|---|---|---|
| 30 | **2026-09-08** | [5.3, 29.7] | 24pp |
| 100 | 2026-09-11 | [8.5, 22.1] | 14pp |
| **200** | **2026-09-14** | [10.3, 20.0] | **10pp** |
| 400 | 2026-09-21 | [11.2, 18.0] | 7pp |

**n=30 arrives tomorrow and means almost nothing** — it unlocks *reporting*, not
confidence. **2026-09-14 is the first date any statement about edge is worth
hearing**, and only if the rate holds.

Entry rate is *not* the bottleneck — 28/day is ample. No loosening needed, and
loosening the criteria would only add positions the depth filter exists to
exclude.

---

## Part 4 — Ranked by what most reduces the chance Frank loses money

1. **Disambiguate the 43% unpriceable rate (G2).** This is the sharpened version
   of "exit depth is the top item" — and the sharpening matters. Exit depth is
   already measured, is already the entry gate, and is already D1's ground
   truth. What is *not* handled is **exit liquidity persistence**: the pool being
   unreachable when you want out. Nearly half of all closes hit it.
2. **Independent ground truth (G3).** Makes the one validated thing falsifiable.
3. **Paper n to 200 (G1).** Time, already running.
4. **Concentration + deployer (G4).** Best candidates for D1's missing 50%.
5. Coverage. Last, deliberately.

Items 1, 2 and 4 were all blocked on the same free key, **which we already had**. They are now unblocked and are work, not asks.

---

## Part 5 — Small stakes vs real size

**Superseded 2026-09-07, and the earlier table was too kind.** It used a
one-way 1/20-of-depth rule of thumb. Frank round-trips: he buys AND sells, and
pays the pool fee twice. Modelled properly on constant-product impact
(`2 x size/(depth+size) + 2 x 0.25% fee`) across 71 tradeable-shape pools,
median quote-side depth **$13,330**:

| size | p25 (good) | MEDIAN | p75 | p90 (bad) | under 5% | over 20% |
|---|---|---|---|---|---|---|
| **$100** | 0.68% | **1.99%** | 7.78% | 12.45% | **70%** | 0% |
| $250 | 0.94% | 4.18% | 17.76% | 27.93% | 59% | 21% |
| $500 | 1.38% | 7.73% | 32.28% | 48.74% | 37% | 30% |
| $1,000 | 2.25% | 14.46% | 55.34% | 78.23% | 37% | 32% |

**The cliff is between $100 and $250, not between $500 and $1,000.** At $100 the
median round trip costs 2% and nothing costs more than 20%. At $500 the median
is 7.7% and **30% of pools cost over a fifth of the position to enter and
leave**. On a $1,000 bankroll that is the difference between friction and the
main source of loss.

| position | tradeable within ~5% slippage |
|---|---|
| $100 | 79% of candidates |
| $250 | 69% |
| $500 | 64% |
| $1,000 | **34%** |
| $5,000 | 22% |
| $10,000 | **9%** |

**The cliff is between $500 and $1,000.** Below it, depth is mostly a non-issue
and the binding constraint is whether there is an edge — so small stakes buy
learning speed and nothing else. Above it, **exit liquidity becomes the entire
game**: two-thirds of candidates become untradeable, and the 43% unpriceable
rate stops being an accounting footnote.

Neither size is supported by a measured edge today. The difference is only how
much is lost while finding out.

---

## ⚠️ Correction: the Helius key was never missing

Written this morning as though the key had to be obtained. It has been in
`.env` since 2026-08-23 and is now wired. G3 and G4 were never blocked on Frank;
they were blocked on me not checking. What follows is what it buys, now live.

## What the Helius key buys, in decision terms

Not "better data." Three specific decisions that cannot currently be made:

1. **Whether an unpriceable exit was a dead pool or a blind spot** — the
   difference between a recoverable position and a total loss, on 43% of closes.
2. **Whether D1's labels are real** — 108 calls converts the detector from
   single-source-believed to independently verified.
3. **Whether concentration explains D1's missing half.**

Cost: **~108 calls to verify every flagged row = 0.011% of the free tier.** The
entire labelled set is 0.24%. Monthly production need is ~114k credits against
1M free — **11%**.

It is free, it is 11% utilised, and three of the five open work items are behind
it. Nothing has been signed up for; creating the account is Frank's call.

---

# Open decisions logged 2026-09-07, deliberately NOT taken before the n=200 close

Each of these was found while fixing something else. Each would move a number
that the 2026-09-14 measurement depends on, so each is written down rather than
acted on. Blast radius is measured, not estimated.

## 1. A single uncorroborated source is currently `trustworthy = True`

`pricecheck._validate_fresh` ends on a fallthrough: when only one of
Dexscreener and GeckoTerminal resolves, it takes that price, labels it
`single_source`, and sets `trustworthy = True`. Combined with the guard
`if dl is not None and gl is not None` on the liquidity-divergence test, a
missing second source means the divergence test is SKIPPED, not failed. That
is how KPOP's E9HaVWoQ pair came back clean at 24h after being quarantined at
1h and 6h.

Sticky quarantine (shipped) closes the specific hole: a rejection now binds
later horizons. It does not answer whether an uncorroborated price should
count at all.

**Blast radius, measured across all 88,235 outcome rows:**

| | n |
|---|---:|
| rows labelled `single_source` | 23 |
| `realizable=True` rows that are `single_source` | 13 of 707 (1.8%) |
| realizable 3x+ rows that are `single_source` | 10 of 182 (5.5%) |

Small, but 5.5% of the win column is not nothing, and flipping it mid-run makes
closes non-comparable. **Decide after 2026-09-14.**

## 2. Lookup health counts dead pools as failed lookups

`PRIMARY_OK_FLOOR` was one global 0.5 across every horizon. 24h resolves at
45.5%, so the outage alarm fired every pass - 21 times by midday - while the
underlying number was the best it has ever been (14.1% on 09-01 to 49.3% on
09-08). Per-horizon floors are shipped as the immediate fix.

The deeper problem is the denominator: `source_dropped` is set on ~60% of 24h
rows, and a pool Dexscreener has deindexed because it died is a **measured
outcome**, not a failed lookup. Health should be judged on lookups that could
have succeeded. That changes what the number means, so it is not being done
days before the run closes. **Decide after 2026-09-14.**

## 3. The 0.00796 template rows are still labelled `realizable = True`

Seven of the sixteen distinct pairs in the 2026-09-07 3x+ set carry the
template constant (depth/liq 0.007957-0.007961) that on-chain reads confirmed
as a 781-794x liquidity overstatement. All seven are fluxbeam; the nine
non-template pairs are pumpswap and meteora, ratios 0.474-0.500. Zero
crossover.

They are still marked realizable, and the win gate never ran on them at all
(`win_checks_failed` is null, not `[]`). Auto-quarantining on the template
constant is a one-line change and is deliberately NOT made here: it would
retroactively move the win column during the locked window, and `RULE_V1` and
the paper entry criteria are frozen until 2026-09-14. **Decide after
2026-09-14, and expect the 3x+ column to shrink by roughly 40% when it lands.**
