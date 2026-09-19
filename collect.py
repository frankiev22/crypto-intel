"""
The collection loop. Run this on a schedule; it is what actually accumulates
the dataset.

One pass does:
  1. scan new pools on each network
  2. journal EVERY result, passed and rejected
  3. score any older observations that have come due at their horizon
  4. push anything that cleared the bar to Discord

Safe to run repeatedly. Outcome scoring is idempotent, and observations are
append-only so a duplicate scan just adds another time-series point.

    python collect.py                    one pass, solana
    python collect.py solana,base        one pass, several networks
    python collect.py solana loop        keep going every 15 minutes

STAGES. Some runners cap a single command well below what a full pass needs -
the Claude dispatch sandbox kills one at ~178s. A killed pass journals nothing
and reports success, which is the worst failure this system can have.

WHICH RUNNER YOU ARE ON DECIDES WHETHER YOU NEED THIS:

  production - .github/workflows/collect.yml, hourly cron, 15-minute job
    timeout. Runs `collect.py solana` UNSTAGED and should keep doing so; a full
    pass is ~11 minutes at the current 1.0s pacing and fits.

  the sandbox - 178s per command. Pacing went 0.05s -> 1.0s per call on
    2026-09-07, so a stage costs roughly its call count in seconds and the
    bigger stages stopped fitting. That was not noticed for three days: passes
    were SIGKILLed part-way, observations/day fell 2,881 -> 678, and the
    coverage log could only say `suspected_cause: killed - no clean exit`.

    THE FIX IS TO MAKE THE WORK FIT THE WINDOW, not to make the calls faster.
    Pacing to the only published rate limit stands. Instead every staged
    invocation carries a CALL BUDGET, defaulting to CRYPTO_STAGE_CALLS=150
    (~170s at 1.116s/call), and stops CLEANLY when it is spent. Scoring is
    idempotent and journal.pending() re-offers whatever was not reached, so a
    short pass loses nothing - the next invocation resumes.

    python collect.py solana --stage scan        ~105 calls, fits
    python collect.py solana --stage watchlist    ~60 calls, fits
    python collect.py solana --stage paper        ~21 calls, fits
    python collect.py solana --stage 1           budgeted, resumes next run
    python collect.py solana --stage 6           budgeted, resumes next run
    python collect.py solana --stage 24          budgeted, resumes next run
    python collect.py solana --stage 168         budgeted, resumes next run

    --stage outcomes is ~421 calls and will now stop after ~150 rather than be
    killed; run the four horizons as separate invocations to drain them.
    Override with --max-calls N. A short pass records kind="pass_short" with
    complete=false and the exact reason, so an incomplete pass is a FACT in
    data/coverage, never an inference from a stale sentinel.

The journal is append-only and outcome scoring is idempotent, so running the
stages separately is behaviour-identical to one full pass.
"""
import os, sys, time, traceback, datetime as dt
import scanner, journal, track, notify, macro, sources, findings, resolve
# The Claude dispatch sandbox SIGKILLs at ~178s. Stop at 155s, leaving 23s for
# the pass to finish its bookkeeping and write its own short-pass record - a
# budget that ends exactly at the kill is not a budget.
#
# Expressed in SECONDS, not calls. The previous 150-call figure assumed
# 1.116s/call, was never re-measured, and the real per-row cost reached 2.77s -
# so 150 calls was 415s against a 178s cap and every staged command died.
STAGE_SECONDS = float(os.environ.get('CRYPTO_STAGE_SECONDS', '155'))
DEFAULT_STAGE_CALLS = None      # no fixed call count; see STAGE_SECONDS

# THE KILL IS THE FIXED POINT, NOT THE BUDGET.
#
# 2026-09-15: --stage scan was killed at the sandbox cap under a 155s budget.
# The budget was working - it is a deadline with per-call cost measured as it
# runs, not the old 1.116s constant - but a stage does not stop the instant its
# deadline passes. It finishes the row in hand (several calls, plus an on-chain
# authority read the call budget never sees) and then does its bookkeeping.
# Scan has overrun its deadline by up to 28s, and 155 + 28 is past 178. So the
# deadline is derived from the kill, less 1.25x the worst overrun this stage
# has actually recorded, and moves when latency does. --max-seconds, when given,
# is a ceiling the calibration can only lower.
KILL_S = float(os.environ.get("CRYPTO_KILL_S", "178"))
MIN_RESERVE_S = 15.0
MIN_BUDGET_S = 30.0


def _recent_overruns(stage, lookback=20):
    """(ran_for_s - budget_s) for this stage's most recent recorded passes."""
    import glob, json
    paths = sorted(glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                          "data", "coverage", "*.jsonl")))[-4:]
    out = []
    for p in paths:
        try:
            with open(p, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    if r.get("kind") not in ("pass_complete", "pass_short"):
                        continue
                    if str(r.get("stage")) != str(stage):
                        continue
                    b = r.get("budget_s") or (r.get("progress") or {}).get("budget_s")
                    ran = r.get("ran_for_s")
                    if b and ran is not None:
                        out.append(float(ran) - float(b))
        except OSError:
            continue
    return out[-lookback:]


def calibrated_budget(stage, ceiling, overruns=None):
    """(seconds, basis). min(ceiling, KILL_S - reserve), floored at MIN_BUDGET_S."""
    over = _recent_overruns(stage) if overruns is None else list(overruns)
    if over:
        worst = max(over)
        reserve = max(MIN_RESERVE_S, 1.25 * worst)
        why = f"worst overrun {worst:.0f}s in {len(over)} recorded {stage} passes"
    else:
        reserve = MIN_RESERVE_S
        why = f"no recorded {stage} passes yet"
    derived = max(MIN_BUDGET_S, KILL_S - reserve)
    budget = min(float(ceiling), derived)
    return budget, (f"{budget:.0f}s = min(ceiling {float(ceiling):.0f}s, kill "
                    f"{KILL_S:.0f}s - reserve {reserve:.0f}s); {why}")

import watchlist
import news
import paper
import fieldguard
import detector
import liveness
import dashboard
import market

# When this process started - the pass clock market_stage() reads.
_PASS_T0 = time.time()

PASS_SCORE = 70
JOURNAL_BATCH = 10

# THE STAGED COMMAND LIST IS CODE, NOT ONLY A SKILL FILE.
#
# Until 2026-09-15 the hourly task ran scan/1/6/24/168 and nothing else, while
# paper.sweep, paperv2.sweep, the unpriceable labeller and watchlist.sweep were
# called only from one_pass() - the unstaged full pass, which the sandbox kills.
# On the host they never ran. The GitHub runner was the only thing closing
# positions, and when it stopped on 9/12 the paper log stopped with it; liveness
# fired and escalated, and nobody acted. Declared, tested, never invoked.
#
# test_stages.py fails if any liveness component is unreachable from STAGES, or
# if the skill file's commands drift from staged_commands().
STAGES = ("scan", "sweep", "watchlist", "market", "1", "6", "24", "168",
          "graduations", "universe")
STAGED_MAX_SECONDS = 110
# What each stage can fire. Bookkeeping at the end of main() fires on every
# invocation, whatever the stage.
STAGE_FIRES = {
    "scan": {"scan.observations", "fieldguard.check", "paper.open",
             # ⭐ v3 enters in the SAME loop as v1 and v2 - same row, same pass,
             # three filters. A forward log moved into a later stage becomes a
             # retrospective one, and every retrospective finding here has died
             # of leakage.
             "paperv3.open"},
    "sweep": {"paper.sweep", "paper.close", "paperv3.sweep", "paperv3.close"},
    "watchlist": {"watchlist.sweep", "milestone.graduated"},
    "market": {"market.snapshot"},
    "graduations": {"graduations.ledger"},
    "universe": {"universe.members"},
    "1": {"outcome.recorded", "milestone.mcap", "milestone.realizable"},
    "6": {"outcome.recorded", "milestone.mcap", "milestone.realizable"},
    "24": {"outcome.recorded", "milestone.mcap", "milestone.realizable"},
    "168": {"outcome.recorded", "milestone.mcap", "milestone.realizable"},
}
EVERY_INVOCATION_FIRES = {"news.freshness", "detector.drift",
                          "dashboard.build"}
STAGE_STOPS = {}


def staged_commands(net="solana"):
    """The exact commands the scheduled task must run, in order."""
    return [f"CRYPTO_ORIGIN=scheduled python3 collect.py {net} --stage {s} "
            f"--max-seconds {STAGED_MAX_SECONDS}" for s in STAGES]


def scan_stage(networks=("solana",), verbose=True):
    """Discovery, journalling and alerting. The half that cannot be redone
    later: an unobserved launch is gone permanently."""
    total_seen = total_passed = 0
    for net in networks:
        # Journal AS WE GO. Waiting for the loop to finish is what turned a
        # stalled Dexscreener lookup into three consecutive zero-observation
        # passes on 2026-08-30. A batch of 10 bounds the loss to 9 pools and
        # still keeps the Supabase push to one call per batch.
        buf, done = [], [0]

        def _flush(_net=net):
            if buf:
                done[0] += journal.record(list(buf), _net, pass_score=PASS_SCORE)
                buf.clear()

        def _on_row(r):
            buf.append(r)
            if len(buf) >= JOURNAL_BATCH:
                _flush()

        rows = []
        try:
            rows = scanner.scan(net, verbose=verbose, on_row=_on_row)
        except Exception as e:
            print(f"  [{net}] scan failed after {done[0]} journalled: {e}")
        _flush()          # keep the tail, and anything a raise left behind
        n = done[0]
        # `passed` is the recorded series (score, unchanged). What is SENT to a
        # human is `surfaced`: grade, so a live or unverified authority can never
        # go out as a pass. PRECOMMIT_surface_grade.md.
        passed = [r for r in rows if r["score"] >= PASS_SCORE]
        surfaced = [r for r in rows if r.get("grade", 0) >= PASS_SCORE]
        # FIELD GUARD. Three silent-drop bugs in two days - vol_to_liq/vol_burst,
        # the news freshness check, and mint/freeze authority - all the same
        # shape: a field computed and never added to journal.record()'s
        # whitelist, so it was discarded without an error. Non-fatal here,
        # because losing a whole pass is worse than losing a column, but it
        # pings the health lane so it cannot go unnoticed the way those did.
        # `python fieldguard.py` exits non-zero, for CI.
        try:
            if rows:
                _w = max(rows, key=lambda r: sum(1 for v in r.values() if v is not None))
                _ok, _dropped = fieldguard.check(_w)
                liveness.beat("fieldguard.check")
                if not _ok:
                    print(f"  !! FIELD GUARD: {_dropped} computed but not persisted")
                    findings.record(
                        "collector-error", "field-guard",
                        f"{len(_dropped)} computed field(s) are not persisted: "
                        f"{', '.join(_dropped)}",
                        detail=("A field computed and not persisted is a field that "
                                "does not exist. Add them to journal.record()'s "
                                "whitelist, or to fieldguard.TRANSIENT with a reason."))
        except Exception as e:
            print(f"  field guard failed (non-fatal): {e}")

        # What the discovery window actually covered. Recorded every pass,
        # because it cannot be reconstructed afterwards.
        cov = journal.record_coverage(net, sources.LAST_WINDOW, n,
                                      PASS_SCORE, len(passed),
                                      scan=dict(scanner.LAST_SCAN))
        # ⛔ LOUD ON PARTIAL COVERAGE. Silent degradation is the failure mode
        # this project keeps rediscovering: four of the five worst bugs this
        # week were things that ran, reported success, and produced less than
        # they claimed. A pass that looked at 83% of its batch must SAY SO.
        # ⛔ WHITELIST ALARM. journal.record() is a field whitelist and it has
        # silently eaten FIVE fields (vol_to_liq, vol_burst, the news NameError,
        # paper_v2_arm, info.socials). Every one was found by a human noticing an
        # absence, long after the data was unrecoverable. The guard that detects
        # number six existed but reported only to a test, so it could not have
        # stopped number six either. It alarms here now.
        if journal.PASS_WHITELIST_DROP:
            _d = ", ".join(sorted(journal.PASS_WHITELIST_DROP))
            print(f"  ⛔ WHITELIST ALARM [{net}]: computed but NOT PERSISTED: {_d}")
            print(f"     These are gone. Add them to the dict in "
                  f"journal.record(), or to journal.TRANSIENT_ROW_KEYS if they "
                  f"are deliberately transient.")
            _sum = os.environ.get("GITHUB_STEP_SUMMARY")
            if _sum:
                try:
                    nl = chr(10)
                    with open(_sum, "a", encoding="utf-8") as _f:
                        _f.write(nl + "### WHITELIST DROP" + nl
                                 + "`" + _d + "`" + nl
                                 + "Computed and not persisted. "
                                 + "See journal.record()." + nl)
                except Exception:
                    pass

        if cov.get("coverage_alarm"):
            _sc = cov.get("scan_coverage")
            print(f"  ⛔ COVERAGE ALARM [{net}]: reached "
                  f"{cov.get('pools_processed')} of {cov.get('pools_seen')} pools"
                  + (f" ({100.0 * _sc:.1f}%)" if _sc is not None else "")
                  + f" - {cov.get('truncate_reason') or 'reason not recorded'}")
            print(f"     {cov.get('carried_forward') or 0} carried to the next pass"
                  + (f", {cov['carry_dropped']} DROPPED at the carry cap"
                     if cov.get("carry_dropped") else ""))
        if verbose and cov.get("span_s") is not None:
            print(f"  [{net}] discovery window {cov['span_s']:.0f}s of launch "
                  f"stream from {cov['pools_returned']} pools")
        total_seen += n
        total_passed += len(passed)
        if verbose:
            print(f"  [{net}] {n} journalled, {len(passed)} scored {PASS_SCORE}+, "
                  f"{len(surfaced)} surfaced (grade {PASS_SCORE}+, authorities verified)")
        if surfaced:
            # the same token often shows up as several pools; one line each
            seen, uniq = set(), []
            for r in surfaced:
                k = r.get("addr") or r.get("name")
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(r)
            chain = net.replace("-", " ").title()
            noun = "token" if len(uniq) == 1 else "tokens"
            notify.send(
                content=(f"**{len(uniq)} new {chain} {noun}** passed the launch filter\n"
                         f"_Graded {PASS_SCORE}+ of 100 on liquidity, real turnover and "
                         f"buy/sell balance, with mint and freeze authority checked and "
                         f"revoked. This is a screen, not a recommendation._"),
                embeds=[notify.candidate_embed(r) for r in uniq[:8]])
    return total_seen, total_passed


def _stage_stop():
    return sources.over_budget(headroom=2)


def _memo_fetch(fetch):
    """One read per pool per stage, paced.

    v1 and v2 hold many of the same pools - every arm-A position is in both. One
    read serves both ledgers, so they close on the SAME price at the same
    moment instead of on two reads seconds apart, and a staged sweep spends
    roughly half the calls. A lookup that RAISED is not cached and is retried.
    """
    cache = {}

    def f(chain, pair):
        k = (chain, pair)
        if k not in cache:
            cache[k] = fetch(chain, pair)
            sources.pace()
        return cache[k]
    return f


def watchlist_stage(verbose=True):
    """The approach band, re-checked. Its own stage so it runs on the host."""
    try:
        s = watchlist.sweep(sources.dexscreener_pair, verbose=verbose,
                            should_stop=_stage_stop)
        if (s or {}).get("deferred"):
            STAGE_STOPS["watchlist"] = (f"time budget reached with {s['deferred']} "
                                        f"members unchecked")
    except Exception as e:
        print(f"  watchlist sweep failed: {e}")


# ⭐ WHAT IS RUNNING NOW, NOT ONLY WHAT LAUNCHED (2026-09-18). Every stage above
# is about tokens at birth. Frank opens the dashboard to see what is moving
# today, and on the first live snapshot 0 of the top 25 24h gainers had ever
# been in our journal. See market.py.
#
# ⛔ The runner's job timeout is 15 minutes and the longest pass on record took
# 13.6. The round-trip checks are the only slow part, so they shrink as the pass
# ages and stop entirely past MARKET_SOFT_LIMIT_S. The snapshot still runs: a
# row that says "not checked" is honest, and a pass killed by the timeout
# commits nothing at all - including every row the scan already collected.
MARKET_SOFT_LIMIT_S = 10 * 60


def market_stage(verbose=True):
    elapsed = time.time() - _PASS_T0
    verify_s = max(0.0, min(market.VERIFY_SECONDS, MARKET_SOFT_LIMIT_S - elapsed))
    if verify_s < market.VERIFY_SECONDS:
        print(f"  market: round-trip checks cut to {verify_s:.0f}s - "
              f"the pass is already {elapsed:.0f}s old")
    try:
        market.build(verbose=verbose, verify_s=verify_s)
    except Exception as e:
        # Non-fatal, like the dashboard: a broken snapshot must never cost a
        # pass of collection. It beats nothing, so liveness reports it stale.
        print(f"  market snapshot failed (non-fatal): {type(e).__name__}: {e}")


# ⭐ THE TRACKED UNIVERSE AND THE GRADUATION LEDGER run LAST, on whatever the
# pass has left. Both are resumable by construction - the ledger keeps a cursor,
# the universe keeps a gate queue - so a short budget costs latency, never data.
# Past LATE_SOFT_LIMIT_S neither runs at all: the runner's job timeout is 15
# minutes, the longest pass on record took 13.6, and a pass killed by the
# timeout commits nothing - including every row the scan already collected.
LATE_SOFT_LIMIT_S = 11 * 60
# Seconds the universe needs besides its gate: Jupiter's verified list, the
# re-check batch, Dexscreener's theme pages, and CoinGecko every 6 hours.
UNIVERSE_OVERHEAD_S = 90


def graduations_stage(verbose=True):
    import graduations
    left = LATE_SOFT_LIMIT_S - (time.time() - _PASS_T0) - UNIVERSE_OVERHEAD_S
    if sources.seconds_left() is not None:      # a staged run's --max-seconds
        left = min(left, sources.seconds_left() - UNIVERSE_OVERHEAD_S)
    if left <= 10:
        STAGE_STOPS["graduations"] = f"skipped: the pass is {time.time() - _PASS_T0:.0f}s old"
        print(f"  graduations: skipped, {STAGE_STOPS['graduations']}")
        return
    try:
        # ~60% of what is left, up to the ledger's own cap. Measured 2026-09-19:
        # ~64 authority txs an hour at ~0.5s each on the keyless public RPC, so a
        # 3.4h median gap owes ~110s. Backlog and lag are on index.json.
        graduations.build(verbose=verbose, seconds=min(graduations.SECONDS, left * 0.6))
    except Exception as e:
        print(f"  graduation ledger failed (non-fatal): {type(e).__name__}: {e}")


def universe_stage(verbose=True):
    import universe
    left = LATE_SOFT_LIMIT_S - (time.time() - _PASS_T0) - UNIVERSE_OVERHEAD_S
    if sources.seconds_left() is not None:      # a staged run's --max-seconds
        left = min(left, sources.seconds_left() - UNIVERSE_OVERHEAD_S)
    if left <= 0:
        STAGE_STOPS["universe"] = f"skipped: the pass is {time.time() - _PASS_T0:.0f}s old"
        print(f"  universe: skipped, {STAGE_STOPS['universe']}")
        return
    try:
        # The safety verdict's budget comes out of the same clock, first: a
        # verdict on every tracked token matters more than a few more quotes.
        safety_s = min(universe.SAFETY_SECONDS, left * 0.4)
        universe.build(verbose=verbose, safety_s=safety_s,
                       gate_s=max(0.0, min(universe.GATE_SECONDS, left - safety_s)))
    except Exception as e:
        print(f"  universe failed (non-fatal): {type(e).__name__}: {e}")


def sweep_stage(verbose=True):
    """Close the paper log - both ledgers - then label the unambiguously dead."""
    fetch = _memo_fetch(sources.dexscreener_pair)
    deferred = 0
    try:
        s1 = paper.sweep(fetch, verbose=verbose, should_stop=_stage_stop)
        deferred += (s1 or {}).get("deferred", 0)
        # v2 sweeps in the same stage, on the same shared close_decision and
        # the same read of each pool, so the two ledgers close identically.
        try:
            import paperv2
            s2 = paperv2.sweep(fetch, verbose=verbose, should_stop=_stage_stop)
            deferred += (s2 or {}).get("deferred", 0)
        except Exception as e:
            print(f"  v2 sweep failed: {e}")
    except Exception as e:
        print(f"  paper sweep failed: {e}")
    if deferred:
        STAGE_STOPS["sweep"] = (f"time budget reached with {deferred} open "
                                f"positions unchecked")
    # ⭐ V3, THE LEDGER THAT PRICES ITS FILLS ON REAL QUOTES. Nothing scheduled
    # it until 2026-09-18: 71 passing tests, a pre-committed rule, one hand-run
    # entry, and collect.py never called it. ⛔ Its own try block and its own
    # ledger - a v3 failure can never touch a v1 or v2 close.
    try:
        import paperv3
        s3 = paperv3.sweep(verbose=verbose, should_stop=_stage_stop)
        if (s3 or {}).get("deferred"):
            STAGE_STOPS["sweep"] = (f"time budget reached with {s3['deferred']} "
                                    f"v3 positions unchecked")
        if verbose and (s3 or {}).get("checked"):
            print(f"  [v3] swept {s3['checked']} open, closed {s3['closed']}"
                  + (f", {s3['errors']} recording errors" if s3.get("errors") else ""))
    except Exception as e:
        print(f"  v3 sweep failed: {e}")
    try:
        _made, _left = paper.label_unpriceable(dry_run=False, verbose=verbose)
        if _made:
            print(f"  [paper] labelled {len(_made)} inferred total losses, "
                  f"{len(_left)} left honestly unpriceable")
    except Exception as e:
        print(f"  paper labelling failed: {e}")


def one_pass(networks=("solana",), verbose=True):
    total_seen, total_passed = scan_stage(networks, verbose=verbose)
    # APPROACH BAND, every pass. Tokens between $45k and $69k of FDV are the
    # only population where graduation is still ahead of them and observable;
    # the 1/6/24/168h outcome schedule cannot see a crossing that takes
    # minutes. Costs Dexscreener calls only - it spends none of the scarce
    # GeckoTerminal budget. Runs before outcome scoring so a graduation is
    # claimed on the freshest possible read.
    watchlist_stage(verbose=verbose)
    # CLOSE THE PAPER LOG. A log of open positions is a wishlist; the losers
    # are what make it evidence. Every position that has met its declared exit
    # rule is closed here, whatever the number says, including to zero.
    sweep_stage(verbose=verbose)
    # WHAT IS RUNNING NOW. Before outcome scoring, which is the long, resumable
    # part of a pass - a snapshot is only worth anything if it is taken.
    market_stage(verbose=verbose)
    # LABEL THE UNAMBIGUOUSLY DEAD. A close whose pool was last seen rugged or
    # dead holding ~$0 did not have an unknown outcome, and leaving 65% of
    # closes unmeasurable would hand 2026-09-13 a sample too thin to read.
    # Asserts a multiple of ZERO from liquidity - never the last-known price,
    # which on these pools medians 0.967x and would manufacture wins. Appended
    # as its own record type, so the log is still derivable both ways.
    # (the labelling now runs inside sweep_stage, straight after the closes)
    try:
        track.score_all(verbose=verbose)
    except Exception as e:
        print(f"  outcome scoring failed: {e}")
    # EVERY GRADUATION, then EVERY REAL $1M COIN. Last, on leftover time.
    graduations_stage(verbose=verbose)
    universe_stage(verbose=verbose)
    return total_seen, total_passed


def main():
    # LINE-BUFFER STDOUT. Python block-buffers when stdout is a pipe, so a pass
    # SIGKILLed at the 178s cap flushed NOTHING - the work it had narrated was
    # still sitting in a 8KB buffer when the process died. That is why seven
    # dead stages looked like silence instead of seven error reports, and it is
    # the same lesson as the incomplete-pass marker: a failure that cannot
    # speak is indistinguishable from nothing happening.
    try:
        sys.stdout.reconfigure(line_buffering=True)
        sys.stderr.reconfigure(line_buffering=True)
    except Exception:
        pass
    argv = [a for a in sys.argv[1:]]
    stage = "full"
    if "--stage" in argv:
        i = argv.index("--stage")
        stage = argv[i + 1] if i + 1 < len(argv) else "full"
        del argv[i:i + 2]

    # CALL BUDGET. A staged invocation must fit its window, and the window is
    # 178s on the Claude dispatch sandbox. At ~1.116s per call that is ~150
    # calls, so a staged run defaults to a budget and stops CLEANLY at it.
    # Unstaged runs - the GitHub runner, 15-minute timeout - stay unlimited.
    max_calls = None
    max_seconds = None
    if "--max-seconds" in argv:
        i = argv.index("--max-seconds")
        max_seconds = float(argv[i + 1]) if i + 1 < len(argv) else STAGE_SECONDS
        del argv[i:i + 2]
    if "--max-calls" in argv:
        i = argv.index("--max-calls")
        max_calls = int(argv[i + 1]) if i + 1 < len(argv) else None
        del argv[i:i + 2]
    if max_seconds is None and (stage != "full"
                                or not os.environ.get("GITHUB_ACTIONS")):
        max_seconds = STAGE_SECONDS
    if False:  # retained branch shape; superseded by the time budget
        pass
    elif not os.environ.get("GITHUB_ACTIONS"):
        # An UNSTAGED pass off the GitHub runner is still a sandbox pass, and
        # a full pass is ~607 calls against a 178s cap. 10 of the 57 recent
        # aborts were exactly this: stage=full, killed at the cap. Budgeting
        # them makes the pass short-and-recorded instead of dead-and-inferred.
        # GITHUB_ACTIONS is set by Actions itself, so the hosted runner keeps
        # its unlimited full pass unchanged.
        pass
    if not (stage in STAGES or stage in ("full", "outcomes") or stage.isdigit()):
        # A typo in the skill file used to fall through to one_pass(): an
        # unstaged full pass, which the sandbox kills. Refuse it instead.
        print(f"  unknown stage {stage!r}; known: {', '.join(STAGES)}, outcomes, full")
        return 2
    os.environ["CRYPTO_ORIGIN"] = liveness.origin()
    if max_seconds and not os.environ.get("GITHUB_ACTIONS"):
        try:
            max_seconds, _basis = calibrated_budget(stage, max_seconds)
            print(f"  budget calibration: {_basis}")
        except Exception as e:
            print(f"  budget calibration failed, keeping {max_seconds:.0f}s: {e}")
    sources.set_time_budget(max_seconds, call_cap=max_calls)
    if max_seconds:
        print(f"  budget: {max_seconds:.0f}s wall"
              + (f", cap {max_calls} calls" if max_calls else "")
              + f" (per-call estimate {sources.per_call_estimate():.2f}s, "
                f"re-measured as it runs)")

    nets = ("solana",)
    loop = False
    if argv:
        nets = tuple(x.strip() for x in argv[0].split(","))
    if len(argv) > 1 and argv[1] == "loop":
        loop = True

    # Claim the pass before doing any work. If the previous one left its marker
    # behind it was killed, and that hour needs to be on the record as broken
    # rather than quiet.
    stale = journal.pass_begin(",".join(nets), stage, budget=max_calls,
                               origin=os.environ.get("CRYPTO_ORIGIN"))
    if stale:
        ab = journal.record_aborted(stale)
        print(f"  PREVIOUS PASS NEVER FINISHED: stage={ab['stage']} "
              f"ran {ab['ran_for_s']}s before dying. Recorded as an aborted pass.")

    rc = 0
    while True:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")
        print(f"\n=== pass {stamp} UTC · {','.join(nets)} · stage={stage} ===")
        # ⭐ Pass-level tally, cleared once per pass rather than per record()
        # batch. journal.record() clears LAST_WHITELIST_DROP on every call, so a
        # pass that records in batches kept only the last batch's drops - a
        # total that was wrong in the quiet direction.
        journal.reset_pass_drops()
        try:
            if stage == "outcomes":
                track.score_all()
                journal.pass_note(phase="outcomes", calls=sources.calls_made())
            elif stage == "sweep":
                sweep_stage()
                journal.pass_note(phase="sweep", calls=sources.calls_made())
            elif stage == "watchlist":
                watchlist_stage()
                journal.pass_note(phase="watchlist", calls=sources.calls_made())
            elif stage == "market":
                market_stage()
                journal.pass_note(phase="market", calls=market.CALLS["n"])
            elif stage == "graduations":
                graduations_stage()
                import graduations
                journal.pass_note(phase="graduations", calls=graduations.CALLS["n"])
            elif stage == "universe":
                universe_stage()
                import universe
                journal.pass_note(phase="universe", calls=universe.CALLS["n"])
            elif stage.isdigit():
                track.score_horizon(int(stage))
                journal.pass_note(phase=f"{stage}h", calls=sources.calls_made())
            else:
                seen, passed = (scan_stage(nets) if stage == "scan" else one_pass(nets))
                s = journal.stats()
                print(f"  journal now: {s['observations']} obs · {s['unique_pairs']} pairs · "
                      f"{s['outcomes']} outcomes · {s['hours_covered']}h")
                # A pass that journalled NOTHING is not a quiet market, it is a
                # broken pass: scanner.scan swallows its own exception and
                # returns no rows, which is what an IP-level rate limit looks
                # like from a shared runner. Exit non-zero so the scheduler
                # reports a failure instead of a silent no-op hour.
                if seen == 0:
                    print("  NOTHING JOURNALLED - failed pass, not a quiet one")
                    rc = 1
                    # This must reach Frank, not a log file. It is the one
                    # condition that means the dataset stopped growing, and it
                    # went unnoticed six times because the error class had
                    # already pinged once and was suppressed thereafter.
                    _, _, pinged, why = findings.record(
                        "collector-zero", ",".join(nets),
                        "collector journalled ZERO observations while the host was up",
                        f"stage={stage}. Discovery returned "
                        f"{scanner.LAST_SCAN['pools']} pools, enriched "
                        f"{scanner.LAST_SCAN['enriched']}, failed "
                        f"{scanner.LAST_SCAN['failed']}, budget_hit="
                        f"{scanner.LAST_SCAN['budget_hit']}. This hour has no "
                        f"observations and cannot be recovered.")
                    print(f"  zero-result alert: {why}")
        except Exception:
            traceback.print_exc()
            rc = 1
        if not loop:
            break
        time.sleep(900)

    # Per-source reliability. If Dexscreener is a single point of failure it
    # should at least be a measured one.
    try:
        h = resolve.log_health()
        drops = h["dexscreener_dropped"]
        if drops:
            tot = drops + h["dexscreener_ok"]
            print(f"  source health: dexscreener dropped {drops}/{tot} lookups, "
                  f"geckoterminal recovered {h['geckoterminal_ok']}, "
                  f"{h['unresolved']} unresolved")
    except Exception as e:
        print(f"  source-health log failed (non-fatal): {e}")

    # PER-OUTLET NEWS FRESHNESS. A 6x drop in daily article count was spotted by
    # hand on 2026-09-06 and turned out to be ordinary weekend cadence - every
    # weekend in the record drops 4-5x and all four outlets drop together. A
    # volume alert would therefore fire two days in seven and be muted inside a
    # week. This checks staleness PER OUTLET instead, because a real failure is
    # one feed going quiet while the others keep publishing, which is visible on
    # a weekend too. Thresholds sit above every gap observed in 21 days.
    try:
        # NOTE: this block lives in main(), which has no `verbose` local.
        # Passing one here raised NameError on every pass from 2026-09-06
        # 17:11Z and silently killed the freshness check - the very class
        # of silent failure it exists to catch.
        news.check_freshness(record=findings.record, verbose=True)
    except Exception as e:
        print(f"  news-freshness check failed (non-fatal): {e}")

    # THE DETECTOR'S OWN SHELF LIFE. The template pools share depth/liq to five
    # decimal places, which is one operator running one script. When that
    # constant moves, D1's recall falls and absolutely nothing else would say
    # so. Free - it reads the journal, makes no calls.
    try:
        detector.check_drift(record=findings.record, verbose=True)
    except Exception as e:
        print(f"  drift check failed (non-fatal): {e}")

    # ⭐ REBUILD THE SITE. "The deliverable is a site, not chat output" is the
    # first line of CLAUDE.md's session protocol, and the dashboard was rebuilt
    # only when a human ran `python dashboard.py` by hand - `dashboard` appeared
    # nowhere in this file. So the one artifact Frank actually looks at went
    # stale silently while every number behind it stayed current.
    #
    # It costs 4 seconds, reads the journal and makes NO network calls, so there
    # is no reason for it to be a manual step. Runs before the liveness check so
    # a failure to build is itself reported by that check.
    try:
        _t0 = time.time()
        dashboard.build()
        liveness.beat("dashboard.build", 1)
        print(f"  dashboard rebuilt in {time.time() - _t0:.1f}s")
    except Exception as e:
        # ⛔ Non-fatal: a broken renderer must never cost a pass of collection,
        # which cannot be bought back. But it beats nothing, so liveness calls
        # it stale rather than letting a stale page look fresh.
        print(f"  dashboard build failed (non-fatal): {type(e).__name__}: {e}")

    # THE LIVENESS REGISTRY. Runs LAST, after every component has had its
    # chance to fire this pass. Four systems in this repo produced convincing
    # output while doing nothing - the win record, the news check, the volume
    # features and the milestone tracker - and in every case absence of a
    # signal was indistinguishable from a quiet market. This iterates a
    # hardcoded manifest rather than the registry contents, so a component that
    # has NEVER fired is an alarm rather than an empty row nobody reads.
    #
    # It says "it ran", never "it works". Correctness is still the win gate,
    # the paper ledger and D1's interval.
    try:
        liveness.check(record=findings.record, verbose=True)
    except Exception as e:
        print(f"  liveness check failed (non-fatal): {e}")

    # One line a day saying the collector is alive. Failures already page; a
    # week of silence from a runner nobody has seen working does not prove it
    # is running.
    try:
        hb = journal.daily_summary()
        if hb:
            msg = (f"**crypto-intel daily** {hb['hours_with_data']}/24 hours with data, "
                   f"{hb['observations']} observations, {hb['passed']} cleared the filter, "
                   f"{hb['stream_coverage_pct']}% of the launch stream seen")
            if hb["aborted"]:
                msg += f", {hb['aborted']} aborted passes"
            if hb["best_realizable_mult_24h"]:
                msg += f", best realizable {hb['best_realizable_mult_24h']}x"
            # Per-horizon lookup success on the line. A horizon failing at
            # 100% is what happened on 09-03 for four passes running, unseen.
            if hb.get("horizon_lookups"):
                msg += chr(10) + "horizon lookups resolved: " + ", ".join(
                    f"{k} {v}" for k, v in hb["horizon_lookups"].items())
            notify.send(content=msg)
    except Exception as e:
        print(f"  heartbeat failed (non-fatal): {e}")

    if rc == 0:
        # Completeness is RECORDED, not inferred. A budgeted stop is a
        # deliberate short pass; a kill leaves the marker for the next run.
        _stops = {k: v for k, v in track.LAST_STOP.items()}
        _stops.update(STAGE_STOPS)
        _short = bool(_stops) or sources.over_budget()
        journal.pass_end(
            complete=not _short,
            reason=("; ".join(f"{k}{'h' if isinstance(k, int) else ''}: {v}"
                              for k, v in _stops.items())
                    if _stops else ("call budget spent" if _short else None)),
            calls=sources.calls_made(), phase=stage,
            budget_s=max_seconds, per_call_s=sources.per_call_estimate(),
            elapsed_s=sources.budget_report()["elapsed_s"])
        if _short:
            _b = sources.budget_report()
            print(f"  SHORT PASS (recorded): {_b['calls']} calls in "
                  f"{_b['elapsed_s']}s of a {max_seconds:.0f}s budget; measured "
                  f"{_b['per_call_s']}s/call. Remaining work resumes next "
                  f"invocation.")
    return rc


if __name__ == "__main__":
    sys.exit(main())
