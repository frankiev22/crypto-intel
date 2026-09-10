"""
Outcome tracking and learning.

The loop that makes this system improve rather than just alert:

  1. scanner sees a pair          -> journal.record()      (features, at t0)
  2. hours later, check it again  -> score_horizon()       (what actually happened)
  3. once labelled data exists    -> analyse()             (which features predicted)

Step 3 is the whole point. Until there are enough labelled outcomes the honest
answer is "not enough data", and this module says so rather than inventing a
signal from twelve rows.

Horizons: 1h catches the initial pump, 6h catches whether it held, 24h catches
whether it was real, 168h catches whether anything survived a week.
"""
import math, os, time, statistics as st
import journal, pricecheck, resolve, sources as S

# 168h IS RETIRED, AND RETIRED NOW MEANS RETIRED.
#
# It resolves at 2.7-5.1% - measured 2026-09-08, n=9,242 - because the pools
# are gone by then, and it has been described as retired for days while still
# being scored every pass. 1,088 rows sit pending at 168h against 283 at 24h,
# and under the new 150-call staging budget those two compete for the same
# calls. Spending them on a horizon that answers 3% of the time starves the
# one the model actually learns from.
#
# The rows are NOT deleted and the horizon constant stays, so every historical
# 168h outcome remains readable. It is simply no longer scheduled. Anything
# still pending at 168h ages out of pending()'s window deliberately, which is
# the explicit drop rather than the silent one.
HORIZONS_ALL = [1, 6, 24, 168]
HORIZONS_RETIRED = [168]
HORIZONS = [h for h in HORIZONS_ALL if h not in HORIZONS_RETIRED]
MIN_WINS_TO_TRUST = 10            # wins, not rows. Rows are cheap; wins are scarce.


# ---------------------------------------------------------------- scoring ---
# GeckoTerminal is the fallback and it is rate-limited to ~10-15 calls/min, so
# a single pass gets a budget rather than a free hand: a bad hour for
# Dexscreener must not turn into a 429 storm that costs the outcome scoring too.
#
# Measured 2026-09-03: one pass produced 125 dropped lookups and 107 of them
# hit a budget of 8. The drop rate is an order of magnitude above what that
# services, so the budget is now the dial. The hosted runner sets it high - a
# pass takes ~60s against a 900s ceiling, so it can afford 40 fallbacks at
# ~2.5s each - while the sandbox keeps it small to stay inside its 178s cap.
FALLBACK_BUDGET = int(os.environ.get("CRYPTO_FALLBACK_BUDGET", "8"))

# Per-horizon lookup health, and the floor below which a pass says so loudly.
HORIZON_HEALTH = {}
# Why a horizon stopped short, per horizon. Written so an incomplete pass is a
# RECORDED FACT rather than something the next pass has to infer from a stale
# sentinel - the failure mode that let a 76% collection decline run for three
# days looking like quiet market conditions.
LAST_STOP = {}
MIN_LOOKUPS_TO_JUDGE = 10  # do not cry outage over three lookups
SIGNIFICANCE_FLOOR = float(os.environ.get('CRYPTO_SIGNIFICANCE_ALWAYS', '3.0'))

# ONE GLOBAL FLOOR WAS WRONG, AND IT WAS FIRING 21 TIMES BY MIDDAY.
#
# The floor was a flat 0.5: "under half resolving is an outage". That is right
# for 1h and 6h, which resolve at 99.8-100.0% every day on the record. It is
# structurally unreachable at 24h, because the denominator includes tokens that
# no longer exist. A pool that died in its first day is not a failed lookup, it
# is a measured outcome, and Dexscreener deindexes it - `source_dropped` is set
# on ~60% of 24h rows.
#
# MEASURED, all outcome rows, primary resolution by day:
#     horizon   09-01   09-03   09-05   09-07   09-08
#        1h     99.9%   99.9%   99.9%   99.9%  100.0%
#        6h     99.9%   99.9%  100.0%   99.8%  100.0%
#       24h     14.1%   17.2%   38.4%   45.5%   49.3%
#      168h      3.0%    1.9%    3.7%    5.1%    2.7%
#
# So 24h is not degrading - it has risen from 14% to 49% in eight days and is
# the healthiest it has been. It sat just under the flat 0.5 floor, which is
# why the alarm fired every pass while the underlying number improved. An alarm
# that cannot be satisfied is one nobody reads, and 168h is the cautionary case
# in the other direction: at 2.7-5.1% it is genuinely dead, and it was retired.
#
# Floors are per horizon, set below the measured range and above the level that
# would mean the lookup mechanism itself broke. The deeper fix - judging health
# on lookups that COULD have succeeded, excluding pools the source has
# deindexed - is written up in GAPS.md; it changes what the number means and is
# not being done days before the n=200 run closes.
PRIMARY_OK_FLOOR_BY_H = {1: 0.90, 6: 0.90, 24: 0.20, 168: 0.01}
PRIMARY_OK_FLOOR = 0.5     # fallback for an undeclared horizon


def primary_floor(horizon_h):
    return PRIMARY_OK_FLOOR_BY_H.get(horizon_h, PRIMARY_OK_FLOOR)


# Per-horizon slice. The 1h horizon needs the biggest one: a pass pulls ~90 new
# pools and the old flat limit of 80 could not clear them, so the shortfall
# became next pass's backlog and the "1h" check drifted to a median of 2.00h.
# The long horizons see far fewer rows come due per pass and do not need it.
HORIZON_LIMIT = {1: int(os.environ.get("CRYPTO_LIMIT_1H", "200"))}

# Default slice for the other horizons. MEASURED 2026-09-06: new distinct pairs
# arrive at 2,308/day = 96 per hourly pass, against a slice of 80. The deficit
# was 16 per pass and it did not queue - pending() only offers a pair inside a
# 6h window, so the overflow aged out and was NEVER scored at that horizon.
# 4,203 rows were lost that way at 24h (20.8% of everything eligible), 3,238 at
# 6h (14.5%). 120 covers arrival with ~25% headroom; the extra 40 lookups per
# horizon cost ~14s of Dexscreener at a measured 0.116s median, against a
# published 300 req/min, and spend none of the scarce GeckoTerminal budget.
HORIZON_SLICE = int(os.environ.get("CRYPTO_HORIZON_SLICE", "120"))

# A validated realizable multiple at or above this is announced by the runner
# itself. Matches findings.SIGNIFICANCE_ALWAYS so it is never rationed.
WIN_ANNOUNCE_MULT = float(os.environ.get("CRYPTO_WIN_ANNOUNCE_MULT", "3.0"))



def _nth_ordinal(n):
    return {1: "1st", 2: "2nd", 3: "3rd"}.get(n, f"{n}th")


# ---------------------------------------------------------------------------
# THE WIN INDEX IS BUILT ONCE PER PASS, NOT ONCE PER PAIR.
#
# _prior_win_horizons() called journal.outcomes(days=14) inside the per-pair
# loop, and each call re-parsed the whole 14-day outcomes corpus: 1,267,263
# json.loads for a twelve-pair pass, ~2.7s per pair, 66% of the pass's wall
# clock spent re-reading files that had not changed since the pass began.
#
# Measured 2026-09-10, with pacing removed so only real work is counted:
#   HTTP        0.216s/call    6%
#   pace()      1.000s/call   28%
#   this        2.350s/call   66%
# That is the whole "2.5x latency regression". It is not the network and it is
# not the 1.0s rate limit: at 0.216s the network is FASTER than the 1.116s
# budget assumed. The cost is O(pairs x corpus), so it grows every day the log
# grows, which is exactly the shape observed - 1.116s -> 2.77s -> 3.59s per
# call while the corpus went from ~40k to ~100k rows.
# ---------------------------------------------------------------------------
_WIN_INDEX = None
_WIN_INDEX_TS = 0.0
_WIN_INDEX_TTL = float(os.environ.get("CRYPTO_WIN_INDEX_TTL_S", "300"))


def _win_index(force=False):
    """contract address -> [horizons that already cleared the gate at >= the
    announce multiple]. Keyed on contract address, never on ticker."""
    global _WIN_INDEX, _WIN_INDEX_TS
    now = time.time()
    if _WIN_INDEX is not None and not force and now - _WIN_INDEX_TS < _WIN_INDEX_TTL:
        return _WIN_INDEX
    idx = {}
    for r in journal.outcomes(days=14):
        if r.get("realizable") is not True:
            continue
        tok = r.get("token")
        if not tok or (r.get("mult") or 0) < WIN_ANNOUNCE_MULT:
            continue
        idx.setdefault(tok, []).append(r.get("horizon_h") or 0)
    _WIN_INDEX, _WIN_INDEX_TS = idx, now
    return idx


def _prior_win_horizons(token, horizon_h):
    """How many EARLIER horizons already cleared the gate for this contract.

    This used to be wrapped in `except Exception: return 0`, which is the
    absence-of-evidence shape again (instance 8): an unreadable corpus would
    have reported zero prior wins, relabelling a 3rd ping as a 1st. It now
    reuses the last good index rather than inventing a zero, and if there has
    never been a good index it raises rather than answering.
    """
    if not token:
        return 0
    try:
        idx = _win_index()
    except Exception:
        if _WIN_INDEX is None:
            raise
        idx = _WIN_INDEX
    return sum(1 for h in idx.get(token, ()) if h < horizon_h)


def score_horizon(horizon_h, limit=None, verbose=True):
    limit = limit or HORIZON_LIMIT.get(horizon_h, HORIZON_SLICE)
    """Re-check pairs first seen ~horizon_h ago and record what happened."""
    # Built once here, then reused by every pair in this pass.
    _win_index(force=True)
    queue = journal.pending(horizon_h)
    todo = queue[:limit]
    if verbose:
        extra = f", {len(queue) - len(todo)} deferred to the next pass" if len(queue) > len(todo) else ""
        print(f"  {horizon_h}h horizon: {len(todo)} pairs due{extra}")
    done = 0
    fallbacks = 0
    primary_ok = primary_miss = 0
    elapsed_seen = []
    stopped_early = None
    LAST_STOP.pop(horizon_h, None)
    for o in todo:
        # STOP CLEANLY AT THE BUDGET. Reserve headroom for the fallback lookup
        # this row may need, so we never stop half way through one pair.
        if S.over_budget(headroom=2):
            _b = S.budget_report()
            stopped_early = (f"time budget reached after {done} of {len(todo)} "
                             f"pairs: {_b['calls']} calls in {_b['elapsed_s']}s, "
                             f"{_b['seconds_left']}s left, measured "
                             f"{_b['per_call_s']}s/call over {_b['measured_n']} calls")
            if verbose:
                print(f"    stopping cleanly: {stopped_early}")
            break
        try:
            pair = S.dexscreener_pair(o.get("network", "solana"), o["pair"])
        except Exception:
            pair = None
        reasons, src = None, None
        _exit_pair = None          # per-iteration; never leak across the loop
        _sells24 = _buys24 = None
        _mcap = None               # per-iteration; primary branch only
        if pair:
            price = float(pair.get("priceUsd") or 0) or None
            liq   = float((pair.get("liquidity") or {}).get("usd") or 0)
            vol24 = float((pair.get("volume") or {}).get("h24") or 0)
            # What you could actually be paid, not the pool valued at its own
            # token. See resolve.exit_depth_usd().
            depth = resolve.exit_depth_usd(pair)
            src = "dexscreener"
            _exit_pair = pair.get("pairAddress")
            # Sell-side at exit. Free - the pair object is already in hand. A
            # pool with buys and no sells has never had its price tested by
            # anyone trying to leave, which is the template signature that a
            # depth floor cannot catch.
            _t24 = (pair.get("txns") or {}).get("h24") or {}
            try:
                _sells24 = int(_t24.get("sells")) if _t24.get("sells") is not None else None
                _buys24 = int(_t24.get("buys")) if _t24.get("buys") is not None else None
            except (TypeError, ValueError):
                _sells24 = _buys24 = None
            # MARKET CAP AT EXIT, for the mcap milestones. PRIMARY BRANCH ONLY:
            # dexscreener_pair verifies the returned pairAddress is the one we
            # asked for, so this number belongs to the pool we actually hold.
            # The fallback path may price a different pool of the same token -
            # exactly the WOFI failure above - and must never claim a milestone.
            try:
                _mcap = float(pair.get("marketCap") or pair.get("fdv") or 0) or None
            except (TypeError, ValueError):
                _mcap = None
            primary_ok += 1
        else:
            # The primary went quiet. That is NOT the same as the token dying -
            # coins do not stop existing. Resolve it properly before writing a
            # label we cannot take back.
            price = liq = vol24 = depth = None
            primary_miss += 1
            tok = o.get("token")
            if tok and fallbacks < FALLBACK_BUDGET:
                fallbacks += 1
                r = resolve.resolve(tok, o.get("network", "solana"))
                price, liq = r.get("price_usd"), r.get("liq_usd")
                depth = r.get("exit_depth_usd")
                reasons, src = r.get("reasons"), r.get("source")
                _exit_pair = r.get("pair_address")
                # WOFI, 2026-09-04. We entered on pair 4mvH... at $0.00004131,
                # that pool went quiet, the token-level fallback priced the
                # OTHER pool at $0.01377, and the division recorded 333.33x.
                # The pair we actually held went 2.03x. Two pools of one token
                # are not one series and must never be divided into each other.
                if r.get("pair_address") and r["pair_address"] != o["pair"]:
                    reasons = list(reasons or []) + ["cross_pair_fallback"]
                    if verbose:
                        print(f"    {str(o.get('symbol','?'))[:12]:<14} priced from a "
                              f"DIFFERENT pool than we entered - not comparable")
                if verbose:
                    print(f"    {str(o.get('symbol','?'))[:12]:<14} dexscreener dropped it "
                          f"-> {src or 'unresolved'}: {', '.join(reasons or [])}")
            elif tok:
                reasons, src = ["source_dropped", "fallback_budget_spent"], None
        # Validate BEFORE recording, and only for multiples large enough to
        # be believed. A wrong price on a 1.02x costs nothing; a wrong price
        # on a 444x becomes the headline. Shares the fallback budget because
        # the check costs the same rate-limited GeckoTerminal call.
        base_px = o.get("price_usd")
        implied = (price / base_px) if (base_px and price) else None
        verdict = None
        # A rejection already on the record costs nothing to honour, and it must
        # be honoured BEFORE the budget test. KPOP's E9HaVWoQ was quarantined at
        # 1h and 6h for a 31x liquidity disagreement, then came back clean at
        # 24h - not because anything had improved, but because the fallback
        # budget was spent, so the check never ran and the row fell through to
        # the trustworthy path. A spent budget is a reason to know less, never a
        # reason to admit more.
        sticky = pricecheck.quarantined(o.get("token"))
        if sticky:
            verdict = {"trustworthy": False, "confidence": sticky["confidence"],
                       "sticky_quarantine": True,
                       "detail": f"sticky: {sticky.get('detail') or ''}"[:300]}
            if verbose:
                print(f"    {str(o.get('symbol','?'))[:12]:<14} "
                      f"{(implied or 0):>8.2f}x STICKY-QUARANTINED "
                      f"({sticky.get('hits',1)} prior sightings)")
        elif (implied and implied >= pricecheck.VALIDATE_ABOVE
                and o.get("token") and fallbacks < FALLBACK_BUDGET):
            fallbacks += 1
            _okp, verdict = pricecheck.check_multiple(
                o["token"], implied, o.get("network", "solana"),
                base_price=base_px, horizon_h=horizon_h)
            if verdict and not verdict.get("trustworthy") and verbose:
                print(f"    {str(o.get('symbol','?'))[:12]:<14} {implied:>8.2f}x "
                      f"QUARANTINED - {verdict['confidence']}: {verdict['detail'][:70]}")
        # Quote-token consistency needs price_native at BOTH ends. The exit
        # value is already in the pair object we fetched, and the entry value
        # is on the observation, so this costs no call. If entry and exit are
        # quoted against different assets their ratio is not a return.
        try:
            _pn_exit = float(pair.get("priceNative")) if pair else None
        except (TypeError, ValueError):
            _pn_exit = None

        status, mult, gate_ok, gate_failed = journal.record_outcome(
            o["pair"], o["ts"], horizon_h, price, liq, vol24,
            o.get("price_usd"), o.get("liq"), o.get("symbol", ""),
            token=o.get("token", ""), reasons=reasons, source=src,
            price_verdict=verdict, exit_depth=depth,
            base_price_native=o.get("price_native"), price_native=_pn_exit,
            exit_pair=_exit_pair, sells_h24=_sells24, buys_h24=_buys24,
            mcap=_mcap)
        done += 1
        _elapsed = (time.time() - o["ts"]) / 3600.0
        elapsed_seen.append(_elapsed)
        # ANNOUNCE A WIN FROM HERE, not from the desktop skill.
        # Until 2026-09-06 outcome findings existed only in SKILL.md, so the
        # hosted runner - the one that is actually up 24/7 - never announced a
        # win at all. Nothing was rationed; nothing was ever attempted.
        #
        # Only a validated one goes out: realizable, and not quarantined by the
        # cross-source check. Significance is the multiple itself, so the ping
        # budget ranks it by value instead of arrival order.
        # ANNOUNCE ONLY WHAT THE ROW RECORDED. This used to call the old
        # three-check journal.realizable() while the row was gated by the
        # eight-check verify_win() - so the alert path, the part Frank
        # actually sees, was looser than the record. Four of one day's twelve
        # pinged wins came through that gap. `gate_ok` IS the row's verdict.
        # ONE TOKEN, ONE WIN - COUNTED, NOT ONE PER HORIZON.
        #
        # CWINK pinged three times: 3.05x at 1h, 4.08x at 6h, 4.08x at 24h.
        # The 6h ping landed on 2026-09-07 and the 24h ping on 2026-09-08, both
        # reading 4.08x, so it was counted as a clean win on two consecutive
        # days. That was diagnosed as a UTC-vs-ET boundary problem; it is not.
        # It is one token measured at three horizons, straddling a midnight.
        # Measured across the record: 54 ping events for 46 distinct
        # contracts, so daily win counts have run 1.17x inflated (1.29x on
        # 2026-09-07). Same row-vs-token shape that killed the low-score
        # inversion and the "record six-win day" - third time.
        #
        # The ping still fires per horizon, because reaching 4.08x at 24h is
        # genuinely different news from 3.05x at 1h. What changes is that the
        # ping now SAYS which it is, so nothing downstream has to guess.
        _prior = _prior_win_horizons(o.get("token"), horizon_h)
        if (mult is not None and mult >= WIN_ANNOUNCE_MULT and gate_ok
                and (verdict is None or verdict.get("trustworthy"))):
            try:
                import findings
                conf = (verdict or {}).get("confidence") or "unvalidated"
                ratio = (verdict or {}).get("ratio")
                # KEY ON THE CONTRACT ADDRESS. The dedupe class is identity,
                # and a ticker is not identity: there are 25 distinct FLORK
                # contracts, and the one that returned 5.49x on 2026-09-05
                # (DKwc8cML...) is NOT the one that collapsed to a $24k FDV
                # (AH8DQTFk...). Keyed on the symbol, the second FLORK would
                # have been suppressed as a repeat of the first.
                findings.record(
                    "outcome-win", o.get("token") or o.get("symbol", "?"),
                    f"{o.get('symbol','?')} {mult:,.2f}x, realizable, at the "
                    f"{horizon_h}h horizon (measured {_elapsed:.2f}h after "
                    f"observation) "
                    + (f"[{_nth_ordinal(_prior + 1)} horizon to clear for this "
                       f"contract - COUNT IT ONCE]" if _prior
                       else "[first horizon to clear for this contract]"),
                    detail=(
                        "contract " + str(o.get("token")) + chr(10)
                        + "pair     " + str(o["pair"]) + chr(10)
                        + f"entry    ${(o.get('price_usd') or 0):.10g}" + chr(10)
                        + f"now      ${(price or 0):.10g}" + chr(10)
                        + f"exit depth ${(depth or 0):,.0f} of ${(liq or 0):,.0f} reported" + chr(10)
                        + f"price     {conf}"
                        + (f", sources within {ratio:.4f}x" if ratio else "")
                        + chr(10)
                        + f"NOMINAL {horizon_h}h, ACTUAL {_elapsed:.2f}h elapsed - "
                          "read actual_elapsed_h, not the label."),
                    significance=float(mult))
            except Exception as e:
                print(f"    win announcement failed (non-fatal): {type(e).__name__}")
        if verbose and mult and mult >= 2:
            if gate_ok:
                print(f"    {o.get('symbol','?'):<12} {mult:>6.2f}x  ({status})")
            else:
                print(f"    {o.get('symbol','?'):<12} {mult:>6.2f}x  NOT REALIZABLE - "
                      f"failed {', '.join(gate_failed)}")
        S.pace()

    # A lookup class failing at ~100% inside one pass is not weather, it is an
    # outage, and on 2026-09-03 the 24h and 168h horizons failed at ~100% for
    # four consecutive passes without raising anything. These are the horizons
    # that would prove or kill the scoring model. Alert loudly, every time.
    seen_n = primary_ok + primary_miss
    med_drift = None
    if elapsed_seen:
        e = sorted(elapsed_seen)
        med_drift = e[len(e) // 2] / horizon_h
    HORIZON_HEALTH[horizon_h] = {"due": len(todo), "primary_ok": primary_ok,
                                 "primary_miss": primary_miss,
                                 "median_drift": med_drift,
                                 "deferred": len(queue) - len(todo)}
    # A horizon label that does not mean what it says corrupts every analysis
    # built on it, silently, and it did: the "1h" gradient was measured over a
    # median 2.00h window. Say so as soon as a pass drifts.
    if med_drift is not None and med_drift > journal.DRIFT_TOLERANCE and len(elapsed_seen) >= 10:
        import findings
        findings.record(
            "horizon-drift", f"{horizon_h}h",
            f"{horizon_h}h horizon checked at a median {med_drift:.2f}x its label "
            f"({med_drift * horizon_h:.2f}h elapsed) across {len(elapsed_seen)} rows",
            detail=(f"{len(queue) - len(todo)} rows were deferred to a later pass. "
                    f"Nominal horizon_h is a label, not a measurement - read "
                    f"actual_elapsed_h instead. Anything bucketed on the label "
                    f"is measuring a variable window."))
    _floor = primary_floor(horizon_h)
    if seen_n >= MIN_LOOKUPS_TO_JUDGE and primary_ok / seen_n < _floor:
        rate = primary_ok / seen_n
        msg = (f"{horizon_h}h horizon: primary price source resolved only "
               f"{primary_ok}/{seen_n} lookups ({rate:.0%}), under this "
               f"horizon's {_floor:.0%} floor")
        print(f"    LOOKUP OUTAGE - {msg}")
        try:
            import findings
            findings.record("lookup-outage", f"{horizon_h}h", msg,
                            f"{primary_miss} of {seen_n} lookups fell through to "
                            f"the fallback or failed entirely. Outcomes at this "
                            f"horizon are being priced off a fallback or not at "
                            f"all, which is how a scoring model dies quietly.",
                            always_ping=True,
                            # SIGNIFICANCE, NOT JUST always_ping.
                            #
                            # always_ping only clears the DEDUPE. The finding
                            # still entered the routine budget lane carrying
                            # significance=None, and a None cannot displace
                            # anything when the 4-per-hour budget is spent - so
                            # a persistent outage lost to any four routine
                            # findings and stopped pinging. That is the
                            # alert-suppression failure mode for the third
                            # time. An outage is now ranked the way a win is:
                            # a total outage scores 4.0, a marginal one just
                            # over 3.0, and SIGNIFICANCE_ALWAYS is 3.0, so it
                            # is never rationed.
                            significance=float(SIGNIFICANCE_FLOOR + (1.0 - rate)))
        except Exception as e:
            print(f"    (could not raise the outage finding: {e})")
    if stopped_early:
        LAST_STOP[horizon_h] = stopped_early
    return done


def score_all(verbose=True):
    out = {}
    for h in HORIZONS:
        if S.over_budget(headroom=2):
            LAST_STOP[h] = (f"skipped entirely: time budget spent "
                            f"({S.budget_report()})")
            out[h] = 0
            if verbose:
                print(f"  {h}h horizon: skipped, call budget spent")
            continue
        out[h] = score_horizon(h, verbose=verbose)
    return out


# --------------------------------------------------------------- analysis ---
def _joined(horizon_h):
    """Observations joined to their outcome at one horizon."""
    outs = {o["pair"]: o for o in journal.outcomes() if o["horizon_h"] == horizon_h}
    first = {}
    for o in journal.observations():
        p = o.get("pair")
        if p and (p not in first or o["ts"] < first[p]["ts"]):
            first[p] = o
    return [(first[p], outs[p]) for p in outs if p in first]


def wilson(k, n, z=1.96):
    """95% confidence interval for a rate. Every number this module prints rests
    on a handful of wins, and a bare point estimate at n=13 reads as if it had
    been measured. The interval is the honesty."""
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def analyse(horizon_h=1, win_mult=2.0):
    """Which observed features actually separated winners from losers.

    THE DENOMINATOR IS EVERY PAIR THAT CAME DUE, not the survivors.

    Filtering the sample down to realizable rows and measuring the hit rate
    inside it answers "given the token survived with exit liquidity, did it
    double" - which is not the question. It discards every dead, gone and
    rugged token, 98.5% of the data, and those are precisely the outcomes the
    score exists to avoid. Measured that way the score looked barely better
    than a coin flip and actively worse at 3x. Measured on the full sample the
    same score separates winners from losers by roughly 19x at 1h, because
    nearly all of its power is in predicting SURVIVAL rather than the size of
    the multiple given survival.

    So: a win is realizable AND mult >= win_mult. Everything else, including
    going to zero, is a loss. `realizable` gates the WIN, never the SAMPLE.
    """
    rows = _joined(horizon_h)
    if not rows:
        return {"ok": False, "msg": f"no labelled pairs at {horizon_h}h yet"}

    def _won(r):
        return bool(r.get("realizable")) and (r.get("mult") or 0) >= win_mult

    wins = [(o, r) for o, r in rows if _won(r)]
    rest = [(o, r) for o, r in rows if not _won(r)]
    rugs = [r for _, r in rows if r["status"] in ("rugged", "gone")]

    feats = ["score", "liq", "vol_h24", "vol_h1", "txns_h1", "age_hours", "chg_h1"]
    table = {}
    for f in feats:
        w = [o[f] for o, _ in wins if o.get(f) is not None]
        l = [o[f] for o, _ in rest if o.get(f) is not None]
        if len(w) >= 5 and len(l) >= 5:
            mw, ml = st.median(w), st.median(l)
            table[f] = {"winners_median": round(mw, 4), "others_median": round(ml, 4),
                        "ratio": round(mw / ml, 2) if ml else None}

    # The filter's own record, on the SAME definition of a win as the base rate
    # it is compared against. This line used to count any mult >= win_mult while
    # the base rate counted only realizable ones, so the filter was graded
    # against a softer test than its own baseline and looked better than it was.
    # Both sides are realizable-gated now.
    passed = [(o, r) for o, r in rows if o.get("passed")]
    pw = [1 for o, r in passed if _won(r)]
    base_rate = len(wins) / len(rows)
    f_rate = (len(pw) / len(passed)) if passed else None
    blo, bhi = wilson(len(wins), len(rows))
    flo, fhi = wilson(len(pw), len(passed)) if passed else (None, None)

    return {"ok": True, "horizon_h": horizon_h, "win_mult": win_mult,
            "labelled": len(rows), "winners": len(wins),
            "win_rate": round(base_rate, 5), "win_rate_ci": (blo, bhi),
            "rug_rate": round(len(rugs) / len(rows), 3),
            "filter_fired": len(passed), "filter_wins": len(pw),
            "filter_win_rate": round(f_rate, 5) if f_rate is not None else None,
            "filter_win_rate_ci": (flo, fhi),
            "filter_lift": round(f_rate / base_rate, 1) if (f_rate and base_rate) else None,
            # Below this many wins nothing here is a finding, however many losers
            # the sample holds. Rows are cheap; wins are what is scarce.
            "thin": len(pw) < MIN_WINS_TO_TRUST,
            "features": table}


def leaders(limit=10, min_mult=2.0):
    """Best REALIZABLE outcomes. This is what a findings report should quote;
    quoting raw `mult` is what produced a leaderboard of rugged pools."""
    rows = [o for o in journal.outcomes()
            if o.get("realizable") and (o.get("mult") or 0) >= min_mult]
    rows.sort(key=lambda o: -(o.get("mult") or 0))
    return rows[:limit]


def blocked_leaders(limit=10):
    """What the old code would have reported, and why each is rejected."""
    rows = [o for o in journal.outcomes()
            if not o.get("realizable") and (o.get("mult") or 0) >= 2]
    rows.sort(key=lambda o: -(o.get("mult") or 0))
    return rows[:limit]


def report():
    """The scoreboard.

    Centred on 2x at 1h and 6h: those are the horizons with enough closed
    outcomes to say anything, and 2x is the bar the data supports. 3x is
    printed alongside rather than dropped, because the earlier finding that the
    score had no edge at 3x came from measuring inside the survivor subset; on
    the full sample 3x at 1h separates too. 24h and 168h are shown for
    completeness and are too thin to read.
    """
    s = journal.stats()
    print("\n  JOURNAL")
    print(f"  {s['observations']} observations, {s['unique_pairs']} pairs, "
          f"{s['passed']} passed filter, {s['outcomes']} outcomes, "
          f"{s['hours_covered']}h covered")
    if s["by_status"]:
        print(f"  outcome status: {s['by_status']}")
    print("\n  A win is REALIZABLE and >= the multiple. Everything else, including")
    print("  going to zero, is a loss. The denominator is every pair that came due.")

    for h in HORIZONS:
        head = False
        for m in (2.0, 3.0):
            a = analyse(h, win_mult=m)
            if not a["ok"]:
                if not head:
                    print(f"\n  {h}h: {a['msg']}")
                    head = True
                continue
            if not head:
                print(f"\n  {h}h horizon, {a['labelled']} pairs came due, "
                      f"rug/gone rate {a['rug_rate']:.1%}")
                head = True
            lo, hi = a["win_rate_ci"]
            print(f"    {m:.0f}x  base {a['win_rate']:.2%} [{lo:.2%},{hi:.2%}] "
                  f"({a['winners']} of {a['labelled']})")
            if a["filter_win_rate"] is None:
                continue
            flo, fhi = a["filter_win_rate_ci"]
            lift = f"{a['filter_lift']}x" if a['filter_lift'] else "n/a (no wins)"
            print(f"        filter fired {a['filter_fired']}x -> "
                  f"{a['filter_win_rate']:.2%} [{flo:.2%},{fhi:.2%}] "
                  f"({a['filter_wins']} wins), lift {lift}")
            if a["thin"]:
                print(f"        THIN: {a['filter_wins']} wins is under the "
                      f"{MIN_WINS_TO_TRUST} needed to call this a finding")
            elif a["filter_lift"] and a["filter_lift"] <= 1:
                print("        NOTE: the filter is not beating random selection here.")
        a2 = analyse(h, win_mult=2.0)
        if a2["ok"]:
            for f, v in a2["features"].items():
                if v["ratio"] and (v["ratio"] > 1.3 or v["ratio"] < 0.77):
                    print(f"    {f:<10} winners {v['winners_median']:>12,.2f}  "
                          f"others {v['others_median']:>12,.2f}  ({v['ratio']}x)")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "score":
        score_all()
    report()
