"""Enforces docs/ENGINEERING_DISCIPLINE.md. Run: python test_discipline.py

⛔ THE RULE: verify the OUTPUT, never the execution. Every failure this week was
the same mistake - we checked that something ran, not that it produced what it
claimed. Four of the five were silent.

A rule nobody checks is a comment, so these are machine-checked:

  A. coverage is recorded on EVERY pass, including when it is 100%
  B. truncation is never silent - both break sites carry their remainder
  C. nothing is discarded - a truncated pass owes it forward, a clean pass clears
  D. beats count ROWS, not firings, and an empty firing does not read as health
"""
import ast
import datetime as dt
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import tempfile
import time

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


HERE = os.path.dirname(os.path.abspath(__file__))

print("=" * 70)
print("A. coverage is recorded on every pass, even a complete one")
print("=" * 70)

import journal

WINDOW = {"pools": 90, "oldest": 1, "newest": 2, "span_s": 120.0, "pages_lost": 0}
_real = journal.COV
journal.COV = tempfile.mkdtemp()

full = journal.record_coverage("solana", WINDOW, 88, 70, 5,
                               scan={"pools": 90, "reached": 90, "enriched": 90,
                                     "failed": 0, "coverage": 1.0,
                                     "budget_hit": False, "pools_fresh": 90,
                                     "pools_carried": 0, "carried_forward": 0,
                                     "carry_dropped": 0})
for f in ("pools_seen", "pools_processed", "scan_coverage", "truncated",
          "coverage_alarm"):
    check(f"a COMPLETE pass still records {f}", full.get(f) is not None,
          repr(full.get(f)))
check("⭐ and 90/90 raises no alarm", full["coverage_alarm"] is False)
check("pools_seen is the loop's input", full["pools_seen"] == 90)
check("pools_processed is the loop's output", full["pools_processed"] == 90)

part = journal.record_coverage("solana", WINDOW, 60, 70, 3,
                               scan={"pools": 90, "reached": 69, "enriched": 69,
                                     "failed": 0, "coverage": 69 / 90,
                                     "budget_hit": True, "pools_fresh": 90,
                                     "pools_carried": 0, "carried_forward": 21,
                                     "carry_dropped": 0,
                                     "truncate_reason": "enrichment budget spent"})
check("⛔ a PARTIAL pass raises the alarm", part["coverage_alarm"] is True)
check("and names the reason", "budget" in (part.get("truncate_reason") or ""))
check("and records what it owes forward", part["carried_forward"] == 21)
check("⚠️ `scanned` and `pools_processed` are NOT the same field",
      part["scanned"] == 60 and part["pools_processed"] == 69,
      "rows journalled vs pools reached")

# ⛔ THE FALSE POSITIVE THIS ALARM SHIPPED WITH, 2026-09-18 14:29Z.
#
# Run 35356362447 reached every one of 83 pools - the 540s runner budget did
# its job and truncated nothing - and the alarm still fired:
#
#     ⛔ COVERAGE ALARM [solana]: processed 80 of 83 pools (100.0%)
#                                 - reason not recorded
#
# "80 of 83" and "100.0%" in the same line, with budget_hit false. The cause
# was `pools_processed` reading LAST_SCAN["enriched"], which counts pools that
# produced a ROW; three pools were reached and produced none (no address, a
# failed fetch). That is an enrichment failure, not a coverage failure, and it
# is not what the alarm is for. ⭐ An alarm that fires when nothing is wrong is
# the "alarm nobody reads" failure docs/ENGINEERING_DISCIPLINE.md §5 warns
# about - the rule is not a mandate to assert everything.
clean = journal.record_coverage("solana", WINDOW, 80, 70, 4,
                                scan={"pools": 83, "reached": 83, "enriched": 80,
                                      "failed": 3, "coverage": 1.0,
                                      "budget_hit": False, "pools_fresh": 83,
                                      "pools_carried": 0, "carried_forward": 0,
                                      "carry_dropped": 0})
check("⛔ REGRESSION: reached 83/83 but enriched 80 raises NO alarm",
      clean["coverage_alarm"] is False,
      "an alarm that fires when nothing is wrong is one nobody reads")
check("...because pools_processed is what the LOOP reached",
      clean["pools_processed"] == 83)
check("⚠️ and the enrichment shortfall is still recorded, separately",
      clean["pools_enriched"] == 80 and clean["pools_failed"] == 3,
      f"enriched={clean['pools_enriched']} failed={clean['pools_failed']}")
check("⭐ the printed count and the printed percentage agree",
      clean["pools_processed"] == clean["pools_seen"]
      and clean["scan_coverage"] == 1.0)

# And the source of that number: `reached` must be the loop counter itself, not
# anything downstream of whether a pool yielded a row.
_ssrc = io.open(os.path.join(HERE, "scanner.py"), encoding="utf-8").read()
check("⛔ scanner sets `reached` from the loop index, not from a row count",
      'LAST_SCAN["reached"] = i + 1' in _ssrc)
check("...and journal reads `reached`, never `enriched`, for the alarm",
      'proc = sc.get("reached")' in
      io.open(os.path.join(HERE, "journal.py"), encoding="utf-8").read())
journal.COV = _real

print()
print("=" * 70)
print("B. truncation is never silent - checked in the source, not the changelog")
print("=" * 70)

src = io.open(os.path.join(HERE, "scanner.py"), encoding="utf-8").read()
tree = ast.parse(src)
fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "scan")

# Every `break` directly in the pool loop must be immediately preceded by a
# _truncate() call. A break that just leaves is exactly the silent discard.
loops = [n for n in ast.walk(fn) if isinstance(n, ast.For)]
breaks_ok, breaks_total = 0, 0
for lp in loops:
    for node in ast.walk(lp):
        if not isinstance(node, ast.If):
            continue
        body = node.body
        if not any(isinstance(b, ast.Break) for b in body):
            continue
        breaks_total += 1
        calls = [c for b in body for c in ast.walk(b)
                 if isinstance(c, ast.Call) and isinstance(c.func, ast.Name)
                 and c.func.id == "_truncate"]
        if calls:
            breaks_ok += 1
check(f"the scan loop has {breaks_total} conditional break(s)", breaks_total >= 2,
      str(breaks_total))
check("⛔ EVERY one routes through _truncate()", breaks_ok == breaks_total,
      f"{breaks_ok}/{breaks_total}")

import scanner
check("_truncate records the skipped ADDRESSES, not just a count",
      "skipped" in io.open(os.path.join(HERE, "scanner.py"), encoding="utf-8").read()
      .split("def _truncate")[1].split("def ")[0])
check("⭐ the runner gets a budget that is not the sandbox's",
      scanner.RUNNER_SCAN_BUDGET_S > scanner.SCAN_BUDGET_S,
      f"{scanner.SCAN_BUDGET_S} -> {scanner.RUNNER_SCAN_BUDGET_S}")
os.environ["GITHUB_ACTIONS"] = "true"
try:
    check("and scan_budget() actually returns it on the runner",
          scanner.scan_budget(None) == scanner.RUNNER_SCAN_BUDGET_S)
finally:
    os.environ.pop("GITHUB_ACTIONS", None)
check("off the runner it keeps the sandbox budget",
      scanner.scan_budget(None) == scanner.SCAN_BUDGET_S)
check("an explicit budget always wins", scanner.scan_budget(7) == 7)

print()
print("=" * 70)
print("C. nothing is discarded - the carry round-trips")
print("=" * 70)

scanner.CARRY_PATH = os.path.join(tempfile.mkdtemp(), "carry.json")
pools = [{"attributes": {"address": f"POOL{i:03d}"}} for i in range(50)]
scanner.LAST_SCAN.clear()
rest = scanner._truncate(pools, 10, "test", verbose=False)
check("⛔ a truncation carries the remainder", len(rest) == 40, str(len(rest)))
check("and persists it to disk", os.path.exists(scanner.CARRY_PATH))
check("which reloads identically", len(scanner._carry_load()) == 40)
check("coverage is recorded as the ratio", abs(scanner.LAST_SCAN["coverage"] - 0.2) < 1e-9,
      str(scanner.LAST_SCAN["coverage"]))
check("skipped addresses are recorded", len(scanner.LAST_SCAN["skipped"]) == 40)
check("the reason is recorded", scanner.LAST_SCAN.get("truncate_reason") == "test")
# ⛔ OFF BY ONE, IN THE OPTIMISTIC DIRECTION. A pass that breaks at index i has
# NOT reached pool i - _truncate carries pools[i:], that pool included. Setting
# the counter at the top of the loop body would have claimed i+1.
check("⛔ a truncation at 10 reports 10 reached, not 11",
      scanner.LAST_SCAN.get("reached") == 10,
      str(scanner.LAST_SCAN.get("reached")))
check("...which is exactly what is NOT carried",
      scanner.LAST_SCAN["reached"] + len(rest) == len(pools))

# ⚠️ the cap must DROP LOUDLY, never silently
_cap = scanner.CARRY_MAX
scanner.CARRY_MAX = 5
try:
    scanner.LAST_SCAN.clear()
    rest = scanner._truncate(pools, 10, "test", verbose=False)
    check("⚠️ at the cap it keeps only CARRY_MAX", len(rest) == 5)
    check("⛔ and RECORDS the drop rather than hiding it",
          scanner.LAST_SCAN["carry_dropped"] == 35,
          str(scanner.LAST_SCAN.get("carry_dropped")))
finally:
    scanner.CARRY_MAX = _cap

scanner._carry_save([{"attributes": {"address": "LEFTOVER"}}], 0)
check("a stale carry exists before a clean pass", len(scanner._carry_load()) == 1)
check("⭐ and a COMPLETE pass clears it, or it replays forever",
      "if not LAST_SCAN.get(\"budget_hit\")" in src
      and "_carry_save([], 0)" in src)

print()
print("=" * 70)
print("D. beats count ROWS, not firings")
print("=" * 70)

import liveness
d = tempfile.mkdtemp()
liveness.REG = os.path.join(d, "reg.json")
liveness.LEDGER_DIR = os.path.join(d, "ledger")
os.environ["CRYPTO_ORIGIN"] = "scheduled"

liveness.beat("scan.observations", 0)
liveness.beat("scan.observations", 0)
reg = json.load(io.open(liveness.REG, encoding="utf-8"))["scan.observations"]
check("two empty firings are COUNTED as firings", reg["firings"] == 2)
check("⛔ but produce zero rows", reg["rows_total"] == 0)
check("and are counted as empty", reg["empty_firings"] == 2)
check("⭐ the ROWS clock is never set by an empty firing",
      reg.get("last_rows_ts") is None, repr(reg.get("last_rows_ts")))
check("⚠️ while the FIRING clock IS set - they are different questions",
      reg.get("last_ts") is not None)

liveness.beat("scan.observations", 42)
reg = json.load(io.open(liveness.REG, encoding="utf-8"))["scan.observations"]
check("a real firing sets the rows clock", reg.get("last_rows_ts") is not None)
check("and accumulates the rows", reg["rows_total"] == 42)
check("empty_firings does not increase on a real one", reg["empty_firings"] == 2)

# ⚠️ THE DISTINCTION I GOT WRONG TWICE WHILE WRITING THIS.
# "empty" must mean "ran unattended and produced nothing". It must NOT swallow:
#   - a component only ever run BY HAND (that is not running; it is `stale`)
#   - a component whose rows clock predates row-tracking (reporting it dead
#     because a FIELD is young is the same mislabelling in a new costume)
_name = sorted(liveness.COMPONENTS)[0]
_max_h = liveness.COMPONENTS[_name][0]
_now = int(time.time())


def _put(entry):
    io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({_name: entry}))
    return next(x for x in liveness.status() if x["name"] == _name)


v = _put({"last_ts": _now, "last_at": "x", "count": 1, "first_ts": _now,
          "last_origin": "scheduled", "last_unattended_ts": _now,
          "firings": 3, "rows_total": 0, "empty_firings": 3})
check("⭐ fires unattended, zero rows -> EMPTY", v["verdict"] == "empty",
      v["verdict"])

v = _put({"last_ts": _now, "last_at": "x", "count": 1, "first_ts": _now,
          "last_origin": "manual", "firings": 1, "rows_total": 1,
          "empty_firings": 0})
check("⚠️ hand-run only -> NOT empty, it is not running",
      v["verdict"] != "empty", v["verdict"])

_old = _now - int((_max_h + 40) * 3600)
v = _put({"last_ts": _old, "last_at": "x", "count": 9, "first_ts": _old,
          "last_origin": "scheduled", "last_unattended_ts": _old})
check("⚠️ an entry from BEFORE row-tracking is still judged, not voided",
      v["verdict"] == "stale", v["verdict"])

v = _put({"last_ts": _now, "last_at": "x", "count": 9, "first_ts": _old,
          "last_origin": "scheduled", "last_unattended_ts": _now,
          "last_unattended_rows_ts": _old, "firings": 9, "rows_total": 100,
          "empty_firings": 4})
check("⭐ produced rows once, now firing empty -> EMPTY", v["verdict"] == "empty",
      v["verdict"])

lsrc = io.open(os.path.join(HERE, "liveness.py"), encoding="utf-8").read()
check("⭐ status() has a distinct 'empty' verdict", '"empty"' in lsrc)
check("...used when the component is firing but not producing",
      "firing_ok" in lsrc and 'verdict = "empty" if firing_ok else "stale"' in lsrc)

# ⛔ AND IT MUST REACH A HUMAN. status() gained `empty` on 2026-09-18 and
# line(), check() and the __main__ exit code all still listed the four OLD
# verdicts - so the new signal was computed correctly and shown to nobody, for
# the whole day it existed. Computing and surfacing are two separate steps;
# this is the journal.record() whitelist bug in a second place on the same day.
_now2 = int(time.time())
io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({
    _name: {"last_ts": _now2, "last_at": "x", "count": 5, "first_ts": _now2,
            "last_origin": "scheduled", "last_unattended_ts": _now2,
            "firings": 5, "rows_total": 0, "empty_firings": 5}}))
_st = liveness.status()
_ln = liveness.line(_st)
check("⛔ an EMPTY component appears in the daily line at all",
      "EMPTY" in _ln, _ln.splitlines()[0])
check("...and in the summary counts, not only the detail",
      "1 empty" in _ln, _ln.splitlines()[0])
_emitted = []
liveness.check(record=lambda *a, **k: _emitted.append(a), verbose=False)
check("⛔ and check() emits a finding for it",
      any(_name in str(a) for a in _emitted), str(_emitted[:1]))
check("...saying the trigger works and the WORK produces nothing",
      any("producing NO ROWS" in str(a) for a in _emitted))
check("⭐ the exit-code list includes it, or a red run reads green",
      re.search(r'bad = \[s for s in st if s\["verdict"\] in \([^)]*"empty"', lsrc))

# ⛔ RETIRED IS NOT STALE, AND A RETIRED COMPONENT THAT WRITES IS AN ALARM.
# 2026-09-19: "paper.sweep 84h stale" was the quarantined v1 ledger, whose sweep
# returns before it beats. The registry held a deliberately stopped component
# to a 12h bar and reported the stop as an outage.
_ret = next(iter(liveness.RETIRED))
_rts = int(dt.datetime.strptime(liveness.RETIRED[_ret][0], "%Y-%m-%dT%H:%M:%SZ").replace(
    tzinfo=dt.timezone.utc).timestamp())


def _put_ret(ts, origin="scheduled"):
    io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({_ret: {
        "last_ts": ts, "last_at": "x", "count": 3, "first_ts": ts, "last_origin": origin,
        "last_unattended_ts": ts if origin == "scheduled" else _rts - 3600}}))
    return next(x for x in liveness.status() if x["name"] == _ret)


v = _put_ret(_rts - 3600)
check("⭐ a retired component silent since retirement reads RETIRED, not stale",
      v["verdict"] == "retired", v["verdict"])
v = _put_ret(_rts + 3600)
check("⛔ ...and one that beat UNATTENDED after retirement reads UNDEAD", v["verdict"] == "undead", v["verdict"])
_em = []
liveness.check(record=lambda *a, **k: _em.append(a), verbose=False)
check("⛔ ...which check() reports as a frozen ledger being written",
      any("after it was retired" in str(a) for a in _em), str(_em[:1]))
check("⛔ ...and which fails the exit code",
      re.search(r'bad = \[s for s in st if s\["verdict"\] in \([^)]*"undead"', lsrc))
v = _put_ret(int(time.time()), origin="manual")
check("a MANUAL beat after retirement (a test, a hand run) does not make it undead",
      v["verdict"] == "retired", v["verdict"])

# ⚠️ And the report must not crash on a component with no declaration date.
# An undeclared beat made line() raise TypeError on None and took the whole
# health report down - the one tool whose job is to tell you something is wrong.
io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({
    "nobody.declared.this": {"last_ts": _now2, "last_at": "x", "count": 1,
                             "first_ts": _now2}}))
try:
    _ln2 = liveness.line(liveness.status())
    _ok = "UNDECLARED" in _ln2
except Exception as e:
    _ln2, _ok = f"{type(e).__name__}: {e}", False
check("⛔ an UNDECLARED component does not crash the report", _ok, _ln2.strip()[:60])
check("...and its age is reported, not thrown away",
      "no age recorded" not in _ln2, _ln2.strip()[:60])

# ⛔ A HOSTED RUNNER IS NOT AUTOMATICALLY UNATTENDED.
# origin() returned "runner" for every Actions run, so a workflow_dispatch I
# pressed myself recorded identically to a cron fire - and "did a pass run that
# nobody triggered" then had to be read off `gh run list` and correlated by
# timestamp. Taking the answer from somewhere other than the thing that claims
# it is standing rule 16, and it flattered us in the direction we were already
# wrong: 87% of passes were manual.
_saved = {k: os.environ.get(k)
          for k in ("GITHUB_ACTIONS", "GITHUB_EVENT_NAME", "CRYPTO_ORIGIN")}


def _origin(**env):
    for k in _saved:
        os.environ.pop(k, None)
    os.environ.update({k: v for k, v in env.items() if v is not None})
    return liveness.origin()


check("⭐ a cron fire is `scheduled`",
      _origin(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="schedule") == "scheduled")
check("⛔ a workflow_dispatch is NOT - a human pressed it",
      _origin(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="workflow_dispatch")
      == liveness.DISPATCH)
check("...nor is a push-triggered run",
      _origin(GITHUB_ACTIONS="true", GITHUB_EVENT_NAME="push") == liveness.DISPATCH)
check("⛔ and `dispatch` does not count as unattended",
      liveness.DISPATCH not in liveness.UNATTENDED)
check("off Actions it is still manual unless told otherwise",
      _origin() == "manual")
check("and CRYPTO_ORIGIN still wins off Actions",
      _origin(CRYPTO_ORIGIN="scheduled") == "scheduled")
for k, v in _saved.items():
    os.environ.pop(k, None)
    if v is not None:
        os.environ[k] = v

# ⭐ And the question has to be answerable FROM THE JOURNAL.
_now3 = int(time.time())
io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({
    "a": {"last_ts": _now3, "count": 1, "first_ts": _now3,
          "last_origin": "manual"},
    "b": {"last_ts": _now3, "count": 1, "first_ts": _now3,
          "last_origin": "scheduled", "last_unattended_rows_ts": _now3 - 7200}}))
_ts, _who, _org = liveness.unattended_rows()
check("⭐ unattended_rows() finds the newest unattended ROW clock",
      _who == "b" and _ts == _now3 - 7200, f"{_who} {_ts}")
io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps({
    "a": {"last_ts": _now3, "count": 1, "first_ts": _now3,
          "last_origin": "manual"}}))
check("⛔ and reports NOTHING rather than a manual beat when there is none",
      liveness.unattended_rows() == (None, None, None),
      str(liveness.unattended_rows()))

print()
print("=" * 70)
print("E. the data guard blames the right writer")
print("=" * 70)

# ⛔ run_tests.py asserts that no suite wrote into data/. When a scheduled pass
# is running at the same time, that assertion fires on the PASS's rows and
# accuses the suites. That is not cosmetic: the identical message is what led me
# to `git checkout data/` on 2026-09-20 and destroy ~10.5h of liveness beats.
#
# The first fix asked "did an unattended pass beat BETWEEN t0 and t1" and STILL
# missed one, because a beat marks the end of a stage's work, not its span. On
# 2026-09-21 the suite ran inside a 98-second gap between two beats while the
# market stage made live Jupiter calls through it and wrote _jupiter_usage.json
# mid-run. Sampler narrower than the phenomenon - standing rule 13.
import run_tests

margin = run_tests._pass_margin()
try:
    import collect
    _kill = float(collect.KILL_S)
except Exception:
    _kill = None
check("the window margin comes from collect.KILL_S, not a literal",
      _kill is not None and margin >= _kill, f"margin {margin}s, KILL_S {_kill}")
check("⭐ and it covers a whole silent stage", _kill is None or margin > _kill,
      f"{margin} > {_kill}")

_lv = os.path.join(HERE, "data", "liveness")
_month = dt.datetime.now(dt.timezone.utc).strftime("%Y-%m")
_real_path = os.path.join(_lv, f"{_month}.jsonl")
_tmpdir = tempfile.mkdtemp()
_saved_here = run_tests.HERE
try:
    os.makedirs(os.path.join(_tmpdir, "data", "liveness"))
    now = int(time.time())
    # a pass that beats 100s before the run and 100s after it, and NEVER inside:
    # exactly the shape that fooled the strict window.
    rows = [{"name": "dashboard.build", "ts": now - 100, "n": 1, "origin": "scheduled"},
            {"name": "market.snapshot", "ts": now + 100, "n": 412, "origin": "scheduled"}]
    with io.open(os.path.join(_tmpdir, "data", "liveness", f"{_month}.jsonl"),
                 "w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r) + "\n")
    run_tests.HERE = _tmpdir
    got = run_tests._unattended_beats(now - 20, now + 20)   # the suite's own window
    check("⭐ a pass that beat only OUTSIDE the run is still detected",
          len(got) == 1 and got[0][0] == "scheduled" and got[0][2] == 2,
          repr(got))
    # ...and a manual hand-run must NOT excuse a dirty data/ dir.
    with io.open(os.path.join(_tmpdir, "data", "liveness", f"{_month}.jsonl"),
                 "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"name": "scan.observations", "ts": now,
                            "n": 9, "origin": "manual"}) + "\n")
    check("⛔ a MANUAL beat never excuses it - only unattended does",
          run_tests._unattended_beats(now - 20, now + 20) == [])
    # ...and a pass from yesterday must not excuse today's run either.
    with io.open(os.path.join(_tmpdir, "data", "liveness", f"{_month}.jsonl"),
                 "w", encoding="utf-8", newline="\n") as f:
        f.write(json.dumps({"name": "scan.observations", "ts": now - 86400,
                            "n": 9, "origin": "scheduled"}) + "\n")
    check("⛔ and a pass from 24h ago does not either",
          run_tests._unattended_beats(now - 20, now + 20) == [])
finally:
    run_tests.HERE = _saved_here

src = io.open(os.path.join(HERE, "run_tests.py"), encoding="utf-8").read()
check("⛔ the message forbids `git checkout data/` in words",
      "NEVER `git checkout` data/" in src)
check("and it names the writer instead of blaming the suites",
      "UNATTENDED PASS WAS WRITING" in src)

print()
print("=" * 70)
print("F. the rule is written down where the next session will find it")
print("=" * 70)

doc = os.path.join(HERE, "docs", "ENGINEERING_DISCIPLINE.md")
check("docs/ENGINEERING_DISCIPLINE.md exists", os.path.exists(doc))
if os.path.exists(doc):
    t = io.open(doc, encoding="utf-8").read()
    for phrase in ("verified that something RAN", "count ROWS, not beats",
                   "loud failure beats silent degradation", "provenance"):
        check(f"...and states: {phrase!r}", phrase.lower() in t.lower())
    check("⚠️ and states what it does NOT license",
          "does NOT license" in t and "781x" in t)
claude = io.open(os.path.join(HERE, "CLAUDE.md"), encoding="utf-8").read()
check("CLAUDE.md carries it as a standing rule",
      "ENGINEERING_DISCIPLINE" in claude)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
