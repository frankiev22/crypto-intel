# Pre-commitment: is D1 a fraud detector or a fluxbeam detector?

Written 2026-09-07, **before the data exists**. This is the single question that
decides whether Frank has a filter at all.

## The competing hypotheses

**H_venue** — D1 is a proxy for `dex_id == fluxbeam`. One operator, one venue.
Evidence for it today: 33 of D1's 38 flags are fluxbeam; `dex_id == fluxbeam`
alone scores 100% [90.1, 100.0] precision at 46.7% recall, matching D1's 97.37%
[86.5, 99.5] at 49.3%; D1 with fluxbeam removed flags 5 rows at 80% [37.6, 96.4].

**H_general** — the fingerprint is a mechanism that appears wherever the
operator works, and fluxbeam merely dominates the current sample.

## The discriminating evidence is out-of-venue — agreed

Already true and worth stating: **the mechanism is not absent off fluxbeam.**
5 of 1,173 non-fluxbeam labelled rows flag, a rate of **0.426%**. So H_venue in
its strong form ("zero off fluxbeam") is already false. The open question is
whether off-venue flags are *correct*.

## The test

Score D1 **on non-fluxbeam rows only**, with labels from on-chain reserves
(the exact token-swap decoder for token-swap pools, the layout scanner
otherwise). Dexscreener supplies the pool pointer and the claimed liquidity;
the depth numerator comes from chain.

**Sample floor: 20 non-fluxbeam flagged rows carrying on-chain labels.**
Same floor as H1, for the same reason: below it the Wilson interval is wider
than the thing being measured.

**Timing, measured not guessed.** Non-fluxbeam labelled rows accumulate at
**537/day**. At the observed 0.426% off-venue flag rate, 20 flags needs ~4,692
non-fluxbeam labelled rows. We have 1,173. **~3,519 more = 7 days.**

> **Earliest honest read: 2026-09-14.** That is weeks-scale, not days-scale, in
> the sense that matters: nothing can be said before it. It is the same date as
> paper n=200, so both land together.

## Outcomes, fixed now

- **H_general supported** if non-fluxbeam precision ≥ 85% with a 95% lower
  bound ≥ 70% at n ≥ 20. Then D1 is a mechanism and should keep its name.
- **H_venue supported** if non-fluxbeam precision < 70%, or if the flag rate
  off fluxbeam stays below 0.1% so that n=20 is unreachable within 30 days.
  Then **every future report must call it "a fluxbeam/one-operator detector"**,
  not a fraud detector, and its value is scoped to that venue.
- **Inconclusive** otherwise, and reported as inconclusive.

## What must not happen

- No lowering the floor because the answer is nearly there. H1 sat at 17 of 20
  on 2026-09-07 and was reported untestable rather than rounded up.
- No adding venues to the exclusion until the test completes.
- If fluxbeam pools stop appearing entirely, that is **not** a pass for
  H_general — it is loss of the sample, and is reported as such.
