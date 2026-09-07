"""When did each tracker last fire, LIVE, on real data - and which never have?

WHY THIS EXISTS. Four systems in this repo have produced convincing output while
doing nothing at all:

    the win record      scored outcomes off a pool we did not hold
    the news check      raised NameError every pass for 20 hours, silently
    the volume features computed, then dropped by an allowlist before storage
    the milestones      1,329 mcap crossings that are ONE backfill minute, and
                        a call site passing mcap=None so no tier ever fired

In every case there was output, the output was plausible, and nothing was
running. The common shape is not "we have bugs". It is that ABSENCE OF A SIGNAL
LOOKS EXACTLY LIKE A QUIET PERIOD, and this project's whole subject matter -
new token launches - is genuinely bursty, so quiet is always plausible.

------------------------------------------------------------------------------
THE ONE DESIGN DECISION: THE MANIFEST IS THE SOURCE OF TRUTH, NOT THE REGISTRY.
------------------------------------------------------------------------------

The obvious way to build this is to let components register themselves and then
report on what the registry contains. THAT WOULD HAVE CAUGHT NOTHING. If the
mcap tracker never writes a row, a contents-driven registry lists ten healthy
components and says nothing at all - it reproduces the exact failure it exists
to catch, one level up.

So COMPONENTS below is hardcoded, and the checker iterates the MANIFEST, not the
data. Every declared entry is asked "when did you last fire?" and one that has
never fired answers `never`, which is the alarm condition. mcap_1m would have
alarmed on 2026-09-04, two days after it shipped broken, instead of surviving
five days until it was found by hand.

Three consequences worth stating, because they are the reasons to trust it:

  IT FAILS LOUD.  Delete data/liveness.json, or make it unwritable, and every
      component reads `never` - maximum noise, not silence. The degenerate mode
      of this design is a screaming alarm. That is the property that makes it
      different from the four failures above, all of which degraded to quiet.

  IT DETECTS DRIFT IN BOTH DIRECTIONS.  A beat from a name that is NOT in the
      manifest is also reported. Adding a tracker and forgetting to declare it
      is visible, which is the one hole a manifest-driven design otherwise has.
      (Same idea as fieldguard.py, which diffs produced keys against stored
      keys rather than trusting either side.)

  NEVER-FIRED IS NOT AUTOMATICALLY AN ALARM.  It becomes one when the component
      has been declared for longer than its own threshold. paper.close has
      never fired and should not alarm today - nothing has been open for 24h
      yet. This avoids the failure mode where a new registry screams on day one
      and is muted within a week, which is how the news volume alert died.

WHAT THIS DOES NOT DO, AND MUST NOT BE READ AS DOING: liveness is not
correctness. It proves a code path executed and produced an event. It cannot
tell you the event was right. D1's precision, the paper ledger's outcomes and
the win gate are all still the only evidence about whether the numbers mean
anything. A green registry says "it ran", never "it works".

BACKFILL MUST NEVER BEAT. A replay of history is not a detection - that is the
whole mcap lesson - so only live execution paths call beat().

THRESHOLDS. The hosted runner does NOT run hourly despite its cron. Measured
over the 7 days to 2026-09-07, 46 intervals: median gap 3.4h, p90 5.0h, MAX
5.5h - about 7 passes a day, 29% of nominal. GitHub deprioritises scheduled
workflows under load. So a per-pass threshold of 12h is ~2x the worst observed
gap: late enough never to fire on normal scheduling, early enough to catch a
real outage within half a day. Anything marked `provisional` below has no
measured cadence yet and should be tightened once it has one.
"""
import json, os, time, datetime as dt

BASE = os.path.dirname(os.path.abspath(__file__))
REG = os.path.join(BASE, "data", "liveness.json")
LEDGER_DIR = os.path.join(BASE, "data", "liveness")

# name -> (max_age_h, declared instant, basis, what a beat means)
#
# `declared` is an INSTANT, not a date. Grace runs from the moment the beat was
# wired in, so a component gets one full threshold window to fire before
# `never` becomes an alarm. Using a date would start the clock at midnight and
# make every 12h component alarm the moment it shipped - a registry that
# screams on day one gets muted inside a week, which is how the news volume
# alert died.
COMPONENTS = {
    "scan.observations":    (12, "2026-09-07T12:05:00Z", "measured",
                             "the scanner journalled at least one observation"),
    "outcome.recorded":     (12, "2026-09-07T12:05:00Z", "measured",
                             "an outcome row was written at some horizon"),
    "milestone.mcap":       (48, "2026-09-07T12:05:00Z", "provisional",
                             "a token crossed 100k/200k/1m/5m and was claimed LIVE"),
    "milestone.realizable": (48, "2026-09-07T12:05:00Z", "measured",
                             "a realizable 2x/3x/10x was claimed"),
    "milestone.graduated":  (96, "2026-09-07T12:05:00Z", "provisional",
                             "a token crossed the pump.fun graduation threshold"),
    "watchlist.sweep":      (12, "2026-09-07T12:05:00Z", "measured",
                             "the approach band was re-checked"),
    "paper.sweep":          (12, "2026-09-07T12:05:00Z", "measured",
                             "the paper log looked for positions to close"),
    "paper.open":           (48, "2026-09-07T12:05:00Z", "provisional",
                             "a paper position was opened"),
    "paper.close":          (72, "2026-09-07T12:05:00Z", "provisional",
                             "a paper position was closed - the losers, the evidence"),
    "detector.drift":       (12, "2026-09-07T12:05:00Z", "measured",
                             "the template fingerprint was re-measured"),
    "news.freshness":       (12, "2026-09-07T12:05:00Z", "measured",
                             "per-outlet news staleness was checked"),
    "fieldguard.check":     (12, "2026-09-07T12:05:00Z", "measured",
                             "produced fields were diffed against stored fields"),
}


def _load():
    try:
        with open(REG, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        # Missing or corrupt reads as EMPTY, which makes every component report
        # `never`. That is deliberate: see IT FAILS LOUD above.
        return {}


def beat(name, n=1, detail=None):
    """Record that `name` just fired, live. Never raises - a health probe that
    can break the pass it is measuring is worse than no probe."""
    try:
        reg = _load()
        now = int(time.time())
        cur = reg.get(name) or {}
        reg[name] = {"last_ts": now,
                     "last_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
                     "count": (cur.get("count") or 0) + n,
                     "first_ts": cur.get("first_ts") or now,
                     "detail": detail}
        os.makedirs(os.path.dirname(REG), exist_ok=True)
        tmp = REG + ".tmp"
        with open(tmp, "w", encoding="utf-8", newline="
") as f:
            json.dump(reg, f, indent=1, ensure_ascii=False)
        os.replace(tmp, REG)          # atomic; a killed pass cannot truncate it
        os.makedirs(LEDGER_DIR, exist_ok=True)
        path = os.path.join(LEDGER_DIR,
                            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m") + ".jsonl")
        with open(path, "a", encoding="utf-8", newline="
") as f:
            f.write(json.dumps({"name": name, "ts": now, "n": n,
                                "detail": detail}, ensure_ascii=False) + "\n")
        return True
    except Exception:
        return False


def status():
    """Every DECLARED component, whether or not it has ever been seen."""
    reg = _load()
    now = time.time()
    out = []
    for name, (max_age_h, declared, basis, what) in sorted(COMPONENTS.items()):
        r = reg.get(name) or {}
        last = r.get("last_ts")
        try:
            decl_ts = dt.datetime.strptime(
                declared, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            decl_ts = now
        age_h = ((now - last) / 3600.0) if last else None
        declared_h = (now - decl_ts) / 3600.0
        if last is None:
            # Never fired. Only an alarm once it has had longer than its own
            # threshold to do so - otherwise a new declaration screams on day
            # one and gets muted, which is how alerts die.
            verdict = "never" if declared_h > max_age_h else "pending"
        elif age_h > max_age_h:
            verdict = "stale"
        else:
            verdict = "ok"
        out.append({"name": name, "verdict": verdict, "age_h": age_h,
                    "max_age_h": max_age_h, "count": r.get("count") or 0,
                    "declared": declared, "declared_h": declared_h,
                    "basis": basis, "what": what,
                    "last_at": r.get("last_at")})
    # Drift the other way: beating without being declared.
    for name in reg:
        if name not in COMPONENTS:
            out.append({"name": name, "verdict": "undeclared", "age_h": None,
                        "max_age_h": None,
                        "count": (reg[name] or {}).get("count") or 0,
                        "declared": None, "declared_h": None, "basis": None,
                        "what": "beats but is not in COMPONENTS - declare it or remove it",
                        "last_at": (reg[name] or {}).get("last_at")})
    return out


def line(st=None):
    """The daily line. Groups by verdict so the bad news is not buried."""
    st = st or status()
    by = {}
    for s in st:
        by.setdefault(s["verdict"], []).append(s)
    ls = [f"liveness: {len(by.get('ok', []))} ok, {len(by.get('stale', []))} stale, "
          f"{len(by.get('never', []))} never, {len(by.get('pending', []))} pending, "
          f"{len(by.get('undeclared', []))} undeclared"]
    for v in ("never", "stale", "undeclared", "pending"):
        for s in by.get(v, []):
            if s["age_h"] is not None:
                age = f"{s['age_h']:.1f}h ago"
            elif v == "pending":
                age = f"not fired yet, {max(0.0, s['declared_h']):.1f}h into grace"
            else:
                age = f"NEVER, {s['declared_h']:.0f}h since declared"
            ls.append(f"  {v.upper():<10} {s['name']:<22} {age}"
                      + (f" (limit {s['max_age_h']}h)" if s["max_age_h"] else ""))
    return "\n".join(ls)


def check(record=None, verbose=True):
    """Emit a finding per dead component. Health lane, keyed per component."""
    st = status()
    if verbose:
        print("  " + line(st).replace("\n", "\n  "))
    for s in st:
        if s["verdict"] not in ("never", "stale", "undeclared"):
            continue
        if not record:
            continue
        if s["verdict"] == "never":
            msg = (f"{s['name']} has NEVER fired in the {s['declared_h']:.0f}h "
                   f"since it was declared")
            detail = (f"A tracker that has never fired is broken or unnecessary, "
                      f"and which one it is has to be decided, not left. "
                      f"Expected: {s['what']}. Threshold {s['max_age_h']}h "
                      f"({s['basis']}).")
        elif s["verdict"] == "stale":
            msg = (f"{s['name']} last fired {s['age_h']:.1f}h ago, over its "
                   f"{s['max_age_h']}h threshold")
            detail = (f"Expected: {s['what']}. It has fired {s['count']} times "
                      f"before, so the path works and something stopped it.")
        else:
            msg = f"{s['name']} is recording beats but is not declared in COMPONENTS"
            detail = ("Declare it with a threshold, or remove the beat. An "
                      "undeclared component is invisible to this check.")
        record("liveness", s["name"], msg, detail=detail)
    return st


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    st = status()
    print(line(st))
    bad = [s for s in st if s["verdict"] in ("never", "stale", "undeclared")]
    sys.exit(1 if bad else 0)
