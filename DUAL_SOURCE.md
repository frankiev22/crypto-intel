# Reading both price sources on every observation: the cost, measured first

2026-09-06. Instruction was to report the added latency and call volume against
the free rate limits **before committing**. Measured, not estimated. **The
answer is no** — not on the free tier, and not close.

## First, a correction to the premise

The second source is **not** read "only on failure". It is read on failure
**and** on every multiple at or above 2.0x — `pricecheck.VALIDATE_ABOVE = 2.0`,
called from `track.py:115`. `pricecheck` pulls Dexscreener and GeckoTerminal
side by side and quarantines on divergence, which is what produced
`quarantined_divergent`, `quarantined_liquidity_divergent` and
`quarantined_multiple_mismatch`.

So both sources already cover the population where a wrong number does damage:
anything that could be announced as a win. The actual gap is **routine
sub-2x observations** — which is where a second opinion is worth least.

## Latency

Twelve contract addresses, one call per address, never batched:

| | median | p90 | n |
|---|---:|---:|---:|
| Dexscreener | **0.116s** | 0.119s | 12/12 resolved |
| GeckoTerminal | **0.180s** | — | 7/12 resolved |

Latency is not the problem. **+0.18s per observation** is affordable.

## Rate limit — this is the problem

GeckoTerminal, unauthenticated, clean run with nothing else contending:

    12 calls at 3.5s spacing = 16.3 calls/min attempted
    -> 7 succeeded, 5 returned HTTP 429  (42% rejected)
    -> effective throughput ~9.5 successful calls/min

An earlier run at ~24 calls/min returned 429 on **10 of 12**. The documented
"~30/min" was optimistic; the sustainable rate is **under 10 successful calls
per minute**. Dexscreener, by contrast, answered 12/12 and publishes 300/min on
the pairs endpoint.

## Call volume, current against proposed

Per pass, measured from this morning's run (85 pools pulled, 79 journalled):

| | Dexscreener | GeckoTerminal |
|---|---:|---:|
| discovery (`new_pools`, 5 pages) | — | **5** |
| enrichment (`dexscreener_pair`) | 79 | 0 |
| outcome lookups (6h 80 + 24h 80 + 168h 53) | 213 | 0 |
| fallback + >=2x verification | — | **8–15** |
| **total now** | **~292** | **13–20** |
| **total if both read every observation** | ~292 | **~297** |

**Dual-source reads would multiply GeckoTerminal traffic by roughly 20x.**

At the measured ~9.5 successful calls/min, 297 calls is **31 minutes of pure
GeckoTerminal requests, every hour**, before retries. The pass would not finish.

## And the current budget is already over-subscribed

The fallback path is failing right now, at today's volume:

| pass | GT attempted | ok | fail |
|---:|---:|---:|---:|
| 1 | 2 | 0 | **2** |
| 2 | 8 | 4 | **4** |
| 3 | 15 | 7 | **8** |
| 4 | 8 | 4 | **4** |

**GeckoTerminal is failing about half its fallback calls at 8–15 calls per
pass.** That is not a capacity we can spend 20x more of; it is a capacity
already short of what the fallback needs.

Worth separating two things that look alike in the logs. `LOOKUP OUTAGE - 24h
horizon: primary price source resolved only 9/80 (11%)` is **Dexscreener
dropping delisted pairs**, not rate limiting — that is the source's own
indexing, and it is the reason retrospective labelling was impossible. The
`geckoterminal_fail` column above **is** rate limiting, and it is ours.

My own scoping calls earlier today caused exactly this: two `new_pools` sweeps
(10 GT calls) immediately before a collection run left the pass 429'd on pages
4 and 5, and it journalled nothing. Self-inflicted, and a fair demonstration of
how little headroom there is.

## What is affordable instead

- **Nothing changes.** Both sources already cover every multiple >=2x and every
  Dexscreener failure. That is the population where a second opinion pays.
- **Fix the over-subscription that already exists** rather than adding to it:
  pace `resolve._geckoterminal` to the measured ceiling and let it queue across
  passes, so a fallback that fails on rate limit is retried next hour instead of
  being recorded as `unresolved`. This *reduces* wasted calls.
- **A keyed GeckoTerminal tier would lift this**, and its price belongs in the
  same report as the RPC tier for holder concentration. Not signed up for,
  per standing instruction.

## What this does not say

It does not say the second source is unnecessary — it says reading it on
*every* row is unaffordable, while reading it where it matters is already done.
If the free ceiling rises or a key is bought, revisit; the measurement above is
the thing to re-run.
