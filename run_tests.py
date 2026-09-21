"""Run every suite and FAIL if it changed data/. Run: python run_tests.py

⛔ TWO THINGS THIS ASSERTS, AND THE SECOND IS THE POINT.

1. Every `test_*.py` exits 0. There was no single command for this; suites were
   run by hand, individually, which means "the suite passes" was never a fact
   anybody had actually checked.

2. ⭐ THE SUITES DID NOT WRITE INTO `data/`. Measured 2026-09-18: a full run
   appended 24 rows to `data/liveness/2026-09.jsonl` and 3 to
   `data/findings/2026-09-18.md`. `liveness` is what answers "is the collector
   alive", so the tests were quietly writing into the health signal - the
   instrument changing the thing it measures, the same family as standing rules
   13 and 14. Rule 8 means the rows already committed stay. This stops more.

   ⚠️ This is an assertion on the OUTPUT (did data/ change) rather than on the
   process (did the suite remember to import testsandbox), which is the whole of
   docs/ENGINEERING_DISCIPLINE.md rule A. A suite can sandbox itself however it
   likes; it just may not leave fingerprints.

Exit 0 only if both hold.
"""
import glob
import hashlib
import io
import os
import subprocess
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
DATA = os.path.join(HERE, "data")


def snapshot():
    """path -> sha1, for every file under data/. Content, not mtime."""
    out = {}
    for root, dirs, files in os.walk(DATA):
        dirs[:] = [d for d in dirs if d != ".git"]
        for f in files:
            # An atomic write lands as <name>.tmp and is renamed. Catching one
            # mid-flight is a race in the reader, not a change to the journal.
            if f.endswith(".tmp"):
                continue
            p = os.path.join(root, f)
            try:
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, HERE)] = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                pass
    return out


UNATTENDED = ("scheduled", "runner")


def _pass_margin():
    """How long a pass can be WORKING AND SILENT, from collect.py's own limits.

    ⛔ The first version of this detector asked only "did an unattended pass beat
    BETWEEN t0 and t1". It missed a pass that was writing the whole time: on
    2026-09-21 the suite ran inside a 98-second gap between `dashboard.build`
    (05:10:22) and `market.snapshot` (05:12:00), and the market stage spent that
    gap making live Jupiter calls - it wrote data/_jupiter_usage.json at
    05:11:35, mid-suite, and the run still reported "THE SUITE WROTE INTO data/".

    That is standing rule 13 at small scale: a sampler narrower than the thing it
    samples. A beat marks the END of a stage's work, not its span, so a window
    that only counts beats inside it cannot see a stage that is mid-flight. The
    margin is taken from KILL_S - the longest a single staged command is allowed
    to run - so "a beat this close to the window" means "a stage could have been
    working through it". Imported, never hardcoded, so it tracks the real limit.
    """
    try:
        import collect
        return float(collect.KILL_S) + 60.0
    except Exception:
        return 240.0


def _unattended_beats(t0, t1):
    """Beats an unattended pass wrote around the suite run: [(origin, names, n,
    first_ts, last_ts)]. Read straight from the liveness journal - the same
    rows the collector writes - so it is evidence, not an inference.

    The window is widened by _pass_margin() on BOTH sides: a pass whose last
    beat lands just before the suite starts is still running through it, and one
    whose first beat lands just after was working during it. See that docstring
    for the failure this exists to catch."""
    import collections
    import datetime as _dt
    import json
    m = _pass_margin()
    t0, t1 = t0 - m, t1 + m
    now = _dt.datetime.now(_dt.timezone.utc)
    seen = collections.defaultdict(lambda: [set(), 0, None, None])
    for month in {now.strftime("%Y-%m"), (now - _dt.timedelta(days=1)).strftime("%Y-%m")}:
        path = os.path.join(HERE, "data", "liveness", f"{month}.jsonl")
        try:
            with open(path, encoding="utf-8") as f:
                for line in f:
                    try:
                        r = json.loads(line)
                    except ValueError:
                        continue
                    ts, o = r.get("ts"), str(r.get("origin"))
                    if not isinstance(ts, (int, float)) or not (t0 <= ts <= t1):
                        continue
                    if o not in UNATTENDED:
                        continue
                    e = seen[o]
                    e[0].add(str(r.get("name")))
                    e[1] += 1
                    e[2] = ts if e[2] is None else min(e[2], ts)
                    e[3] = ts if e[3] is None else max(e[3], ts)
        except OSError:
            continue
    return [(o, v[0], v[1], v[2], v[3]) for o, v in sorted(seen.items())]


def main():
    suites = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    # --live hits the network and costs credits; never on by default.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    before = snapshot()
    _t_start = time.time()
    print(f"{len(before)} files under data/ hashed")
    print("=" * 72)

    failed, results = [], []
    for s in suites:
        name = os.path.basename(s)
        t0 = time.time()
        r = subprocess.run([sys.executable, s], capture_output=True, text=True,
                           encoding="utf-8", errors="replace", env=env, cwd=HERE)
        dt = time.time() - t0
        tail = [l for l in (r.stdout or "").splitlines() if l.strip()]
        last = tail[-1] if tail else (r.stderr or "").strip().splitlines()[-1:] or [""]
        last = last if isinstance(last, str) else (last[0] if last else "")
        ok = r.returncode == 0
        if not ok:
            failed.append((name, r))
        results.append((name, ok, dt, last))
        print(f"  {'PASS' if ok else 'FAIL'}  {name:<24} {dt:5.1f}s  {last}")

    after = snapshot()
    print("=" * 72)

    added = sorted(set(after) - set(before))
    removed = sorted(set(before) - set(after))
    changed = sorted(p for p in set(before) & set(after) if before[p] != after[p])
    dirty = added + removed + changed

    if dirty:
        # ⭐ WHO WROTE IT? A collector pass that fires mid-suite changes data/
        # too, and it is not the suite's fault. On 2026-09-19 this message was
        # read as "my test did it", the files were reverted with git checkout,
        # and ~10.5h of liveness beats were destroyed - standing rule 8, broken
        # by the tool that exists to protect the journal. It now names the
        # writer before it accuses anything.
        _t_end = time.time()
        beats = _unattended_beats(_t_start, _t_end)
        if beats:
            print("⚠ data/ changed during the run, but an UNATTENDED PASS WAS WRITING:")
            for o, names, n, lo, hi in beats:
                # ⭐ Say WHERE the beats fell relative to the run. "A pass was
                # beating throughout" and "a pass beat 40s before it started"
                # are different strengths of evidence and must not read alike.
                if lo <= _t_start and hi >= _t_end:
                    where = "throughout the run"
                elif hi < _t_start:
                    where = f"ending {_t_start - hi:.0f}s BEFORE the run - mid-stage through it"
                elif lo > _t_end:
                    where = f"starting {lo - _t_end:.0f}s AFTER it - working during it"
                else:
                    where = "overlapping the run"
                print(f"     origin={o}: {n} beats over {hi - lo:.0f}s, {where}  "
                      f"({', '.join(sorted(names)[:6])})")
            print("   The suites are not implicated by this alone. Re-run when no "
                  "pass is in flight to separate the two.")
        else:
            print("⛔ THE SUITE WROTE INTO data/. A test may not touch the journal.")
        for p in changed:
            print(f"     CHANGED  {p}")
        for p in added:
            print(f"     ADDED    {p}")
        for p in removed:
            print(f"     ⛔ REMOVED {p}   <- standing rule 8")
        if not beats:
            print("   Fix: `import testsandbox; testsandbox.activate()` at the top of"
                  " the offending suite, before it imports anything that writes.")
        print("   ⛔ NEVER `git checkout` data/ to clear this. The journals are "
              "append-only and what you discard is unrecoverable (standing rule 8).")
    else:
        print("⭐ data/ is byte-identical after the run")

    n = len(results)
    print(f"{n - len(failed)}/{n} suites passed")
    if failed:
        print()
        for name, r in failed:
            print(f"--- {name} ---")
            print((r.stdout or "")[-1500:])
            if r.stderr.strip():
                print((r.stderr or "")[-1500:])
    return 1 if (failed or dirty) else 0


if __name__ == "__main__":
    sys.exit(main())
