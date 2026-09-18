"""Regression tests for the paper ledger's three money-critical invariants.

Run: python test_paper.py    (offline, sandboxed, writes nothing real)

1. `chain_depth_usd` persists. Solana RPC has no historical account state at any
   tier, so a reserve reading not stored at the moment of close can never be
   recovered. A silent drop here does not produce a wrong number, it produces a
   permanently unauditable ledger. Four fields have been silently dropped in
   this repo already, all by `journal.record()`'s whitelist; `paper._append()`
   has no whitelist, and this test exists to keep it that way.

2. The entry gate cannot widen. Every gate constant reads an environment
   variable, so the rule could be loosened without touching Python. The
   measurement runs to n=200 on 2026-09-14 and a gate that moves mid-run makes
   the closes non-comparable.

3. Unknown mint/freeze authority fails closed. It used to pass: 85% of
   qualifying observations had no authority recorded, so 85% of entries were
   opened without knowing whether the deployer could print or freeze.
"""
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ⛔ Before anything that writes. A full suite run was appending rows to
# data/liveness/ - the file that answers "is the collector alive" - so the
# tests were writing into the health signal they are meant to check.
# run_tests.py fails if data/ changes at all; this is how a suite complies.
import testsandbox
testsandbox.activate()
import tempfile

import paper

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


print("=" * 70)
print("1. chain_depth_usd must reach storage and come back")
print("=" * 70)
paper.LEDGER = os.path.join(tempfile.mkdtemp(), "ledger.jsonl")
e = paper.open_entry("TESTcontract1111111111111111111111111111111",
                     symbol="TESTONLY", price=0.001, exit_depth=5000,
                     liq=10000, fdv=10000, score=80, venue_type="amm",
                     dex_id="test", pair="TESTpair")
rec = paper.close_entry(e["hash"], price=0.002, exit_depth=4000,
                        reason="test", chain_depth=1234.56)
on_disk = [json.loads(l) for l in open(paper.LEDGER, encoding="utf-8")
           if json.loads(l).get("type") == "exit"][0]
check("close_entry returns it", rec.get("chain_depth_usd") == 1234.56)
check("it is written to the jsonl", on_disk.get("chain_depth_usd") == 1234.56,
      f"got {on_disk.get('chain_depth_usd')!r}")
check("it survives _read()",
      [r for r in paper._read() if r.get("type") == "exit"][0]
      .get("chain_depth_usd") == 1234.56)
check("the hash chain is still intact", paper.verify()[0])
# An unmeasurable reading must record None, not silently vanish or become 0.
e2 = paper.open_entry("TESTcontract2222222222222222222222222222222",
                      symbol="TESTONLY2", price=0.001, exit_depth=5000,
                      liq=10000, fdv=10000, score=80, venue_type="amm",
                      dex_id="test", pair="TESTpair2")
r2 = paper.close_entry(e2["hash"], price=0.001, exit_depth=10, reason="test")
check("an unmeasured reading records None, never 0",
      "chain_depth_usd" in r2 and r2["chain_depth_usd"] is None,
      f"got {r2.get('chain_depth_usd')!r}")

print()
print("=" * 70)
print("2. the entry gate cannot widen (locked until n=200 on 2026-09-14)")
print("=" * 70)
check("gate is unchanged right now", not paper.gate_drift(),
      str(paper.gate_drift()))
_orig = paper.MIN_EXIT_DEPTH
paper.MIN_EXIT_DEPTH = 10.0                      # simulate a loosened env var
drift = paper.gate_drift()
check("a widened gate is detected", bool(drift), str(drift))
ok, why = paper.qualifies({"venue_type": "amm", "exit_depth_usd": 50,
                           "score": 80, "can_mint": False, "can_freeze": False,
                           "sells_h1": 5, "buys_h1": 20})
check("a widened gate refuses every entry", ok is False)
check("and says why", "DRIFTED" in why, why[:60])
paper.MIN_EXIT_DEPTH = _orig

print()
print("=" * 70)
print("3. unknown mint/freeze authority fails closed")
print("=" * 70)
base = {"venue_type": "amm", "exit_depth_usd": 5000, "score": 80,
        "sells_h1": 5, "buys_h1": 20}
check("unknown authority does NOT qualify", paper.qualifies(dict(base))[0] is False)
check("live mint authority does NOT qualify",
      paper.qualifies(dict(base, can_mint=True, can_freeze=False))[0] is False)
check("live freeze authority does NOT qualify",
      paper.qualifies(dict(base, can_mint=False, can_freeze=True))[0] is False)
check("both revoked DOES qualify",
      paper.qualifies(dict(base, can_mint=False, can_freeze=False))[0] is True)

print()
print("=" * 70)
print("4. a merge fork is not tampering, but tampering is still caught")
print("=" * 70)
import json as _json
paper.LEDGER = os.path.join(tempfile.mkdtemp(), "ledger.jsonl")
a = paper.open_entry("TESTaaa1111111111111111111111111111111111111", symbol="A",
                     price=0.001, exit_depth=5000, liq=1, fdv=1, score=80,
                     venue_type="amm", dex_id="t", pair="pA")
b = paper.open_entry("TESTbbb2222222222222222222222222222222222222", symbol="B",
                     price=0.001, exit_depth=5000, liq=1, fdv=1, score=80,
                     venue_type="amm", dex_id="t", pair="pB")
check("a clean chain verifies", paper.verify()[0])

# simulate the merge: a second writer's row that chains to the FIRST row, so
# two rows share seq=1 and one re-parents. Nothing edited, nothing removed.
rows = [_json.loads(l) for l in open(paper.LEDGER, encoding="utf-8")]
forked = dict(rows[1]); forked["contract"] = "TESTccc333333333333333333333333333333333333"
forked["symbol"] = "C"; forked["prev"] = rows[0]["hash"]; forked["seq"] = 1
forked["hash"] = paper._hash(forked)
with open(paper.LEDGER, "a", encoding="utf-8") as f:
    f.write(_json.dumps(forked, sort_keys=True) + "\n")
ok, _, msg = paper.verify()
check("a concurrent-writer fork verifies as OK", ok, msg)
check("and is reported as a fork, not as intact", "FORKED" in msg, msg[:70])

# now actually tamper: edit a row's content without rehashing
rows = [_json.loads(l) for l in open(paper.LEDGER, encoding="utf-8")]
rows[0]["entry_price_usd"] = 999999.0
with open(paper.LEDGER, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(_json.dumps(r, sort_keys=True) + "\n")
ok2, _, msg2 = paper.verify()
check("an edited row still FAILS verification", ok2 is False, msg2[:70])
check("and says it was edited in place", "hash" in msg2, msg2[:70])

print()
print("=" * 70)
print("5. the score must never gate the authority lookup")
print("=" * 70)
import ast
import io
import scanner

# The predicate itself may not read `score`, at the AST level - a comment
# saying so is not enforcement.
fn = next(n for n in ast.walk(ast.parse(io.open("paper.py", encoding="utf-8").read()))
          if isinstance(n, ast.FunctionDef) and n.name == "wants_authority_check")
names = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant)
         and isinstance(n.value, str)}
attrs = {n.attr for n in ast.walk(fn) if isinstance(n, ast.Attribute)}
check("wants_authority_check never mentions score",
      "score" not in names and "score" not in attrs, str(names | attrs))

row = {"venue_type": "amm", "exit_depth_usd": 50000.0,
       "sells_h1": 40, "buys_h1": 60}
verdicts = set()
for sc in (0, 10, 44, 69, 70, 100, None):
    verdicts.add(paper.wants_authority_check(dict(row, score=sc)))
check("the verdict is identical at every score", verdicts == {True}, str(verdicts))
check("a curve row still earns no lookup",
      paper.wants_authority_check(dict(row, venue_type="bonding_curve")) is False)
check("a row under the depth floor earns no lookup",
      paper.wants_authority_check(dict(row, exit_depth_usd=999.0)) is False)
check("a row with no sell side earns no lookup",
      paper.wants_authority_check(dict(row, sells_h1=0, buys_h1=10)) is False)

# and the scanner must actually use it, with no score comparison left behind
ssrc = io.open("scanner.py", encoding="utf-8").read()
check("scanner calls the predicate",
      "paper.wants_authority_check(row)" in ssrc)
check("the dead `or paper.qualifies(row)[0]` branch is gone",
      "AUTHORITY_CHECK_SCORE) or paper.qualifies(row)[0]" not in ssrc)

# The gate itself must be untouched by all of this.
check("gate constants still match RULE_V1", not paper.gate_drift(),
      str(paper.gate_drift()))

bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
