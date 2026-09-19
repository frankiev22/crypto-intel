# crypto-intel

**Handoff file. Read this first, then the two or three `docs/` files your task
touches. Do not re-derive what is written here.**

Last updated 2026-09-19. ⚠️ **Keep this current. It is the handoff, not a
one-off** — if you change architecture, numbers, or blockers, update it in the
same session.

---

## What this is

A **filter and an explainer** for Solana memecoins. Frank trades his own picks in
**$100 clips**. The system's job is to **show him things he would otherwise
miss** and to **stop a class of loss**, then get out of the way. He makes the
call.

## ⛔ What this is NOT

**It does not predict winners. Five attempts have been built and retracted.**

The Marino result is why: perfect knowledge of graduation probability still
loses money, because price outruns probability. By the time a signal is
readable, it is priced. **Do not propose a scoring model that ranks tokens by
expected return.** `dashboard.py` enforces this in code — sections sort by
recency or size, never by anything readable as a quality ordering, and `score`
is never displayed.

⛔ **The 70-99 score band is DELETED from the v1 entry gate as of 2026-09-18.**
It refused a token graded **100** - the cleanest grade the scorer awards - with
"score 100 outside 70-99", on two intervals that overlap (4.55% [2.62, 7.78] vs
1.20% [0.64, 2.27]) measured on a population its own gate had hollowed out.
**It had been "fixed" once before and only the wording changed.** The band now
survives solely in `paper.qualifies_v1_historical()`, which explains the 409
frozen rows and defines RULE_V2's arms. ⭐ **`test_scoreband.py` fails if a score
term reappears in the branch of any entry gate**, checked at the AST level -
`ENTRY_GATES` there is the list of guarded function names, so a new entry gate
must be added to it.

**The exception, and it is narrow:** describing something that has **already**
happened is not predicting. The 1M tracker (`docs/TRACKER_SCOPING.md`) watches
completed crossings and explains them. Marino does not apply to description.
**It does apply to anything forward-looking**, including "will this run
further" — scope those separately and hold them to the measurement bar below.

---

## The numbers. Use these, do not recompute them casually

| figure | value | source |
|---|---|---|
| graduation base rate, published | **0.198%** [0.189, 0.208], n=832,941 | Kamat, arXiv:2607.02823 |
| graduation base rate, ours | **0.22%** (30 / 13,709 mature) | `GRADUATION.md` |
| ⛔ **2.10%** | **NEVER QUOTE** | see below |
| $1M crossings/day, raw | **59.0** | `docs/TRACKER_SCOPING.md` §2 |
| $1M crossings/day, **verified** | **24.5** | same |
| verification pass rate at $1M | **25.4%** [22.3, 28.8], n=696 | same |
| reported liquidity overstatement | **median 781x** | `CONTAMINATION.md`, `TEMPLATE_ATTACK.md` |
| ⛔ **verified wins** | **none.** `7uMjiTCQ…` "4.58x" FAILED: graded TRAP at observation, then its freeze authority froze 50 buyers the second each bought, and their SOL was the multiple | `docs/BACKLOG.md` A42 |
| ⛔ paper v1 hit rate | **QUARANTINED - no usable rate.** The retired 9/76 = 11.84% was on mid-priced exits, and 96 v1+v2 positions were never closed (09-15 → 09-17). `paper.summary()` returns `QUARANTINED` from 2026-09-19 | `PRECOMMIT_paper_v3.md` §2a |
| ⭐ median holders, our own "winners" | **9** (54% under 10) | `docs/TRUSTED_FIELDS.md` §1 |
| median holders, Jupiter-TRADEABLE | **1,350** | same |
| median holders, Jupiter-TOTAL_LOSS | **3** | same |
| ⭐ **launch coverage, measured from chain** | **1.26%** [0.49, 3.20], 4/317 creates | `COVERAGE.md`, `coverage_probe.py` |
| ⭐ **graduation coverage, measured from chain** | **1.67%** [1.06, 2.63], 18/1,077 — the whole ledger, every pass (was 1.95%, 5/257 sampled) | `data/graduations/index.json` |
| top-25 24h gainers ever in our journal | **0/25** (first snapshot, 2026-09-18) | `data/market/index.json` |
| ⭐ Solana tokens ≥ $1M on the listings | **1,035** (Jupiter-verified 668 ∪ CoinGecko 784 ∪ ours 15); **863** under the pre-committed rule (Jupiter's mcap wins) | `docs/UNIVERSE.md` §1 |
| ⛔ ...of which a $100 round trip is TRADEABLE | **65.0%** [54.1, 74.5], 52/80 seeded random | same |
| ⛔ ≥ $1M tokens running that NEITHER listing has | **11 of 42** (26%) in one market snapshot | same |
| pump.fun graduations per hour, from the ledger | **~45** (944 in 21.0h, 2026-09-19) — ⚠️ vs a 0.198% base rate, unreconciled | `data/graduations/` |
| ⛔ volume-manipulation rule (M1/M2), validated | **FAILS**: flags 96.7% of sellable vs 90.0% of unsellable tokens; M2 tracks activity. **M1′ alone vs the wallet farm: 0/30 flagged vs 4/30 of the control, null** | `docs/VOLUME_INTEGRITY.md` §3c, §3e |
| ⭐ **our base rate: AMM token → >= 2x with >= $500 quote depth at +6h/+24h, authorities revoked** | **0.27%** [0.05, 1.54], 1 / 364 priced from chain (409 sampled, 09-12 → 09-18) | `PRECOMMIT_cluster_rule.md` "Result" |
| ⛔ **wallet-cluster rule (3+ wallets / 10 min / $1,500)** | **INCONCLUSIVE**: fired on 7 of our 409 sample tokens (bar n=30); degentape's wallets touched only 38 of them | same |
| degentape's "win" (profit > $0), re-derived from their tape | **39.7%** [39.3, 40.1] of 45,853 closed positions - reproduces their own 39.4% | `docs/EXISTING_TOOLS.md` §4a |
| ⭐ ...the same positions on OUR definition (proceeds >= 2x cost) | **6.0%** [5.8, 6.3]; median position 0.925x, median hold 2.4 min | same |
| paper ledger, re-derived 2026-09-17 | 86 closes, **−$2,495** by mult / **−$4,168** realizable | `docs/LIQUIDITY.md` §8 |

⛔ **Never quote the 2.10% graduation rate.** It is 397/18,920 computed on
**reported liquidity** — the field measured overstating by a median 781x. Our
clean figure is 0.22%, which agrees with Kamat's 0.198%. **Any lift ever quoted
against 2.10% needs recomputing.**

⛔ **v1 AND v2 PAPER LEDGERS ARE QUARANTINED (2026-09-17).** Both price fills off
the Dexscreener mid: `notional_usd` is recorded on every entry and **never
applied**, so the multiple is a price nobody could obtain at any size. That is
why the wins do not verify - the exits were fictional, not optimistic. Appends
raise; reads still work. ⛔ **Never quote their P&L again** - specifically the
retired **-$3,099 / -$40.78** and my re-derivation **-$2,495 / -$4,168 over 86
closes**. Honest status: **"no usable P&L"**, not a loss figure. See
`PRECOMMIT_paper_v3.md` §2.

⚠️ **The paper log is a SIMULATION.** Frank has **no realized P&L**. Never
describe paper results as his trading record. `data/paper/ledger.jsonl` (v1) and
`ledger_v2.jsonl` (v2) contain no transaction signatures, wallets, fills or
fees. Any path that depends on a track record has nothing to sell yet.

---

## Standing rules — non-negotiable

1. **Re-derive any figure a brief hands you** before acting on it. Say plainly
   when it is stale or wrong. **Lead with the correction.**
2. **Key on the contract address, never the ticker.** Tickers are display only.
   398 contracts in our data impersonate an incumbent name; one "DOGE" showed
   $86.5B FDV against $0.0002 of real sellable depth. ⛔ **And a ticker can
   render as a name it does not contain:** 112 contracts carry a bidi control in
   the symbol (`'U‮CDЅ'` displays as **USDC**, and claimed the highest
   liquidity of 2026-09-18 with zero sells), 48 more mix Cyrillic into Latin.
   `html.escape()` does NOT neutralise this - use `dashboard.safe_sym()`. See
   `docs/SYMBOL_ATTACKS.md`.
3. **Liquidity-gate every headline number.** Reported liquidity overstates by a
   median 781x. A market cap, a multiple or a win is not real until it is
   checked against **quote-side depth from on-chain reserves**.
4. ⚠️ **Phantom crossings are the norm, not the exception.** Only **25.4%** of
   $1M crossings survive a basic integrity screen. Never fire an alert on an
   unverified crossing — he will act on it.
5. **Unknown renders as "unknown", never as 0 or blank.** Five separate failures
   came from an absent measurement rendering as a real value. See the `usd()`
   docstring in `dashboard.py` — it is the clearest statement of the rule.
6. **Numbers carry n and a Wilson interval.** Every threshold is pre-committed
   to a file **before** anyone looks at the data.
7. **No hit rate below n=30 closed distinct contracts per arm.** Report both
   ways: late closes in/out, inferred losses in/out.
8. **Nothing is ever deleted.** The journals are append-only.
9. **Free tools only. Never sign up for anything. Never execute a trade.**
   Price things and report; signup is Frank's decision alone.
10. **"Exists but never runs" bugs are verified by observing an unattended run**,
    not by reading config.
11. ⛔ **Never hand Frank a manual process.** "Set the alerts by hand" is not an
    answer. If it cannot be automated, say so and say why.
13. ⛔ **Never measure a phenomenon with a sampler slower than the phenomenon.**
    Three failures from this one class: fast winners logged as losses (first
    checkpoint 1h, median time-to-bond ~1min); and the retracted band-dwell
    finding, where per-batch `ts` and hourly discovery produced "88% seen once"
    by construction. **Before quoting any duration, state the sampling interval
    and show it is shorter than what you are measuring.** When Frank's lived
    experience contradicts a measurement, the measurement is the suspect.
14. ⛔ **A/B measurements on live traffic must run SIMULTANEOUSLY, never in
    sequence.** Memecoin activity is bursty, so two samples minutes apart are
    two different populations. Measuring the filtered and unfiltered Helius
    streams back-to-back made the *filtered* stream look 22% busier than the
    unfiltered baseline — an impossible result that only resolved when four
    subscriptions ran concurrently on the same traffic (`docs/LIQUIDITY.md` §7).
    **If you are comparing two conditions, open both at once and share a start
    barrier.** Same family as rule 13: a measurement taken at the wrong moment
    does not describe the moment you care about.
15. ⛔ **A truncated sample must record WHAT it missed, not just how much.**
    The scanner enriches `pools` newest-first and `break`s on a time budget, so
    the rows it drops are always the tail - systematically the oldest pools in
    the batch. Measured across 399 passes: 97.0% coverage overall, 99% median,
    but 55% of passes truncate and the worst saw 19%. `LAST_SCAN["skipped"]` now
    carries the addresses. ⚠️ **I first reported this as "24% dropped" from a
    single pass I happened to watch - an 8x overstatement, and the same
    generalise-from-one-observation error this rule exists to catch.** Small-n
    findings are the exposed ones; see `docs/SAMPLING_BIAS.md`.
16. ⛔⛔ **VERIFY THE OUTPUT, NEVER THE EXECUTION.** Every failure this week is
    the same mistake: socials dropped (we checked the field was *computed*, not
    that it *landed in a row*), the score band (we checked the *changelog*, not
    the *source*), pool truncation (we checked the pass *completed*, not what
    fraction it *processed*), liquidity off 781x (we checked a number *came
    back*, not that it was *true*), the collector dead 4 days (we checked the
    task *fired*, not that *rows appeared*). **Four of those five were silent.**
    ⭐ **A component that cannot tell us it is broken is worse than one that is
    obviously broken.** Every component asserts its own output; the liveness
    registry counts **rows, not beats**; every headline number carries its n and
    its provenance. **Read `docs/ENGINEERING_DISCIPLINE.md` before adding any
    component**, and `test_discipline.py` enforces what can be enforced.

17. ⛔⛔ **Every third-party crypto tool is UNTRUSTED BY DEFAULT** (Frank,
    2026-09-19, permanent: *"Treat everything as unsafe and something we would
    want to rebuild as a feature of our site. Or something we can use externally
    for aggregation"*). Two relationships only: ⭐ **REBUILD** (build the
    capability into our site) or ⭐ **AGGREGATE** (read its public output over
    HTTP, never depend on it, never authenticate). ⛔ **Never connect a wallet to
    any of them, no exceptions. Never take a dependency that needs auth.**
    ⚠️ **Their claims are marketing until verified against our own data or the
    chain.** Every tool's label lives in `docs/EXISTING_TOOLS.md`; `RULES.md`
    rule 24 has the reasoning.

12. ⚠️ **Any script hitting a Cloudflare-fronted API must set a `User-Agent`.**
    Python's default `Python-urllib/3.x` is blocked with a bare `403 error code:
    1010`, which looks exactly like an auth failure and is not. `sources.py:12`
    does this correctly; copy it. This has bitten twice.

---

## Architecture: what runs where

| component | what it does | state |
|---|---|---|
| `collect.py` | hourly staged collector: scan, sweep, watchlist, 1/6/24/168h | ✅ **running again on the hosted runner, 2026-09-18** |
| ⭐ `market.py` | **what is running NOW** - movers, volume, trending, clusters, the tape → `data/market/` | ✅ **UNATTENDED, verified 2026-09-18 23:49Z** (scheduled run 35407026193: 412 rows, 18/18 sources ok from GitHub's IPs, 44.6s). ⛔ **The pipeline only ever collected tokens at birth; 0 of the top 25 24h gainers were in our journal.** Schema for the site: `docs/MARKET_DATA.md` |
| ⭐⭐ `universe.py` | **THE TRACKED UNIVERSE**: every Solana token ≥ $1M, admitted only on a TRADEABLE $100 round trip, **never removed**; trending × universe → narratives → `data/universe/` | ✅ **UNATTENDED, verified 2026-09-19 01:48Z** (scheduled run 35413442372: 701 members, 20.3s). Seeded by hand first: 922 quoted, 699 admitted. Rule pre-committed in `docs/UNIVERSE.md` §3. ⛔ **The $100 gate admits a wallet farm ($3.53B claimed on a fraction of a percent of backing): never show a cap without `cap_backing_pct` (§3a).** ⭐ **Read by the site on production from 2026-09-19** (`site/api/market.mjs`, verified ~02:05Z), ⚠️ **but that source is uncommitted until the site session commits it (BACKLOG C16)** |
| ⭐⭐ `safety.py` | **the safety verdict on every tracked token** (DANGER / WARN / NO FLAGS / UNKNOWN), rule `PRECOMMIT_safety_v1.md` v1.1: the $100 round trip, mint account from chain (authorities, Token-2022 extensions), D1 on the live pair, holders, cap backing, RugCheck (attributed, optional). ⛔ **Fake volume and bundles are NOT CHECKED on every verdict, in words** | ✅ **in every universe pass from 2026-09-19, and RENDERED ON PRODUCTION** (observed 18:55Z: per-row verdicts, per-list tallies, "not checked: fake volume, bundles / insiders" in words; BACKLOG A40 SHIPPED) |
| ⭐ `live.py` + `supa.py` | the 10-second path: Jupiter every 10s (hot) / 60s (all), D1 every 60s, published to Supabase `live_*` tables (`supabase/migrations/002_live.sql`) under its own path name; `.live/status.json` on the host | ⛔ **BLOCKED: the schema is not applied** - nothing on disk can run DDL on `rxofejxostyqlgjlzqmk` (BACKLOG A41) |
| ⭐ `graduations.py` | **every pump.fun graduation** (C14): pages the migration authority from a cursor, every signature accounted for → `data/graduations/` | ✅ **UNATTENDED, verified 2026-09-19 01:48Z** on the keyless public RPC (17/17 accounted, lag 11s). Runs before the universe, which re-checks 72h of graduations for $1M |
| ⭐ `paperv3.py` | the ledger that prices fills on real quotes | ✅ **SCHEDULED 2026-09-18** — enters in the scan loop beside v1/v2, sweeps in the sweep stage. ⛔ **Nothing called it before that**, despite 71 passing tests |
| GitHub Actions `collect.yml` | same, hosted | 🟡 **Free and unlimited (public repo), but ⛔ the 11:37, 14:50 and 17:38Z passes on 2026-09-19 were CANCELLED at the 15-min job timeout before they could commit - every row lost, silently** (BACKLOG C17). Fix `b13267f`: job 35 min, Collect step 24, runner pass clock 20 min, outcomes stop at 13, artifact on cancel too, `test_stages.py` §10 ties them together. ⚠️ **Not yet observed on an unattended pass** |
| Claude desktop task `crypto-collect-hourly` | same, staged, on the host (all ten stages incl. `sweep`) | ✅ **alive again 2026-09-19** after the desktop restart cleared the Plan9 mount: scheduled passes observed 06:24–06:41Z and 07:07Z, and it closed a v3 position unattended (Pigeon, 07:07:55Z). ⚠️ **Recurring outage**: a reboot that loses the mount kills it silently. ⛔ It is NOT Windows Task Scheduler - there is no crypto task there, and none should be added (`479e9cc`) |
| `site/` on Vercel (`crypto-intel-one-eta.vercel.app`) | ⭐ **the deliverable**: trending, tracked universe, narratives, crossings, movers, paper v3 counts. **Owned by the site session**; every cap goes through `honest.capWithBacking()` | ✅ **all four C16 reads live, verified 2026-09-19** from the pipeline side. ⛔ The pipeline session never stages `site/` files, `site/README.md` included |
| `site/api/helius.mjs` on Vercel | Helius webhook receiver → Supabase → Discord | ✅ **deployed and answering**, but watching 0 addresses |
| `data/dashboard.html` | static phone-first dashboard, built by `dashboard.py` | ✅ **rebuilt on every pass from 2026-09-18** (`dashboard.build`, 4.0s, stdlib only, no network). ⛔ Before that it appeared nowhere in `collect.py` and went stale silently |

**State store is git.** `data/` is committed after every run. Supabase is a
write-only mirror (no SELECT grant), so it cannot serve as state.

**Live deployment:** `https://crypto-intel-one-eta.vercel.app` —
`/api/helius` is the receiver. Webhook `75056f75-c129-4f43-b686-0f369f8fa669`
is `active: true`, `transactionTypes: ["ANY"]`, **`accountAddresses: []`**.
⛔ **That empty list is why whale alerts have never fired.**

### Current blockers, in order

1. ⚠️ **`onchain_reserves.exit_depth()` is unreliable — but it is NO LONGER what
   everything depends on, and the old wording here conflated two functions with
   similar names.** Re-derived 2026-09-18:

   - **`onchain_reserves.exit_depth(pool, base, quote)`** — the real on-chain
     read, 5 of 6 failed on 09-17. ⭐ **It has exactly ONE live caller:**
     `paper.py:810`, inside the **quarantined** v1 close path, where it fills a
     supplementary `chain_depth` field. Nothing else in the repo imports it.
   - **`resolve.exit_depth_usd(pair)`** — computed from the Dexscreener
     `liquidity` payload. **This is the one on the hot path**, with ⛔ **four
     copies**: `resolve`, `scanner`, `watchlist`, `paper`. It gates
     `paper.wants_authority_check()` and therefore the whole v3 funnel.

   ⭐ **What verifies a number today is `chainfields.round_trip()`** — Jupiter,
   realizable, used by `check.py` and `paperv3`. The leverage moved with it.
   See `test_depth.py` for the two divergences between the four copies.
2. ✅ **RESOLVED 2026-09-18 — the collector runs on GitHub Actions again.**
   The repo is **public**, so Actions minutes are free and unlimited and the
   ~$31/mo question is closed. Runs take ~9-10 min at the 2026-09-07 pacing
   (`CRYPTO_HTTP_PACE_S` 1.0, correct and not to be reverted).
   ⚠️ **Windows Task Scheduler is NOT the answer and was deliberately removed**
   (`479e9cc`). Do not reintroduce it.
3. ⚠️ **A concurrent push can still cost a pass, and once did.** On 2026-09-18 a
   scheduled run collected a full pass and then died in `Commit the journal`
   because a human pushed during its ~10 minutes; `git pull --rebase` stopped at
   the first conflict and the ephemeral runner was destroyed with the rows on it.
   Fixed two ways: `*.jsonl merge=union` in `.gitattributes`, and a push loop
   that resolves conflicts and uploads `data/` as an artifact if it still cannot
   push. ⛔ **Avoid pushing while a run is in flight anyway.**
4. ⛔ **A cancelled run loses its rows and says nothing** (2026-09-19, BACKLOG
   C17). Three passes ran past the 15-minute job timeout; `cancelled` is not
   `failure`, so nothing alarmed, and origin/master sat at 07:26Z for 11 hours
   while the site served stale data. The desktop task's rows were committed by
   hand (`2ef6de5`). ⛔ **The desktop task never commits** - its rows reach origin
   only when this session commits them. **When a pass grows, check its duration
   against the workflow's timeouts** - `test_stages.py` §10 now does.

---

## Map of the repo

**Start here for a task about…**

| topic | file |
|---|---|
| ⭐ **the flagship experiment** — pre-launch social signal | `docs/PRELAUNCH_SIGNAL.md` |
| ⭐ **liquidity: what to trust, and the plan to replace `liq`** | `docs/LIQUIDITY.md` |
| ⭐ **holders, mcap, volume, bundles — all from chain** | `docs/TRUSTED_FIELDS.md` |
| ⭐ **every killed strategy and whether its killer survives** | `docs/UNKILL.md` |
| ⭐ **what already exists — compose, don't rebuild** | `docs/EXISTING_TOOLS.md` |
| ⛔ **every third-party crypto tool's label (REBUILD / AGGREGATE / neither), degentape verified on chain** | `docs/EXISTING_TOOLS.md` §4 |
| volume manipulation: methods and pre-committed thresholds | `docs/VOLUME_INTEGRITY.md` |
| ⭐ **dev wallet history, funding graphs, first buyers, LP** | `docs/DEV_WALLET.md` |
| ⭐ **paper trader v3 — fills priced on real quotes** | `docs/PAPER_V3.md`, `PRECOMMIT_paper_v3.md` |
| ⛔⛔ **EVERY commitment and its status — read at session start** | `docs/BACKLOG.md` (⛔ read the **SHIPPED-row audit** section first) |
| ⭐⭐ **the tracked universe: size, cost, source, the pre-committed gate** | `docs/UNIVERSE.md` |
| ⭐ **what is running now: every `data/market/` file, field and rendering rule** | `docs/MARKET_DATA.md` |
| ⭐ **one place: what is scattered, what retires, what Frank must decide** | `docs/CONSOLIDATION_PLAN.md` (plan only - nothing moved) |
| ⛔ **Cash Cat is RETRACTED - never cite it as a hit** | `docs/BACKLOG.md` A37 |
| ⭐ **how much of the launch stream we see, and the costed good version** | `COVERAGE.md` (2026-09-18 section) |
| ⛔⛔ **how we test: verify output, not execution** | `docs/ENGINEERING_DISCIPLINE.md` |
| ⛔ **symbols that render as a different token** | `docs/SYMBOL_ATTACKS.md` |
| ⛔ **why no score may gate an entry, and the AST check** | `test_scoreband.py` |
| outcome-queue expiry: 21% of checks, and why | `docs/SAMPLING_BIAS.md` §5 |
| crypto history, organised by recurring mechanism | `docs/CRYPTO_HISTORY.md` |
| the 1M tracker, crossing rates, real-time architecture | `docs/TRACKER_SCOPING.md` (**§5c supersedes §5b**) |
| buyer and creator rules, rejected ideas | `docs/RULES.md` (§B buyer, §C creator, §O observations) |
| standing reporting rules | `RULES.md` (root — different file, do not confuse) |
| terms, base rates | `docs/GLOSSARY.md` |
| chains, venues | `docs/CHAINS.md` |
| trading economics, fees, sizing | `docs/TRADING_PLAYBOOK.md` |
| launch mechanics, curve geometry | `docs/TOKEN_MECHANICS.md`, `docs/CREATOR_PLAYBOOK.md` |
| the long-form reference and open questions | `docs/TRENCHES_REFERENCE.md` |
| the 781x liquidity finding | `CONTAMINATION.md`, `TEMPLATE_ATTACK.md`, `EXIT_DEPTH.md` |
| what the detectors do and their recall | `FRAUD_DETECTION.md` |
| open gaps and their measurement bars | `GAPS.md`, `OPEN_ITEMS.md`, `QUESTIONS.md` |
| X/Twitter API prices | `X_API.md` |
| any pre-committed threshold | `PRECOMMIT_*.md` |

⭐ **Existing credentials — full disk scan 2026-09-18, do not re-ask.** 62
distinct credential names across 37 files. **Values are never printed anywhere.**

**crypto-intel/.env:** `HELIUS_API_KEY` (✅ RPC 200, free tier 1M credits/mo),
⭐ `JUPITER_API_KEY` (free tier, 25M credits/mo then $1/M; **measured ceiling
~1.1 req/s — the key buys reliability, not speed**; usage in
`data/_jupiter_usage.json` via `chainfields.usage()`), `BIRDEYE_API_KEY`
(⛔ **dies after ~7 calls, permanently 401 — do not use**), `ALCHEMY_API_KEY`,
`ETHERSCAN_API_KEY`, `HELIUS_WEBHOOK_SECRET`, Supabase, 4 × `CRYPTO_*_SECRET`.

⭐ **X / Twitter: SEVEN credentials, and the account is ALIVE.** In
`dispatch-workspace/.env` **and** `~/Documents/openclaw-review/gateway.cmd` and
`~/OLD-OC-old/gateway.cmd` (⚠️ bearer is 112 chars in `.env`, 113 in
`gateway.cmd` — the `.env` one is the one that authenticates):
`TWITTER_BEARER_TOKEN`, `_ACCESS_TOKEN`, `_ACCESS_SECRET`, `_CONSUMER_KEY`,
`_CONSUMER_SECRET`, `_OAUTH2_CLIENT_ID`, `_OAUTH2_CLIENT_SECRET`, plus
`TWITTER_USERNAME`/`_PASSWORD` (account, not API).

⛔ **ALL FOUR AUTH PATHS PROBED 2026-09-18** (`scratchpad/xprobe.py`; it prints
status codes only, never a key). The seven names are ONE app's credential set in
four flavours, plus a second bearer that is not a copy of the first:

```
bearer A (.env, 112 ch)   /2/usage/tweets          200  cap 3,000,000  usage 0
                          /2/tweets/search/recent  402  credits depleted
                          /2/tweets/search/all     402  credits depleted  <- historical
                          /2/users/by/username/..  402  credits depleted
                          /2/users/me              403
bearer B (gateway.cmd)    every endpoint           500
OAuth 1.0a user context   usage 403, all data      401  Unauthorized
OAuth2 client_credentials /2/oauth2/token          400  invalid_request
```

⭐ **CORRECTION: this is a DEPLETED CREDIT BALANCE, not a lapsed subscription.**
X's own problem URI is `.../problems/credits-depleted`. Frank remembered buying
credits and not paying for a developer account, and the error matches his
account, not the earlier "billing lapse" reading.
⚠️ **Two different meters, and both statements are true:** the 3M/month POST cap
is untouched (`project_usage 0`), and the consumable read credits are at zero.
⛔ **No credential unlocks full-archive search.** The ask is a **credit top-up**,
not a subscription — and it is Frank's call alone.
⭐ **Re-probed 2026-09-19 18:52Z (`scratchpad/xprobe2.py`):** the app-only bearer
minted from the CONSUMER key/secret (`POST /oauth2/token`) returns 200 and is
**identical to bearer A** - the app is alive, the consumer keys are valid. Every
data endpoint, full-archive included, is **402 credits-depleted**: the same gate as
recent search, not a 403 plan refusal, so credits are the only gate (inferred from
the error type). `~/OLD-OC-old/gateway.cmd` holds the same values as `gateway.cmd`.
BACKLOG C11.

⛔ **Solana now carries VERSION-1 transactions (~5%, measured 2026-09-19).** Any
`getTransaction` must ask for `maxSupportedTransactionVersion: 1`; with `0` the
node returns -32015 and the transaction silently becomes a "fetch failure".

⛔ **`XAI_API_KEY` is DEAD** — `400 Incorrect API key` from `api.x.ai/v1/models`.
Present in the same three files. It needs replacing, not finding.

⛔ **Grep every project `.env` before ever saying a key does not exist.** We lost
15 days to that once, and I repeated a version of it this session: I "corrected"
myself to say the Twitter keys were only in `gateway.cmd`, then found they are in
`dispatch-workspace/.env` too — my scan had printed only the first two locations.

**Key modules:** `collect.py` (orchestrator, `STAGES`/`staged_commands()`) ·
`journal.py` (append-only store; `record()` is a **field whitelist** — a field
not added there does not exist) · `paper.py` / `paperv2.py` (simulation ledgers)
· `check.py` (one CA in, one verdict out — the model for the analyzer) ·
`detector.py` (D1/D2) · `onchain_reserves.py` (quote-side depth) ·
`liveness.py` (origin tagging; `UNATTENDED = ("runner","scheduled")`) ·
`dashboard.py` · `sources.py` (all HTTP; sets the UA correctly) · ⭐ `market.py`
(market-wide snapshot, keyless) · ⭐ `universe.py` (the tracked universe) ·
⭐ `graduations.py` (graduation ledger) · `volintegrity.py` (volume M1/M2 under
the pre-committed rule; validation, not a live gate) · `crossingdepth.py` (re-links historical
crossings to the depth measured at them) · `coverage_probe.py` (launch coverage
from pump.fun's own signers).

⛔ **Jupiter's "organic" volume split is NOT a wash signal.** SOL itself runs
1.8% organic; a low share is the norm. It is published beside SOL's baseline
and flags nothing. There is no wash detector in `data/market/`.

⭐ **mcap and multiple milestone claims carry `exit_depth_at_crossing`** from
2026-09-18 - the same values the outcome row records, measured in the same call.
History (1,097 crossings, 09-09 onward) is in
`data/milestones/depth_at_crossing.jsonl`.

⭐ **`devwallet.py`** — `deployer()`, `launches()`, `activity_before()`,
`funding_chain()`, `first_buyers()`, `buyer_funding_overlap()`, `lp_detail()`,
`track_record()`. ⛔ **Runs, but on n=4 it did NOT separate good from bad** — see
`docs/DEV_WALLET.md` §5. Never date a wallet by walking its history; ask
`activity_before()` instead (a walk gave WOFI an age of **minus** 0.1h).

⭐ **`chainfields.py` is the trusted-field source** — `round_trip()` (realizable
liquidity), `supply()`, `market_cap()`, `holder_count()`, `trusted()`. ⛔ **Unknown
is None, never 0.** Decision-point only: a process-wide bucket caps Jupiter at
55/min, so it must never reach the per-row scan path. `test_chainfields.py --live`.
⛔ **A failed quote is not a route answer (2026-09-19).** Only Jupiter's own
`errorCode` (`NO_ROUTES_FOUND`…) makes `NO_BUY_ROUTE` / `NO_SELL_ROUTE`
(`chainfields.answered()`). An HTTP 5xx, a dead network or rate limiting is
verdict `None` from `round_trip()` and `QUOTE_FAILED` from `sell_quote()` - before
this, a Jupiter outage would have booked v3 total losses, DANGER verdicts and
universe refusals. v3 retries a failed exit quote and voids only 6h past the hold.

⛔ **The win gate has NINE checks from 2026-09-19**: `authority_live` fails any
multiple measured from a moment when the mint or freeze authority was live
(`authority_live_at_entry` on every outcome row; None = unchecked, not failed).
And a win announcement no longer says "realizable" - nothing in it quotes a sell.

⛔ **The runner has NO `.env`, and two things quietly depend on that.**
`config.helius_rpc()` falls back to `api.mainnet-beta.solana.com`, which
serves `getTokenAccounts` but wants **`mintAddress`** where Helius wants
**`mint`** — `chainfields.holder_count()` switches on the endpoint's own error,
verified keyless at **977 holders**, the same number the keyed path returns.
Jupiter falls back to the keyless lite-api and round-tripped BONK at **0.0244%**.
⭐ **No repo secret is needed.** Without the spelling switch, paperv3 would have
entered normally by hand and **nothing at all unattended**.

⭐ **`holders` is on observation rows from 2026-09-18** — fetched at the decision
point only, for rows that cleared every free condition of RULE_V3 (~7 a pass,
measured 92 of 1,003 rows over three days). Helius DAS, never Jupiter. Forward
only: no historical row has it. `holders_truncated` means the number is a FLOOR.

⚠️ **`journal.record()` is a whitelist and it has silently eaten four fields**
(`vol_to_liq`, `vol_burst`, the news NameError, `paper_v2_arm`) plus
`info.socials`, which is fetched on every row and never stored. **Compute and
persist are two separate steps. Do both.**

---

## Commands

```
python collect.py solana --stage scan --max-seconds 110   # one staged pass
python check.py <CONTRACT_ADDRESS>                        # fraud check, one CA
python dashboard.py                                       # rebuild data/dashboard.html
python -c "import paper; print(paper.summary())"          # paper ledger counts
python run_tests.py                                       # ⭐ EVERY suite + proves data/ was untouched
python test_stages.py                                     # SKILL.md must match staged_commands()
python test_references.py                                 # every file the repo names exists (run before ANY doc move)
python universe.py --gate-seconds 60                      # one universe pass (writes data/universe/)
gh run list --workflow=collect.yml --limit 10             # runner state
```

**Liveness check that actually means something:** `python liveness.py`. Its last
line answers the only question that matters — **when did a pass NOBODY TRIGGERED
last write rows.** ⛔ **A task firing is not the same as a pass running** (the
desktop task fired hourly for two days while collecting nothing), and **a hosted
runner is not the same as unattended**: `origin()` returned `"runner"` for every
Actions run until 2026-09-18, so a `workflow_dispatch` a human pressed recorded
identically to a cron fire. It now returns **`scheduled`** for cron and
**`dispatch`** for a button press, and only `("runner", "scheduled")` count.
⚠️ **`runner` rows written before 2026-09-18 are a mix of the two and cannot be
re-derived**, so any unattended figure spanning them is an upper bound.

---

## Real-time detection: settled conclusions

**You can trigger on market cap.** Nothing on chain emits it, but every swap
mutates the AMM pool account and mcap is computable from reserves on each
update. **The trigger is possible; the question was only ever how many accounts
you can watch.** Do not tell Frank it is impossible.

**Measured, 2026-09-17 (`docs/TRACKER_SCOPING.md` §5c):**
- Helius webhook ceiling is **100,000 addresses** — never the constraint.
- **Credits are:** a pool at $600k–$1M does a median **206 txns/hour ≈ 4,944
  pushes/day**, so the free 1M credits/month covers only ~7 watched pools;
  $49/mo Developer covers ~66. Webhook **edits cost 100 credits each**.
- ⛔⛔ **RETRACTED 2026-09-17: the "88% / 9-minute dwell" finding was an
  artifact and the claim that nomination cannot work is withdrawn.** `ts` is
  per-batch, not per-token; all 10 "multi-sighting" contracts were inside a
  single pass (gaps of 0–545s), so it measured our scan loop, not coin
  behaviour. **Third instance of this error class — see standing rule 13.**
  Whether nomination works is now an open question, not a settled one.
- ✅ **The answer is `programSubscribe` on the AMM programs** — watch the
  program, not a list of pools. No nomination, no miss window, no address
  ceiling. Needs an always-on process (**VPS ~$4–6/mo**; a Vercel function caps
  at 300s and cannot hold a subscription).
- ✅ **Costed by measurement, 2026-09-17.** Helius bills standard WebSockets at
  **20 credits/MB**. A live 45s `programSubscribe` on pump.fun measured **56
  notifications/sec, 31 KB/s, 542 B median → 82 GB and 1.64M credits/month**.
  **Free tier fails (1.6x over); Developer $49/mo fits at 16%, 6x headroom;
  Business $499 is not needed.** A $4–6 VPS is far more than enough — 56 small
  JSON messages/sec is trivial. **Total real-time cost ≈ $53–55/month.**

## The one genuinely urgent thing

⛔ **Socials capture (commit `ce0d33a`) is forward-only.** Two collectors run
again as of 2026-09-19 (the runner, ~7-9 passes a day, and the desktop task,
hourly while its mount holds), but every hour without one is sample that cannot be
bought back at any price. **Restoring collection outranks every purchase decision on the board** —
see `docs/DECISION_X_DATA.md`.

## Knowledge corpus

Durable knowledge accumulates in `docs/`, one file per domain, **appended to
rather than re-derived each session.** Existing: `CHAINS.md`,
`TOKEN_MECHANICS.md`, `CREATOR_PLAYBOOK.md`, `TRADING_PLAYBOOK.md`,
`TRENCHES_REFERENCE.md`, `GLOSSARY.md`, `RULES.md`.

**Planned, not yet written** — create on first substantive finding, do not
scaffold empty:

| file | covers |
|---|---|
| `docs/RUNNERS.md` | runners this cycle and every prior cycle, by CA, with what drove each |
| `docs/SECTORS.md` | NFTs, gaming, metaverse, DeFi, AI and utility tokens |
| `docs/NEWSFLOW.md` | crypto news sources, insider flow, how narratives propagate |
| `docs/NEW_CHAINS.md` | new chains and how to get in early (Arc launched 2026-09-16 — Circle L1, USDC gas, PoA, institutional validators, no memecoin venue) |
| `docs/UPCOMING.md` | large upcoming on-chain projects |

## X / Grok access — priced, not bought

`X_API.md` (2026-09-07) correctly rules out **continuous** monitoring: the
cheapest useful configuration costs roughly twice Frank's bankroll per month.
**That verdict stands for real-time. It does not apply to a bounded historical
pull.** Via xAI X Search: **$5 per 1,000 posts, $10 per 1,000 profiles**, which
makes the flagship backtest ~$65 at the core sample and ~$361 at full size.
⚠️ **Pricing changes 2026-09-21 12:00 PT** — before then it is $5 per 1,000
*calls*, which is materially cheaper for bulk history.

## ⛔ The backlog is the promise

`docs/BACKLOG.md` holds **every commitment made to Frank, with a status of
SHIPPED / IN PROGRESS / BLOCKED / NOT STARTED and verification evidence on each**.
⭐ **Append-only for commitments; nothing leaves NOT STARTED without evidence of
what was OBSERVED, not what was written.** There is no "designed" or "specced" —
those are NOT STARTED. **Read it at the start of every session.**

⚠️ **It exposed a pattern worth keeping in mind:** `chainfields` is imported only
by `paperv3`, `devwallet` by nothing at all, and `paperv3` is scheduled by
nothing. **A module that only runs when called by hand has not shipped**, and
passing tests are not evidence that it is in the system.

⛔⛔ **Audited 2026-09-19: 13 of the 48 rows marked SHIPPED were not.** 11 run
unattended and write files **no page reads** (market, clusters, crossing depth,
v3, holders, `dashboard.html`); 2 are hand-run only. They are IN PROGRESS now.
**The test for "shipped" is: it runs unattended AND its output reaches the site
or Discord.** Before marking anything SHIPPED, name the page or message it
reaches. The worst case: `exit_depth_at_crossing` lands on every claim and the
site's crossings panel ignores it, so production still shows 0 verifiable.

## Session protocol

⛔ **This repo has one session. Everything routes through it.** Do not start a
second window for crypto-intel work — context is the asset here, and the
findings in this file were expensive to produce.

**Working style Frank has asked for:** be direct, lead with corrections, own
mistakes without softening, and never present a manual workaround as a
deliverable. The goal is something **robust and genuinely novel**, not an
indicator.

**The deliverable is a site**, not chat output: enter a CA, get the analysis,
plus live market information. ⭐ **From 2026-09-19 its centre is the tracked
universe** (Frank: *"all coins over $1M market cap tracked and the top trending
ones always visible"*): trending on top, narratives read off the universe, the
launch-side sections below the fold. `docs/CONSOLIDATION_PLAN.md` §8. Design toward one analyzer with two triggers —
`analyze(CA) -> report`, called both by the automatic crossing detector and by
Frank pasting an address. `check.py` already has that shape.
