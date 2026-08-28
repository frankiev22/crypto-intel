# The funnel is 1% wide

Measured 2026-08-28. This supersedes the scoring analysis in `SCOREBOARD.md`,
which was computed on a population that contains none of the winners.

## The arithmetic

`sources.new_pools` polls GeckoTerminal `/new_pools`. Measured live:

| fact | value |
|---|---|
| pools returned at `pages=2` | 40 |
| launch stream those 40 pools spanned | **37-67 seconds** |
| pagination limit | page 10 (page 11 returns HTTP 429) |
| best reach in one pass | 200 pools ≈ **5.2 minutes** |
| implied Solana new-pool rate | **~3,900 pools/hour** |
| collector interval | 3600 seconds |

**At `pages=2`, run hourly, the collector observes ~1-2% of the launch stream.
At the maximum `pages=10` it would observe ~9%.** Everything else is invisible,
permanently, and cannot be recovered later.

## This is why real CYBERLEEK was missed

Real CYBERLEEK `AcEESrd5QPbFFy5CtUBdm14ukw5FGvS9hr9qpKnBpump`, pool created
**2026-08-27 23:47:09Z** on pumpswap. The next collector pass ran at ~00:05 and
its window reached back about one minute — call it 5 minutes at best. CYBERLEEK
was ~18 minutes and roughly 1,200 pools deep by then. **It was never reachable.**

`crypto_observations` contains zero rows for that address. Confirmed.

**The PumpSwap hypothesis is wrong.** The feed does return pumpswap pools — the
DEX breakdown of a live 40-pool sample was pump-fun 35, pumpswap 3,
meteora-damm-v2 2. This is not a venue gap. It is a sampling-rate gap.

## What the scanner scored 100 instead

`Ccv4CQkLe8FRYSsGn7mGgR46ryLtF8CeAabP4mk1j9QG`, symbol CYBERLEEK, on **meteora**,
pool created 2026-08-24 16:27:49Z. Today: FDV $5, liquidity $1. A copycat that
went to zero. Different contract, different DEX, different day.

## One correction to the brief

Real CYBERLEEK is **not** a $381M token today. Live: FDV **$1,927**, liquidity
$2,011, **24h price change −95.77%**, 24h volume $2.2M. It ran hard and round-
tripped ~96% inside a day. The pool creation time and contract address in the
brief are exactly right; the valuation was a snapshot from while it was running.

That distinction matters for calibration. "We missed a $381M winner" and "we
missed a token that spiked and gave it all back within a day" imply very
different models. On the evidence it is the second, and it reinforces the
earlier finding that **the binding constraint is exit, not selection.**

## Why "just raise `pages`" is not the fix

Full coverage needs ~3,900 pools/hour ÷ 20 per call = **~195 GeckoTerminal
calls/hour**. Measured sustainable rate from a residential IP: **429s appear at
20 calls/min** — 2 of 6 calls failed at 3.0s spacing. The code's "~30 calls/min"
comment is optimistic. From a shared datacenter IP it will be worse.

Raising `pages` from 2 to 10 is free and takes coverage from ~1% to ~9%. Worth
doing. It does not solve the problem.

**The real fix is to stop polling a rate-limited aggregator and subscribe to the
source.** Frank already has the pieces: a Helius API key, `pumpfun.py` that
reads the pump.fun program account off-chain, and a deployed Helius webhook at
`crypto-intel-one-eta.vercel.app/api/helius`. A program-subscription webhook
sees every launch as it happens, with no polling window and no page limit.
Helius free tier covers this. That is the P1 build.

## Coverage is now measured, not guessed

`journal.record_coverage` writes one row per pass to `data/coverage/`, holding
the discovery window's oldest and newest pool timestamps and its span in
seconds. Divided by the pass interval, that is the coverage rate.

It is recorded per pass because it is **not reconstructable afterwards** — the
window a pass saw is gone the moment the pass ends.

This is the stub of the dashboard's headline number. The honest version needs
the other half: of all tokens that crossed $1M today, what fraction did we
observe before they crossed. That needs the missed-winner ledger, which needs a
1M-crossing feed, which is P2.
