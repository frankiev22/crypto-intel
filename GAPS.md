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

---

# 2026-09-08: the 24h hold vs pool lifespan — a mismatch we are keeping on purpose

## Correction first: the "6.4h median indexed lifespan" was a censoring artifact

I reported that the median paper-entered pair stays indexed 6.4h and that only
34% are still indexed at 24h. **The 6.4h figure is wrong and is withdrawn.**

It was computed as "the last horizon at which a price resolved", across all
entries. But only 27 of 57 paper-entered pairs have *reached* a 24h checkpoint
yet - the rest are too recent. For those, the last horizon with a price is 6h
because 6h is the last check that has run, not because the pool died. That is
right-censoring read as mortality.

The 34% was also the wrong population: it is the all-pairs number, not the
gate-passing one.

## What the survival curve actually says

Measured as: of the pairs that reached each checkpoint, what fraction still
returned a price.

| checkpoint | all observed pairs | | paper-entered pairs | |
|---|---:|---|---:|---|
| | survival | n | survival | n |
| 1h | 99.7% [99.6, 99.7] | 26,969 | 98.2% [90.7, 99.7] | 57 |
| 6h | 99.6% [99.5, 99.7] | 24,609 | 98.0% [89.7, 99.7] | 51 |
| **24h** | **34.1%** [33.5, 34.7] | 21,876 | **74.1%** [55.3, 86.8] | 27 |
| 168h | 4.2% [3.8, 4.6] | 9,242 | — | — |

Two things follow, and they point in opposite directions:

1. **The market-wide number is brutal and it is solid.** Two thirds of new
   Solana pools stop being publicly price-trackable within a day, n=21,876.
2. **Our entry gate selects pools that last.** 74.1% of gate-passing pairs are
   still trackable at 24h against 34.1% of everything - but on n=27, with an
   interval from 55% to 87%. Suggestive, not established.

**And trackable is not exitable.** Of the 20 paper-entered pairs still priced
at 24h, only 11 - **55% [34.2, 74.2]** - still held $1,000 or more of
liquidity. A price print on a drained pool is the single most common way this
project has been fooled.

## The mismatch, and why we keep it

A 24h hold against a population where a third of pools stop being trackable
inside a day is a design mismatch. It is being kept, deliberately, and the
reason is sample continuity: the 61 entries so far were opened under a 24h
rule, changing it resets the sample to zero, slips n=200 past 2026-09-14, and
structurally suppresses 2x hits (fewer pools reach 2x in 6h than in 24h). Three
costs to buy information we can get for free by labelling instead.

**Revisit after n=200 closes on 2026-09-13, not before.**

---

# Discovery is a ~1%-wide window at birth, and we never look again

*Filed 2026-09-10, from the attempt to build an approach band.*

## The finding

The pre-committed approach band — bonding-curve tokens at 75% or more of the
$69,000 graduation mcap — is **empty in practice**. 21 contracts across five
days, and zero on 9/09 and 9/10.

It is not a band-placement problem, and the FDV distribution says so plainly:

| bonding-curve observations | n=7,033 |
|---|---|
| median FDV | $2,938 |
| p25 / p75 | $2,832 / $3,147 |
| p95 | $42,616 |
| inside the $51,750–$69,000 band | **0.54%** |

We see curve tokens clustered tightly at ~$2,900 — that is, minutes after
launch — and essentially never on the way up. **The window is roughly 1% wide
and it sits at birth.** GeckoTerminal's new-pools feed spans about 37 seconds
of launches per page and dies at page 10, so one pass reaches ~5 minutes back
at best. A token that graduates six hours later does so unobserved.

**So an approach band is not currently buildable.** Not because the threshold
is wrong, but because we have no capability to re-observe a token we have
already seen. The band would work; the sampling cannot feed it.

## What it would cost to fix — measured, not estimated

Dexscreener's token endpoint accepts **30 comma-separated addresses per call**.
Verified live on 2026-09-10 with 30 real curve contracts: one call, 0.380s, 28
of 30 resolved (the 2 that did not are delisted, which is itself the signal).

1,615 distinct bonding-curve contracts were seen in the last 48h → **54 calls
per full sweep.**

| cadence | calls/day | budget/day |
|---|---|---|
| every 6h | 216 | 4.4 min |
| every 4h | 324 | 6.6 min |
| every 2h | 648 | 13.1 min |
| every 1h | 1,296 | 26.3 min |

Against ~2,200 observations/day at one call each, a 6-hourly re-poll is a **~10%
increase in call volume** and 4.4 minutes of wall clock. This is cheap.

## Why it is filed and not built

It is a new capability, not a fix, and it was not asked for. Filing the price
so the decision is a decision. Two things to weigh before building it:

1. It would create a second observation stream with different cadence from the
   discovery stream. Every rate computed across both would need its
   denominator stated, or we get the row-vs-token double-count a fourth time.
2. Re-polling tells us a curve token's FDV rose. It does **not** tell us it
   will graduate, and graduation would not tell us it appreciates. This buys a
   *universe*, not a signal.

## Related, and already fixed

The same shape one level down: `is_graduated` was a venue flag wearing a
graduation name. Renamed `has_amm_pool` on 2026-09-10. Only **86 of 1,730**
AMM contracts (5.0%) were ever observed on a curve first, so the flag could not
have witnessed a graduation in 95% of cases. `graduated` now means the
watchlist milestone only: a contract tracked in the approach band that later
crossed, with a before and an after.

**Those 86 observed curve→AMM transitions are a real graduation detector we
have not built.** n=86 is thin but it is honest, and it is the only graduation
evidence in the corpus that we witnessed rather than inferred.

---

# The closer does not consult the quarantine (v1 and v2, shared)

*Filed 2026-09-14, while auditing v2's B_high wins before reporting them.*

## The finding

`paper.close_decision` prices an exit from the pool as Dexscreener reports it.
It never asks `pricecheck` whether that contract has already been quarantined.
So a contract flagged for **price divergence** can still close as a target, on
the very price that was flagged.

**WIF2** (`HpuPG7dTVXaYf9a2WMJMFkoJ8XqNNiRE9R5vQjLRpQPX`, v2 arm B_high):

| | |
|---|---|
| entered | 2026-09-10 19:07:29Z at $1.46e-05 |
| quarantined `divergent` | 2026-09-10 20:08:50Z — Dexscreener $7.714e-05 vs GeckoTerminal $2.298e-05, **3.36x apart** |
| closed `target` | 2026-09-11 06:44:01Z at $9.287e-05 = **6.361x** — **10.6h after** the quarantine |
| same exit on GeckoTerminal's scale | **1.895x — under the 2.0x target** |

## What it is not

Two other B_high wins sit on quarantined contracts, and they are a different
thing. **RUSH** (+5.2h) and **NeMo** (+3.1h) were quarantined *after* they
closed, both for exit depth falling to dust. They closed on $38,525 and $11,077
of real quote-side depth. The pool draining afterwards does not reach back and
unmake an exit that was available.

## Blast radius

- **v1: none.** None of its six counted wins is on a quarantined contract.
- **v2 B_high: 1 of 4 gated wins.** 4/47 → 3/47 without it.
- v2 A and B_low: none.

## Why it is filed and not fixed

`close_decision` is the pinned exit rule, shared by both ledgers, mid-run.
Adding a quarantine check now changes how positions close after outcomes
exist — tuning, however well-motivated. It is reported both ways instead, and
belongs in the next rule version, pre-committed before that version's first
close.

## A second, related gap: a two-minute target is a quote, not a fill

Three target closes happened within about two minutes of entry: **OPAI** in v1
(5.375x in 1m56s) and v2 (7.890x in 2m25s), and **NeMo** in v2 (2.026x in
1m40s). OPAI's pool held $2,948 of liquidity and $1,475 of quote depth at
entry. A $100 notional is ~7% of that quote side, so the entry price moves
against a real buyer, and a $537 exit is ~16% of the $3,416 exit depth. The
depth floor ($1,000) was sized for a $100 exit, not for a 5x one. Both prints
are genuine, since two independent sweeps saw them minutes apart. What they
cannot show is what a trade would have realised. Same reasoning: disclosed, not
changed mid-run.

# Liveness: the registry was right, and it was still ignored (2026-09-15)

`paper.sweep` and `watchlist.sweep` ran only inside the unstaged full pass,
which the host sandbox kills. The GitHub runner was their only caller, so they
went dark when it stopped on 9/12. The registry caught this. It failed in three
ways anyway:

1. **It fired and escalated, and nobody acted.** `watchlist.sweep`: 91 stale
   findings and 4 duration escalations. `paper.sweep`: 55 findings and 3
   escalations (`data/findings/_seen.json`). The hourly task is told to stay
   silent, so the only readers were Discord and the findings file.
2. **It cried wolf first.** All 104 stale findings for these two components on
   9/10–9/11 were false. The runner had swept within 12h, but a runner beat
   reaches this machine only when the runner's commits are merged. The 42 on
   9/14–9/15 were real, and by then the alarm had taught its readers to ignore
   it.
3. **A manual run silenced it.** The 9/14 20:04Z hand sweep put `paper.sweep`
   back to ok for 12h. A killed ad-hoc full pass at 9/15 03:12Z did the same
   for both components. Meanwhile the staged list still called neither.

**Fixed (57e4608):**
- (3): every beat records its origin, and staleness is judged on unattended
  beats only.
- (2), for these components: the host now runs `--stage sweep` and
  `--stage watchlist` itself every hour, so their health no longer depends on
  unmerged runner commits.

**Not fixed:**
- The registry still cannot see beats from a runner whose commits have not been
  merged, so any component that only the runner exercises is still exposed.
- (1) is a gap in how people act on alerts, not in the code.

# 168h: a retired horizon still spends a stage every hour

`track.py` declares 168h retired (`HORIZONS_RETIRED`), and `score_all` skips
it. But `--stage 168` calls `score_horizon(168)` directly, which bypasses the
retirement, so it still spends ~155s and ~100 calls every hour. It resolves at
2.7–5.1% (n=9,242).

**The contradiction, settled.** From 9/14 18:00Z to ~04:50Z on 9/15:

| | rows |
|---|---|
| arrived into the 168h window | 1,120 |
| scored | 771 |
| aged out of the 18h pending window unscored | 1,618 |
| queue | 2,095 → 826 |

(2,095 + 1,120 − 771 − 1,618 = 826.) Both readings were true. Per pass,
arrivals did outrun scoring. Across the day, the queue fell by expiry, not by
drain. The collector's "N deferred to the next pass" is a standing queue, not a
growth rate, and most of those rows are never reached.

**Recommendation, not action:** stop computing it.

# Two three-minute targets whose pools were drained ten minutes later (2026-09-15)

The first unattended sweep closed two positions in both ledgers, each 2m49s
after entry:
- **Oiled** (`cF343mQ4vkgBuaB2Q4BN4HSbNuxfqcHr292CtbKzZhv`) at 2.918x, on $2,973
  of quote depth.
- **titcoin** (`615SfRNhtqQzM2XzMscSpeq4tNtteq3XuDpQG2AAQyWY`) at 3.353x, on
  $2,000.

Nine minutes later, at 05:17:58Z:
- Oiled's entered pool held $0.67. GeckoTerminal's token read, $33,856, is a
  different pool.
- titcoin's pool held $0.74 on Dexscreener and $0.28 on GeckoTerminal. The two
  sources agree on price.

Both prints were real, and both passed the depth gate. Both were a pump before a
pull. The exits they record, $292 and $335, are ~10% and ~17% of a quote side
that was gone minutes later.

This is the two-minute-target gap above, now with its ending attached. Three of
v1's nine gated wins closed within three minutes of entry: OPAI, Oiled and
titcoin.

| v1 | with them | without them |
|---|---|---|
| measured | 9/76 = 11.84% [6.36, 21.00] | 6/73 = 8.22% [3.82, 16.79] |
| + inferred losses | 9/123 = 7.32% [3.90, 13.32] | 6/120 = 5.00% [2.31, 10.48] |

Reported both ways, and not changed mid-run.

# "Graduated" on the dashboard meant an FDV print, not a pool (fixed 2026-09-15)

A graduation claim fires on `fdv_cross OR real_pool`, and both signatures are
recorded by design. The dashboard listed every live claim without reading
`real_pool`. The result: 21 of 31 claims on record, and 17 of the 24 in the last
seven days, were shown as graduations with no real pool behind them. Most of
those pools held under $1. The first unattended claim, Minecraft
(`4cUCNc1q2fadRdhDgyHpRR7trj63NFDFBebzVTd9zNTG`, 05:10:55Z), was FDV $135,771 on
$0.49 of liquidity and $0.26 of exit depth. Both sources agree on the price and
on a dead pool.

The fix is at the surface: `dashboard.graduated_split` shows only `real_pool`
claims and counts the rest beside them as not graduated. Claim records are
unchanged. The stage is left in the
list because removing a Claude-side stage is not mine to do. To remove it, take
`"168"` out of `collect.STAGES` and delete the matching skill-file line in the
same change; `test_stages.py` checks both.
