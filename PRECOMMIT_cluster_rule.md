# PRE-COMMITTED: the wallet-cluster rule — written 2026-09-19, before any data is looked at

**Status: NOT RUN.** Nothing below has been measured. This file exists so the
thresholds and the bar cannot move once numbers appear (standing rule 6).

## The claim under test

trenchscope.live (untrusted; `RULES.md` rule 24, REBUILD) fires when **3 or more
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
| **D** — degentape's tracked traders | the wallets behind degentape.com's tape, if it publishes them (AGGREGATE, read-only) | ⭐ **data available (2026-09-19, see below)**; not run |
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

## Data availability, recorded 2026-09-19 (definitions and bar above unchanged)

- **Our journal has no per-wallet buy data.** Observation rows carry pool-level
  counts (`txns_h1`), never who bought. Arm U needs it from chain: the ~200k
  `getTransaction` calls costed above.
- **Arm D has it for free.** degentape's public tape (`GET /api/tape`, no login)
  carries the Solana wallet (`solana`), the signature (`tx`), `usd`, `token_amt`,
  `side` and block time for 905 leaderboard wallets (897 with a Solana address).
  **182 of 182 sampled fills verified on chain**: signature, signer, token amount
  and quote amount (`docs/EXISTING_TOOLS.md` §4a). Solana history starts
  ~2026-09-10 03:25Z, so the 09-12 → 09-18 sample is covered.
- ⚠️ **Rule 13 applies to their indexer.** Rows land a median 106s and up to 21
  min after block time, so a 10-minute window is complete only once ~25 min
  have passed. The test reads history, so this costs nothing retrospectively;
  a live version would have to wait the same 25 min.
- ⚠️ **Paging**: `before=<id>` pages, 1,000 rows max, sorted by time but cut by
  id (121 duplicates in 9,000 rows): dedupe on `id`, never on position.
- **Seen before this was written:** only a COUNT of fires (70 tokens in 4.4h of
  Solana tape, ~16/hour), by the assessment agent. No outcome of any fired token
  has been looked at.
- Cost of arm D: ~350-500 paged GETs to degentape (7 days of Solana tape, paced
  1/s, ~8 min) plus a few chain calls per fired token that falls in our sample
  for entry and outcome prices. ⚠️ **The overlap between degentape's fires and
  our scanner's 493-row sample is unknown and may leave arm D under n = 30**, in
  which case the verdict is "inconclusive", as pre-committed.
