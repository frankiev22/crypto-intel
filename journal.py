"""
The memory. Every pair the scanner sees is appended here the moment it is seen,
with all features, whether it passed the filter or not.

This is the most important file in the project and it has nothing to do with
trading. Without it the system cannot learn: on-chain history at this
granularity is not retroactively queryable for free, so every hour we do not
record is training data destroyed permanently.

Rejections matter as much as passes. You cannot evaluate a filter without
knowing what it threw away.

Storage is append-only JSONL, not SQLite. SQLite needs POSIX file locking and
this lives on a mounted Windows volume, where locking fails with disk I/O
errors. JSONL appends survive interruption, need no locking, and load into
SQLite or pandas trivially for analysis.
"""
import json, os, time, glob, urllib.request, datetime as dt

import config  # noqa: F401 - importing this loads .env
import milestones
import liveness
import tickers
import plausibility
import pricecheck

import safeload
from scanner import CFG as _SCAN_CFG

# --------------------------------------------------------------------------
# Realizability.
#
# A multiple is only real if you could actually have sold at it. record_outcome
# used to divide exit price by entry price with no regard for whether a pool
# still had depth, so a drained AMM quoting a garbage price produced records
# like SOL at 565,693x and CATE at 162,477x, both at ZERO liquidity. Nobody
# could have exited those at any price.
#
# The floor is DERIVED from the scanner's own entry floor rather than picked
# separately. scanner.CFG["min_liquidity_usd"] is already the codebase's
# definition of "below this you cannot exit size"; having the tracker call
# $1,000 "alive" while the scanner calls $8,000 the exit floor is exactly the
# kind of quiet disagreement that produced this bug.
#
# The ceiling FLAGS rather than clamps. A genuine 1000x inside a week on a pool
# that still holds real liquidity is possible but far less likely than a
# decimals change, a token migration or a bad price tick, so it is marked for
# review instead of being silently dropped or silently believed.
# --------------------------------------------------------------------------
MIN_EXIT_LIQ_USD = _SCAN_CFG["min_liquidity_usd"]
MAX_PLAUSIBLE_MULT = 1000


def realizable(*a, **k):
    """SEALED. This was a door beside the gate. Use verify_win().

    Kept as a raising shim rather than deleted, and rather than merely renamed:

      - deleting it turns an external call into a NameError with no
        explanation of what to use instead;
      - renaming it alone leaves the name free for someone to reintroduce
        under the old meaning, which is how it got called from the ping path
        in the first place;
      - a shim that raises converts a silent bypass into a loud failure AT the
        call site, names the replacement, and stays greppable forever.

    The three checks it performed (alive, depth floor, plausibility) are a
    strict subset of verify_win's eight. Anything it passed and verify_win
    fails was never a win.
    """
    raise RuntimeError(
        "journal.realizable() is sealed: it applied 3 of the 8 checks and was "
        "being used to announce wins that the recorded gate had rejected. Use "
        "verify_win(...) for the gate, or read the row's own `realizable` "
        "field, which is what the gate decided.")


def _exit_liquidity_ok(status, liq, mult, exit_depth=None):
    """INTERNAL. Alive + depth floor + plausibility only - NOT the gate.

    Three of verify_win's eight checks. Only for backfilling rows that predate
    the fields the other five need; never for deciding that something counts.

    `exit_depth` is the quote side of the pool, and it is REQUIRED.

    UNTIL 2026-09-11 THIS SUBSTITUTED `liq` WHEN DEPTH WAS MISSING:

        judged = exit_depth if exit_depth is not None else liq

    which silently turned a $1,000 exit-depth floor into a $1,000 reported-
    liquidity check. `liq` counts the base token valued at its own price, so a
    pool holding a billion of its own token and $10k of SOL reports $1.28M of
    "liquidity" and clears any floor set against it. On the measured
    distribution (n=104) depth/liq is ~0.496 for a healthy pool, so the
    substitution understates by ~2x there - tolerable - but 15.4% of rows sit
    below 0.10, where it overstates exitable size by up to 125x. Those are
    exactly the one-sided template pools the floor exists to catch.

    It now fails closed instead. A computed stand-in must never be returned
    from something whose answer is read as a measurement: if the quote side was
    never read, the honest answer is "not measured", not "here is the other
    number". verify_win() has always failed closed on this; this subset had not.
    """
    if status != "alive":
        return False, f"status is {status}, not alive"
    if exit_depth is None:
        return False, ("exit depth was never measured - refusing to judge "
                       "exitability from `liq`, which counts the base side")
    if exit_depth < MIN_EXIT_LIQ_USD:
        return False, (f"exit depth ${exit_depth:,.0f} is below the "
                       f"${MIN_EXIT_LIQ_USD:,.0f} exit floor")
    if mult is not None and mult > MAX_PLAUSIBLE_MULT:
        return False, (f"{mult:,.0f}x exceeds the {MAX_PLAUSIBLE_MULT}x plausibility "
                       f"ceiling; treat as a data error until checked by hand")
    return True, None

# MEASURED 2026-09-06, n=104 outcome rows that carry BOTH a measured exit depth
# and a reported liquidity. depth/liq distribution:
#
#     p05 0.008   p25 0.482   median 0.496   p75 0.499   p95 0.500
#
# A healthy constant-product pool sits at almost exactly 0.5, as the arithmetic
# says it must - so using `liq` where depth is unknown overstates exitable size
# by about 2x, which is tolerable. But **16 of 104 rows (15.4%) sit below 0.10**,
# and those are the one-sided pools where the overstatement reaches 125x.
#
# 495 of 599 realizable rows (82.6%) have no measured depth, 161 of them at
# >=2x. GeckoTerminal can NEVER supply it: its pool payload carries only
# `reserve_in_usd`, a combined total with no base/quote split, confirmed against
# a live response on 2026-09-06. All 20 GT-sourced realizable rows lack depth,
# though none is currently >=2x.
#
# This is RECORDED, NOT FILTERED. Standing rule 10 - no detector filters or
# backfills until it reports precision and recall against a labelled set. The
# flag lets every downstream analysis exclude unverified rows by choice; it does
# not make that choice for them.
DEPTH_VERIFIED_RATIO = 0.10


# ---------------------------------------------------------------------------
# THE WIN GATE. Added 2026-09-07, P0.
#
# FOUR HEADLINE RESULTS HAVE NOW EVAPORATED ON INSPECTION: the 718x, the
# liquidity-trajectory gradient, the low-score inversion, and now more than half
# of every win on the books. Four for four. The common factor is not that the
# checks did not exist - most of them did - but that they were a checklist
# somebody had to remember to apply, and applying them depended on a human
# spot-check that caught it about half the time.
#
# So this is a GATE, not a checklist. A row cannot be marked realizable without
# passing every check, each one is recorded by name on the row, and adding a new
# check here applies it everywhere at once.
#
# Treat every win as contaminated until specifically proven otherwise.
WIN_CHECKS = ("pair_identity", "depth_measured", "depth_floor", "sell_side",
              "source_agreement", "plausibility", "elapsed_recorded", "alive")

# A price nobody has ever sold at is not a price you can realise. MEASURED
# 2026-09-07 on the 141 outcome rows reporting $1.2M-$1.35M of liquidity, which
# are 85 of the 165 realizable 3x+ wins on the books:
#
#   every row with a measured depth shows depth/liq = 0.00796 - IDENTICAL to
#   five decimal places across CHAD, GME, JERSEY, ZODL, U SDD, cTERX and S500 -
#   i.e. $1.26M reported against ~$10,045 of real quote side, 125.6x overstated
#   liq/fdv median 1.0020, so the entire supply IS the pool
#   56 of 63 entries had ZERO sells against >=10 buys
#   56 of 63 were already flagged template_suspect at entry
#
# These clear a $100 depth floor on $10k of quote, so depth alone does NOT
# disqualify them. What disqualifies them is that nobody has ever sold: the
# price is set by a curve with no counterparty and has never been tested.
MIN_SELLS_FOR_WIN = int(os.environ.get("CRYPTO_MIN_SELLS_WIN", "1"))


def verify_win(status, liq, mult, exit_depth=None, pair=None, exit_pair=None,
               price_verdict=None, elapsed_h=None, reasons=None,
               sells_h24=None, buys_h24=None):
    """Every check a multiple must clear before it counts. Returns (ok, failed).

    `failed` is a list of check NAMES, so the row records which gate stopped it
    rather than a single opaque reason string.
    """
    failed = []

    # 1. PAIR IDENTITY. The pool we priced must be the pool we held. Two pools
    #    of one token are not one series and their ratio is not a return.
    if exit_pair is not None and pair is not None and exit_pair != pair:
        failed.append("pair_identity")
    if "cross_pair_fallback" in (reasons or []):
        failed.append("pair_identity")

    # 2/3. DEPTH. `liq` counts the base side valued at its own price; only the
    #      quote side can pay you. Measured 2026-09-06: depth/liq is ~0.496 for
    #      a healthy pool but under 0.10 for 15.4% of rows, where using `liq`
    #      overstates exitable size by up to 125x.
    if exit_depth is None:
        failed.append("depth_measured")
    elif exit_depth < MIN_EXIT_LIQ_USD:
        failed.append("depth_floor")

    # 3b. SELL SIDE. The template pools pass a depth floor - $10k of real quote
    #     is enough to exit $100 - so depth cannot catch them. Silence can: a
    #     pool with buys and no sells has never had its price tested by anyone
    #     trying to leave. Only applied when sell data was actually recorded;
    #     an absent count is not evidence of silence.
    if sells_h24 is not None and buys_h24 is not None:
        if sells_h24 < MIN_SELLS_FOR_WIN and buys_h24 >= 10:
            failed.append("sell_side")

    # 4. SOURCE AGREEMENT, when it was checked at all.
    if price_verdict is not None and not price_verdict.get("trustworthy"):
        failed.append("source_agreement")

    # 5. PLAUSIBILITY.
    if mult is not None and mult > MAX_PLAUSIBLE_MULT:
        failed.append("plausibility")

    # 6. ELAPSED TIME. The label is not the measurement.
    if elapsed_h is None:
        failed.append("elapsed_recorded")

    # 7. The token has to still be there.
    if status != "alive":
        failed.append("alive")

    return (not failed), sorted(set(failed))


def depth_unmeasured(exit_depth):
    """True when exitability was judged on the both-sides figure.

    Not a verdict on the row. A flag saying which measurement stood behind it.
    """
    return exit_depth is None


BASE = os.path.dirname(os.path.abspath(__file__))
OBS  = os.path.join(BASE, "data", "observations")
OUT  = os.path.join(BASE, "data", "outcomes")

COV  = os.path.join(BASE, "data", "coverage")


def record_coverage(network, window, scanned, pass_score=70, passed=0):
    """One row per pass: how wide the discovery window actually was.

    Coverage is the honest health metric for this system - of everything that
    launched, what fraction did we even look at. It is not derivable after the
    fact, because the window a pass saw is gone the moment the pass ends. So it
    is recorded here, per pass, from the start.

    span_s is the seconds of launch stream the pass observed. Divided by the
    interval between passes, that is the coverage rate.
    """
    now = int(time.time())
    obj = {"ts": now, "network": network, "kind": "discovery_window",
           "pools_returned": window.get("pools"),
           "oldest": window.get("oldest"), "newest": window.get("newest"),
           "span_s": window.get("span_s"),
           "pages_lost": window.get("pages_lost", 0),
           "suspected_cause": None,
           "scanned": scanned, "passed": passed, "pass_score": pass_score}
    _append(COV, obj)
    return obj


# --------------------------------------------------------------------------
# Pass sentinel.
#
# A pass that is KILLED cannot report its own death. collect.main's zero-row
# guard only runs if main() reaches the end, and on 2026-08-29 03:21 the
# dispatch sandbox killed a pass at its ~178s command cap partway through the
# scan: nothing journalled, no traceback, no non-zero exit. The hour read as
# quiet rather than broken.
#
# So the marker is written BEFORE the work and cleared AFTER it. A pass that
# finds a stale marker knows the previous one never finished, and can say so.
# This is the only way to detect a SIGKILL, because no in-process handler runs.
# --------------------------------------------------------------------------
PASS_STATE = os.path.join(BASE, "data", ".pass_state.json")


def pass_begin(network, stage="full", budget=None, origin=None):
    """Claim the pass. Returns the previous pass's marker if it never finished."""
    stale = None
    try:
        with open(PASS_STATE, encoding="utf-8") as f:
            stale = json.load(f)
    except FileNotFoundError:
        pass
    except (OSError, json.JSONDecodeError) as e:
        # A marker we cannot read is NOT a clean previous pass. Say so, and let
        # the caller record an abort of unknown extent rather than silence.
        stale = {"unreadable": f"{type(e).__name__}: {e}"}
    os.makedirs(os.path.dirname(PASS_STATE), exist_ok=True)
    safeload.save_json(PASS_STATE,
                       {"started_ts": int(time.time()), "network": network,
                        "stage": stage, "pid": os.getpid(),
                        "call_budget": budget, "origin": origin, "progress": {}},
                       allow_empty=True)
    return stale


def pass_note(**counters):
    """Record progress INTO the marker, so a killed pass leaves evidence.

    The old sentinel recorded a killed pass as `pools_returned: 0, scanned: 0`
    with `suspected_cause` guessing at the reason. That understates the work
    actually done and makes the cause an inference. A pass that dies after
    scanning 33 pools should say 33, and say where it was.
    """
    try:
        st = safeload.load_json(PASS_STATE)
    except Exception:
        return None
    st.setdefault("progress", {}).update(counters)
    st["progress"]["noted_ts"] = int(time.time())
    try:
        safeload.save_json(PASS_STATE, st, allow_empty=True)
    except Exception:
        return None
    return st["progress"]


def pass_end(complete=True, reason=None, **counters):
    """Close the pass and record whether it FINISHED, as a fact not a guess.

    `complete=False` with a reason is a pass that stopped deliberately - a
    spent call budget, say. That is a different thing from being killed, and
    the difference is now recorded rather than reconstructed.
    """
    prog = pass_note(**counters) or {}
    try:
        st = safeload.load_json(PASS_STATE)
    except Exception:
        st = {}
    started = st.get("started_ts")
    obj = {"ts": int(time.time()), "network": st.get("network"),
           "kind": "pass_complete" if complete else "pass_short",
           "stage": st.get("stage"), "started_ts": started,
           "ran_for_s": (int(time.time()) - started) if started else None,
           "complete": bool(complete), "stop_reason": reason,
           "call_budget": st.get("call_budget"),
           "origin": st.get("origin"),
           "progress": prog}
    _append(COV, obj)
    try:
        os.replace(PASS_STATE, PASS_STATE + ".done")
    except OSError:
        pass
    return obj


def record_aborted(stale, cause="killed - no clean exit"):
    """A pass that never finished. Recorded so a silent hour is visible.

    Reports what the dead pass ACTUALLY achieved, from the progress it wrote
    into its own marker, instead of zeros. A 76% collection decline read as
    quiet market conditions for three days because these rows all said 0.
    """
    started = stale.get("started_ts")
    prog = stale.get("progress") or {}
    obj = {"ts": int(time.time()), "network": stale.get("network"),
           "kind": "aborted_pass", "stage": stale.get("stage"),
           "started_ts": started,
           "ran_for_s": (int(time.time()) - started) if started else None,
           "complete": False,
           "suspected_cause": (stale.get("unreadable") or cause),
           "call_budget": stale.get("call_budget"),
           "origin": stale.get("origin"),
           "progress": prog,
           "last_phase": prog.get("phase"),
           "calls_made": prog.get("calls"),
           "pools_returned": prog.get("pools_returned", 0),
           "span_s": None,
           "scanned": prog.get("scanned", 0),
           "passed": prog.get("passed", 0)}
    _append(COV, obj)
    return obj


def coverage(days=None):
    """Discovery-window rows. Local only; there is no Supabase table for these
    yet, and inventing one from here would need a schema change we cannot make
    without a DDL credential."""
    files = sorted(glob.glob(os.path.join(COV, "*.jsonl")))
    if days:
        files = files[-days:]
    out = []
    for fp in files:
        for line in open(fp, encoding="utf-8"):
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    continue
    return out




def _path(root):
    os.makedirs(root, exist_ok=True)
    return os.path.join(root, dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d") + ".jsonl")


def _append(root, obj):
    with open(_path(root), "a", encoding="utf-8") as f:
        f.write(json.dumps(obj, separators=(",", ":")) + "\n")


# --------------------------------------------------------------------------
# Supabase mirror.
#
# JSONL above is the system of record and stays exactly as it was. This is a
# copy so that the record survives the desktop being switched off - an
# overnight shutdown previously cost ~32 hours of collection.
#
# _push CANNOT raise. Every append has already happened by the time it runs, so
# a network problem must never block, retry into, or corrupt the local file.
# --------------------------------------------------------------------------
PUSH = {"sent": 0, "failed": 0, "last_error": None}


def _push(rpc, rows):
    if not rows:
        return
    url = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    sec = os.environ.get("CRYPTO_JOURNAL_SECRET", "").strip()
    if not (url and key and sec):
        PUSH["last_error"] = "supabase not configured; JSONL only"
        return
    try:
        req = urllib.request.Request(
            f"{url}/rest/v1/rpc/{rpc}",
            data=json.dumps({"p_secret": sec, "p_rows": rows}).encode(),
            method="POST",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "Content-Type": "application/json",
                     "User-Agent": "crypto-intel/journal"})
        r = urllib.request.urlopen(req, timeout=30)
        PUSH["sent"] += int((r.read().decode().strip() or "0"))
    except Exception as e:
        PUSH["failed"] += len(rows)
        PUSH["last_error"] = f"{type(e).__name__}: {str(e)[:140]}"


def _read(root, days=None):
    files = sorted(glob.glob(os.path.join(root, "*.jsonl")))
    if days:
        files = files[-days:]
    out = []
    for fp in files:
        with open(fp, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if line:
                    try:
                        rec = json.loads(line)
                    except json.JSONDecodeError:
                        continue      # torn final line after a crash
                    # Files on this mount cannot be deleted, so stray probe rows
                    # live forever. Ignore anything without the required keys
                    # rather than letting one bad line break every reader.
                    if isinstance(rec, dict) and "ts" in rec and "pair" in rec:
                        out.append(rec)
                    elif isinstance(rec, dict) and "horizon_h" in rec:
                        out.append(rec)
    return out


# --------------------------------------------------------------------------
# Daily heartbeat.
#
# Every failure path pages: a zero-observation pass pings Discord every time,
# and a failed Actions run emails the repo owner. Nothing reports SUCCESS,
# which is correct hourly and wrong across a week away - silence from a
# runner that has never been seen working is indistinguishable from a runner
# that never started.
#
# One message per UTC day, on the first pass of that day. Not hourly: Frank
# rejected hourly noise and that must not creep back.
# --------------------------------------------------------------------------
HEARTBEAT = os.path.join(BASE, "data", ".heartbeat.json")


def _hb_state():
    try:
        with open(HEARTBEAT, encoding="utf-8") as f:
            return json.load(f)
    except (OSError, json.JSONDecodeError):
        return {}


def daily_summary(force=False):
    """Yesterday's collection, in one line. Returns None if already sent today."""
    today = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%d")
    st = _hb_state()
    if st.get("last") == today and not force:
        return None

    day_ago = time.time() - 86400
    obs = [o for o in observations() if o["ts"] >= day_ago]
    hours = len({dt.datetime.fromtimestamp(o["ts"], dt.timezone.utc).strftime("%H")
                 for o in obs})
    cov = [c for c in coverage() if c.get("ts", 0) >= day_ago]
    spans = [c["span_s"] for c in cov if c.get("span_s")]
    aborted = sum(1 for c in cov if c.get("kind") == "aborted_pass")
    window = (sum(spans) / 3600 / 24 * 100) if spans else 0.0
    passed = sum(1 for o in obs if o.get("passed"))
    best = max(((o.get("mult") or 0) for o in outcomes()
                if o.get("realizable") and (o.get("checked_ts") or 0) >= day_ago),
               default=0)

    if not force:
        st["last"] = today
        try:
            # Atomic: a SIGKILL at the 178s cap truncated data/liveness.json
            # mid-write on 2026-09-09. Every state file this process rewrites
            # is either the old version or the new one, never a fragment.
            safeload.save_json(HEARTBEAT, st, allow_empty=True)
        except OSError:
            pass

    try:
        import track
        hh = {f"{k}h": f"{v['primary_ok']}/{v['primary_ok']+v['primary_miss']}"
              for k, v in sorted(track.HORIZON_HEALTH.items())}
    except Exception:
        hh = {}
    return {"horizon_lookups": hh,
            "hours_with_data": hours, "observations": len(obs), "passed": passed,
            "passes": len(cov), "aborted": aborted,
            "stream_coverage_pct": round(window, 2),
            "best_realizable_mult_24h": round(best, 2)}


def record(rows, network, pass_score=70):
    """Write every scanned pair, passed AND rejected."""
    now = int(time.time())
    n = 0
    mirror = []
    # Ticker collision is recorded, never scored. 58.1% of everything we have
    # seen shares a symbol with something else, and the outcome difference
    # between variant-count buckets does not survive its own confidence
    # intervals - see tickers.py. Impersonation is a separate, structural flag.
    try:
        tick_idx = tickers._load()
    except Exception:
        tick_idx = {}
    for r in rows:
        obj = {
            "ts": now, "network": network,
            "pair": r.get("pair"), "token": r.get("addr"), "symbol": r.get("name"),
            "score": r.get("score"), "passed": int(r.get("score", 0) >= pass_score),
            "liq": r.get("liq"), "fdv": r.get("fdv"),
            "vol_h1": r.get("vol_h1"), "vol_h24": r.get("v24"),
            "txns_h1": r.get("txns_h1"), "buys_h1": r.get("buys_h1"),
            "sells_h1": r.get("sells_h1"),
            "dex_id": r.get("dex_id"), "venue_type": r.get("venue_type"),
            # A VENUE FACT, not a graduation event - see venue.assess. The old
            # key is still written because 100,000+ rows carry it and nothing
            # is ever deleted; readers use venue.has_pool(row), which takes
            # either. Both are added to this whitelist deliberately: a field
            # computed and not persisted is a field that does not exist.
            "has_amm_pool": r.get("has_amm_pool", r.get("is_graduated")),
            "is_graduated": r.get("is_graduated", r.get("has_amm_pool")),
            "liq_base": r.get("liq_base"), "liq_quote": r.get("liq_quote"),
            "price_native": r.get("price_native"),
            "exit_depth_usd": r.get("exit_depth_usd"),
            "price_usd": r.get("price_usd"), "chg_h1": r.get("chg_h1"),
            "chg_h24": r.get("chg_h24"), "age_hours": r.get("age_h"),
            # Volume shape, not level. Added 2026-09-06 and SILENTLY DROPPED
            # until 2026-09-07 because this dict is a whitelist and they were
            # never added to it - the same class of quiet loss as the news
            # NameError. A field computed and not persisted is a field that
            # does not exist.
            "vol_to_liq": r.get("vol_to_liq"), "vol_burst": r.get("vol_burst"),
            # CAPABILITY, not statistic. Live mint authority means the deployer
            # can print supply into your bid; live freeze means they can stop
            # you selling. Checked only on rows we would act on.
            "mint_authority": r.get("mint_authority"),
            "freeze_authority": r.get("freeze_authority"),
            "can_mint": r.get("can_mint"), "can_freeze": r.get("can_freeze"),
            "authorities_error": r.get("authorities_error"),
            # WHY a capability is absent, not just that it is. Until 2026-09-10
            # a row whose lookup never ran was byte-identical to one whose
            # lookup failed: can_mint None, no error. 201 such rows exist.
            # A non-attempt is a fact and it gets persisted like any other.
            "authorities_checked": r.get("authorities_checked"),
            "authorities_skipped": r.get("authorities_skipped"),
            # What was SHOWN, beside what was scored. PRECOMMIT_surface_grade.md.
            "grade": r.get("grade"), "grade_label": r.get("grade_label"),
            # THE PARALLEL V2 ARM, computed every pass and dropped by this very
            # whitelist for 14 hours on 2026-09-10/11 - the fourth field lost
            # this way, after vol_to_liq, vol_burst and the news NameError.
            # The experiment itself never lost anything: `arm` is written on
            # the v2 LEDGER row, which is the system of record. What was
            # missing was the back-reference that makes the split queryable
            # from an observation row.
            "paper_v2_entry": r.get("paper_v2_entry"),
            "paper_v2_arm": r.get("paper_v2_arm"),
            "reasons": r.get("reasons", []), "flags": r.get("flags", []),
            # which weight set produced this score. Without it a 66 from v2 and
            # a 66 from v5 look identical in the scoreboard and are not.
            "weights_version": r.get("weights_version"),
        }
        try:
            obj["ticker_variants"] = tickers.note(
                r.get("name"), r.get("addr"), idx=tick_idx)
            obj["impersonation"] = tickers.impersonation(r.get("name"))
        except Exception:
            obj["ticker_variants"] = None
            obj["impersonation"] = []
        # Liquidity plausibility and the template fingerprint, from stored
        # fields only. Doing it here means no analysis ever has to fetch pool
        # reserves again to exclude the template class.
        try:
            plausibility.annotate(obj)
        except Exception:
            obj["liq_to_fdv_ratio"] = None
            obj["template_suspect"] = None
            obj["liquidity_plausible"] = None
        _append(OBS, obj)      # system of record, first and unconditional
        mirror.append(obj)
        n += 1
    try:
        tickers._save(tick_idx)
    except Exception:
        pass
    _push("record_observations", mirror)   # best effort, never raises
    if n:
        liveness.beat("scan.observations", n)
    return n


def observations(days=None):
    """Observations, with the plausibility assessment filled in.

    Computed on READ, not written back. Every input it needs - liq, fdv,
    age_hours, buys_h1, sells_h1 - has been on every row since the beginning,
    so history classifies exactly and the archive is never rewritten. Nothing
    is deleted and nothing is restated; the flags are derived, not recorded.
    """
    rows = _read(OBS, days)
    for o in rows:
        if o.get("template_suspect") is None:
            try:
                plausibility.annotate(o)
            except Exception:
                pass
    return rows


def _fill_elapsed(o):
    """Historical rows predate actual_elapsed_h but carry both timestamps, so
    the true elapsed time is recoverable exactly. Nothing is rewritten on disk."""
    if o.get("actual_elapsed_h") is None:
        ct, ot = o.get("checked_ts"), o.get("observed_ts")
        if ct and ot:
            o["actual_elapsed_h"] = round((ct - ot) / 3600.0, 4)
    e, h = o.get("actual_elapsed_h"), o.get("horizon_h")
    if o.get("on_time") is None and e is not None and h:
        o["on_time"] = e <= h * DRIFT_TOLERANCE
    return o


def outcomes(days=None):
    """Outcomes, with realizability filled in for any legacy row that predates
    the field. Computed on read so historical data is correct immediately and
    does not depend on a file rewrite succeeding on this mount."""
    rows = _read(OUT, days)
    for o in rows:
        if "realizable" not in o:
            # THE GATE, not the three-check subset. Currently unreachable -
            # 0 of 100,504 rows lack the field - but a door nobody walks
            # through is still a door, and this one used to answer differently
            # from the gate that wrote the rows.
            ok, failed = verify_win(
                o.get("status"), o.get("liq"), o.get("mult"),
                exit_depth=o.get("exit_depth_usd"), pair=o.get("pair"),
                exit_pair=o.get("exit_pair"), elapsed_h=o.get("actual_elapsed_h"),
                reasons=o.get("reasons"), sells_h24=o.get("sells_h24"),
                buys_h24=o.get("buys_h24"))
            o["realizable"] = ok
            o["unrealizable_reason"] = None if ok else "failed " + ", ".join(failed)
            o["realizable_basis"] = "backfilled_on_read"
        # Depth provenance, derived on read so the whole archive carries it
        # immediately and nothing is rewritten. Every input has been on every
        # row since the field existed; where it never existed the answer is
        # still correct, because absent IS unmeasured.
        if "depth_unmeasured" not in o:
            o["depth_unmeasured"] = depth_unmeasured(o.get("exit_depth_usd"))
        # PAIR IDENTITY IS UNVERIFIABLE FOR EVERY ROW WRITTEN BEFORE 2026-09-07.
        # The exit pair was never stored, and the pools involved are delisted,
        # so it cannot be reconstructed - not from the journal, not from the
        # API. These rows must be EXCLUDED from analysis, not merely flagged:
        # 165 of them are realizable 3x+ wins and 85 sit in one $1.2M-$1.35M
        # liquidity band across 53 symbols, which is the signature of many
        # tokens priced off one shared reference pool.
        if "pair_identity_verifiable" not in o:
            o["pair_identity_verifiable"] = ("exit_pair" in o)
        _fill_elapsed(o)
    return rows


# THE RECORD STARTS HERE. Everything before this timestamp is unverifiable:
# no outcome row written earlier carries an exit_pair, the pools are delisted,
# and pair identity cannot be reconstructed from any source. Those rows are not
# wrong - they are unknowable, which is worse, because nothing can settle them.
#
# Instruction 2026-09-07: nothing before this date is cited by anyone - not the
# daily research task, not the memory writer, not a report. A caller that tries
# to quote a pre-epoch win gets an exception, not a quiet empty list.
RECORD_EPOCH = int(dt.datetime(2026, 9, 7, tzinfo=dt.timezone.utc).timestamp())


class UnverifiableRecord(Exception):
    """Raised when something tries to cite a win from before RECORD_EPOCH."""


def assert_citable(rows, what="this result"):
    """Fail LOUDLY if any row predates the epoch. Call before reporting."""
    bad = [r for r in rows
           if (r.get("checked_ts") or r.get("ts") or 0) < RECORD_EPOCH]
    if bad:
        raise UnverifiableRecord(
            f"{what} cites {len(bad)} row(s) from before {dt.datetime.fromtimestamp(RECORD_EPOCH, dt.timezone.utc).date()}. "
            f"Zero of 165 pre-epoch wins are verifiable - no exit_pair was ever "
            f"recorded and the pools are delisted. Use journal.verified_outcomes() "
            f"as the denominator; do not quote the historical record.")
    return rows


def verified_outcomes(days=None, require_identity=True, since_epoch=True):
    """Outcomes that clear the win gate. THE denominator for any win claim.

    Use this, not `outcomes()`, wherever a result is going to be reported.
    Rows predating 2026-09-07 carry no exit pair and cannot pass identity, so
    with the default they are excluded entirely - which is correct, because
    their identity is unknowable rather than merely unrecorded.
    """
    keep = []
    for o in outcomes(days):
        if since_epoch and (o.get("checked_ts") or 0) < RECORD_EPOCH:
            continue
        if require_identity and not o.get("pair_identity_verifiable"):
            continue
        ok, failed = verify_win(
            o.get("status"), o.get("liq"), o.get("mult"),
            exit_depth=o.get("exit_depth_usd"), pair=o.get("pair"),
            exit_pair=o.get("exit_pair"), elapsed_h=o.get("actual_elapsed_h"),
            reasons=o.get("reasons"))
        o["gate_ok"], o["gate_failed"] = ok, failed
        if ok:
            keep.append(o)
    return keep


def scored_pairs():
    """(pair, horizon) already scored, so outcome runs are idempotent."""
    return {(o["pair"], o["horizon_h"]) for o in outcomes()}


# How far past its nominal horizon a check may land and still be treated as
# measuring that horizon. 1.5x is generous; it is set where it is because at
# 1.0-1.5x the 1h cohort still holds 575 of 1,350 rows, enough to analyse.
DRIFT_TOLERANCE = float(os.environ.get("CRYPTO_DRIFT_TOLERANCE", "1.5"))


def record_outcome(pair, observed_ts, horizon_h, price, liq, vol24,
                   base_price, base_liq, symbol="", token="",
                   reasons=None, source=None, price_verdict=None,
                   exit_depth=None, base_price_native=None, price_native=None,
                   exit_pair=None, sells_h24=None, buys_h24=None, mcap=None):
    mult   = (price / base_price) if (base_price and price) else None
    liqchg = ((liq - base_liq) / base_liq * 100) if (base_liq and liq is not None) else None
    if liq is None:
        status = "gone"
    elif base_liq and liq < base_liq * 0.15:
        status = "rugged"
    elif liq < 1000:
        status = "dead"
    else:
        status = "alive"
    # THE GATE. Every check applied in one place, each recorded by name. See
    # verify_win() for why this is a gate and not a checklist.
    _elapsed_pre = ((time.time() - observed_ts) / 3600.0) if observed_ts else None
    quote_check = pricecheck.check_quote_consistency(
        base_price, base_price_native, price, price_native)
    _verdict = price_verdict
    if _verdict is None and not quote_check.get("trustworthy"):
        _verdict = quote_check
    ok, failed = verify_win(status, liq, mult, exit_depth=exit_depth,
                            pair=pair, exit_pair=exit_pair,
                            price_verdict=_verdict, elapsed_h=_elapsed_pre,
                            reasons=reasons, sells_h24=sells_h24,
                            buys_h24=buys_h24)
    why = None if ok else ("failed " + ", ".join(failed))
    if not ok and "source_agreement" in failed and _verdict is not None:
        why += f" ({_verdict.get('confidence')}: {_verdict.get('detail')})"
    checked_ts = int(time.time())
    # THE LABEL IS NOT THE MEASUREMENT. Measured 2026-09-05: the median "1h"
    # row was checked 2.00 hours after observation, 51.4% landed past 2h, p90
    # was 5.23h and the worst 7.01h. The scheduler never checks EARLY - the
    # minimum equals the nominal horizon exactly - so this is one-sided
    # queueing lag, and any analysis that reads horizon_h as elapsed time is
    # measuring a variable window. Record what actually happened.
    elapsed_h = round((checked_ts - observed_ts) / 3600.0, 4) if observed_ts else None
    obj = {"pair": pair, "symbol": symbol, "observed_ts": observed_ts,
           # THE CONTRACT ADDRESS. Accepted as an argument since this function
           # was written, used for milestones, and never written to the row -
           # 0 of 88,235 outcome rows carry one. Standing rule is to key on
           # contract address and never on ticker, and no outcome row on the
           # record could obey it. The fifth field silently dropped here.
           #
           # Purely additive: it changes no label, no gate and no measurement,
           # so it is safe to land inside the locked n=200 window.
           "token": token or None,
           "checked_ts": checked_ts, "horizon_h": horizon_h,
           # Which measurement stood behind `realizable`. True means the quote
           # side was never seen and `liq` was used instead - fine for a
           # balanced pool, off by up to 125x for a one-sided one.
           "depth_unmeasured": depth_unmeasured(exit_depth),
           # THE POOL WE ACTUALLY PRICED. Recorded on every row from
           # 2026-09-07 so pair identity is auditable forever instead of being
           # unrecoverable, which is what made 165 historical wins unverifiable.
           "exit_pair": exit_pair,
           "win_checks_failed": failed,
           "sells_h24": sells_h24,
           "buys_h24": buys_h24,
           "price_native": price_native,
           "base_price_native": base_price_native,
           "quote_asset_entry": quote_check.get("entry_quote_asset"),
           "quote_asset_exit": quote_check.get("exit_quote_asset"),
           "quote_consistent": quote_check.get("trustworthy"),
           "actual_elapsed_h": elapsed_h,
           "on_time": (None if elapsed_h is None
                       else elapsed_h <= horizon_h * DRIFT_TOLERANCE),
           "price_usd": price, "liq": liq, "vol_h24": vol24,
           "mult": mult, "liq_change_pct": liqchg, "status": status,
           # The quote side only. `liq` counts the token side too, which for a
           # one-sided pool is FDV in disguise - measured 2026-09-04 at ~125x
           # the real depth. Nothing downstream should size an exit off `liq`.
           "exit_depth_usd": exit_depth,
           "realizable": ok, "unrealizable_reason": why,
           # WHY the reading looks the way it does. "our index went quiet",
           # "the pool drained" and "the price went to zero" are three facts,
           # and collapsing them into status="gone" destroyed outcome labels.
           "reasons": reasons or [], "price_source": source,
           "price_confidence": (price_verdict or {}).get("confidence"),
           "price_sources_ratio": (price_verdict or {}).get("ratio")}
    _append(OUT, obj)                      # system of record, first
    _push("record_outcomes", [obj])        # best effort, never raises
    liveness.beat("outcome.recorded")

    # Milestone crossings claim themselves, atomically. Nothing downstream may
    # decide it is "the first" by inspecting history and hoping - on 2026-09-01
    # two passes each announced the first realizable 3x when 82 were already on
    # record. A claim is an O_EXCL file create; the OS picks the winner.
    try:
        # mcap=None was hardcoded here when milestones.py was created
        # (f8b03bc, 2026-09-02 04:28Z). check_outcome guards on `if mcap:`, so
        # all four mcap tiers were unreachable from the moment the module
        # shipped. The 1,329 mcap crossings on record are ONE backfill run
        # written in that same minute; not one has ever fired live. Found and
        # fixed 2026-09-07 - five days of crossings were never detected.
        obj["new_milestones"] = milestones.check_outcome(
            token, symbol, mult, ok, mcap=mcap)
    except Exception as e:
        obj["new_milestones"] = []
        print(f"    milestone check failed (non-fatal): {type(e).__name__}")
    # RETURN THE GATE VERDICT THAT WAS RECORDED, not just status/mult.
    #
    # track.py used to decide whether to ANNOUNCE a win by calling the old
    # three-check journal.realizable() - status alive, depth floor,
    # plausibility - while the row itself was gated by the eight-check
    # verify_win(). Two computations, two answers, and the looser one drove
    # the alerts Frank actually sees. Four of one day's twelve pinged wins
    # went through that door. A caller cannot diverge from the row if it is
    # handed the row's own verdict.
    return status, mult, ok, failed


# How far back a pair stays ELIGIBLE after its horizon comes due. This is not a
# cosmetic dial: a pair outside the window is not deferred, it is gone - the
# queue never offers it again and it is never scored at that horizon. At 6h,
# with arrival above slice capacity, that silently discarded 20.8% of the 24h
# horizon. Widening costs nothing, because actual_elapsed_h already records the
# honest elapsed time, so a late check is a late check and not a mislabelled
# one. Raised 2026-09-06; see OUTCOMES.md for the loss table.
PENDING_WINDOW_H = float(os.environ.get("CRYPTO_PENDING_WINDOW_H", "18"))


def pending(horizon_h, window_h=None):
    """First observation of each pair now old enough to score at this horizon
    and not yet scored at it."""
    window_h = PENDING_WINDOW_H if window_h is None else window_h
    done = scored_pairs()
    cutoff = time.time() - horizon_h * 3600
    first = {}
    for o in observations():
        p = o.get("pair")
        if not p:
            continue
        if p not in first or o["ts"] < first[p]["ts"]:
            first[p] = o
    due = [o for p, o in first.items()
           if cutoff - window_h * 3600 <= o["ts"] <= cutoff
           and (p, horizon_h) not in done]
    # FRESHEST-DUE FIRST. The caller takes a slice, and whatever it does not
    # reach this pass gets checked later with a larger elapsed time. Scoring the
    # oldest backlog first pushed every fresh row's check further out and made
    # the drift self-sustaining: the median "1h" check landed at 2.00h. Sorting
    # this way spends the slice on the rows that can still be measured at their
    # nominal horizon. Nothing is dropped - stragglers stay due until the window
    # closes and carry an honest actual_elapsed_h when they are scored.
    due.sort(key=lambda o: o["ts"], reverse=True)
    return due


def stats():
    obs, out = observations(), outcomes()
    by = {}
    for o in out:
        by[o["status"]] = by.get(o["status"], 0) + 1
    span = ((max(o["ts"] for o in obs) - min(o["ts"] for o in obs)) / 3600) if obs else 0
    return dict(observations=len(obs), unique_pairs=len({o["pair"] for o in obs}),
                passed=sum(o["passed"] for o in obs), outcomes=len(out),
                hours_covered=round(span, 1), by_status=by)


def mark_outcomes():
    """Persist realizability onto the historical outcome files. Rows are marked,
    never removed. Each file is backed up first and rewritten in place, because
    this mount allows overwrite but not delete."""
    files = sorted(glob.glob(os.path.join(OUT, "*.jsonl")))
    changed = total = 0
    for fp in files:
        lines = [l for l in open(fp, encoding="utf-8") if l.strip()]
        out, hit = [], 0
        for l in lines:
            try:
                rec = json.loads(l)
            except json.JSONDecodeError:
                out.append(l.rstrip()); continue
            if isinstance(rec, dict) and "horizon_h" in rec and "realizable" not in rec:
                ok, failed = verify_win(
                    rec.get("status"), rec.get("liq"), rec.get("mult"),
                    exit_depth=rec.get("exit_depth_usd"), pair=rec.get("pair"),
                    exit_pair=rec.get("exit_pair"),
                    elapsed_h=rec.get("actual_elapsed_h"),
                    reasons=rec.get("reasons"), sells_h24=rec.get("sells_h24"),
                    buys_h24=rec.get("buys_h24"))
                rec["realizable"] = ok
                rec["unrealizable_reason"] = None if ok else "failed " + ", ".join(failed)
                rec["realizable_basis"] = "backfilled_on_read"
                hit += 1
            out.append(json.dumps(rec, separators=(",", ":")))
        total += len(lines)
        if hit:
            with open(fp + ".bak", "w", encoding="utf-8") as b:
                b.writelines(lines)
            NL = chr(10)
            with open(fp, "w", encoding="utf-8", newline=NL) as f:
                f.write(NL.join(out) + NL)
            changed += hit
        print(f"  {os.path.basename(fp)}: {len(lines)} rows, {hit} newly marked")
    print(f"  marked {changed} of {total} outcome rows; backups written alongside")
    return changed


def backfill(batch=250):
    """Push whatever JSONL history is already on disk. Idempotent: the unique
    constraints mean re-running adds nothing."""
    obs, outs = observations(), outcomes()
    print(f"  on disk: {len(obs)} observations, {len(outs)} outcomes")
    for name, rpc, rows in (("observations", "record_observations", obs),
                            ("outcomes", "record_outcomes", outs)):
        before = PUSH["sent"]
        for i in range(0, len(rows), batch):
            chunk = rows[i:i + batch]
            _push(rpc, chunk)
            print(f"    {name}: {min(i+batch, len(rows))}/{len(rows)}"
                  f"  inserted so far {PUSH['sent'] - before}", flush=True)
        print(f"  {name}: {PUSH['sent'] - before} new rows inserted"
              f"{', ' + str(PUSH['failed']) + ' failed' if PUSH['failed'] else ''}")
    if PUSH["last_error"]:
        print(f"  last error: {PUSH['last_error']}")


if __name__ == "__main__":
    import sys
    if "--backfill" in sys.argv:
        backfill(); raise SystemExit(0)
    if "--mark-outcomes" in sys.argv:
        mark_outcomes(); raise SystemExit(0)
    s = stats()
    print("\n  JOURNAL")
    print(f"  observations  {s['observations']:>7}   unique pairs {s['unique_pairs']:>6}")
    print(f"  passed filter {s['passed']:>7}   outcomes     {s['outcomes']:>6}")
    print(f"  hours covered {s['hours_covered']:>7}")
    if s["by_status"]:
        print(f"  by status: {s['by_status']}")
    print()
