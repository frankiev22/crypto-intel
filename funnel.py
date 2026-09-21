"""THE FUNNEL: what each pass reached, what it dropped, and what it is about to lose.

⛔ WHY THIS EXISTS. On 2026-09-19/20 the pipeline was discarding data at both
ends and nothing on disk said so:

  * scan coverage ran 33-40% - ~200 pools seen, ~70 processed - with the
    remainder carried hour to hour (109 -> 143 over one night);
  * 1,129 outcome rows stood due, 121 of them due to age out UNSCORED within
    the hour, and a row that ages out is gone: `journal.pending()` never offers
    it again and the label cannot be backfilled;
  * the graduation ledger's backlog went 306 -> 880 and its lag 5.2h -> 12.0h.

Every one of those numbers already EXISTED in the process. `track.LAST_COVERAGE`
was populated on every pass and **read by nothing**; queue depth was printed to
stdout and then thrown away with the process. That is the same class of failure
as standing rule 16: the work was done, the output was never persisted, so the
degradation was invisible until someone read a log by hand.

This module writes those numbers to `data/funnel/` on every pass, beats the
liveness registry with ROWS (never a bare heartbeat), and alarms when the funnel
narrows. ⛔ Absent numbers are recorded as null and render as "unknown" - never
as 0, which would read as "nothing was dropped" (standing rule 5).

⚠️ THE THRESHOLDS BELOW ARE OPERATIONAL ALARM LEVELS, NOT A MEASUREMENT BAR.
They were chosen on 2026-09-20 AFTER reading that night's telemetry, which is
the right way round for an alarm (you calibrate it against the failure you just
had) and the wrong way round for a finding. Nothing here may be quoted as a
result; `PRECOMMIT_*.md` files remain the only place a measurement threshold is
fixed before the data is seen.
"""
import datetime as dt
import json
import os
import time

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "data", "funnel")
LATEST = os.path.join(DIR, "latest.json")

# Alarm levels. See the warning in the module docstring.
SCAN_COVERAGE_FLOOR = 0.80      # below this, the scan is dropping pools it reached for
QUEUE_TOTAL_ALARM = 750         # standing outcome queue across all horizons
GRAD_LAG_ALARM_H = 3.0          # graduation ledger lag
GRAD_BACKLOG_ALARM = 250        # graduation signatures waiting
# Any row at all about to age out unscored is an alarm: it is unrecoverable.
EXPIRING_ALARM = 1


def _rows_path(now=None):
    n = dt.datetime.fromtimestamp(now or time.time(), dt.timezone.utc)
    return os.path.join(DIR, f"{n:%Y-%m}.jsonl")


def _scan():
    """Coverage of the discovery window, from the scanner's own last pass."""
    try:
        import scanner
        ls = scanner.LAST_SCAN
    except Exception:
        return None
    seen, proc = ls.get("pools"), ls.get("reached")
    if seen is None and proc is None:
        return None
    cov = (proc / seen) if (seen and proc is not None) else None
    return {"pools_seen": seen, "pools_reached": proc,
            "coverage": None if cov is None else round(cov, 4),
            "enriched": ls.get("enriched"), "failed": ls.get("failed"),
            "truncated": bool(ls.get("budget_hit")),
            "truncate_reason": ls.get("truncate_reason"),
            "carried_forward": ls.get("carried_forward"),
            "carried_in": ls.get("pools_carried"),
            "skipped_addresses": len(ls.get("skipped") or [])}


def _outcomes():
    """Per-horizon queue depth, from the scoring pass that just ran.

    ⛔ Only horizons scored THIS pass appear. A horizon that did not run is
    absent, not zero - `collect.py` skipping the 24h horizon for want of budget
    is exactly the failure this file has to make visible.
    """
    try:
        import track
        lc = track.LAST_COVERAGE
    except Exception:
        return None
    if not lc:
        return None
    # ⭐ THE PRIMARY PRICE SOURCE, PER HORIZON (2026-09-21). `track.HORIZON_HEALTH`
    # holds primary_ok / primary_miss for the pass that just ran and was read by
    # nothing but the daily Discord line, so the only durable record of the rate
    # was the TEXT of a lookup-outage finding - which is written ONLY when the
    # rate is already under the floor. That is a biased sample: you can see the
    # crossings and never the trend. Asked "is Dexscreener degrading?" on
    # 2026-09-21 the honest answer was "the journal cannot say", which is the
    # same hole this file exists to close.
    #
    # ⚠️ Persisted, NOT alarmed. track.score_horizon already alarms per pass
    # against its own pre-committed per-horizon floor. A trend threshold would
    # have to be pre-committed against a baseline we do not have yet, and
    # inventing one after reading the data is what standing rule 6 forbids.
    try:
        hh = track.HORIZON_HEALTH or {}
    except Exception:
        hh = {}
    out = {}
    for h, v in sorted(lc.items()):
        row = {"due": v.get("due"), "scored": v.get("scored_this_pass"),
               "not_reached": v.get("not_reached"),
               "expiring_before_next_pass": v.get("expiring_before_next_pass"),
               "coverage": None if v.get("coverage") is None else round(v["coverage"], 4),
               "slice_limit": v.get("slice_limit")}
        g = hh.get(h) or {}
        ok, miss = g.get("primary_ok"), g.get("primary_miss")
        seen = None if (ok is None and miss is None) else (ok or 0) + (miss or 0)
        row.update(primary_ok=ok, primary_miss=miss, primary_seen=seen,
                   # ⛔ Unknown is None, never 0 - a 0% rate and "nobody looked"
                   # are different facts (standing rule 5).
                   primary_rate=(None if not seen else round((ok or 0) / seen, 4)),
                   primary_floor=_floor(h))
        out[f"{h}h"] = row
    return out


def _floor(h):
    """This horizon's pre-committed primary-source floor, or None if unreadable."""
    try:
        import track
        return track.primary_floor(h)
    except Exception:
        return None


def _graduations():
    try:
        with open(os.path.join(BASE, "data", "graduations", "index.json"),
                  encoding="utf-8") as f:
            g = json.load(f)
    except Exception:
        return None
    lag = g.get("lag_s")
    return {"backlog": g.get("backlog"), "lag_s": lag,
            "lag_h": None if lag is None else round(lag / 3600.0, 2),
            "processed_last_pass": g.get("processed"),
            "failed_txs_skipped": g.get("failed_txs_skipped"),
            "retry_queue": g.get("retry_queue"), "accounted": g.get("accounted")}


def _lookups():
    """What the batched prefetch did - the fix's own output, per pass."""
    try:
        import sources
        p = dict(sources.PREFETCH_STATS)
    except Exception:
        return None
    if not p.get("asked"):
        return None
    p["hit_rate"] = round(p["found"] / p["asked"], 4) if p["asked"] else None
    return p


def alarms(row):
    """The list of reasons this funnel is losing data. Empty means healthy."""
    out = []
    sc = row.get("scan") or {}
    if sc.get("coverage") is not None and sc["coverage"] < SCAN_COVERAGE_FLOOR:
        out.append(f"scan coverage {sc['coverage']:.1%} below {SCAN_COVERAGE_FLOOR:.0%}: "
                   f"{sc.get('pools_seen')} pools seen, {sc.get('pools_reached')} reached, "
                   f"{sc.get('carried_forward')} carried forward")
    oc = row.get("outcomes") or {}
    exp = {h: v.get("expiring_before_next_pass") for h, v in oc.items()
           if (v.get("expiring_before_next_pass") or 0) >= EXPIRING_ALARM}
    if exp:
        out.append("rows will age out UNSCORED before the next pass and cannot be "
                   "recovered: " + ", ".join(f"{v} at {h}" for h, v in exp.items()))
    due = sum(v.get("due") or 0 for v in oc.values())
    if oc and due >= QUEUE_TOTAL_ALARM:
        out.append(f"outcome queue {due} due across {len(oc)} horizon(s), "
                   f"at or above {QUEUE_TOTAL_ALARM}")
    g = row.get("graduations") or {}
    if (g.get("lag_h") or 0) >= GRAD_LAG_ALARM_H:
        out.append(f"graduation ledger {g['lag_h']}h behind, backlog {g.get('backlog')}")
    elif (g.get("backlog") or 0) >= GRAD_BACKLOG_ALARM:
        out.append(f"graduation backlog {g['backlog']}, at or above {GRAD_BACKLOG_ALARM}")
    return out


def record(stage=None, origin=None, verbose=True, record_finding=None, now=None):
    """Write this pass's funnel row, beat liveness, and alarm. Returns the row."""
    row = {"ts": int(now or time.time()), "stage": stage,
           "origin": origin or os.environ.get("CRYPTO_ORIGIN") or None,
           "scan": _scan(), "outcomes": _outcomes(),
           "graduations": _graduations(), "lookups": _lookups()}
    row["alarms"] = alarms(row)
    # Nothing to say: no scan, no scoring, no ledger. Do not write a row that
    # would read as "everything was fine".
    if not any(row[k] for k in ("scan", "outcomes", "graduations")):
        return None
    os.makedirs(DIR, exist_ok=True)
    with open(_rows_path(row["ts"]), "a", encoding="utf-8") as f:
        f.write(json.dumps(row) + "\n")
    try:
        import safeload
        safeload.save_json(LATEST, row, allow_empty=True)
    except Exception:
        pass
    try:
        import liveness
        liveness.beat("funnel.recorded", 1,
                      detail="; ".join(row["alarms"])[:180] or "no alarms")
    except Exception:
        pass
    if verbose:
        print("  " + line(row))
        for a in row["alarms"]:
            print(f"    ⛔ {a}")
    if row["alarms"] and record_finding:
        record_finding("funnel-narrowing", stage or "pass",
                       row["alarms"][0][:200],
                       detail=("Every number here is per pass, from data/funnel/. "
                               + " | ".join(row["alarms"])))
    return row


def _pct(x):
    return "unknown" if x is None else f"{x:.0%}"


def line(row):
    """One line for a pass log. Unknown is 'unknown', never 0."""
    sc, oc, g = row.get("scan") or {}, row.get("outcomes") or {}, row.get("graduations") or {}
    bits = []
    if sc:
        bits.append(f"scan {_pct(sc.get('coverage'))} "
                    f"({sc.get('pools_reached')}/{sc.get('pools_seen')}, "
                    f"{sc.get('carried_forward')} carried)")
    if oc:
        due = sum(v.get("due") or 0 for v in oc.values())
        exp = sum(v.get("expiring_before_next_pass") or 0 for v in oc.values())
        bits.append(f"queue {due} due, {exp} about to age out")
        pr = [(h, v) for h, v in sorted(oc.items()) if v.get("primary_rate") is not None]
        if pr:
            bits.append("primary source " + ", ".join(
                f"{h} {v['primary_rate']:.0%} of {v['primary_seen']}"
                + ("" if v.get("primary_floor") is None
                   else ("" if v["primary_rate"] >= v["primary_floor"] else " UNDER FLOOR"))
                for h, v in pr))
    if g:
        bits.append(f"graduations backlog {g.get('backlog')}, "
                    f"lag {'unknown' if g.get('lag_h') is None else str(g['lag_h']) + 'h'}")
    lk = row.get("lookups") or {}
    if lk.get("calls"):
        bits.append(f"pair lookups {lk['asked']} in {lk['calls']} calls")
    return "funnel: " + ("; ".join(bits) if bits else "nothing measured this pass")


def rows(months=2):
    out = []
    try:
        names = sorted(f for f in os.listdir(DIR) if f.endswith(".jsonl"))[-months:]
    except OSError:
        return out
    for n in names:
        with open(os.path.join(DIR, n), encoding="utf-8") as f:
            for line_ in f:
                try:
                    out.append(json.loads(line_))
                except ValueError:
                    continue
    return out


def summary(hours=24, now=None):
    """The funnel over the last `hours`, for the dashboard and the site."""
    cut = (now or time.time()) - hours * 3600
    rs = [r for r in rows() if r.get("ts", 0) >= cut]
    scans = [r["scan"]["coverage"] for r in rs
             if (r.get("scan") or {}).get("coverage") is not None]
    exp = sum((v.get("expiring_before_next_pass") or 0)
              for r in rs for v in (r.get("outcomes") or {}).values())
    last = rs[-1] if rs else None
    med = None
    if scans:
        s = sorted(scans)
        med = s[len(s) // 2] if len(s) % 2 else (s[len(s) // 2 - 1] + s[len(s) // 2]) / 2
    prim = {}
    for r in rs:
        for h, v in (r.get("outcomes") or {}).items():
            if v.get("primary_rate") is not None:
                prim.setdefault(h, []).append(v["primary_rate"])
    prim_med = {}
    for h, v in prim.items():
        v = sorted(v)
        prim_med[h] = {"median": round(v[len(v) // 2] if len(v) % 2 else
                                      (v[len(v) // 2 - 1] + v[len(v) // 2]) / 2, 4),
                       "n_passes": len(v), "min": v[0], "max": v[-1]}
    return {"passes": len(rs), "hours": hours,
            "primary_rate_by_horizon": prim_med or None,
            "scan_coverage_median": None if med is None else round(med, 4),
            "scan_coverage_n": len(scans),
            "rows_expiring_unscored": exp if rs else None,
            "queue_due_last": (None if not last else
                               sum(v.get("due") or 0 for v in (last.get("outcomes") or {}).values())
                               or None),
            "graduation_backlog_last": (last or {}).get("graduations", {}).get("backlog") if last else None,
            "graduation_lag_h_last": (last or {}).get("graduations", {}).get("lag_h") if last else None,
            "alarms_last": (last or {}).get("alarms") if last else None}


if __name__ == "__main__":
    import pprint
    pprint.pprint(summary())
