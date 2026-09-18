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
            p = os.path.join(root, f)
            try:
                with open(p, "rb") as fh:
                    out[os.path.relpath(p, HERE)] = hashlib.sha1(fh.read()).hexdigest()
            except OSError:
                pass
    return out


def main():
    suites = sorted(glob.glob(os.path.join(HERE, "test_*.py")))
    # --live hits the network and costs credits; never on by default.
    env = dict(os.environ, PYTHONIOENCODING="utf-8")

    before = snapshot()
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
        print("⛔ THE SUITE WROTE INTO data/. A test may not touch the journal.")
        for p in changed:
            print(f"     CHANGED  {p}")
        for p in added:
            print(f"     ADDED    {p}")
        for p in removed:
            print(f"     ⛔ REMOVED {p}   <- standing rule 8")
        print("   Fix: `import testsandbox; testsandbox.activate()` at the top of"
              " the offending suite, before it imports anything that writes.")
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
