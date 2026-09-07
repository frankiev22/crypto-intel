# Standing rules

Every rule here was bought with a specific mistake. The mistake is named so the
rule does not get relaxed by someone who has forgotten why it exists.

## Reporting

**1. Report the distribution, not a single statistic.** *Added 2026-09-06.*

This supersedes "medians, never bare means" by generalising it. Means failed
first: the zero-sell cohort had a mean liquidity of $169,061,510 against a
median of $256,219, and best-realizable-multiple has a mean of 0.307 against a
median of 0.000. So the rule became medians.

**Then the median failed too.** Median `vol_h1` appeared to collapse before
graduation — 8,623 in the $40–55k band to 715 in the approach band — which
looked like a real pre-graduation signal. The quartiles showed it was not: below
$55k the p25 is $1,762–$3,091, above it the p25 is **$1**. The population is
bimodal, and the median was reporting a change in the *mix* as if it were a
change in the *level*. Among rows that trade at all, volume does not fall.

    Means hid the tail.  Medians hid the mode.  Quartiles found it.

Quote p25/median/p75 as a minimum. If two summaries disagree, the population is
mixed and needs splitting before any statistic means anything.

**2. Report n alongside every rate, and refuse to conclude below a stated
minimum.** `MIN_N = 30`, declared in code before the data exists so it cannot be
moved to meet a result. `paper.summary()` returns `WITHHELD - k closed, need 30`
and will for weeks; that is correct behaviour.

**3. Use the full denominator.** *Bought 2026-09-06.* Hit rates quoted on the
realizable-outcome denominator read 62.9% and 80%. On every token first seen in
the band they are **0.16%** and **8.87%** — a factor of ~390. Survivorship
enters through the denominator, not the numerator. Open positions and dead
tokens both stay in it.

**4. Lead with the correction.** If a finding contradicts something previously
reported, the correction goes first, before the new result.

**5. Every claim is backed by a query or API call actually made.** No inferred
numbers, no "approximately" standing in for something unmeasured.

## Measurement

**6. `actual_elapsed_h`, never `horizon_h`.** The label is nominal; a "1h" check
has landed as late as 6.0h. Read the elapsed time that was recorded.

**7. Key on contract address, never ticker.** 57.9% of tokens share a ticker
with another; FLORK alone has 25 distinct contracts.

**8. Exit depth is the quote side only.** `liquidity.usd` counts both sides with
the base valued at its own price. Five measured pools overstated tradeable depth
by 125.6–125.8x.

**9. Split bonding curve from AMM before any analysis.** They are 227x apart —
0.01% vs 2.27% at ≥2x — and pooling them dilutes one with the other.

## Shipping

**10a. A win must clear a GATE, not a checklist.** *Added 2026-09-07, after the
fourth headline result evaporated.* `journal.verify_win()` runs inside
`record_outcome()` before any row is written, and records each failed check by
name. Pair identity, depth measured, depth floor, sell side, source agreement,
plausibility, elapsed recorded, alive. **Treat every win as contaminated until
specifically proven otherwise** — the four that died (718x, liquidity gradient,
low-score inversion, half the win record) all had checks that existed and were
not applied. Adding a check to the gate applies it everywhere at once; a
checklist depends on someone remembering, which caught it about half the time.

**10. No detector filters, scores or backfills until it reports precision and
recall with counts against a labelled set built from reserves**, both classes.
A filter with an unmeasured false-positive rate is worse than none, because it
discards real data silently. A score-zeroing gate shipped on unvalidated
evidence and was withdrawn the same day.

**11. Deduplication suppresses repetition. It must never suppress duration.**
A two-day outage produced one ping because the class was already in `_seen.json`.
Health findings escalate with age and re-alert every 6h.

**12. Alerts must not fire on normal variation.** *Added 2026-09-06.* News
volume drops 4–5x every weekend, in all four outlets together. A volume alert
would fire two days in seven and be muted within a week. Calibrate thresholds
against the observed distribution so nothing in the historical record would have
fired, then alert per-source so independent failures cannot collapse into one
suppressed ping.

**13. Nothing is ever deleted.** Data ages out of Postgres, not out of
existence. A mistaken paper-log entry is closed with a `void` record and stays
on the chain.

**14. Prefer forward records to retrospective ones.** Three findings have died
of leakage — the liquidity gradient, the score reversal, the graduation
predictor — each a restatement of progress already made. History has no ordering
we can trust; a forward append-only log does.

## Operating

**15. Free tools only.** Surface paid options with prices. Never sign up.

**16. Analysis and simulation only.** No trades, no wallet or exchange writes,
no specific buy recommendations.

**17. Secrets go in the runner's secret store.** Never commit a key, never print
one, never put a `service_role` key anywhere a browser can reach it.

**18. Report the cost before building.** Passes, API calls, latency, and monthly
price where money is involved — so the decision is made with a number.
