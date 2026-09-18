"""The staged command list must reach every declared component.

2026-09-15: paper.sweep, paper.close and watchlist.sweep - and
milestone.graduated, which only watchlist.sweep can fire - had tests, liveness
declarations and thresholds, and nothing in the hourly staged list ever called
them. They ran only inside the unstaged full pass, which the host sandbox kills,
so the GitHub runner was their only caller. When it stopped on 9/12 the paper
log stopped with it. Existing, tested, never invoked.

Run: python test_stages.py    (offline; writes only to temp paths)
"""
import inspect
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

import liveness

TMP = tempfile.mkdtemp()
liveness.REG = os.path.join(TMP, "liveness.json")
liveness.LEDGER_DIR = os.path.join(TMP, "liveness")

import collect
import journal
import paper
import paperv2
import sources
import watchlist

paper.LEDGER = os.path.join(TMP, "ledger.jsonl")
paperv2.LOG_DIR = TMP
paperv2.LEDGER = os.path.join(TMP, "ledger_v2.jsonl")
journal.PASS_STATE = os.path.join(TMP, "pass_state.json")
sources.pace = lambda *a, **k: None          # no sleeping in tests

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


def section(t):
    print("=" * 70)
    print(t)
    print("=" * 70)


section("1. every declared liveness component is reachable from the staged list")
fired = set(collect.EVERY_INVOCATION_FIRES)
for s in collect.STAGES:
    fired |= collect.STAGE_FIRES.get(s, set())
missing = set(liveness.COMPONENTS) - fired
check("no declared component is unreachable", not missing, f"unreachable: {sorted(missing)}")
check("the stage map names no undeclared component",
      not (fired - set(liveness.COMPONENTS)), sorted(fired - set(liveness.COMPONENTS)))
check("every stage has a map entry", all(s in collect.STAGE_FIRES for s in collect.STAGES))
check("the five from 9/15 are all reachable",
      {"paper.close", "paper.sweep", "milestone.mcap", "milestone.realizable",
       "watchlist.sweep"} <= fired)

section("1b. ⛔ and something the COLLECTOR IMPORTS actually beats it")

# ⛔ THE CHECK THAT WOULD HAVE CAUGHT paperv3.
#
# Section 1 proves the stage MAP is consistent with COMPONENTS. It cannot see
# whether any code ever calls liveness.beat() for a name, or whether the module
# that does is one collect.py can reach. paperv3 had 71 passing tests, a beat in
# open_entry(), and collect.py did not import it - so the beat could not fire on
# a pass no matter what the map said.
#
# ⚠️ Same family as the other two: `chainfields` was imported only by paperv3,
# and `devwallet` by nothing at all. "It has tests" is not "it is in the system".
import ast as _ast
import glob as _glob

_HERE = os.path.dirname(os.path.abspath(__file__))
_LOCAL = {os.path.splitext(os.path.basename(f))[0]
          for f in _glob.glob(os.path.join(_HERE, "*.py"))}


def _imports(mod):
    try:
        tree = _ast.parse(io.open(os.path.join(_HERE, mod + ".py"),
                                  encoding="utf-8").read())
    except Exception:
        return set()
    out = set()
    for n in _ast.walk(tree):
        if isinstance(n, _ast.Import):
            out |= {a.name.split(".")[0] for a in n.names}
        elif isinstance(n, _ast.ImportFrom) and n.module and n.level == 0:
            out.add(n.module.split(".")[0])
    return out & _LOCAL


# Transitive closure from collect.py - what a pass can actually reach.
_reach, _todo = set(), ["collect"]
while _todo:
    m = _todo.pop()
    if m in _reach:
        continue
    _reach.add(m)
    _todo.extend(_imports(m))

# Every beat("name") literal, and which module it lives in.
_beats = {}
_prefix = {}
for f in sorted(_glob.glob(os.path.join(_HERE, "*.py"))):
    mod = os.path.splitext(os.path.basename(f))[0]
    if mod.startswith("test_"):
        continue
    try:
        tree = _ast.parse(io.open(f, encoding="utf-8").read())
    except Exception:
        continue
    for n in _ast.walk(tree):
        if not isinstance(n, _ast.Call):
            continue
        fn = n.func
        name = (fn.attr if isinstance(fn, _ast.Attribute)
                else fn.id if isinstance(fn, _ast.Name) else None)
        if name != "beat" or not n.args:
            continue
        a = n.args[0]
        if isinstance(a, _ast.Constant) and isinstance(a.value, str):
            _beats.setdefault(a.value, set()).add(mod)
        elif isinstance(a, _ast.JoinedStr) and a.values:
            # ⚠️ A COMPUTED NAME, e.g. beat(f"milestone.{fam}"). The literal
            # prefix is all that can be checked statically, so these are matched
            # by prefix and REPORTED as such - a weaker check has to say it is
            # weaker, or it reads as the strong one and nobody looks again.
            first = a.values[0]
            if isinstance(first, _ast.Constant) and isinstance(first.value, str)                     and first.value:
                _prefix.setdefault(first.value, set()).add(mod)

_nobeat, _by_prefix = [], []
for c in sorted(liveness.COMPONENTS):
    if c in _beats:
        continue
    hit = [p for p in _prefix if c.startswith(p)]
    if hit:
        _by_prefix.append(f"{c} <- f-string {hit[0]!r}")
        _beats.setdefault(c, set()).update(*(_prefix[p] for p in hit))
    else:
        _nobeat.append(c)
check("⛔ every declared component is beaten by some module", not _nobeat,
      f"declared but nothing calls beat(): {_nobeat}")
check(f"⚠️ {len(_by_prefix)} matched only by an f-string PREFIX, not exactly",
      True, "; ".join(_by_prefix) or "none")

_unreachable = sorted(c for c, mods in _beats.items()
                      if c in liveness.COMPONENTS and not (mods & _reach))
check("⛔ and that module is REACHABLE from collect.py", not _unreachable,
      f"beaten only by modules the collector never imports: {_unreachable}")

check("⭐ the import walk actually found the collector's graph",
      {"scanner", "journal", "liveness", "paperv3", "dashboard"} <= _reach,
      f"{len(_reach)} modules reachable")

section("2. the map is backed by the call path, not just asserted")
src = inspect.getsource
check("sweep stage calls paper.sweep", "paper.sweep(" in src(collect.sweep_stage))
check("sweep stage calls paperv2.sweep", "paperv2.sweep(" in src(collect.sweep_stage))
check("sweep stage labels the dead", "label_unpriceable(" in src(collect.sweep_stage))
check("watchlist stage calls watchlist.sweep", "watchlist.sweep(" in src(collect.watchlist_stage))
check("paper.sweep beats paper.sweep", 'beat("paper.sweep")' in src(paper.sweep))
check("a paper close beats paper.close",
      'beat("paper.close"' in io.open(paper.__file__, encoding="utf-8").read())
check("watchlist.sweep beats, and can claim a graduation",
      'beat("watchlist.sweep")' in src(watchlist.sweep)
      and 'claim(ca, "graduated"' in src(watchlist.sweep))
check("outcome recording reaches the mcap/realizable milestones",
      "milestones.check_outcome(" in io.open(journal.__file__, encoding="utf-8").read())
_main = src(collect.main)
check("main dispatches --stage sweep", 'stage == "sweep"' in _main and "sweep_stage()" in _main)
check("main dispatches --stage watchlist",
      'stage == "watchlist"' in _main and "watchlist_stage()" in _main)
check("the full pass still runs both",
      "sweep_stage(" in src(collect.one_pass) and "watchlist_stage(" in src(collect.one_pass))

section("3. an unknown stage is refused, not run as a killable full pass")
_argv = sys.argv
sys.argv = ["collect.py", "solana", "--stage", "sweeep"]
try:
    rc = collect.main()
finally:
    sys.argv = _argv
check("an unknown stage returns 2", rc == 2, f"rc={rc}")
check("...and claims no pass marker", not os.path.exists(journal.PASS_STATE))

section("4. a sweep stopped by its budget touches nothing and loses nothing")
calls = []


def fetch(chain, pair):
    calls.append(pair)
    return None


paper.open_entry("STAGEtest1111111111111111111111111111111111",
                 symbol="STAGETEST", price=0.001, exit_depth=5000, liq=10000,
                 fdv=10000, score=80, venue_type="amm", dex_id="test",
                 pair="STAGEpair")
st = paper.sweep(fetch, verbose=False, should_stop=lambda: True)
check("paper.sweep: a stopped sweep makes no calls", calls == [], calls)
check("...defers the position rather than skipping it silently",
      st.get("deferred") == 1 and st.get("checked") == 0, st)
check("...and writes no exit", not [r for r in paper._read() if r.get("type") == "exit"])
st = paper.sweep(fetch, verbose=False)
check("without should_stop it reaches the position as before",
      st.get("checked") == 1 and st.get("deferred") == 0, st)

V2ROW = {"venue_type": "amm", "exit_depth_usd": 5000.0, "can_mint": False,
         "can_freeze": False, "sells_h1": 5, "buys_h1": 20, "price_usd": 0.001,
         "liq": 10000.0, "fdv": 10000.0, "pair": "V" * 43, "score": 100,
         "addr": "W" * 43, "token": "W" * 43, "name": "V2STAGE"}
v2e, why = paperv2.open_entry(V2ROW)
check("fixture: a v2 entry opened", v2e is not None, why)
calls.clear()
st2 = paperv2.sweep(fetch, verbose=False, should_stop=lambda: True)
check("paperv2.sweep: a stopped sweep makes no calls and defers",
      calls == [] and st2.get("deferred", 0) >= 1 and st2.get("checked") == 0, st2)

_state = {"X" * 43: {"contract": "X" * 43, "pair": "XP", "symbol": "X",
                     "network": "solana", "added_ts": 0, "checks": 0}}
_saved, _appended = {}, []
watchlist._load = lambda: _state
watchlist._save = lambda s: _saved.update(s=dict(s))
watchlist._append = lambda path, rec: _appended.append(rec)
calls.clear()
ws = watchlist.sweep(fetch, verbose=False, should_stop=lambda: True)
check("watchlist.sweep: a stopped sweep makes no calls and defers",
      calls == [] and ws.get("deferred") == 1 and ws.get("checked") == 0, ws)
check("...and retires nobody, even a member past its TTL",
      "X" * 43 in _saved.get("s", {}) and not _appended)

section("5. one read per pool per stage")
seen = []


def f(chain, pair):
    seen.append(pair)
    return {"p": pair}


m = collect._memo_fetch(f)
a, b = m("solana", "A"), m("solana", "A")
m("solana", "B")
check("v1 and v2 share one read of the same pool", seen == ["A", "B"] and a is b, seen)
n = {"k": 0}


def g(chain, pair):
    n["k"] += 1
    raise RuntimeError("down")


mg = collect._memo_fetch(g)
for _ in range(2):
    try:
        mg("solana", "Z")
    except RuntimeError:
        pass
check("a lookup that raised is not cached", n["k"] == 2)

section("6. the budget is derived from the kill, and --max-seconds only lowers it")
bud, why = collect.calibrated_budget("scan", 155, overruns=[9, -1, 28])
check("178 - 1.25 x 28s worst overrun = 143, under a 155 ceiling", abs(bud - 143.0) < 0.01, why)
bud, _ = collect.calibrated_budget("scan", 110, overruns=[28])
check("a lower ceiling wins", bud == 110.0, bud)
bud, _ = collect.calibrated_budget("1", 155, overruns=[1, -1])
check("small overruns still keep a 15s reserve", abs(bud - 155.0) < 0.01, bud)
bud, _ = collect.calibrated_budget("x", 155, overruns=[500])
check("never below the 30s floor", bud == 30.0, bud)
bud, _ = collect.calibrated_budget("x", 400, overruns=[])
check("no history still respects the kill", abs(bud - 163.0) < 0.01, bud)

section("7. a manual beat cannot turn a stale component green")
_env = {k: os.environ.get(k) for k in ("GITHUB_ACTIONS", "CRYPTO_ORIGIN")}
os.environ.pop("GITHUB_ACTIONS", None)
_old = int(time.time()) - 30 * 3600
io.open(liveness.REG, "w", encoding="utf-8").write(json.dumps(
    {"detector.drift": {"last_ts": _old, "count": 5, "first_ts": _old}}))
os.environ["CRYPTO_ORIGIN"] = "manual"
liveness.beat("detector.drift")
v = {s["name"]: s for s in liveness.status()}["detector.drift"]
check("a manual beat on a 30h-stale component leaves it stale", v["verdict"] == "stale", v)
check("...the manual beat is shown", v.get("manual_age_h") is not None and v["manual_age_h"] < 0.1, v)
check("...and line() says it was not counted", "not counted" in liveness.line())
os.environ["CRYPTO_ORIGIN"] = "scheduled"
liveness.beat("detector.drift")
v = {s["name"]: s for s in liveness.status()}["detector.drift"]
check("a scheduled beat clears it", v["verdict"] == "ok", v)
os.environ["GITHUB_ACTIONS"] = "true"
check("the runner is unattended", liveness.origin() == "runner")
for k, val in _env.items():
    if val is None:
        os.environ.pop(k, None)
    else:
        os.environ[k] = val

section("8. the scan loop obeys the stage deadline, not only its own constant")
import scanner
_scan_src = inspect.getsource(scanner.scan)
check("scanner.scan checks the stage deadline every row",
      "S.seconds_left()" in _scan_src and "row_s.append(" in _scan_src)
check("...and still keeps its own ceiling for unbudgeted callers",
      "time.time() - started > budget" in _scan_src)

section("9. the skill file runs exactly staged_commands()")
SKILL = os.environ.get("CRYPTO_SKILL_FILE") or os.path.join(
    os.path.expanduser("~"), "Documents", "Claude", "Scheduled",
    "crypto-collect-hourly", "SKILL.md")
if os.path.exists(SKILL):
    txt = io.open(SKILL, encoding="utf-8").read()
    found = [re.sub(r"\s+", " ", x).strip()
             for x in re.findall(r"&&\s*(CRYPTO_ORIGIN=\S+\s+python3 collect\.py[^\n`]*)", txt)]
    bare = re.findall(r"python3 collect\.py solana --stage[^\n`]*", txt)
    check("skill file commands == staged_commands(), in order",
          found == collect.staged_commands(), f"skill has {found}")
    check("no skill command runs a stage without the origin marker",
          len(bare) == len(found), f"{len(bare)} stage commands, {len(found)} marked")
else:
    print(f"  SKIP  skill file not present here ({SKILL})")

ok = sum(1 for _, c, _ in R if c)
print(f"\n{ok}/{len(R)} passed")
sys.exit(0 if ok == len(R) else 1)
