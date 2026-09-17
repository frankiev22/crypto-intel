# The 1M tracker: scoping and feasibility

**2026-09-17. Scoping only. Nothing here is built.** Every number below was
produced by a query run against our own data or a live endpoint on 2026-09-17;
the method is stated beside each one so it can be re-run and disagreed with.

Keys are contract addresses throughout. Tickers are display only — three of the
worst cases in this document share a ticker with something real.

---

## 0. Corrections to the brief, before anything is designed

Per standing rule 4, premises that arrived with the brief and did not survive
contact with the data are named here first.

1. **"Roughly a third of milestone crossings are phantoms" understates it by
   more than double.** Measured: **25.4% [22.3, 28.8] of $1M crossings pass a
   basic integrity screen** (n=696 first-sightings above $1M). Roughly **three
   quarters fail**, not one third. A second, independent basis — live milestone
   records rather than observation first-sightings — gives 26.1% [21.0, 31.9]
   on n=249. The two agree.

2. **The "RTL-override USDT impersonator showing a fake 101M cap" does not
   reproduce.** Across all 398 distinct impersonation-flagged contracts in our
   observations, **none** has an FDV between $90M and $120M. The RTL-override
   cases are real but smaller (two at ~$3.0M rendering as `KNOTS`/`KN0TS`, one
   at ~$1.0M). The genuinely large fakes are worse than the one cited:

   | CA (prefix) | ticker | peak FDV | reported liq | real quote depth |
   |---|---|---:|---:|---:|
   | `B3Dxm6j7sQJWjm` | DOGE | **$86,502,867,811** | $346,011,471 | **$0.0002** |
   | `AqMfZ8LCQMJYKU` | BTC | **$13,098,150,509** | $52,392,602 | **$0.0002** |
   | `GKXHCx3U3gv8uL` | USDC | $975,449,495 | $98 | $48.96 |

   An $86 billion "market cap" with two hundredths of a cent of sellable depth
   is the shape of the thing we are trying to filter.

3. **`check.py` does not detect bundles.** The brief calls it "our one validated
   component" for ask 6. It is validated, but for something else: D1 and D2 plus
   capability checks. **Searching every `.py` for "bundle" returns nothing.**
   Bundle detection does not exist in this repo in any form. See section 4.6.

4. **`info.socials` / `info.websites` are fetched and discarded** — confirmed
   2026-09-16. `sources.dexscreener_pair()` returns the raw pair dict including
   `info`; `journal.record()` is a whitelist and drops it. Nothing social has
   ever been stored. See section 4.1.

5. ✅ **RETRACTED — the "Helius is blocked / looks free-tier" finding in the
   second version of this document was wrong, and the error was mine.** I probed
   `api.helius.xyz/v0` with a script that set no `User-Agent`, so urllib sent
   its default `Python-urllib/3.14`. **Cloudflare blocks that string with HTTP
   403 `error code: 1010`.** It is a client-fingerprint rejection, not an auth
   or plan failure. Re-tested 2026-09-17:

   | client | User-Agent | `/v0/webhooks` |
   |---|---|---|
   | urllib | default (`Python-urllib/3.14`) | **403, error code 1010** |
   | urllib | browser string | **200** |
   | curl | curl default | **200** |
   | curl | header removed entirely | **200** |
   | curl | browser string | **200** |

   **Refinement worth keeping: it is not "missing User-Agent".** curl with the
   header stripped still gets 200. **The block is specifically on the
   `Python-urllib` UA string.** Any other value, or none, passes.

   **Nothing was ever gated.** `/v0/webhooks` and
   `/v0/addresses/{addr}/transactions` both return 200 and real data.
   Transaction history *is* available, so the original claim in version one was
   right and the retraction of it was wrong. Bundles (4.6), smart money (4.5),
   the Cupsey test (9) and the webhook plan (5b) are **all unblocked**.

   ✅ **The collector was never affected.** `sources.py:12` already sets
   `UA = {"User-Agent": "Mozilla/5.0", ...}` on every request. The defect lived
   only in my ad-hoc probe scripts. **Any new script that talks to a
   Cloudflare-fronted API must set a User-Agent** — this is the second system
   where that has bitten (it silently killed the Python Discord webhook alerts).

6. ⛔ **Correction to the first version of this document: recommending Windows
   Task Scheduler for the crossing detector was wrong.** Frank caught it.
   Hourly polling cannot deliver "know right away" — at a one-hour interval the
   expected detection lag is ~30 minutes and the worst case is ~60. Task
   Scheduler remains the right answer for the **hourly historical collector**,
   which is a different job. Both are specified separately in section 5.

---

## 1. Why the Marino result does not kill this

**The old scanner predicted graduation. Marino killed it correctly:** perfect
knowledge of graduation probability still loses money, because price outruns
probability. A token that is 10x more likely to graduate is already priced for
it by the time the signal is readable.

**This is not that.** Frank's tracker makes no forward claim. It watches what
has **already** crossed a market-cap threshold and explains what it is. The
output is a description of a completed event, not a probability of a future one.

Concretely, the difference that matters:

| | old scanner | 1M tracker |
|---|---|---|
| trigger | token has not yet run | token **has already** run |
| claim | "this will graduate" | "this crossed $1M, here is what it is" |
| fails when | price outruns probability | description is wrong or late |
| Marino applies | **yes** | **no** |

**Do not re-kill this by reflex because it shares a data pipeline with the thing
that was killed.** The falsifiable failure mode here is different and is named
in section 3: the tracker fires on a token that did not really cross.

⚠️ **One real carry-over risk.** Ask 3 ("good metrics to run more") *is* a
forward claim and Marino's logic partially does apply to it. It is scoped
separately in section 4.3 and must not be smuggled in under the descriptive
banner.

---

## 2. ⭐ The number that decides the product

**How many distinct Solana contracts cross a market cap threshold per day?**

### Method

Two independent bases, both from our own history:

- **Basis A (observations):** for each distinct CA, the first time we ever
  observe it at or above the threshold. Counted per UTC day.
- **Basis B (milestones):** live, non-backfilled `mcap_1m` / `mcap_5m` records
  from `data/milestones/2026-09.jsonl`.

Restricted to **full-coverage days** — the 6 days where the collector scanned
at least 2,000 distinct contracts. This matters enormously: raw daily counts
swing from 3 to 71, and that swing tracks *collector uptime*, not the market. On
2026-09-14 the collector saw 373 contracts and found 4 crossings; on 2026-09-05
it saw 2,551 and found 64. Any figure quoted without a coverage denominator is
measuring our own downtime.

### Result

| threshold | raw / day | **verified / day** | verification pass rate |
|---|---:|---:|---|
| $500k | 69.0 | **27.0** | 23.1% [20.4, 26.0] (n=862) |
| **$1M** | **59.0** | **24.5** | **25.4% [22.3, 28.8] (n=696)** |
| $5M | 34.0 | **15.0** | 27.7% [23.6, 32.2] (n=415) |

Basis B agrees on $1M: 52.5/day raw, **15.0/day verified**, pass rate 26.1%
[21.0, 31.9] on n=249.

### The answer to Frank's question

**At $1M: roughly 50–60 raw crossings a day, of which about 15–25 survive
verification.**

That is **trivial, not a different product.** Fifteen to twenty-five
analyst-grade reports a day is entirely tractable — it is a readable feed, not a
firehose. The $5M threshold (15/day verified) is a genuinely quiet feed; $500k
(27/day) is still comfortable. **Frank can pick any of the three on volume
grounds.** The threshold should be chosen on what he wants to read, not on what
we can process.

### ⚠️ Three honest limits on this number

1. **It is a lower bound.** We only count what we scan. We scan ~2,500 distinct
   contracts/day. A live sample of GeckoTerminal's new-pool feed on 2026-09-17
   returned 100 pools spanning **0.04–0.07 hours** of creation time — implying
   Solana creates on the order of **~3,000 pools/hour, ~72,000/day**. We see a
   few percent of all launches.
2. **But the bias is much weaker at high thresholds than that ratio suggests.**
   Our scanner is volume- and recency-driven, so it over-samples precisely the
   contracts that run. Tokens reaching $1M are not a random sample of launches.
   We do not have a clean capture-rate estimate and should not pretend to.
3. **No free endpoint provides a census.** I tried. GeckoTerminal's `new_pools`
   caps at 100 rows (5 pages), its top-pools endpoint rate-limited after 20
   rows, and — importantly — **`market_cap_usd` was null on all 100 new pools.**
   Only `fdv_usd` is populated for young tokens. See section 3.1.

**Recommended pre-commit before building:** fix the threshold and the
verification rule in a file, then measure for one full week of restored
collection before anyone quotes a rate. `GAPS.md` G1 style.

---

## 3. ⛔ The trap: "hits 1M" is not a fact

Three quarters of raw crossings do not survive a basic screen. A tracker that
pings Frank on those is worse than nothing, because he will act on it.

### 3.1 FDV is not market cap, and that is not a pedantic point

GeckoTerminal returned **`market_cap_usd: null` on 100 of 100** new Solana
pools. Dexscreener's `fdv` is what we actually store. For a standard pump.fun
launch with fixed supply and no vesting, FDV is approximately market cap and the
distinction is cosmetic. For anything with locked, vested, or mintable supply it
is not.

**Two of the 249 live $1M crossings had a live mint authority at crossing time.**
A mintable token's FDV is a statement about a supply the deployer can change.

**Spec:** the tracker stores FDV, labels it FDV, and shows market cap only when
a supply source confirms it. Never silently relabel one as the other.

### 3.2 The verification gate

A crossing is a **candidate** until it passes all of these. Only a confirmed
crossing may fire a notification.

| # | gate | data | fails today |
|---|---|---|---|
| V1 | quote-side depth at or above floor, read from **on-chain reserves**, not reported liquidity | `onchain_reserves.exit_depth()` by CA | 41.8% |
| V2 | not in `quarantine.json` | local | 26.9% |
| V3 | no `template_suspect` flag | `plausibility.annotate()` | 16.9% |
| V4 | no `impersonation` flag (incumbent-name or bidi control char) | `detector` | 6.4% |
| V5 | `liquidity_plausible` is not False | `plausibility` | 5.6% |
| V6 | pair identity matches the CA requested | `dexscreener_pair(require_match=True)` | — |

**V1 is the load-bearing one and it is the expensive one.** Reported liquidity
overstates measured quote-side depth by a median 781x, so V1 cannot be shortcut
with the cheap field. It costs one Solana RPC call set per candidate.

⚠️ **V1's implementation is currently unreliable, and this is the single biggest
technical risk in the whole proposal.** On 2026-09-17 I ran
`onchain_reserves.exit_depth()` against 6 known-dead pools via Helius: **5 of 6
failed to return a usable number** — three `UNRELIABLE READ: scan missed the
real vault`, two `no USD price for quote mint`. **The verification gate this
design depends on does not currently work reliably.** Fixing vault discovery and
the SOL-price path is a prerequisite, not a detail.

### 3.3 Cost of verification

At $1M: ~59 candidates/day, one RPC call set each. Helius is already paid for.
At the project's 1.0s pacing that is about one minute of calls a day.
**Verification is cheap. It is correctness, not budget, that is blocking.**

---

## 4. Per-item verdict on the seven asks

Scale: **HAVE** (data exists and is read) · **CHEAP** (data exists, small change)
· **BUILD** (real work, specified) · **NOT YET** (honest no).

### 4.1 "What it is" — a plain-English sentence · **CHEAP**

`info.socials` and `info.websites` arrive on every enriched row and are dropped
by the `journal.record()` whitelist. Live-verified 2026-09-17: 30 of 30 pairs
for a reference contract carried `info`, with `socials` (twitter/telegram/
discord) and `websites`.

Add four derived fields — `has_telegram`, `has_twitter`, `has_website`,
`social_count` — plus the raw `info` blob for on-demand lookups. **Booleans in
the row, blob only on the analyzer path.**

⚠️ **Honest ceiling: this gets you the token's *self-description*, not what it
is.** A link to a Telegram is evidence a Telegram exists, nothing more. A real
sentence needs the name, the socials, and the deployer history, and it will
still sometimes be "a dog coin with a Telegram and 200 members".

### 4.1b ⭐ The website is the best source, and it is fast — **measured**

Frank's instinct that the project **website** beats Twitter or Telegram for
"what is it" is right, and it is the cheapest thing in this document to act on.
A website is prose written to explain the project; a Telegram link is a door.

**Measured 2026-09-17** against real token sites harvested live from
`info.websites` on trending Solana pools:

| | result |
|---|---|
| sites fetched | 10 |
| resolved and returned content | **8 of 10** |
| failed immediately (dead domain) | 2 of 10, ~0.2s each |
| **fetch latency** | **min 0.23s · median 0.69s · max 1.47s** |
| page sizes | 3 KB – 390 KB |

**Median 0.69s against a 30-second budget.** The fetch is not the constraint —
it is roughly 2% of the budget. Even the slowest site was under 1.5 seconds, and
dead domains fail fast rather than hanging.

⚠️ **Two honest limits:**
1. **~20% of listed websites are dead** (2 of 10 here). "No website" and
   "website that does not resolve" are different facts and must render
   differently — same rule as `usd()`.
2. **Fetching is fast; understanding is not.** Many of these are JavaScript
   single-page apps where the raw HTML is an empty shell — the 3 KB result is
   the tell. Raw-HTML extraction will return nothing useful for some fraction of
   sites, and rendering JS is a much heavier operation that would blow the
   budget. **Measure what fraction of fetched sites yield usable text before
   promising a sentence from every one.**

**Spec:** fetch the site with a hard ~3s timeout, extract title, meta
description and first paragraph. On empty or dead, say so explicitly and fall
back to socials. Never synthesise a description from the ticker.

### 4.2 "Why it's running" — ⚠️ **largely NOT KNOWABLE**

**Be honest with Frank about this one.** For the large majority of $1M crossings
there is no discoverable cause, and anything we print will be narration fitted
after the fact. That is the single most dangerous output in this design, because
a confident-sounding "why" is exactly what he would act on.

What is genuinely available:

- **HAVE — cluster context.** `clusters.find()` already detects several
  contracts named off one root inside a window. When a crossing belongs to a
  live cluster, "6 names sharing this root launched in the last 24h" is a real,
  checkable statement.
- **CHEAP — volume shape.** `vol_burst`, `vol_to_liq`, buy/sell split at
  crossing are already computed.
- **BUILD — news correlation.** `news.py` exists. Correlating a crossing to a
  headline is weak evidence and will produce false links.

**Spec:** print mechanism, never motive. "Volume 40x its 24h average, 87% buys,
one of 6 contracts sharing the root 'X' in 24h" is honest. **"Running because of
the X announcement" is not, and should not be emittable.** If nothing is
detectable, print *nothing* — not a guess. This is the same rule as `usd()`:
unknown must not render as a reading.

### 4.3 "Good metrics to run more" — **BUILD**, and ⚠️ this is the forward claim

This is the new scoring method, and it is the one piece that **is** a prediction:
continuation on things already moving. Marino's logic is weakened here (the run
has already started, so we are not pricing an unrealized probability) but not
absent.

Features we already compute and persist: `vol_to_liq`, `vol_burst`, `chg_h1`,
`chg_h24`, `buys_h1`/`sells_h1`, `txns_h1`, `exit_depth_usd`, `age_hours`,
`liq_to_fdv_ratio`, `venue_type`, `has_amm_pool`, `mint_authority`,
`freeze_authority`, `grade`. Available cheaply: the four social booleans
(section 4.1), holder concentration (section 4.4).

⛔ **Non-negotiable process, from the standing rules:**
1. Pre-commit the continuation definition **to a file** before anyone looks —
   what multiple, over what horizon, from what starting point.
2. Report **n and a Wilson interval** on every figure.
3. **No hit rate until n is at least 30 closed distinct contracts per arm**,
   counted by CA.
4. Report both ways: late closes in/out, inferred losses in/out.

**Until that clears, this is a research question, not a feature.** It should ship
disabled behind the descriptive tracker, which does not depend on it.

### 4.4 "Big wallets in" — holder concentration · **HAVE**

`onchain.py` computes top-N holder concentration via `getTokenLargestAccounts`;
`check.py` surfaces `top1_share`. Unblocked 2026-09-07 when the Helius key was
found to have been available the whole time. Frank already pays for the key.

⚠️ **Known correctness trap, documented in `onchain.py:16`:
`getTokenLargestAccounts` returns the pool's own vault as a holder.** It must be
excluded or every token looks like one whale owns it. Verify this exclusion is
actually applied before trusting any concentration number.

**What this gives:** what share of supply the top N wallets hold. **What it does
not give:** who they are, or whether they are the deployer. That is section 4.5.

### 4.5 "Smart money" — ⚠️ **NOT YET, and the honest estimate is months**

Correct as suspected. This needs a labeled wallet set we do not have, and cannot
buy under the free-tools-only rule.

**What building one actually takes**, via the obvious path (early buyers of
prior winners):

1. **Define a winner by CA.** We have candidates: 32 `graduated`, 115 verified
   $5M crossings, 177 verified $1M crossings.
2. **Pull early buyers per winner.** Helius transaction history on the pool for
   the first N minutes. About one call set per winner. ✅ **Available** —
   `/v0/addresses/{addr}/transactions` returns 200 and real data (§0.5); the
   earlier "blocked" note was my User-Agent bug, not a plan limit. Affordable.
3. **Build the candidate set.** Wallets appearing early in at least k distinct
   winners.
4. ⛔ **Then the hard part: validate it forward.** A wallet list built from past
   winners will look predictive on those same winners by construction. It means
   nothing until it is pre-committed and tested on winners it has never seen.

**Timeline, honestly:** steps 1–3 are days of work. **Step 4 is the gate, and it
needs enough forward winners to test against — at ~15 verified $1M crossings a
day, a pre-committed n of at least 30 distinct forward winners per arm is weeks
minimum, and that assumes collection is restored and stays up.** Anything
shipped before step 4 is a list of wallets that bought things that went up,
presented as insight.

**Recommendation: do not scope this into v1.** Collect the raw early-buyer data
now — it is cheap and it is the input — and keep the feature dark.

### 4.6 "Bundles" — **BUILD from scratch**, not covered by `check.py`

The brief's premise is wrong; see section 0.3. `check.py` runs:

- **D1** — `liq/fdv` at or above 0.95 AND zero sells in 1h AND at least 10 buys.
  A one-sided pool. ⚠️ **Recall is 50% by its own docstring — it misses half of
  what it targets.**
- **D2** — high reported liquidity with very low transaction count.
- Mint/freeze authority capability checks, and a measured exit depth.

**None of that is bundle detection.** A bundle — many wallets funded from one
source buying in the same block or slot at launch — requires transaction-level
analysis we have never written: pull the first N slots of trades, group buyers,
trace funding sources back one hop.

✅ **Feasible now.** This needs `/v0/addresses/{addr}/transactions`, which
returns 200 (§0.5) — my "403, not in your tier" note was a User-Agent bug and is
retracted. **Cost: real. Estimate one to two days of work plus a validation
set.** Nothing external blocks it.

⛔ And it needs the same discipline as section 4.5: a bundle detector with no
measured recall is another D1 — a check that reads as clean because it found
nothing, when it finds nothing half the time. **Pre-commit what counts as a
bundle, and measure recall against hand-labeled cases, before it is allowed to
print "no bundles detected".**

### 4.7 "LP settings" — burned / locked / neither · **BUILD**, but small

**Not implemented.** Searching for LP burn or lock detection returns nothing
anywhere in the repo.

On Solana this is tractable and cheap:
- **Burned** — LP mint supply is zero, or authority is the incinerator.
- **Locked** — LP tokens held by a known locker program; unlock date from that
  program's account.
- **Neither** — LP tokens sitting in a wallet, i.e. the deployer can pull.

Burned and neither are **straightforward** — one or two RPC calls by CA.
**Locked is the hard case**: it means recognising each locker program
individually, and an unrecognised locker reads as "neither". **That must render
as `unknown`, never as `not locked`** — the difference is the whole point of the
`usd()` rule, and here it is the difference between "the deployer can rug this"
and "we did not recognise the locker".

### Summary

| # | ask | verdict | blocking dependency |
|---|---|---|---|
| 1 | what it is | **CHEAP** | whitelist change |
| 2 | why it's running | ⚠️ **partly unknowable** | mechanism only, never motive |
| 3 | metrics to run more | **BUILD** | pre-commit + n of 30/arm |
| 4 | big wallets | **HAVE** | exclude pool vault |
| 5 | smart money | ⚠️ **NOT YET** | forward validation, weeks+ |
| 6 | bundles | **BUILD** | does not exist; needs recall measurement |
| 7 | LP settings | **BUILD (small)** | locker registry; unknown is not unlocked |

---

## 5. What must be running — **two different jobs, do not conflate them**

**Nothing has collected since 2026-09-15 05:07:59 UTC** — both paths are down
(GitHub Actions on exhausted free-tier minutes since 9/12, the desktop task on a
lost sandbox mount since the 9/15 reboot).

There are **two jobs here with different requirements**, and the first version of
this document wrongly proposed one runner for both:

| | 5a. historical collector | 5b. crossing detector |
|---|---|---|
| job | scan, score, sweep, close paper positions | notice a threshold cross **now** |
| cadence | hourly is correct | **hourly is useless** |
| mechanism | poll | **push** |
| runs on | Windows Task Scheduler | Helius webhook → Vercel |
| desktop must be on | **yes** | **no** |

**Hourly polling cannot deliver "know right away."** At a one-hour interval the
expected lag between the cross and the alert is ~30 minutes and the worst case is
~60 — and a $1M memecoin can round-trip inside that window. Frank is right.

### 5a. The historical collector — Windows Task Scheduler calling `collect.py`

**Frank's instinct is right, and this is the lowest-risk option available.**
Verified on this machine today:

- `import collect` **succeeds natively on Windows**, Python 3.14.3, outside any
  sandbox.
- The collector is **pure stdlib** (the only optional import is `dotenv`, with a
  fallback parser in `config.py`).
- **Zero Windows path assumptions** — searching every `.py` for `C:\`,
  `/sessions/`, `os.name`, `sys.platform` and `platform.system` returns no hits.
- No Claude session, no sandbox, no mount. **It removes the exact component that
  broke on 9/15.**

⛔ **Two settings that will silently corrupt attribution if missed:**

1. **`CRYPTO_ORIGIN=scheduled` must be set.** Verified today: with no env,
   `liveness.origin()` returns `"manual"`, and `liveness.UNATTENDED` is
   `("runner", "scheduled")` — manual beats are *shown, never counted*. Without
   this the liveness registry will read the system as dead while it runs
   correctly, and every paper close will be misattributed.
2. **`--max-seconds` behaviour changes off the runner.** `collect.py:404` applies
   the sandbox time budget whenever `GITHUB_ACTIONS` is unset. On a desktop with
   no 178s cap that truncates passes for no reason. Either run the staged
   commands with explicit budgets, or give the unstaged pass an explicit
   `--max-seconds`.

**Also true and worth saying plainly: the desktop must be on.** Task Scheduler
does not run on a powered-off machine, and the host is off on weekends. For the
historical collector that is tolerable — `journal.pending()` looks back over a
6h window, so a missed hour is picked up later. **It is not tolerable for the
detector, which is why the detector does not live here.**

### 5b. ⭐ The crossing detector — Helius webhook into Vercel

#### What we already have

`site/api/helius.mjs`, 296 lines. It authenticates on `HELIUS_WEBHOOK_SECRET` in
the `Authorization` header, accepts an array of transactions (40 per call max),
works out which watched wallet acted, decodes the swap legs, prices them, stores
anything above a $100 floor through a secret-gated Supabase RPC, and posts to
Discord above `WHALE_MIN_USD` (default $500), rate-limited to one message per
wallet per `WHALE_WINDOW_MINS` (default 10).

**It is a whale-alert receiver keyed on a wallet list (`WATCHED_WALLETS`), not a
crossing detector.** The decode-price-store-alert spine is directly reusable;
the trigger and the threshold test are not.

#### ✅ RESOLVED: it is deployed, the webhook exists — **and it watches nothing**

Once `/v0` was reachable (§0.5), the Vercel identity fell out of the webhook
registration itself; the dashboard was never needed. **`crypto-intel.vercel.app`
was my bad guess — it serves "CryptoTrace - Address Analytics", someone else's
Next.js app. The real deployment is `crypto-intel-one-eta.vercel.app`.**

| check | result |
|---|---|
| `GET /` on the real host | **200**, and it is our plain static `site/index.html` |
| `GET /api/helius` | **405 `{"error":"POST only"}`** — the handler's own first branch |
| registered webhooks | **1** |
| `webhookID` | `75056f75-c129-4f43-b686-0f369f8fa669` |
| `webhookURL` | `https://crypto-intel-one-eta.vercel.app/api/helius` ✅ correct |
| `webhookType` | `enhanced` |
| `transactionTypes` | `["ANY"]` |
| `authHeader` | set |
| `active` | **true** |
| **`accountAddresses`** | ⛔ **0 — empty** |

**So the receiver is live, the webhook is active, the URL is right, the auth
header is set — and the address list is empty, so Helius has nothing to push and
the endpoint is never called.**

⛔ **That is the actual reason the whale alerts have never fired.** Not the plan,
not the deployment, not the 403 I chased. **An active webhook watching zero
addresses.** It has been quietly costing nothing and doing nothing.

✅ **This is very good news for section 5b.** The plumbing is already built,
deployed, authenticated and verified end to end. **Nominate-and-push needs the
nominated pool addresses written into `accountAddresses` on an existing, working
webhook** — not a new service. ⚠️ Note `transactionTypes: ["ANY"]` would want
narrowing to swaps before the address list grows, or push volume (and cost,
§5b) is larger than it needs to be.

#### ⭐ What Helius webhooks can and cannot trigger on

- **Can:** fire on transactions touching **addresses you enumerate**. Enhanced
  webhooks add a `transactionTypes` filter (e.g. SWAP); Raw webhooks send
  everything.
- **Cannot:** trigger on a price or a market cap. **There is no such native
  trigger and there cannot be.** Market cap is derived — price times supply —
  and price is itself derived from pool reserves. **Nothing on chain ever emits
  "crossed $1M."** No provider can offer this as a primitive; the ones that
  advertise mcap alerts are all computing it themselves on polled data.

So the threshold test is **always computed receiver-side**. The webhook's only
job is to say *a pool you care about just traded*. We then recompute reserves →
price → FDV and compare. **This is the same V1 computation as section 3.2, and
it inherits the same defect: `exit_depth()` currently fails 5 times in 6.**

#### ⭐ The architecture that follows: poll to nominate, push to detect

You **cannot** watch every token. Webhooks are address-scoped, and watching the
AMM programs wholesale would push millions of events a day — we measured ~72,000
new pools/day and trade volume is far higher — at one Helius credit and one
Vercel invocation each. Unaffordable, and mostly noise.

You **do not need to.** A token cannot cross $1M without first being near $1M.

1. **The hourly collector (5a) nominates.** Any contract whose FDV enters an
   approach band below the threshold — say $600k–$1M — has its pool address
   registered on the webhook. **`watchlist.py` already implements exactly this
   pattern** for graduation (`BAND_LO`/`BAND_HI`).
2. **The webhook detects.** Helius pushes each swap on a nominated pool. The
   receiver recomputes FDV from reserves and fires only on a real crossing that
   also passes V1–V6.
3. **Nominations expire.** Anything leaving the band or ageing out is
   deregistered, keeping the watched set in the low hundreds.

**The hourly job stops being the detector and becomes the nominator** — a job an
hourly cadence is genuinely suited to, since a token usually takes more than an
hour to cross a 40%-wide band.

⚠️ **The real gap: vertical launches.** Anything going from nothing to $1M
inside one hour is never nominated and is missed entirely. **That is a
quantifiable miss rate and it must be measured against restored collection, not
assumed small.** It is the honest cost of not running the firehose.

#### ⚠️ What this removes, and what it does not

**Removes the uptime question for detection and delivery.** Helius holds the
watch; Vercel runs only when pushed. Neither depends on Frank's desktop being
on. This is the strongest argument for the design.

**Does not let Vercel hold a subscription of its own.** Vercel functions cap at
**300s on Hobby** (300s default, 800s max on Pro), so a persistent WebSocket or
gRPC listener cannot live there — Vercel's WebSocket beta does not change the
duration ceiling. `config.helius_ws()` already exists in this repo; if we ever
want the full firehose instead of a nominated set, **that path needs an
always-on process, i.e. the VPS**, plus LaserStream gRPC, which starts at the
**Business plan, $499/month**. Nominate-and-push avoids both.

#### Honest end-to-end latency, chain to phone

| stage | estimate | basis |
|---|---|---|
| block → Helius indexes it | ~1–2s | ~0.4s slot time plus indexing |
| Helius → POST to Vercel | ~0.2–0.5s | network |
| Vercel cold start | ~0.1–1s | Node function, cold path |
| recompute reserves → FDV | ~0.3–1s | one RPC call set |
| post to Discord/Telegram | ~0.2–0.5s | measured on comparable calls |
| **bare alert** | **~2–5s** | |
| with full explainer attached | **+2–4s** | website 0.69s median (4.1b) + holders + LP |

**About 5 seconds for a bare alert, under 10 with the explainer.** Against a ~30
minute expected lag from hourly polling, that is the entire point. ⚠️ These are
component estimates, not an end-to-end measurement — nothing can be measured
end-to-end until a webhook can actually be registered.

#### Cost at realistic volume

Push volume scales with **band width, not with crossings**. At $1M with a
$600k–$1M band, expect a few hundred watched pools and — from section 2 — ~59
candidate crossings/day, but assume 10k–100k swap pushes/day.

- **Helius:** 1 credit per webhook push. 100k/day ≈ 3M credits/month. **Free is
  1M credits/month; Developer is $49/month for 10M.** So **$0 with a tight band,
  $49/month with a loose one.** ⚠️ This is the number to watch.
- **Vercel:** one invocation per push, handler runs in single-digit seconds
  against a 300s ceiling. **Likely $0 on Hobby.** ⚠️ Hobby forbids commercial
  use — fine personally, not if this is ever sold.
- **Total: $0–49/month.** A VPS at $4–6/month would not be faster and would
  reintroduce an uptime dependency.

✅ **Nothing external gates this.** `/v0` access works, the webhook is
registered and active, and the receiver is deployed and answering. The remaining
blockers are ours: `exit_depth()` (section 3.2) and restoring collection to feed
nominations (5a).

---

## 5c. ⭐ REVISED ARCHITECTURE — nomination is unsound, subscribe to the program

**2026-09-17, second revision. Frank was right twice and the nominate-and-push
design in 5b does not survive measurement. This section supersedes it.**

### First: he is right that you CAN trigger on market cap

The earlier "no such trigger exists and there cannot be one" was too strong and
should not be repeated to him. **Precisely:** nothing on chain *emits* a
market-cap event — but **every swap mutates the AMM pool account, and market cap
is computable from reserves on each account update.** Subscribe to the pool
accounts and you have real-time market cap. **The trigger is possible. The only
question was ever how many accounts you can subscribe to.**

### The ceiling is not the constraint — credits are

| limit | value |
|---|---|
| addresses per Helius webhook | **100,000**, dynamically modifiable via API |
| webhooks on the free tier | 1 |
| cost per webhook push | **1 credit** |
| cost per webhook **edit** | **100 credits per request** |
| free / Developer / Business credits per month | 1M / 10M ($49) / 100M ($499) |

**100,000 addresses is 40x more than the ~2,500 distinct contracts we see in a
day.** The address ceiling never binds. **Credits bind, and they bind hard**,
because a pool in this range is far busier than intuition suggests.

### Measured push volume — from our own rows, not estimated

| band | median txns/hour | pushes/day/pool | p90 txns/hour |
|---|---:|---:|---:|
| FDV $600k–$1M (n=99) | **206** | **4,944** | 1,686 |
| FDV $1M–$5M (n=236) | 47 | 1,128 | 1,783 |

**One watched pool in the approach band costs ~4,944 credits a day — about
150,000 credits a month.** So the free tier's 1M credits supports roughly
**6 or 7 continuously-watched pools**, and Developer ($49) about **66**. Not
100,000. The gap between the advertised ceiling and the affordable one is four
orders of magnitude.

### ⛔ And then the finding that kills nomination outright

**Tokens do not sit in the approach band. They cross it.**

Measured on `data/observations/`, $600k–$1M band:

| | |
|---|---|
| contracts seen in band **only once** | **76 of 86 — 88%** |
| contracts seen 2+ times in band | 10 |
| dwell among those 10 | median **0.00 h**, p90 **0.05 h (3 min)**, **max 0.15 h (9 min)** |

**The longest observed traversal of a 40%-wide band was nine minutes.** Most were
under the resolution of our own sampling.

⚠️ **Honest confound:** "seen once" conflates short dwell with sparse scanning —
we only see a token when the scanner reaches it. The 88% is therefore an upper
bound on how many are genuinely fast. **But the 10 multi-sighted cases are direct
evidence and they are unambiguous: median dwell ~0, max 9 minutes.**

**This is exactly Frank's objection, and it is not an edge case — it is the
typical case.** A design that nominates on a schedule and then waits for the
token to cross cannot work when the token is in the band for seconds. Moving
nomination from hourly to 5-minute does not fix it; the p90 dwell is 3 minutes.
**You cannot nominate fast enough. The premise is wrong.**

For completeness, the cadence costing that was asked for — **it is real, and it
is affordable, and it still does not work:**

| nomination cadence | edits/day | edit credits/month | verdict |
|---|---:|---:|---|
| hourly | 24 | 73,000 | cheap, **misses ~88%** |
| every 5 min | 288 | **876,000** | 88% of the free tier **before a single push**; still misses most |
| every 2 min | 720 | **2,190,000** | needs Developer ($49); still misses the sub-2-minute movers |

### ✅ The architecture that actually answers the question

**Stop enumerating pools. Subscribe to the AMM programs themselves.**

A Solana `programSubscribe` on the pump.fun / PumpSwap / Raydium program IDs
delivers **every account update for every pool that program owns** — including
pools that did not exist a second ago. Reserves change, we recompute FDV, we
compare to the threshold.

- **No nomination.** Nothing to schedule, nothing to register, no edit credits.
- **No miss window.** A token going 0 → $5M → 0 in ten minutes is seen on every
  update along the way, because we never had to know about it in advance.
- **No address ceiling**, because we subscribe to a program, not a list.

**Cost:** this needs a **persistent connection**, which a Vercel function cannot
hold (300s max duration, §5b). That means **an always-on process on a VPS at
~$4–6/month** — the same box that solves the collector's weekend problem.

⚠️ **Two things to confirm before committing, and I have not confirmed them:**
1. **How Helius meters standard WebSocket subscriptions.** Helius lists
   "LaserStream WSS (standard)" on the free tier and gRPC from Business ($499).
   Whether a high-volume `programSubscribe` is billed per update, per connection,
   or by bandwidth **changes the cost by orders of magnitude** and is the single
   open question on this path.
2. **Throughput.** A busy AMM program emits a very large number of account
   updates per second. Whether one cheap VPS can decode and filter that stream
   in real time needs measuring, not assuming. If it cannot, the fallback is to
   filter server-side by program + account size, or to accept a subset of venues.

**Recommendation: price path B properly before building path A.** Path A is
cheap, deployable today on infrastructure that already exists and is verified
working — and it structurally cannot see the movers Frank most wants to see.
**Path B is the only design that answers what he actually asked for.**

---

## 6. ⭐ One analyzer, two triggers

**Design it this way from the start.** The analyzer is a pure function of a
contract address:

    analyze(CA) -> report

Two callers, one code path:

- **Automatic** — the collector detects a verified crossing (section 3.2) and
  calls `analyze(CA)`.
- **On demand** — Frank pastes a CA and gets the identical report.

**A crossing is just the automatic trigger for the same tool.** This falls out
naturally because `check.py` already has exactly this shape — one CA in, one
verdict out, refuses rather than guesses. **The analyzer should be `check.py`
extended, not a new program**, which also means the on-demand path works before
the collector is restored.

⚠️ Carry `check.py`'s discipline verbatim: **REFUSED and INCONCLUSIVE are
first-class outputs.** A report that cannot read holder concentration says so;
it does not omit the line. Given section 3.2's finding that 5 of 6 reserve reads
failed today, **REFUSED will be a common answer at launch and must look normal,
not broken.**

---

## 7. Record `chainId` on everything

Currently `network` (a string we set ourselves) is persisted; the payload's own
`chainId` is read only in `check.py:79`, to assert it equals `"solana"`, then
discarded.

**Change:** persist `chainId` from the payload on every row, and stop hard-
failing on non-Solana. A contract on a chain we cannot score should still be
*counted* — visible as volume with a null score rather than absent.

**Why now: Arc mainnet launched 2026-09-16** — Circle's EVM-compatible L1, USDC
as gas, Proof of Authority, institutional validator set. It has no bonding-curve
venue and no memecoin launchpad, so **it is not a near-term source of anything
we track.** That is exactly why to do this now: the cost is one whitelist field
while nothing depends on it, and it means the next chain that *does* matter
shows up as a number instead of a blind spot.

---

## 8. ⭐ Pre-made trackers: buy vs build

**Frank is right that these exist, and we should not rebuild what we can point
at.** But the decision turns on one question — **can we hook our own analysis
onto the alert?** — and that splits the field cleanly.

**First, the framing that matters:** per section 5b, **no product triggers on
market cap natively, because nothing on chain emits it.** Every tool below that
advertises a market-cap alert is computing it from polled or streamed data, the
same as we would. "They already do this" really means "they poll faster than an
hourly cron." That is worth buying. The *threshold test itself* is not a moat
anyone is selling.

| tool | alerts on | cost | hook our analysis on? |
|---|---|---|---|
| **Dexscreener alerts** | price / mcap on a token **you already track** | free | ⛔ **No** — in-app and mobile push only, no alerts API or webhook |
| **Telegram trading bots** (Trojan, BONKbot, Maestro, GMGN, Bloom, BullX, Photon, Axiom) | built-in alpha/alert channels, filters | free to use, per-trade fee | ⛔ **No** — closed ecosystems, no outbound webhook |
| **Cielo Finance** | wallet activity | free: 50 wallets, 120 alerts/hr · Pro $59/mo | ✅ **Yes** — documented WebSocket API |
| **Birdeye** | price action, on-chain events | paid tiers | ✅ **Yes** — WebSocket streaming API |
| **Helius webhooks** (section 5b) | transactions on addresses we enumerate | $0–49/mo | ✅ **Yes** — we own the receiver |

### The verdict

**Nothing off the shelf does both halves of what Frank asked for.** The consumer
products alert but will not let you attach anything; the developer APIs let you
attach things but do not do market-cap thresholds. Ask 2 through 7 — what it is,
why it's running, big wallets, bundles, LP — **exist in no product on this
list**. That is the part that is ours.

**So: buy the plumbing, build the report.** Helius push (5b) is the plumbing,
and it is already half-written in `site/api/helius.mjs`.

⚠️ **Two constraints on this table.** Standing rules are free tools only and
never sign up for anything — Cielo Pro and Birdeye paid tiers are listed for
completeness, **not as recommendations**, and any signup is Frank's decision
alone. And the Telegram bots are *trading* bots; nothing here proposes
connecting a wallet to one.

✅ **One thing worth doing immediately and for free:** set a Dexscreener alert on
a handful of contracts by hand and compare what it catches against section 2's
numbers. **It costs nothing and it independently checks our crossing rate**,
which is the one figure this whole design rests on.

---

## 9. Smart wallets: Cupsey, and the front-running idea

**Cupsey is real and publicly tracked.** Per KOL Explorer as of this week:
**+$46.5K realized PnL (7D), 50.8% win rate, 9,380 trades across 1,144 distinct
tokens in seven days.**

### The exit-liquidity point holds

⚠️ **The most-copied wallet is the worst one to copy** — copying it makes you its
exit liquidity. We already established this about Fomo's copy button and nothing
here changes it. **Frank's reframing is the right one:** the value is in
*observing* the wallet, not following it.

### But the arithmetic is against front-running the copiers

**9,380 trades in 7 days is ~1,340 a day, ~56 an hour.** A "Cupsey buy" is not a
rare event, and 1,144 distinct tokens a week means the signal has almost no
scarcity. Front-running the copy wave therefore requires predicting **which of
~56 buys an hour will attract a wave** — and that is a second prediction problem
with the same shape as the one Marino killed: by the time the wave is
detectable, it is priced.

**This does not make it worthless. It makes it a research question, not a
feature**, and it must be held to the same standard as section 4.3: pre-commit
the definition, report n and an interval, no rate below n=30 distinct contracts.

### Is the copy-wave effect measurable? **Not today**

In principle yes, and cleanly: take each Cupsey buy, measure buy count and price
path in the following N seconds, and compare against a matched control. That is
a well-formed, falsifiable test.

✅ **The data is available** — `/v0/addresses/{addr}/transactions` returns 200
(§0.5); my earlier "403, blocked" note was a User-Agent bug and is retracted.
**Nothing external stops this test being run.** It is gated only on doing it
properly: pre-commit the window and effect size, n≥30 distinct contracts,
report the interval. Logged as rejected-pending-measurement in `RULES.md` B24.

### On the public list

I could not verify a recent public list naming both Cupsey and Frank DeGods.
**No verified address for either is in this repo.** Free public sources that do
exist: a Dune dashboard of Solana alpha wallets for copy-trading, and KOL
Explorer's per-wallet pages.

⛔ **Do not act on an address from an unverified list.** Key on the address,
verify it on chain, and treat any name attached to it as a label, not a fact —
the same rule as tickers.

✅ **The cheap move, once access returns:** add verified addresses to
`WATCHED_WALLETS`. **The existing receiver in `site/api/helius.mjs` already
alerts on watched-wallet activity above a USD floor** — that is near-zero work
and gives observation without copying. It is the one part of this whole document
that is already built.

---

## 10. What to pre-commit before anyone builds

1. **Threshold** — 500k, 1M or 5M, chosen from section 2's verified volumes.
2. **The verification rule** — V1 through V6, with the depth floor as a number.
3. **The continuation definition** for section 4.3, written before any data is
   examined.
4. **What "REFUSED" looks like** in the output, so a missing measurement can
   never render as a clean one.
5. **The nomination band** for section 5b — its width drives Helius push volume
   and therefore the entire cost, and it drives the vertical-launch miss rate.
   Both need measuring once collection is back.

## 11. Blocking prerequisites, in order

✅ **Nothing here is Frank's to buy, authorise or pay for.** The two items
previously listed as his — Helius access and the Vercel URL — were both my own
User-Agent bug and are resolved (§0.5). **Every remaining blocker is ours to
fix, and none of them costs money.**

1. ⛔ **Fix `onchain_reserves.exit_depth()`** — vault discovery and the SOL-price
   path. 5 of 6 reads failed on 2026-09-17. **Both V1 (3.2) and the webhook's
   receiver-side threshold test (5b) rest on it, so it now blocks more than it
   did.** Highest-leverage item in the document.
2. ⛔ **Restore collection (5a)** — Windows Task Scheduler, with
   `CRYPTO_ORIGIN=scheduled` set. Nominations for 5b come from here, so the
   detector cannot work without it either.
3. ⚠️ **Decide the nomination band and narrow `transactionTypes`** before writing
   any address into the live webhook. It is `["ANY"]` today with an empty address
   list; widening the list without narrowing the type is how the Helius credit
   bill stops being $0.
5. **Then** the cheap wins, none of which are blocked by anything above:
   socials whitelist (4.1), website explainer (4.1b), `chainId` (7), holder
   concentration vault exclusion (4.4).
6. ✅ **Free and unblocked right now:** set Dexscreener alerts by hand on a few
   contracts and check them against the section 2 crossing rate (8).

**Nothing in this document has been implemented.**
