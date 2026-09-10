"""There must be exactly one gate, and no door beside it.

track.py decided whether to ANNOUNCE a win by calling the old three-check
journal.realizable() - alive, depth floor, plausibility - while the row itself
was gated by the eight-check verify_win(). Two computations, two answers, and
the looser one drove the alerts. Four of one day's twelve pinged wins went
through that gap, while Frank had been told "nothing gets counted unless it
clears all eight checks".

Run: python test_gate.py    (offline, sandboxed)
"""
import ast
import io
import sys

import journal

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


print("=" * 70)
print("1. the pre-gate helper is sealed")
print("=" * 70)
try:
    journal.realizable("alive", 50000, 4.0)
    check("journal.realizable() raises instead of answering", False, "it returned")
except RuntimeError as e:
    check("journal.realizable() raises instead of answering", True)
    check("and the error names the replacement", "verify_win" in str(e), str(e)[:60])
check("the internal subset still exists for legacy backfill",
      callable(journal._exit_liquidity_ok))

print()
print("=" * 70)
print("2. the gate is strictly stronger than what it replaced")
print("=" * 70)
# alive, deep, plausible: the three old checks all pass.
old_ok, _ = journal._exit_liquidity_ok("alive", 50000, 4.0, exit_depth=20000)
check("the old subset passes this row", old_ok is True)
# ...but the pool priced is not the pool held, depth was never measured, and
# no elapsed time was recorded.
gate_ok, failed = journal.verify_win("alive", 50000, 4.0, exit_depth=None,
                                     pair="POOL_A", exit_pair="POOL_B",
                                     elapsed_h=None)
check("the gate rejects it", gate_ok is False)
check("naming every check it failed",
      set(failed) == {"pair_identity", "depth_measured", "elapsed_recorded"},
      str(failed))
# A row that clears the gate must also clear the subset - the subset is a
# strict sub-part, so the gate can never be the looser of the two.
g2, _ = journal.verify_win("alive", 50000, 4.0, exit_depth=20000, pair="P",
                           exit_pair="P", elapsed_h=24.0, sells_h24=50,
                           buys_h24=40)
o2, _ = journal._exit_liquidity_ok("alive", 50000, 4.0, exit_depth=20000)
check("anything the gate passes, the subset passes too", not (g2 and not o2))

print()
print("=" * 70)
print("3. record_outcome hands back the verdict it recorded")
print("=" * 70)
src = io.open("journal.py", encoding="utf-8").read()
fn = next(n for n in ast.walk(ast.parse(src))
          if isinstance(n, ast.FunctionDef) and n.name == "record_outcome")
rets = [n for n in ast.walk(fn) if isinstance(n, ast.Return)]
check("it returns a 4-tuple, not (status, mult)",
      any(isinstance(r.value, ast.Tuple) and len(r.value.elts) == 4 for r in rets),
      str([len(r.value.elts) for r in rets if isinstance(r.value, ast.Tuple)]))

print()
print("=" * 70)
print("4. NO module reaches for a pre-gate helper any more")
print("=" * 70)
offenders = []
for path in ("track.py", "journal.py", "collect.py", "digest.py", "moves.py",
             "paper.py", "check.py", "milestones.py", "dashboard.py"):
    try:
        tree = ast.parse(io.open(path, encoding="utf-8").read())
    except OSError:
        continue
    for node in ast.walk(tree):
        if not isinstance(node, ast.Call):
            continue
        f = node.func
        name = (f.attr if isinstance(f, ast.Attribute)
                else (f.id if isinstance(f, ast.Name) else None))
        if name == "realizable":
            offenders.append(f"{path}:{node.lineno}")
        # the internal subset may ONLY be called from journal.py
        if name == "_exit_liquidity_ok" and path != "journal.py":
            offenders.append(f"{path}:{node.lineno} (internal subset)")
check("no live call site anywhere", not offenders, str(offenders))

# and the announce path specifically must use the row's verdict
tsrc = io.open("track.py", encoding="utf-8").read()
check("track.py binds the gate verdict from record_outcome",
      "status, mult, gate_ok, gate_failed = journal.record_outcome(" in tsrc)
check("and the win announcement gates on it",
      "and gate_ok" in tsrc and "journal.realizable(" not in tsrc.replace(
          "# three-check journal.realizable()", ""))

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
