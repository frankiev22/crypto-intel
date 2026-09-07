# Pre-commitment: score-100 band, and the low-score inversion

Written 2026-09-07 **before any outcome rate was computed.** Sample sizes were
inspected first, because thresholds have to be set against available power; the
rates themselves were not looked at.

Both findings are **retracted-and-untested**, not disproven. They died when
template pools were removed, and templates were identified by the same
Dexscreener field we have since shown is overstated by a median 781x on exactly
those pools. So the removal was done with a contaminated instrument.

## The trap, stated so it can be checked against later

Frank wants these to work. So does the intermediary. So do I. The population is
now small and clean, which is precisely the condition where a spurious result is
easy to find and easy to believe. Thresholds are therefore fixed here, and
**"no separation at available n" is a result I commit to reporting with the same
prominence as a positive one.**

## Population

- **`journal.verified_outcomes()` only** — post-epoch, gate-passing. Pre-epoch
  rows are excluded from every analysis by standing rule, not merely flagged,
  because their pair identity is unverifiable. The 84,019-row historical column
  is **not** usable and will not be quoted.
- Joined back to the observation by `pair` and `observed_ts` for the score.
- **D1/D2-flagged rows excluded.** Those flags are now independently
  corroborated: the pools they mark are overstated by a median 781.61x against
  on-chain reserves, versus 0.97x for everything else.
- **Known limitation, stated in advance:** D1's recall is ~50%, so roughly half
  the fake pools remain in the population. Residual contamination inflates
  apparent win rates, and it does so *more* in whichever band the templates
  favour. Any positive result must be read against that.

## Metric

**Realizable ≥2x rate**, gated on liquidity per standing rule. Reported as a
proportion with a 95% Wilson interval and the count, never a bare rate.

## Available power, measured today

| band | n (verified outcomes) |
|---|---:|
| score 100 | 24 |
| score 50–69 | 22 |
| score 70–99 | 7 |
| score <50 | 1 |
| **total** | **54** |

The whole verified set is 24 hours old and accruing at **~54/day**, so the
bands below reach n=30 within roughly one to two days.

## Hypotheses and thresholds

**H5 — is score 100 the worst band?** Prior claim: yes, which is why `RULE_V1`
trades 70–99 and excludes 100.

- **Primary comparison: score 100 vs score <100.** Better powered, and reaches
  the floor first.
- **Secondary: score 100 vs 70–99.** The decision-relevant pair, reported only
  when both bands clear the floor.
- **Floor: n ≥ 30 in each compared group.** Below it the answer is
  **"underpowered — cannot test"**, with a date, and no rate is quoted.
- **A finding** only if the two 95% Wilson intervals **do not overlap**.
- Direction is pre-stated: the prior claim is that 100 underperforms. A result
  in **either** direction is reported; a reversal is reported more loudly.

**H6 — the low-score inversion.** Prior claim: scores below 70 outperform
scores at or above 70.

- Comparison: score <70 vs score ≥70.
- Same floor (n ≥ 30 each), same non-overlap requirement.

## What I commit not to do

1. **No band boundaries invented after seeing the data.** The four bands above
   are fixed: <50, 50–69, 70–99, 100. No regrouping to find separation.
2. **No dropping the D1/D2 exclusion** if the result is null with it and
   positive without it. Both would be reported if computed, and the pre-declared
   primary is the excluded one.
3. **No moving to the pre-epoch population** for power. It is excluded by rule.
4. **No lowering the n≥30 floor.** H1 sat at 17 of 20 and was reported
   untestable rather than rounded up; the same standard applies here.
5. **The scanner is not changed on the strength of this test alone.** Even a
   clean result at n=30 is one small sample, and `RULE_V1` is locked until
   2026-09-14 regardless.

## Cluster density

Deferred, as instructed. It needs live milestone labels, and those only began
accruing on 2026-09-07 after the mcap tracker was found never to have fired.
Not testable until that set is meaningful.
