# Index — every document in the repo, one line each

**2026-09-19.** Consolidation plan phase 0 (`docs/CONSOLIDATION_PLAN.md` §6): an
index now, moves later, and only behind `test_references.py`. Start with
`CLAUDE.md`, then `docs/BACKLOG.md`. Dates are each file's last commit.

⚠️ Several root files predate the corrections recorded in CLAUDE.md. **A number
in an older file is not current until CLAUDE.md or the backlog repeats it.**

## Read first

| file | what | last |
|---|---|---|
| `CLAUDE.md` | the handoff: numbers, standing rules, architecture | 09-18 |
| `docs/BACKLOG.md` | every commitment and its status; the SHIPPED-row audit | 09-18 |
| `docs/UNIVERSE.md` | the tracked universe: size, cost, source, pre-committed gate | 09-18 |
| `docs/CONSOLIDATION_PLAN.md` | one place: what is scattered, what retires, Frank's decisions | 09-18 |
| `docs/ENGINEERING_DISCIPLINE.md` | verify the output, never the execution | 09-18 |

## The site and its data

| file | what | last |
|---|---|---|
| `site/README.md` | the hosted dashboard, and what it needs from the pipeline | 09-18 |
| `docs/MARKET_DATA.md` | every `data/market/` file and rendering rule | 09-18 |

## Data integrity and liquidity

| file | what | last |
|---|---|---|
| `docs/LIQUIDITY.md` | a liquidity number we can trust; the plan to replace `liq` | 09-17 |
| `docs/TRUSTED_FIELDS.md` | holders, mcap, volume from chain | 09-17 |
| `CONTAMINATION.md` | the 781x reported-liquidity finding | 09-07 |
| `TEMPLATE_ATTACK.md` | the template attack, in aggregate | 09-05 |
| `EXIT_DEPTH.md` | reported liquidity is not exit liquidity | 09-04 |
| `docs/SYMBOL_ATTACKS.md` | symbols that render as a different token | 09-18 |
| `docs/SAMPLING_BIAS.md` | scanner truncation, and an overstatement corrected | 09-18 |
| `docs/VOLUME_INTEGRITY.md` | volume manipulation, pre-committed thresholds (no code yet) | 09-17 |
| `DUAL_SOURCE.md` | reading both price sources, cost measured first | 09-06 |
| `VENUE.md` | bonding curve vs AMM | 09-06 |
| `TRAJECTORY.md` | liquidity trajectory: RETRACTED as a signal | 09-05 |

## Coverage and collection

| file | what | last |
|---|---|---|
| `COVERAGE.md` | how much of the launch stream we see; the costed good version | 09-18 |
| `OUTCOMES.md` | the outcome-recording gap, diagnosed | 09-06 |
| `ONCHAIN_COST.md` | which data tier, and what it costs | 09-07 |
| `docs/TRACKER_SCOPING.md` | the 1M tracker, crossing rates, real time (§5c supersedes §5b) | 09-17 |

## Strategy, paper trading and pre-commitments

| file | what | last |
|---|---|---|
| `docs/PAPER_V3.md` | paper trader v3, fills on real quotes | 09-18 |
| `PRECOMMIT_paper_v3.md` | v3 rules; v1/v2 quarantine (§2) | 09-18 |
| `PRECOMMIT_rule_v2.md` | RULE_V2 | 09-11 |
| `PRECOMMIT_late_closes.md` | late closes | 09-14 |
| `PRECOMMIT_surface_grade.md` | surfaced grade | 09-15 |
| `PRECOMMIT_universe_v1.md` | launch-side bands (graduated/approaching) — not the $1M universe | 09-10 |
| `PRECOMMIT-2026-09-07.md` | the Helius re-test | 09-07 |
| `PRECOMMIT-SCOREBANDS.md` | score-100 band | 09-07 |
| `PRECOMMIT-VENUE.md` | is D1 a fraud detector or a fluxbeam detector | 09-07 |
| `PAPER_LOG.md` | the forward paper log (v1, quarantined) | 09-06 |
| `GRADUATION.md` | graduation prediction fails; our 0.22% base rate | 09-06 |
| `FRAUD_DETECTION.md` | fraud detection rather than prediction | 09-11 |
| `FEASIBILITY.md` | could the fraud check be a product | 09-07 |
| `docs/UNKILL.md` | every killed strategy and whether its killer survives | 09-17 |
| `docs/PRELAUNCH_SIGNAL.md` | the flagship experiment's backtest design | 09-18 |
| `docs/DEV_WALLET.md` | dev wallet history, funding graphs, LP | 09-17 |
| `docs/EXISTING_TOOLS.md` | what exists already; RugCheck beats ours | 09-17 |

## Decisions and purchases (Frank's call)

| file | what | last |
|---|---|---|
| `docs/DECISION_X_DATA.md` | buy X data before 2026-09-21, or not | 09-17 |
| `X_API.md` | X/Twitter API, priced, not signed up for | 09-07 |

## Knowledge corpus

| file | what | last |
|---|---|---|
| `docs/GLOSSARY.md` | terms and the numbers worth remembering | 09-17 |
| `docs/CHAINS.md` | chains and venues | 09-17 |
| `docs/TOKEN_MECHANICS.md` | tax tokens, reflections | 09-17 |
| `docs/CREATOR_PLAYBOOK.md` | how a launch works, what it pays | 09-17 |
| `docs/TRADING_PLAYBOOK.md` | the buyer's playbook | 09-17 |
| `docs/TRENCHES_REFERENCE.md` | long-form reference, open questions | 09-17 |
| `docs/CRYPTO_HISTORY.md` | history by recurring mechanism | 09-17 |
| `docs/RULES.md` | memecoin rules and observations (§B, §C, §O) | 09-17 |
| `RULES.md` | standing reporting rules (root — a different file) | 09-07 |

## Superseded by `docs/BACKLOG.md` (plan §2 item 21 — kept, not deleted)

| file | what | last |
|---|---|---|
| `GAPS.md` | what stands between this and real money | 09-15 |
| `OPEN_ITEMS.md` | open items | 09-06 |
| `QUESTIONS.md` | question queue | 09-07 |
| `SCOREBOARD.md` | ⚠️ pre-retraction scoring numbers | 08-28 |

## Repo housekeeping

| file | what | last |
|---|---|---|
| `README.md` | ⚠️ describes the 08-20 "regime dashboard"; to be cut to ten lines (plan §2 item 22) | 09-18 |
| `SECURITY.md` | security policy | 09-18 |
