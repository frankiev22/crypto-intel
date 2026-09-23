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

import safeload

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
    # ⭐ THE FUNNEL, 2026-09-20. Coverage and queue depth as first-class rows.
    # A pass that reaches 35% of what it sees is not a healthy pass, and until
    # this component existed nothing on disk said which it had been.
    "funnel.recorded":      (12, "2026-09-20T06:00:00Z", "measured",
                             "a pass wrote what it reached and what it dropped"),
    # ⭐ V3, SCHEDULED FROM 2026-09-18. The sweep runs every pass, so it has a
    # real threshold: 12h matches paper.sweep, which shares the stage.
    # ⭐ THE ONE ARTIFACT FRANK ACTUALLY LOOKS AT. Rebuilt every pass from
    # 2026-09-18; before that only when somebody ran dashboard.py by hand, so it
    # went stale silently while every number behind it stayed current. 12h
    # matches the collector's own bar - the page is only as fresh as the pass.
    "dashboard.build":      (12, "2026-09-18T16:00:00Z", "measured",
                             "data/dashboard.html was rebuilt from the journal"),
    "paperv3.sweep":        (12, "2026-09-18T15:00:00Z", "measured",
                             "the v3 ledger looked for positions to close"),
    # ⭐ WHAT IS RUNNING NOW. Rows are counted by READING THE FILES BACK, not
    # from what market.build() meant to write. Runs in every full pass, so the
    # collector's own 12h bar applies. A pass whose every source failed beats
    # with 0 rows and reads `empty`, not healthy.
    "market.snapshot":      (12, "2026-09-18T23:00:00Z", "measured",
                             "data/market/*.json rebuilt, rows read back from disk"),
    # ⭐ THE TRACKED UNIVERSE (docs/UNIVERSE.md). Counts MEMBERS read back from
    # members.json - an unreadable file beats 0 and reads `empty`, never healthy.
    "universe.members":     (12, "2026-09-19T01:00:00Z", "measured",
                             "data/universe/members.json rewritten, members read back"),
    # ⭐ C14. Rows appended to the ledger, every signature accounted for. ~47
    # graduations an hour measured 2026-09-19, so a 12h pass with none is wrong.
    "graduations.ledger":   (12, "2026-09-19T01:00:00Z", "measured",
                             "migration-authority signatures paged and classified"),
    # ⛔⛔ THE HELIUS POOL RECEIVER, AND IT IS HERE BECAUSE IT FAILED SILENTLY.
    # It took real rows at 2026-09-23 03:53:13Z, 1,571 of them by 04:06:40Z, and
    # by the time anyone looked it was watching ZERO addresses with the database
    # refusing connections. Thirteen minutes to break, most of a day to notice,
    # because nothing counted its rows.
    #
    # `n` is the receiver's own `rows_total`, read back over HTTP from the
    # deployed function - not the fact that heliushook.ensure() ran. A pass where
    # the reconciler fires and the row count has not moved reads as producing
    # nothing, which is exactly what it is doing. 12h matches the collector.
    "chainevents.rows":     (12, "2026-09-23T12:00:00Z", "provisional",
                             "the deployed receiver reported its stored row count"),
    # ⛔ Counts crossings EVALUATED, silent ones included - not alerts sent.
    # 61 crossings landed in the 24h to 2026-09-23, so a pass that evaluates none
    # for 12 hours means the lane is dead, not that the market went quiet.
    # ⛔ Counts quote assets KNOWN, not read this pass: a pass with nothing
    # stale legitimately reads zero, and a registry that has stopped growing is
    # not the same as one that has stopped running.
    "legs.registry":       (12, "2026-09-23T13:00:00Z", "provisional",
                             "the quote-asset registry published what each "
                             "issuer can do to the asset you are paid in"),
    "crossing.decisions":  (12, "2026-09-23T13:00:00Z", "provisional",
                             "track.score_all evaluated every new mcap crossing "
                             "against the pre-committed depth bar"),
    # ⛔ AND THESE TWO HAVE NO THRESHOLD, DELIBERATELY.
    #
    # An entry is a MARKET event, not a schedule event. RULE_V3 is strictly
    # stricter than v1 - amm, both authorities dead, a sell side, holders>=100
    # AND a TRADEABLE $100 round trip - and the entry rate under it has never
    # been observed, because nothing ever ran it. Any staleness bar I set today
    # would be invented, and an alarm that fires when nothing is wrong is the
    # failure this repo documented and I shipped again this morning.
    #
    # `None` means DECLARED AND COUNTED, NEVER ALARMED. It is not a way to
    # silence a component: the verdict is `unmetered`, which is printed, and the
    # threshold gets set from data once there are 30 entries or 14 days,
    # whichever comes first. Recorded in PRECOMMIT_paper_v3.md.
    "paperv3.open":         (None, "2026-09-18T15:00:00Z", "unmetered",
                             "a v3 position was opened at a real quoted fill"),
    "paperv3.close":        (None, "2026-09-18T15:00:00Z", "unmetered",
                             "a v3 position was closed against a live sell quote"),
}

# ⛔ RETIRED: declared components whose source was shut down ON PURPOSE. They
# stay declared, so their history reads, but they are never judged stale again.
#
# 2026-09-19: the relay reported "paper.sweep is 84 hours stale - the close side
# is dead" and asked for a sweep to be added to a launcher. The sweep was never
# missing. The v1 ledger was QUARANTINED at 4676ce3, and a frozen ledger's sweep
# returns before it beats (paper.sweep, by design), so the registry went on
# holding a deliberately stopped component to a 12h bar and reported the stop as
# an outage. An alarm that is true-by-construction is the one that teaches
# everyone to ignore the registry.
#
# ⭐ The inverse is the useful alarm: a retired component that BEATS UNATTENDED
# after its retirement is writing to a ledger that is meant to be frozen. That
# verdict is `undead`, and it alarms. Manual beats (tests, hand runs) are not
# counted, the same as everywhere else in this module.
RETIRED = {
    name: ("2026-09-17T23:37:44Z",
           "v1 ledger QUARANTINED (fills on the Dexscreener mid; PRECOMMIT_paper_v3.md "
           "section 2). Its sweep returns before beating. Superseded by paperv3.*")
    for name in ("paper.sweep", "paper.open", "paper.close")
}


def _load():
    """Absent -> {}. Present-but-corrupt -> safeload.LoadFailed.

    The original lumped these together, reasoning that empty makes every
    component report `never` and `never` is loud. That is CORRECT for status(),
    which only reads. It is destructive in beat(), which loads, mutates and
    atomically writes back - there "unreadable" became "empty" and then became
    true on disk. The two states are now distinct and each caller chooses.
    """
    return safeload.load_json(REG)


# WHO CALLED. A beat proves a code path ran, not that the SYSTEM ran it.
# On 2026-09-14 a hand-run sweep beat paper.sweep and put this registry back to
# ok for twelve hours while the scheduled collector still never called it; on
# 9/15 a killed ad-hoc full pass did the same for watchlist.sweep. A registry
# turned green by manual runs is the quiet-period failure one level up. So each
# beat records its origin and staleness is judged ONLY on unattended beats: the
# GitHub runner, or the scheduled task, which sets CRYPTO_ORIGIN=scheduled on
# every staged command. Anything else is "manual" - shown, never counted.
# ⛔ AND A HOSTED RUNNER IS NOT AUTOMATICALLY UNATTENDED.
#
# `origin()` returned "runner" for every GitHub Actions run, which meant a
# `workflow_dispatch` I pressed myself was recorded identically to a cron fire.
# The one question that matters - "did a pass run that nobody triggered" - was
# therefore not answerable from the journal at all; it had to be read off
# `gh run list` and correlated by timestamp, which is standing rule 16 exactly:
# taking the answer from somewhere other than the thing that claims it.
#
# It also flattered us in the direction we were already wrong. 87% of all passes
# were manual, every "healthy collector" number was carried by a human pressing
# a button, and a dispatch tagged "runner" is precisely that human wearing the
# machine's name.
#
# ⚠️ Historical rows tagged "runner" are a MIX of both and stay counted as
# unattended - they cannot be re-derived, and rule 8 says they are not rewritten.
# Only rows written from here on carry the distinction.
DISPATCH = "dispatch"
UNATTENDED = ("runner", "scheduled")


def origin():
    if os.environ.get("GITHUB_ACTIONS"):
        ev = os.environ.get("GITHUB_EVENT_NAME") or ""
        if ev == "schedule":
            return "scheduled"          # it fired on its own. This is the bar.
        if ev in ("workflow_dispatch", "repository_dispatch"):
            return DISPATCH             # a human pressed the button
        # push, pull_request, anything else: hosted, but somebody caused it.
        return DISPATCH if ev else "runner"
    return os.environ.get("CRYPTO_ORIGIN") or "manual"


def beat(name, n=1, detail=None):
    """Record that `name` just fired, live. Never raises - a health probe that
    can break the pass it is measuring is worse than no probe.

    ⛔ `n` IS THE ROW COUNT, AND FIRING IS NOT THE SAME AS PRODUCING.
    "The liveness registry counts ROWS, not beats. A heartbeat with zero rows
    behind it is a failure, and right now it reads as health." - Frank,
    2026-09-18. He is describing a real defect: this function used to refresh
    `last_ts` on every call, so a scan that journalled NOTHING still looked
    alive. The Claude desktop task fired hourly for two days while collecting
    zero rows and read as healthy the whole time.

    So a beat now records TWO clocks. `last_ts` is when it fired; `last_rows_ts`
    is when it last fired WITH ROWS BEHIND IT. `status()` judges on the second.
    A component that fires empty is reported as producing nothing, which is what
    it is doing.
    """
    try:
        reg = _load()
        now = int(time.time())
        at = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
        who = origin()
        cur = reg.get(name) or {}
        rows = int(n or 0)
        new = {"last_ts": now, "last_at": at,
               "count": (cur.get("count") or 0) + n,
               "first_ts": cur.get("first_ts") or now,
               "detail": detail, "last_origin": who,
               # ⭐ Firings and rows, counted separately and never conflated.
               "firings": (cur.get("firings") or 0) + 1,
               "rows_total": (cur.get("rows_total") or 0) + rows,
               "empty_firings": (cur.get("empty_firings") or 0)
                                + (0 if rows > 0 else 1)}
        if rows > 0:
            new["last_rows_ts"], new["last_rows_at"] = now, at
            if who in UNATTENDED:
                new["last_unattended_rows_ts"] = now
        else:
            for k in ("last_rows_ts", "last_rows_at", "last_unattended_rows_ts"):
                if cur.get(k) is not None:
                    new[k] = cur[k]
        if who in UNATTENDED:
            new["last_unattended_ts"], new["last_unattended_at"] = now, at
        elif "last_origin" not in cur and cur.get("last_ts"):
            # A row from before origins were recorded. Its origin is unknowable,
            # so it is carried as unattended once; every beat after is classified.
            new["last_unattended_ts"] = cur.get("last_ts")
            new["last_unattended_at"] = cur.get("last_at")
        elif cur.get("last_unattended_ts"):
            new["last_unattended_ts"] = cur["last_unattended_ts"]
            new["last_unattended_at"] = cur.get("last_unattended_at")
        reg[name] = new
        # atomic, and refuses to write empty over a populated registry
        safeload.save_json(REG, reg)
        os.makedirs(LEDGER_DIR, exist_ok=True)
        path = os.path.join(LEDGER_DIR,
                            dt.datetime.now(dt.timezone.utc).strftime("%Y-%m") + ".jsonl")
        with open(path, "a", encoding="utf-8", newline="\n") as f:
            f.write(json.dumps({"name": name, "ts": now, "n": n,
                                "detail": detail, "origin": who},
                               ensure_ascii=False) + "\n")
        return True
    except safeload.LoadFailed as e:
        # Ahead of the blanket handler: the registry is there but unreadable,
        # so this beat is dropped rather than written on top of it.
        print(f"  liveness: registry unreadable, beat NOT written - {e}")
        return False
    except Exception:
        return False


def status():
    """Every DECLARED component, whether or not it has ever been seen."""
    try:
        reg = _load()
    except safeload.LoadFailed as e:
        # Do NOT report 11 live components as `never` because one file failed
        # to parse. That is the exact mislabelling this module exists to catch.
        raise RuntimeError(f"liveness registry unreadable, refusing to report "
                           f"every component as never-fired: {e}") from e
    now = time.time()
    out = []
    for name, (max_age_h, declared, basis, what) in sorted(COMPONENTS.items()):
        r = reg.get(name) or {}
        # ⛔ JUDGED ON ROWS, NOT FIRINGS. `last_fired` is kept alongside so a
        # component that is running but producing nothing is visibly distinct
        # from one that is not running at all - those need different fixes and
        # conflating them is how a dead collector read as healthy for two days.
        last = r.get("last_unattended_ts") if "last_origin" in r else r.get("last_ts")
        _rows_clock = (r.get("last_unattended_rows_ts") if "last_origin" in r
                       else r.get("last_rows_ts"))
        # ⚠️ FALL BACK when the rows clock is absent - BUT NOT when the entry has
        # fired and produced nothing. `last_unattended_rows_ts` is new, so an
        # entry that produced rows before this change has none, and reporting it
        # dead because a FIELD is young is the same mislabelling in a new
        # costume. A component with firings and rows_total 0, though, has been
        # measured and came back empty: falling back there would let the firing
        # clock rescue exactly the case this whole change exists to expose.
        never_produced = (r.get("firings") is not None
                          and not r.get("rows_total"))
        if _rows_clock is not None:
            last = _rows_clock
        elif never_produced:
            last = None
        manual_h = None
        if (r.get("last_origin") not in (None,) + UNATTENDED and r.get("last_ts")
                and r.get("last_ts") != last):
            manual_h = (now - r["last_ts"]) / 3600.0
        try:
            decl_ts = dt.datetime.strptime(
                declared, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc).timestamp()
        except ValueError:
            decl_ts = now
        age_h = ((now - last) / 3600.0) if last else None
        declared_h = (now - decl_ts) / 3600.0
        # ⭐ "EMPTY" IS A DISTINCT VERDICT FROM "STALE", and the distinction is
        # the whole point of tracking rows: a component that is firing on time
        # and producing nothing is BROKEN DIFFERENTLY from one that is not
        # firing. The desktop task fired hourly for two days while collecting
        # zero rows; under the old logic that read "ok".
        # ⚠️ THE FIRING CLOCK MUST BE THE UNATTENDED ONE, for the same reason
        # the rows clock is. A component only ever run BY HAND is not "running
        # but producing nothing" - it is not running. Using last_ts here made a
        # manual beat on a 30h-stale component report `empty`, which would have
        # let a hand-run rescue a dead component's verdict. That is the exact
        # mislabelling this module exists to prevent (test_stages.py catches it).
        _fired = (r.get("last_unattended_ts") if "last_origin" in r
                  else r.get("last_ts"))
        fired_h = ((now - _fired) / 3600.0) if _fired else None
        if name in RETIRED:
            _rts, _why = RETIRED[name]
            _rts_s = dt.datetime.strptime(_rts, "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc).timestamp()
            # ⛔ undead: it wrote UNATTENDED after it was shut down.
            _undead = _fired is not None and _fired > _rts_s
            out.append({"name": name, "verdict": "undead" if _undead else "retired",
                        "age_h": age_h, "max_age_h": None, "count": r.get("count") or 0,
                        "declared": declared, "declared_h": declared_h,
                        "basis": basis, "what": what, "retired": _rts, "why": _why,
                        "fired_age_h": fired_h,
                        "last_at": r.get("last_at"),
                        "last_origin": r.get("last_origin"),
                        "manual_age_h": manual_h})
            continue
        if max_age_h is None:
            # ⭐ DECLARED, COUNTED, NEVER ALARMED. There is no honest bar yet.
            out.append({"name": name, "verdict": "unmetered", "age_h": age_h,
                        "max_age_h": None, "count": r.get("count") or 0,
                        "declared": declared, "declared_h": declared_h,
                        "basis": basis, "what": what,
                        "last_at": r.get("last_at"),
                        "last_origin": r.get("last_origin"),
                        "manual_age_h": manual_h})
            continue
        firing_ok = fired_h is not None and fired_h <= max_age_h
        # ⭐ EMPTY means "fired unattended and produced NOTHING", which is only
        # knowable when rows have actually been tracked for this entry.
        if last is None:
            if firing_ok and never_produced:
                verdict = "empty"      # it runs; it has never produced a row
            else:
                # Never fired. Only an alarm once it has had longer than its own
                # threshold to do so - otherwise a new declaration screams on day
                # one and gets muted, which is how alerts die.
                verdict = "never" if declared_h > max_age_h else "pending"
        elif age_h > max_age_h:
            verdict = "empty" if firing_ok else "stale"
        else:
            verdict = "ok"
        out.append({"name": name, "verdict": verdict, "age_h": age_h,
                    "max_age_h": max_age_h, "count": r.get("count") or 0,
                    "firings": r.get("firings"),
                    "rows_total": r.get("rows_total"),
                    "empty_firings": r.get("empty_firings"),
                    "fired_age_h": fired_h,
                    "declared": declared, "declared_h": declared_h,
                    "basis": basis, "what": what,
                    "last_at": r.get("last_at"),
                    "last_origin": r.get("last_origin"),
                    "manual_age_h": manual_h})
    # Drift the other way: beating without being declared.
    for name in reg:
        if name not in COMPONENTS:
            r = reg[name] or {}
            # ⚠️ The age was thrown away here and reported as "no age recorded"
            # while sitting in the registry. Undeclared means "nobody set a
            # threshold", not "nothing is known" - and the age is the first
            # thing you want when deciding whether to declare it or delete it.
            _lt = r.get("last_rows_ts") or r.get("last_ts")
            out.append({"name": name, "verdict": "undeclared",
                        "age_h": ((now - _lt) / 3600.0) if _lt else None,
                        "max_age_h": None,
                        "count": r.get("count") or 0,
                        "declared": None, "declared_h": None, "basis": None,
                        "what": "beats but is not in COMPONENTS - declare it or remove it",
                        "last_at": r.get("last_at")})
    return out


def line(st=None):
    """The daily line. Groups by verdict so the bad news is not buried."""
    st = st or status()
    by = {}
    for s in st:
        by.setdefault(s["verdict"], []).append(s)
    # ⛔ `empty` WAS MISSING FROM THIS LINE FOR THE WHOLE DAY IT EXISTED.
    #
    # status() gained the verdict on 2026-09-18 - "it fires on time and produces
    # nothing", the entire point of counting rows instead of beats - and then
    # line(), check() and the __main__ exit code all still listed the four old
    # verdicts. So the new signal was computed correctly and shown to nobody.
    # That is the whitelist bug in a second place on the same day: compute and
    # surface are two separate steps, and doing only the first is silent.
    ls = [f"liveness: {len(by.get('ok', []))} ok, {len(by.get('stale', []))} stale, "
          f"{len(by.get('empty', []))} empty, "
          f"{len(by.get('never', []))} never, {len(by.get('pending', []))} pending, "
          f"{len(by.get('unmetered', []))} unmetered, "
          f"{len(by.get('undeclared', []))} undeclared, "
          f"{len(by.get('retired', []))} retired"
          + (f", {len(by.get('undead', []))} UNDEAD" if by.get("undead") else "")]
    for v in ("undead", "empty", "never", "stale", "undeclared", "unmetered", "pending", "retired"):
        for s in by.get(v, []):
            if v in ("retired", "undead"):
                age = (f"retired {s['retired'][:10]}"
                       + (f", last unattended beat {s['fired_age_h']:.1f}h ago"
                          if s.get("fired_age_h") is not None else "")
                       + (" - AFTER RETIREMENT: something is writing a frozen ledger"
                          if v == "undead" else ""))
            elif v == "unmetered":
                age = (f"last {s['age_h']:.1f}h ago" if s["age_h"] is not None
                       else "never yet") + ", no threshold set - market event"
            elif v == "empty":
                # The age here is the ROWS clock, which is the whole distinction.
                age = (f"fired {s['age_h']:.1f}h ago with NO ROWS"
                       if s["age_h"] is not None else "fires, produces nothing")
            elif s["age_h"] is not None:
                age = f"{s['age_h']:.1f}h ago"
            elif s["declared_h"] is None:
                # ⚠️ undeclared components have no declaration date, so there is
                # no "since declared" to print. This used to crash the whole
                # report with a TypeError on None - the health tool itself going
                # down, loudly but uselessly, the moment a beat was undeclared.
                age = "no age recorded"
            elif v == "pending":
                age = f"not fired yet, {max(0.0, s['declared_h']):.1f}h into grace"
            else:
                age = f"NEVER, {s['declared_h']:.0f}h since declared"
            ls.append(f"  {v.upper():<10} {s['name']:<22} {age}"
                      + (f" (limit {s['max_age_h']}h)" if s["max_age_h"] else "")
                      + (f" [manual beat {s['manual_age_h']:.1f}h ago - not counted]"
                         if s.get("manual_age_h") is not None else ""))
    return "\n".join(ls)


def check(record=None, verbose=True):
    """Emit a finding per dead component. Health lane, keyed per component."""
    st = status()
    if verbose:
        print("  " + line(st).replace("\n", "\n  "))
    for s in st:
        if s["verdict"] not in ("never", "stale", "undeclared", "empty", "undead"):
            continue
        if not record:
            continue
        if s["verdict"] == "undead":
            msg = (f"{s['name']} beat UNATTENDED after it was retired on "
                   f"{s['retired'][:10]}")
            detail = (f"Retired because: {s['why']}. A retired component that "
                      f"writes means a frozen ledger is being appended to.")
        elif s["verdict"] == "never":
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
        elif s["verdict"] == "empty":
            # ⛔ A DIFFERENT FAILURE FROM stale, NEEDING A DIFFERENT FIX. Stale
            # means the trigger stopped. Empty means the trigger is fine and the
            # work produces nothing - the desktop task fired hourly for two days
            # while collecting zero rows and read as healthy the whole time.
            msg = (f"{s['name']} is firing on schedule and producing NO ROWS"
                   + (f" - last row {s['age_h']:.1f}h ago" if s["age_h"] is not None
                      else " - it has never produced one"))
            detail = (f"Expected: {s['what']}. The trigger works, so this is not "
                      f"a scheduling problem: the work inside it is returning "
                      f"nothing. Threshold {s['max_age_h']}h ({s['basis']}).")
        else:
            msg = f"{s['name']} is recording beats but is not declared in COMPONENTS"
            detail = ("Declare it with a threshold, or remove the beat. An "
                      "undeclared component is invisible to this check.")
        record("liveness", s["name"], msg, detail=detail)
    return st


def unattended_rows():
    """⭐ THE ONE QUESTION: when did a pass NOBODY TRIGGERED last write rows?

    Returns (ts, component, origin) or (None, None, None).

    ⛔ Read off the registry, not off `gh run list`. The bar Frank set is "fresh
    rows written by a run that fired on its own", and until origin() separated
    `scheduled` from `dispatch` the journal could not answer it - every hosted
    run said "runner" whether cron fired it or a human did. Answering a question
    about the data from somewhere other than the data is standing rule 16.

    ⚠️ `runner` rows written before 2026-09-18 are a mix of both and cannot be
    re-derived. They are still counted, and this figure is therefore an UPPER
    bound on how recently the system ran itself, until the pre-split rows age
    out of the window you care about.
    """
    reg = _load()
    best = (None, None, None)
    for name, r in (reg or {}).items():
        if not isinstance(r, dict):
            continue
        ts = r.get("last_unattended_rows_ts")
        if ts and (best[0] is None or ts > best[0]):
            best = (ts, name, r.get("last_origin"))
    return best


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    st = status()
    print(line(st))
    ts, who, org = unattended_rows()
    if ts:
        age = (time.time() - ts) / 3600.0
        print(f"  unattended rows: {who} {age:.1f}h ago"
              + (f" (origin {org})" if org else "")
              + ("   ⚠️ pre-split `runner` may mean a human dispatch"
                 if org == "runner" else ""))
    else:
        print("  ⛔ unattended rows: NEVER - no pass that nobody triggered has "
              "written a row")
    bad = [s for s in st if s["verdict"] in ("never", "stale", "undeclared", "empty", "undead")]
    sys.exit(1 if bad else 0)
