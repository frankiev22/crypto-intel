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

## Pagination does not scale the window either

Measured across 5 pages fetched at 3s spacing:

| page | pools | new (not already seen) | created span |
|---|---:|---:|---|
| 1 | 20 | 20 | 15:52:15 → 15:52:50 |
| 2 | 20 | 20 | 15:53:41 → 15:53:57 |
| 3 | 20 | 20 | 15:53:02 → 15:53:27 |
| 4 | 20 | 7 | 15:52:26 → 15:53:00 |
| 5 | 20 | **0** | 15:52:15 → 15:52:50 |

**100 rows fetched, 67 distinct pools.** Page 5 was a complete duplicate of
page 1, and page ordering is not monotonic in creation time. New pools keep
arriving during the ~15s a sweep takes, so the feed re-sorts underneath it.

Two consequences, both now handled:
- `new_pools` **dedupes by address across pages**, or a third of the enrichment
  budget goes on re-fetching pools already scored.
- A failed page is **skipped, not fatal**. On the first live run at `pages=5`,
  pages 3 and 4 returned 429 and the pass still completed with 52 distinct
  pools covering 128 seconds. Before this change a single 429 would have
  aborted the whole pass, losing the outcome scoring behind it too.

Net: `CRYPTO_NEW_POOL_PAGES` now defaults to 5, taking the window from ~40-67s
to ~128s — roughly 1.5% to 3.6% of an hour. Better, and still nowhere near
enough. The ceiling on this approach is about 9%.

---

## 2026-09-18: measured against the chain, not the clock

⛔ **Every coverage figure before this one was arithmetic** - window per pass ×
passes per day ÷ 86,400. `coverage_probe.py` checks it against the launch
stream itself. pump.fun's mint authority signs every create and its migration
authority every graduation, so paging their signatures over the last complete
24h enumerates both streams as a **ledger** - nothing ages out of it the way a
`/new_pools` window does. A seeded sample of each was fetched, kept only when
the logs show the expected instruction and exactly one non-SOL mint, and looked
up in every observation the journal has ever recorded.

| stream (24h to 2026-09-18 ~21:00Z) | in 24h | sampled | fetch failed | wrong instr. | ambiguous mint | usable | **seen by us** |
|---|---:|---:|---:|---:|---:|---:|---|
| pump.fun creates | 36,568 | 400 | 40 | 4 | 39 | 317 | **4 = 1.26%** [0.49%, 3.20%] |
| pump.fun graduations | 1,647 txs | 400 | 16 | 108 | 19 | 257 | **5 = 1.95%** [0.83%, 4.47%] |

**Triangulation:** the median pass window is **190s** (n=30, p90 288s, ~81
pools), and scheduled passes land a median **3.42h** apart (n=134) - about 7 a
day. 190 × 7 / 86,400 = **1.54%**, inside the measured interval. The 1.9% in
`docs/CHAINS.md` was the right order of magnitude and slightly high.

⭐ **Graduations are seen no better than random launches.** That is the finding
that matters: nothing in the pipeline looks for the tokens that go somewhere. A
token is in our journal only if its creation happened to fall inside one of
~7 three-minute windows a day.

⚠️ **Not a graduation rate.** ~72% of migration-authority transactions carry
`CreatePool`, implying ~1,100 graduations a day - ~3% of creates, against a
published 0.198% (Kamat) and our own 0.22%. Unreconciled. Do not quote it.

### The second half of the scope error

The same day's first market snapshot (`market.py`): **0 of the top 25 24h
gainers had ever been in our journal**, and 2 of 105 mover rows across all
lists. The median top-25 24h gainer was **19.3 hours old** - so most of what is
running is a launch we missed, not an old coin we ignore. Some are old: 27, 9
and 5.5 days on that snapshot.

### What a good version looks like, and what it costs

⛔ Not a defence of the current pipeline. It sees ~1 launch in 80 and was never
designed to see what is running. In order of value per dollar:

| # | change | coverage effect | cost | state |
|---|---|---|---|---|
| 0 | **market-wide lists every pass** (`market.py`) - movers, volume, trending, clusters, tape | what is running NOW, any age, ~280 most-active tokens | $0 | ✅ **shipped 2026-09-18**, first unattended run pending |
| 1 | ⭐ **graduation ledger** - page the migration authority's signatures since the last pass, `getTransaction` each, enrich | graduations **~2% -> ~100%**, because a ledger does not expire between passes. Late by up to one pass gap, but complete | **$0** - ~1,100-1,650 calls/day, ~3-5% of Helius free tier, or keyless on public RPC | 🔴 not started. **The single cheapest change that most increases coverage** |
| 2 | **an always-on box** running the collector every 10-15 min instead of GitHub cron (29% of requested cadence, `docs/BACKLOG.md` C10) | window coverage of launches ~1.3% -> ~20%; every list and crossing fresher | **~$4-6/mo** VPS | 🔴 not started |
| 3 | **`programSubscribe` on the launch programs** (BACKLOG C5) | **every create and swap, as it happens** | ~$53-55/mo (VPS + Helius Developer $49 - free tier fails 1.6x) | 🔴 not started, costed |

**Why 1 before 3:** 99.8% of creates die and most never trade. Frank's question
is about the ones that go somewhere, and graduation is the first public
evidence of that. The ledger captures all of them for nothing; a full firehose
of creates costs $49/mo to learn mostly about tokens that die in minutes.

**Why raising `pages` is still not it:** measured on 2026-08-28 above -
pagination re-sorts under the sweep, page 5 duplicated page 1, and the ceiling
is ~9% at the rate limit.

⚠️ **One option considered and rejected:** a workflow that re-dispatches itself
at the end of each run would make GitHub run continuously for $0. GitHub's
Actions terms exclude using it as a long-running service unrelated to building
the repo's software, and this collector is already the grey edge of that. A
self-perpetuating loop is past it, and the account is the thing at risk.
