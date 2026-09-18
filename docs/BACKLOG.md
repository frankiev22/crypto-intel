# BACKLOG — every commitment, one list

**⭐ Two rules for this file:**

1. **It is APPEND-ONLY for commitments.** An item is never deleted. If it turns
   out to be a bad idea, it is marked `DROPPED` **with the reason**, and stays.
2. ⛔ **Nothing leaves NOT STARTED without verification evidence.** A SHA alone
   is not evidence — the row must say what was *observed*, not what was written.

**⛔ Review this at the start of every session.** It is the first file after
`CLAUDE.md`.

**Status is one of: `SHIPPED` · `IN PROGRESS` · `BLOCKED` · `NOT STARTED`.**
⛔ **There is no "designed", "specced", "ready" or "written up". Those are
NOT STARTED.** A design document is not a shipped feature; several rows below
have a doc and a spec and are still NOT STARTED, which is the point.

**Assembled 2026-09-18** from the full session history and `CLAUDE.md`.

---

## A. Data integrity

| # | item | status | evidence |
|---|---|---|---|
| A1 | **Trusted liquidity via Jupiter round-trip** — `chainfields.round_trip()`, buy $100 and sell back exactly what it returned | ✅ **SHIPPED** `8aa2587`, `cc26650` | Run live on 18 contracts; separated 8 tradeable from 126 unexitable in the old "wins". `docs/LIQUIDITY.md` |
| A2 | **Holder count from chain** — deduped by owner, `truncated` flag, unknown is `None` | ✅ **SHIPPED** `2b85aa4` | Live: ROCK 1,466 · WOFI 43 · BONK 24,916 (truncated). Median 1,350 TRADEABLE vs 3 TOTAL_LOSS |
| A3 | **Market cap / FDV from chain** — `chainfields.supply()`, `market_cap()` off the round-trip price | ✅ **SHIPPED** `8aa2587` | `test_chainfields.py`; live values in `docs/TRUSTED_FIELDS.md` |
| A4 | ⛔ **Replace the 781x-overstating `liq` field at EVERY call site** | 🟡 **IN PROGRESS — 1 of 4 call sites** | ⛔ **Verified 2026-09-18 and it is worse than I first wrote here.** `chainfields` is imported by **`paperv3.py` and its own test, and nothing else**. `check.py`, `scanner.py`, `track.py` and `dashboard.py` imported it **zero** times. ✅ **`check.py` migrated 2026-09-18** — the realizable round trip now runs BEFORE the refusal gate and a live route overrides a failed reserve read. ⬜ **`scanner.py`, `track.py`, `dashboard.py` still not migrated** (21/7/6 `liq` reads). ⚠️ **Those three are the per-row path and CANNOT take a Jupiter call per row** — chainfields caps at 55/min. They need a different design, not a copy of the check.py change |
| A5 | **Score band deleted from the v1 entry gate** | ✅ **SHIPPED** `a55f405` | `paper.qualifies()` no longer reads a score; 100-grade token now passes. `test_scoreband.py` 25 checks + negative control that fails when the band is smuggled back |
| A6 | **Pool truncation: stop discarding, carry forward** | ✅ **SHIPPED** `a1cbca9` | Live: pass 1 truncated 7/82 and carried 75; pass 2 loaded them, deduped 20, processed owed first |
| A7 | **Permanent coverage recording** — `pools_seen`/`pools_processed` every pass + alarm | ✅ **SHIPPED** `a1cbca9`, fixed `24cc464` | `test_discipline.py` asserts both present even at 100%; `COVERAGE ALARM` prints on mismatch. ⛔ **The alarm shipped with a false positive and its own first live run caught it** (run `35356362447`, 14:29Z): `processed 80 of 83 pools (100.0%)` with `budget_hit` false — a contradiction in one line. `pools_processed` was reading `enriched` (pools that produced a **row**); three pools were reached and produced none. Now `LAST_SCAN["reached"]`, taken from the loop index **after** both break checks, since a pass stopping at `i` has not reached pool `i`. Enrichment shortfall kept separately as `pools_enriched`/`pools_failed`. 58 checks incl. the live case as a fixture |
| A8 | **Output-assertion discipline as a standing rule** | ✅ **SHIPPED** `a1cbca9` | `docs/ENGINEERING_DISCIPLINE.md`, CLAUDE.md standing rule 16, `test_discipline.py` 50 checks |
| A9 | **Liveness counts ROWS, not beats** | ✅ **SHIPPED** `a1cbca9` | Two clocks; new `empty` verdict distinct from `stale`. Three boundary bugs found and locked in as tests |
| A10 | ⛔ **Whitelist guard so a sixth field cannot silently drop** | ✅ **SHIPPED** `24cc464` | ⛔ **The BLOCKED status was right, and the gap was worse than "unverified".** `LAST_WHITELIST_DROP` was written by `journal.py` and read by **`test_whitelist.py` and nothing else** — while the comment beside it claimed *"printed by collect.py"*, which never referenced it. **The guard built to stop a sixth silent drop reported only to a test, so it could not have stopped number six either.** Also `record()` cleared it on every call, so a batched pass kept only the last batch's drops — a total wrong in the quiet direction. Now: `PASS_WHITELIST_DROP` accumulates per pass, `collect.py` prints a **WHITELIST ALARM** and writes it to `GITHUB_STEP_SUMMARY`. `test_whitelist.py` asserts the alarm reaches the runtime and that the pass tally survives two `record()` calls |
| A17 | ⛔ **The `empty` verdict was computed and shown to nobody** | ✅ **SHIPPED** | ⛔ **Found by running `python liveness.py`, which crashed with a `TypeError` on `None`** — the health tool itself, down, the moment a component beat without being declared. Fixing that exposed the larger bug: `status()` gained the `empty` verdict on 2026-09-18 — *fires on time, produces nothing*, the entire point of A9 — and **`line()`, `check()` and the `__main__` exit code all still listed the four old verdicts**. So an `empty` component was invisible in the daily line, emitted no finding, and left the exit code green. **The `journal.record()` whitelist bug in a second place on the same day: computing and surfacing are two steps, and A9 shipped only the first.** Now in all three, plus the undeclared age it was throwing away (`paperv3.open`/`close`, 1.0h). `test_discipline.py` 58 → 65 checks |
| A18 | ⛔ **A hosted runner was being recorded as "unattended" even when I pressed the button** | ✅ **SHIPPED** | `liveness.origin()` returned `"runner"` for every Actions run, so a `workflow_dispatch` recorded identically to a cron fire — **and C3, "fresh rows from a run nobody triggered", was therefore not answerable from the journal at all.** It had to be read off `gh run list` and correlated by timestamp, which is standing rule 16 exactly. It also flattered us in the direction we were already wrong: **87% of all passes were manual.** Now `scheduled` for cron, `dispatch` for a button press, and `dispatch` is **not** in `UNATTENDED`. `liveness.unattended_rows()` answers the question from the registry and `python liveness.py` prints it. ⚠️ **Pre-2026-09-18 `runner` rows are a mix and cannot be re-derived** — the tool says so on the line itself. 6 origin cases + 2 query cases in `test_discipline.py` |
| A19 | ⚠️ **The workflow printed the Python version and called it an assertion** | ✅ **SHIPPED** | The `Python` step ran `python3 -VV` with a comment claiming it *"keeps a runner image change loud instead of silent"*. It passes on any Python 3 ever shipped. ⚠️ **This matters on a date:** GitHub notices on every run that **`ubuntu-latest` migrates to Ubuntu 26 from 2026-10-19**. Now asserts a **3.9 floor** — a floor, not a pin, because pinning would break the collector on the very migration the check exists to survive. ⭐ **Verified by extracting the step from the YAML and running it both ways:** exit 0 at the floor, exit 1 with a `::error::` annotation below it |
| A11 | **Phantom-crossing verification at $1M** | ✅ **SHIPPED** (pre-session) | 25.4% [22.3, 28.8] pass rate, n=696, `docs/TRACKER_SCOPING.md` §2 |
| A12 | **Symbols that render as another token** (bidi + homoglyph) | ✅ **SHIPPED** `902bd43` | 112 bidi + 48 mixed-script contracts found; `dashboard.safe_sym()`; verified zero bidi chars in the built `data/dashboard.html`. `docs/SYMBOL_ATTACKS.md` |
| A14 | ⛔ **The test suite was writing into `data/`** | ✅ **SHIPPED** `a6ac74b` | ⛔ **Found by building the runner, not by suspecting it.** A full suite run appended **158 rows** to `data/liveness/2026-09.jsonl` and 3 findings — all `origin: manual`, `n=1`, from `test_paper`/`test_paperv3`/`test_labels`/`test_whitelist`/`test_safeload`. `liveness` is what answers *"is the collector alive"*, so the suite was writing into the health signal it checks — standing rules 13/14, the instrument changing what it measures. `testsandbox.activate()` redirects 16 modules' data paths; the rows were discarded, not committed (they never entered the record, and all 158 fell inside the 14 minutes of suite runs). Copy in the session scratchpad |
| A15 | ⭐ **One command that runs every suite and proves it touched nothing** | ✅ **SHIPPED** `a6ac74b` | `python run_tests.py`. There was no single command before, so *"the suite passes"* was never a fact anybody had checked. It hashes every file under `data/` before and after and fails on a single changed byte — an assertion on the **output**, not on whether a suite remembered to sandbox itself. ⭐ **Verified both directions:** a canary suite writing one byte into `data/` makes it exit **1**; removed, it exits **0** and reports `data/` byte-identical. Current: **17/17 suites, 463 checks** |
| A16 | ⭐ **The backlog's own evidence is machine-checked** | ✅ **SHIPPED** | ⛔ **Ten minutes after writing two SHAs into this file I rebased to push, git rewrote both commits, and the rows cited SHAs that exist in nobody's repository.** A citation that does not resolve is not weaker evidence, it is none — and it fails silently, because the row still reads SHIPPED. `test_backlog.py` now asserts every cited SHA is an **ancestor of HEAD** (a dangling pre-rebase commit satisfies `cat-file` and is garbage in a fortnight), that every status is one of the four, that no status says *designed / specced / ready*, and that no SHIPPED row rests on a bare SHA. ⭐ **Verified by planting both orphan types** — a dangling real commit and an unknown hex string — and confirming it exits **1** and names both. ⚠️ It checks the citation resolves; it cannot check the commit does what the row claims. That is what reading the evidence column is for |
| A13 | ⛔ **`onchain_reserves.exit_depth()` is unreliable AND was causing FALSE REFUSALS** | 🟡 **IN PROGRESS — contained in `check.py`, still wrong everywhere else** | ⛔ **Found by running on a real CA 2026-09-18:** `check.py` refused OpenClaw as *"dead or drained — $0 on the quote side"* while Jupiter round-tripped the same token at **0.77%** in the same minute. The refusal ran before anything trusted was consulted. **Now the live route overrides a failed reserve read, one-directionally** — a route can rescue a bad scan, never suppress a refusal when both agree. `test_check.py` 21 checks incl. the false-refusal fixture. **`exit_depth` is still on the scanner/track hot path and still wrong** |

## B. Detection

| # | item | status | evidence |
|---|---|---|---|
| B1 | **Dev wallet history + funding-graph traversal** | 🟡 **BLOCKED on a labelled sample** | `devwallet.py` SHIPPED `31c5fd4`, run live on 4 CAs. ⛔ **On n=4 it did NOT separate good from bad** — both bad tokens got the same verdict. Needs serial launchers and n≥30/arm. ⛔ **Also: `devwallet` is imported by NOTHING — not even a test.** It is a module you can run by hand, not a part of the system |
| B2 | **Wallet age distribution of early buyers** | 🔴 **NOT STARTED** | `activity_before()` exists (SHIPPED, after a walk gave WOFI age **−0.1h**). The distribution across first buyers was never computed |
| B3 | **First-buyer shared-funding analysis** | 🟡 **IN PROGRESS** | Runs; found TPAID 4 buyers / 2 funders. ⛔ **`buyer_funding_overlap()` discards the `exact` flag, so `SHARED=True` is a candidate, not a finding.** Fix before quoting |
| B4 | **LP burned vs locked, unlock date, % of supply** | 🟡 **IN PROGRESS** | `lp_detail()` SHIPPED; returns lockers/providers/liquidity. ⚠️ **`lpLockedPct` was 100 for all 4 tested — discriminates nothing.** Unlock DATE and % of supply not implemented |
| B5 | **Volume-manipulation detection with thresholds** | 🔴 **NOT STARTED** | `docs/VOLUME_INTEGRITY.md` written with pre-committed thresholds. **No code.** A doc is not a detector |
| B6 | **Bundle detection benchmarked against existing tools** | 🔴 **NOT STARTED** | `docs/EXISTING_TOOLS.md` surveyed them and found **RugCheck beats our detector, free and keyless**. The benchmark itself was never run |
| B7 | **Holder-count quality gate** | ✅ **SHIPPED** `902bd43` | In `paperv3.qualifies()` as `holders >= 100`. ⭐ Earned itself live: refused a USDC impersonator that was TRADEABLE at 0.02% with 10 holders |
| B8 | **Bond-as-threshold + the non-curve equivalent** | 🔴 **NOT STARTED** | Attention threshold discussed; graduation per chain never defined for non-curve venues |
| B9 | **Un-kill list, each killer marked as surviving correction or not** | ✅ **SHIPPED** `46f9543` | `docs/UNKILL.md`. Honest finding: **the labels were poisoned (94.2%), so the negatives don't stand either** |

## C. Infrastructure

| # | item | status | evidence |
|---|---|---|---|
| C1 | **Repo public** | ✅ **SHIPPED** `13b3255` | `{"isPrivate":false,"visibility":"PUBLIC"}`. Full git-history secret audit run first; LICENSE + SECURITY.md added |
| C2 | **Actions collector running, free** | ✅ **SHIPPED** `c82411f` | `billable UBUNTU total_ms 0` against 533,000ms and 602,000ms of runtime. Scheduled run fired unaided 11:54:15Z and collected a full pass |
| C3 | ⛔ **Fresh rows from a run NOBODY triggered** | 🟡 **IN PROGRESS** | The 11:54Z scheduled run collected but **lost its rows** to a commit conflict I caused. Conflict fixed and verified under the real condition (`c82411f`). **Waiting on the next scheduled run. Today's committed rows are still from manual dispatches.** |
| C4 | ⛔ **The hourly cron has NEVER been hourly** | 🟡 **IN PROGRESS — mitigation shipped, unproven** | **Measured over 100 scheduled runs, 09-03→09-18: median gap 3.24h, and 0 of 99 gaps were ≤1.5h.** Before the billing block 3.23h, after 3.81h — **the failures did not cause it.** ⛔ **Consequence: only 91 of 691 passes were scheduled. 87% were manual.** At ~7 unattended passes/day vs ~2,300 new pairs/day the outcome queue gets ~37% of needed capacity. **Mitigation `bd08431+`: cron widened to 4×/hour at :07/:22/:37/:52, off the contended :00. This is an EXPERIMENT — see the pre-commit below.** |
| C4a | **Pre-committed measurement for the C4 cron experiment** | 🔴 **NOT STARTED — measure after 48h** | ⛔ **Written before the result, so it cannot be moved to fit one.** Baseline: **median gap 3.24h, n=99**. ⭐ **Success = median gap ≤ 1.5h over ≥30 consecutive scheduled runs.** Partial = 1.5–2.5h (keep, note it). **Failure = >2.5h → the cron approach is exhausted and the answer is C5's always-on box, not more cron lines.** ⚠️ **Do not re-tune the minutes and re-measure — that is fitting the schedule to the data.** |
| C5 | **`programSubscribe` crossing detector** | 🔴 **NOT STARTED** | Fully costed: 56 notif/sec, 31 KB/s → 1.64M credits/mo. Free tier fails 1.6x; Developer $49/mo fits at 16%. Needs an always-on box (~$4–6 VPS). **Costed is not built** |
| C6 | **`chainId` on every row so Arc is config, not a rewrite** | 🔴 **NOT STARTED** | Discussed as "chains as config". No schema change made |
| C7 | **Graduation thresholds per chain** | 🔴 **NOT STARTED** | Solana-only today |
| C8 | ⛔ **Webhook receiver watching actual addresses** | 🟡 **BLOCKED** | Deployed and answering at `/api/helius`, but **`accountAddresses: []`** — watching nothing. **This is why whale alerts have never fired** |
| C9 | **Windows Task Scheduler** | ⛔ **DROPPED** `479e9cc` | Frank reversed it: *"didn't we decide windows task scheduler wasn't the right move? Delete all of that."* Task and launcher removed. **Do not reintroduce** |

## D. Analysis

| # | item | status | evidence |
|---|---|---|---|
| D1 | **CA analyzer at a 30-second budget** | 🔴 **NOT STARTED** | `check.py` has the right shape (`analyze(CA) -> report`) but was never held to a time budget or wired to `chainfields` |
| D2 | **Paper trader on real quotes** | 🟡 **IN PROGRESS** | `paperv3.py` + 71 tests SHIPPED `902bd43`, run live `d341d3b`. ⛔ **Nothing schedules it — `collect.py` does not call it, so the ledger has zero rows.** v1/v2 quarantined `4676ce3` |
| D3 | **Pre-launch social signal backtest** | 🟡 **BLOCKED on X credits** | The flagship experiment. ~$65 at core sample via xAI X Search. **Blocked: X bearer returns 402 credits depleted, `XAI_API_KEY` returns 400 invalid** |
| D4 | **Re-verify the 165 "wins" against real liquidity** | ✅ **SHIPPED** `71abd83` | Of 141 checked, **8 tradeable, 126 not exitable**. The wins did not survive |
| D5 | **Outcome-queue expiry measured** | ✅ **SHIPPED** `4949874` | 21% of due checks age out. Slice fix worked (24h: 19.1%→5.8%); the rest is downtime. ⛔ **CORRECTED 2026-09-18: the 5.8% "healthy period" figure was achieved on days with 38–204 passes of which only 6–8 were scheduled — it was carried by MANUAL runs, not by the collector.** Unattended-only capacity is ~37% of arrivals. See C4 |

## E. Knowledge

| # | item | status | evidence |
|---|---|---|---|
| E1 | **Crypto history corpus** | 🟡 **IN PROGRESS** | `docs/CRYPTO_HISTORY.md` SHIPPED, organised by recurring mechanism. ⚠️ **Zcash and XRP narrative depth not written** — the "recognise a reference before others" use case is unserved |
| E2 | **Glossary** | ✅ **SHIPPED** | `docs/GLOSSARY.md`, 177 lines, 54 entries, alphabetical. Carries the eight numbers worth remembering, incl. graduation at **85 SOL / 410.8 SOL FDV ≈ $40,994** — ⛔ **not the $69,000 everyone quotes**, and the SOL figure is the one to read because the USD drifts |
| E3 | **Rules file** | ✅ **SHIPPED** | `docs/RULES.md` (§B buyer, §C creator, §O observations) + root `RULES.md` |
| E4 | **Existing-tracker survey** | ✅ **SHIPPED** `9519f4a` | `docs/EXISTING_TOOLS.md`: bubblemaps, rugcheck, solsniffer, GMGN, TrenchRadar. **RugCheck beats ours** |
| E5 | **Grok / X access decision** | 🟡 **BLOCKED on Frank** | Priced. ⛔ **Never sign up — his call alone.** See the key list below |
| E6 | `docs/RUNNERS.md`, `SECTORS.md`, `NEWSFLOW.md`, `NEW_CHAINS.md`, `UPCOMING.md` | 🔴 **NOT STARTED** | Declared in CLAUDE.md as "create on first substantive finding, do not scaffold empty" |

---

## Scoreboard

| status | count |
|---|---:|
| ✅ SHIPPED | **18** |
| 🟡 IN PROGRESS / BLOCKED | **9** |
| 🔴 NOT STARTED | **12** |
| ⛔ DROPPED | **1** |

⚠️ **A4 moved from IN PROGRESS to NOT STARTED while writing this file**, because
I checked instead of remembering. That is the file working.

### ⛔ The pattern this list exposes

**Three of the most-discussed modules are wired to nothing.** `chainfields`
(the trusted-field source) is used only by `paperv3`; `devwallet` is imported by
no file at all; `paperv3` itself is scheduled by nothing. **We have been
building components and counting them as done because the tests pass.**

⚠️ That is standing rule 16 applied one level up: *a module that runs when you
call it by hand, and that nothing calls, has not shipped.* **`test_*.py` passing
is not evidence that a component is in the system.** Rows A4, B1 and D2 are all
the same failure.

⭐ **The three that unblock the most:** **A4** (the poisoned field is still read at
four call sites), **C3** (an unattended row landing), **D2** (nothing schedules
paperv3, so the one asset with a route to being worth money records nothing).
