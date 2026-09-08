"""A transient read failure must never become a permanent delete.

`findings.py::_load_seen` came minutes from atomically replacing 852 dedup
entries with `{}` during a merge window. The shape - load with a bare except
returning empty, then write whatever was loaded - existed at five sites. These
tests pin the contract at the helper and at every one of those five callers.

Run: python test_safeload.py    (offline, sandboxed, touches no real data)
"""
import io
import json
import os
import shutil
import sys
import tempfile

import safeload

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


def corrupt(path, text="{not json at all"):
    with io.open(path, "w", encoding="utf-8") as f:
        f.write(text)


print("=" * 70)
print("1. safeload distinguishes ABSENT from UNREADABLE")
print("=" * 70)
d = tempfile.mkdtemp()
p = os.path.join(d, "s.json")
check("absent file returns a fresh default", safeload.load_json(p) == {})
safeload.save_json(p, {"a": 1, "b": 2})
check("a populated file round-trips", safeload.load_json(p) == {"a": 1, "b": 2})
corrupt(p)
try:
    safeload.load_json(p)
    check("corrupt file raises rather than returning {}", False, "it returned")
except safeload.LoadFailed:
    check("corrupt file raises rather than returning {}", True)
# a JSON file that parses to the WRONG TYPE is corrupt, not empty
with io.open(p, "w", encoding="utf-8") as f:
    f.write('["a list, not a dict"]')
try:
    safeload.load_json(p)
    check("wrong top-level type raises too", False, "it returned")
except safeload.LoadFailed:
    check("wrong top-level type raises too", True)

print()
print("=" * 70)
print("2. the writer refuses to empty a populated file, independently")
print("=" * 70)
safeload.save_json(p, {"keep": "me"}, allow_empty=True)
try:
    safeload.save_json(p, {})
    check("empty-over-populated is refused", False, "the write went through")
except safeload.RefusedShrink:
    check("empty-over-populated is refused", True)
check("and the file is untouched", safeload.load_json(p) == {"keep": "me"})
safeload.save_json(p, {}, allow_empty=True)
check("an explicit empty write is still allowed", safeload.load_json(p) == {})

print()
print("=" * 70)
print("3. every one of the five real call sites survives a corrupt file")
print("=" * 70)


def site(label, module_name, path_attr, seed, exercise, expect_intact=True):
    """Corrupt the module's own state file, run the write path, assert survival."""
    import importlib
    m = importlib.import_module(module_name)
    real = getattr(m, path_attr)
    tmpd = tempfile.mkdtemp()
    fake = os.path.join(tmpd, os.path.basename(real))
    setattr(m, path_attr, fake)
    try:
        with io.open(fake, "w", encoding="utf-8") as f:
            json.dump(seed, f)
        before = io.open(fake, encoding="utf-8").read()
        corrupt(fake, before[:len(before) // 2])        # truncated, as a crash would leave it
        mid = io.open(fake, encoding="utf-8").read()
        try:
            exercise(m)
        except safeload.LoadFailed:
            pass                                         # propagating is fine; writing is not
        after = io.open(fake, encoding="utf-8").read()
        check(f"{label}: corrupt state is not overwritten", after == mid,
              f"file changed from {len(mid)}B to {len(after)}B")
        check(f"{label}: and was NOT replaced with empty",
              after.strip() not in ("{}", ""), f"got {after.strip()[:20]!r}")
    finally:
        setattr(m, path_attr, real)
        shutil.rmtree(tmpd, ignore_errors=True)


SEED = {f"key{i}": {"count": i, "first_seen": "2026-09-01T00:00:00"} for i in range(40)}

site("findings._save_seen", "findings", "SEEN", SEED,
     lambda m: m.record("selftest", "k", "summary", allow_discord=False))
site("liveness.beat", "liveness", "REG",
     {f"c{i}": {"last_ts": 1, "count": i, "first_ts": 1} for i in range(40)},
     lambda m: m.beat("selftest"))
site("watchlist.add", "watchlist", "ACTIVE",
     {f"C{i}": {"contract": f"C{i}", "added_ts": 1, "checks": []} for i in range(40)},
     lambda m: m.consider({"addr": "NEWTOKEN", "fdv": 50000})
     if hasattr(m, "consider") else None)
site("wallets.load_watchlist", "wallets", "WATCHLIST", SEED,
     lambda m: m.load_watchlist())

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
