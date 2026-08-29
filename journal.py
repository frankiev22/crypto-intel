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


def realizable(status, liq, mult):
    """(bool, reason_if_not). Could this multiple actually have been taken?"""
    if status != "alive":
        return False, f"status is {status}, not alive"
    if liq is None or liq < MIN_EXIT_LIQ_USD:
        return False, (f"exit liquidity ${(liq or 0):,.0f} is below the "
                       f"${MIN_EXIT_LIQ_USD:,.0f} exit floor")
    if mult is not None and mult > MAX_PLAUSIBLE_MULT:
        return False, (f"{mult:,.0f}x exceeds the {MAX_PLAUSIBLE_MULT}x plausibility "
                       f"ceiling; treat as a data error until checked by hand")
    return True, None

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


def pass_begin(network, stage="full"):
    """Claim the pass. Returns the previous pass's marker if it never finished."""
    stale = None
    try:
        with open(PASS_STATE, encoding="utf-8") as f:
            stale = json.load(f)
    except (OSError, json.JSONDecodeError):
        pass
    os.makedirs(os.path.dirname(PASS_STATE), exist_ok=True)
    with open(PASS_STATE, "w", encoding="utf-8") as f:
        json.dump({"started_ts": int(time.time()), "network": network,
                   "stage": stage, "pid": os.getpid()}, f)
    return stale


def pass_end():
    """Clear the marker. Only reached on a clean finish, which is the point."""
    try:
        os.replace(PASS_STATE, PASS_STATE + ".done")
    except OSError:
        pass


def record_aborted(stale, cause="killed - no clean exit"):
    """A pass that never finished. Recorded so a silent hour is visible."""
    started = stale.get("started_ts")
    obj = {"ts": int(time.time()), "network": stale.get("network"),
           "kind": "aborted_pass", "stage": stale.get("stage"),
           "started_ts": started,
           "ran_for_s": (int(time.time()) - started) if started else None,
           "suspected_cause": cause,
           "pools_returned": 0, "span_s": None, "scanned": 0, "passed": 0}
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


def record(rows, network, pass_score=70):
    """Write every scanned pair, passed AND rejected."""
    now = int(time.time())
    n = 0
    mirror = []
    for r in rows:
        obj = {
            "ts": now, "network": network,
            "pair": r.get("pair"), "token": r.get("addr"), "symbol": r.get("name"),
            "score": r.get("score"), "passed": int(r.get("score", 0) >= pass_score),
            "liq": r.get("liq"), "fdv": r.get("fdv"),
            "vol_h1": r.get("vol_h1"), "vol_h24": r.get("v24"),
            "txns_h1": r.get("txns_h1"), "buys_h1": r.get("buys_h1"),
            "sells_h1": r.get("sells_h1"),
            "price_usd": r.get("price_usd"), "chg_h1": r.get("chg_h1"),
            "chg_h24": r.get("chg_h24"), "age_hours": r.get("age_h"),
            "reasons": r.get("reasons", []), "flags": r.get("flags", []),
            # which weight set produced this score. Without it a 66 from v2 and
            # a 66 from v5 look identical in the scoreboard and are not.
            "weights_version": r.get("weights_version"),
        }
        _append(OBS, obj)      # system of record, first and unconditional
        mirror.append(obj)
        n += 1
    _push("record_observations", mirror)   # best effort, never raises
    return n


def observations(days=None):
    return _read(OBS, days)


def outcomes(days=None):
    """Outcomes, with realizability filled in for any legacy row that predates
    the field. Computed on read so historical data is correct immediately and
    does not depend on a file rewrite succeeding on this mount."""
    rows = _read(OUT, days)
    for o in rows:
        if "realizable" not in o:
            ok, why = realizable(o.get("status"), o.get("liq"), o.get("mult"))
            o["realizable"], o["unrealizable_reason"] = ok, why
    return rows


def scored_pairs():
    """(pair, horizon) already scored, so outcome runs are idempotent."""
    return {(o["pair"], o["horizon_h"]) for o in outcomes()}


def record_outcome(pair, observed_ts, horizon_h, price, liq, vol24,
                   base_price, base_liq, symbol=""):
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
    ok, why = realizable(status, liq, mult)
    obj = {"pair": pair, "symbol": symbol, "observed_ts": observed_ts,
           "checked_ts": int(time.time()), "horizon_h": horizon_h,
           "price_usd": price, "liq": liq, "vol_h24": vol24,
           "mult": mult, "liq_change_pct": liqchg, "status": status,
           "realizable": ok, "unrealizable_reason": why}
    _append(OUT, obj)                      # system of record, first
    _push("record_outcomes", [obj])        # best effort, never raises
    return status, mult


def pending(horizon_h, window_h=6):
    """First observation of each pair now old enough to score at this horizon
    and not yet scored at it."""
    done = scored_pairs()
    cutoff = time.time() - horizon_h * 3600
    first = {}
    for o in observations():
        p = o.get("pair")
        if not p:
            continue
        if p not in first or o["ts"] < first[p]["ts"]:
            first[p] = o
    return [o for p, o in first.items()
            if cutoff - window_h * 3600 <= o["ts"] <= cutoff
            and (p, horizon_h) not in done]


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
                ok, why = realizable(rec.get("status"), rec.get("liq"), rec.get("mult"))
                rec["realizable"], rec["unrealizable_reason"] = ok, why
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
