# crypto-intel

**Handoff file. Read this first, then the two or three `docs/` files your task
touches. Do not re-derive what is written here.**

Last updated 2026-09-17. ⚠️ **Keep this current. It is the handoff, not a
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
| paper v1 record | 9 wins / 76 measured closes = **11.84%** [6.36, 21.00] | `paper.summary()` |
| ⭐ median holders, our own "winners" | **9** (54% under 10) | `docs/TRUSTED_FIELDS.md` §1 |
| median holders, Jupiter-TRADEABLE | **1,350** | same |
| median holders, Jupiter-TOTAL_LOSS | **3** | same |
| paper ledger, re-derived 2026-09-17 | 86 closes, **−$2,495** by mult / **−$4,168** realizable | `docs/LIQUIDITY.md` §8 |

⛔ **Never quote the 2.10% graduation rate.** It is 397/18,920 computed on
**reported liquidity** — the field measured overstating by a median 781x. Our
clean figure is 0.22%, which agrees with Kamat's 0.198%. **Any lift ever quoted
against 2.10% needs recomputing.**

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
   $86.5B FDV against $0.0002 of real sellable depth.
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
12. ⚠️ **Any script hitting a Cloudflare-fronted API must set a `User-Agent`.**
    Python's default `Python-urllib/3.x` is blocked with a bare `403 error code:
    1010`, which looks exactly like an auth failure and is not. `sources.py:12`
    does this correctly; copy it. This has bitten twice.

---

## Architecture: what runs where

| component | what it does | state |
|---|---|---|
| `collect.py` | hourly staged collector: scan, sweep, watchlist, 1/6/24/168h | ⛔ **dead since 2026-09-15 05:07:59 UTC** |
| GitHub Actions `collect.yml` | same, hosted | ⛔ dead since 2026-09-12 — free-tier minutes exhausted |
| Claude desktop task | same, on the host | ⛔ dead since the 9/15 reboot — sandbox lost its drive mount |
| `site/api/helius.mjs` on Vercel | Helius webhook receiver → Supabase → Discord | ✅ **deployed and answering**, but watching 0 addresses |
| `data/dashboard.html` | static phone-first dashboard, built by `dashboard.py` | builds fine; not in the hourly stage list, so it goes stale silently |

**State store is git.** `data/` is committed after every run. Supabase is a
write-only mirror (no SELECT grant), so it cannot serve as state.

**Live deployment:** `https://crypto-intel-one-eta.vercel.app` —
`/api/helius` is the receiver. Webhook `75056f75-c129-4f43-b686-0f369f8fa669`
is `active: true`, `transactionTypes: ["ANY"]`, **`accountAddresses: []`**.
⛔ **That empty list is why whale alerts have never fired.**

### Current blockers, in order

1. ⛔ **`onchain_reserves.exit_depth()` is unreliable** — 5 of 6 reads failed on
   2026-09-17 (`UNRELIABLE READ: scan missed the real vault`, `no USD price for
   quote mint`). **Everything that verifies a number depends on this.** Highest
   leverage fix in the repo.
2. ⛔ **No collector is running.** Restore it (see `docs/TRACKER_SCOPING.md` §5a
   — Windows Task Scheduler calling `collect.py` directly; **`CRYPTO_ORIGIN=
   scheduled` must be set** or every beat logs as `manual` and is never counted).
3. ⚠️ **GitHub Actions billing** is Frank's to clear. The 2026-09-07 pacing fix
   (`CRYPTO_HTTP_PACE_S` 0.05 → 1.0, correct and not to be reverted) took runs
   from 2.6 to 9.9 minutes, i.e. 1,872 → 7,128 min/month against a 2,000-minute
   free allowance. ~$31/mo to resume, or $0 if the repo goes public.

---

## Map of the repo

**Start here for a task about…**

| topic | file |
|---|---|
| ⭐ **the flagship experiment** — pre-launch social signal | `docs/PRELAUNCH_SIGNAL.md` |
| ⭐ **liquidity: what to trust, and the plan to replace `liq`** | `docs/LIQUIDITY.md` |
| ⭐ **holders, mcap, volume, bundles — all from chain** | `docs/TRUSTED_FIELDS.md` |
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

⭐ **Existing credentials — checked 2026-09-17, do not re-ask.** `crypto-intel/.env`
has `HELIUS_API_KEY`, `BIRDEYE_API_KEY` (dies after ~7 calls), `ALCHEMY_API_KEY`,
`ETHERSCAN_API_KEY`, `CRYPTOPANIC_API_TOKEN`, Supabase. **`dispatch-workspace/.env`
has a full `TWITTER_*` set and `XAI_API_KEY`** — the X bearer token returns
**`402 credits depleted`, not `401`**, so an X developer account exists and is
authenticated. `XAI_API_KEY` returns `400 Incorrect API key`. `~/.openclaw` has a
Brave Search key. ⛔ **Grep every project `.env`, not just this one.**

**Key modules:** `collect.py` (orchestrator, `STAGES`/`staged_commands()`) ·
`journal.py` (append-only store; `record()` is a **field whitelist** — a field
not added there does not exist) · `paper.py` / `paperv2.py` (simulation ledgers)
· `check.py` (one CA in, one verdict out — the model for the analyzer) ·
`detector.py` (D1/D2) · `onchain_reserves.py` (quote-side depth) ·
`liveness.py` (origin tagging; `UNATTENDED = ("runner","scheduled")`) ·
`dashboard.py` · `sources.py` (all HTTP; sets the UA correctly).

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
python test_stages.py                                     # SKILL.md must match staged_commands()
gh run list --workflow=collect.yml --limit 10             # runner state
```

**Liveness check that actually means something:** newest `ts` in
`data/observations/`, or `last_unattended_at` in `data/liveness.json`. **A task
firing is not the same as a pass running** — the desktop task fired hourly for
two days while collecting nothing.

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

⛔ **Socials capture (commit `ce0d33a`) is forward-only and no collector is
running.** Every hour without one is sample that cannot be bought back at any
price. **Restoring collection outranks every purchase decision on the board** —
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

## Session protocol

⛔ **This repo has one session. Everything routes through it.** Do not start a
second window for crypto-intel work — context is the asset here, and the
findings in this file were expensive to produce.

**Working style Frank has asked for:** be direct, lead with corrections, own
mistakes without softening, and never present a manual workaround as a
deliverable. The goal is something **robust and genuinely novel**, not an
indicator.

**The deliverable is a site**, not chat output: enter a CA, get the analysis,
plus live market information. Design toward one analyzer with two triggers —
`analyze(CA) -> report`, called both by the automatic crossing detector and by
Frank pasting an address. `check.py` already has that shape.
