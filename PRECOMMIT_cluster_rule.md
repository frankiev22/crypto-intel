# PRE-COMMITTED: the wallet-cluster rule — written 2026-09-19, before any data is looked at

**Status: NOT RUN.** Nothing below has been measured. This file exists so the
thresholds and the bar cannot move once numbers appear (standing rule 6).

## The claim under test

trenchscope.live (untrusted; `RULES.md` rule 19, REBUILD) fires when **3 or more
distinct wallets buy the same token inside 10 minutes, at least $1,500
combined**, where the wallets come from a list re-ranked nightly by 90-day
realized PnL, and swaps are streamed over Helius gRPC. Its own record shows only
winners and its fine print calls its numbers "illustrative", so the claim is a
hypothesis with no evidence behind it.

⛔ **This is a forward-looking entry rule, so Marino applies** (`CLAUDE.md`,
"What this is NOT"). The test prices entry at the first fill AFTER the rule could
have fired, never at the cluster's own prices. Whatever the result, it would be a
filter Frank reads, never a ranking.

## Definitions, frozen

| term | definition |
|---|---|
| buy | a swap in which a wallet's balance of the token rises and its SOL/USDC/USDT falls, read from the transaction's own pre/post token balances; USD size = quote spent x the quote's USD price at that block |
| wallet | the balance OWNER that received the tokens, not the fee payer. ⚠️ App co-signers (e.g. `AgmLJBMD…`, ~73k tx/hour, fee payer on 60/60 sampled) sign for thousands of users and must never count as a wallet |
| fire | the moment the 3rd distinct qualifying wallet's buy lands, with the last 10 minutes of qualifying buys summing to >= $1,500 |
| entry | the pool price in the first transaction AFTER the fire, from the pool's own vault balances (standing rule 3: quote-side depth from chain, not a reported field) |
| win | pool-price multiple >= 2.0x at +6h or +24h after entry, with >= $500 of quote-side depth at that moment, AND mint and freeze authority both revoked at entry (the `authority_live` win check, BACKLOG A42) |

## Arms

| arm | wallet set | status |
|---|---|---|
| **U** — unselected | any wallet | runnable from chain; it tests an ACTIVITY threshold, not trenchscope's rule |
| **D** — degentape's tracked traders | the wallets behind degentape.com's tape, if it publishes them (AGGREGATE, read-only) | depends on what degentape exposes |
| **S** — trenchscope's actual rule | top wallets by 90-day realized PnL | ⛔ NOT STARTED: needs 90 days of every swap by every candidate wallet; the cost is unpriced |
| **B** — base rate | every token in the same sample, measured from our scanner's first sighting | runnable |

Sample: every AMM token our scanner observed between 2026-09-12 and 2026-09-18
(493 rows with a txns_h1 reading; distinct tokens counted, never rows). Detection
window: the first 2 hours after our observation.

## The bar

- **n >= 30 distinct fired tokens per arm**, or the verdict is "inconclusive"
  (standing rule 7). Wilson 95% intervals on every rate.
- **"Beats the base rate"** only if the arm's Wilson LOWER bound is above arm B's
  Wilson UPPER bound. Overlap = "does not beat".
- Reported both ways: authority-live tokens in and out; tokens whose pool died
  before +24h in (as losses) and out.
- The full multiple distribution (p25 / median / p75) is reported beside every
  rate (`RULES.md` rule 1).

## What it costs before it runs (standing rule 18)

Measured 2026-09-19 on the sample: median **209** transactions in the hour before
observation (p25 19, p75 981, p90 1,833). The detection window alone is roughly
400 transactions per token at the median, about **200k `getTransaction` calls**
for the sample. The free Helius tier is 1M credits a month, shared with the
collector. The keyless public RPC is the alternative, rate-limited and slower.
**Not run until that cost is agreed.**
