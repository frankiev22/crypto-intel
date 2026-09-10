"""The sweep must catch the bug it was written for, or "none" means nothing.

scanner.py:273 is fixed, so a clean report is now the expected result - which
makes the report worthless as evidence unless the detector is shown to still
fire on the defect. These tests feed it the ORIGINAL defective source and the
shapes it must generalise to.

Run: python test_evidenceguard.py    (offline, writes to a temp dir)
"""
import os
import sys
import tempfile

import evidenceguard as EG

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


TMP = tempfile.mkdtemp()


def write(name, src):
    p = os.path.join(TMP, name)
    open(p, "w", encoding="utf-8").write(src)
    return p


print("=" * 70)
print("1. the original defect is still caught")
print("=" * 70)
ORIGINAL = '''
import onchain, paper
def enrich(row):
    _act = (row.get("score", 0) >= 70) or paper.qualifies(row)[0]
    if _act and row.get("addr"):
        a = onchain.authorities(row["addr"])
        row["can_mint"] = a.get("can_mint")
    return row
'''
hits = EG.audit([write("original.py", ORIGINAL)])
check("scanner.py:273 as it was, is flagged", len(hits) == 1, str(hits))
if hits:
    check("named as gated by the score", "score" in hits[0]["verdict"], str(hits[0]["verdict"]))
    check("and the evidence it suppresses is named",
          any("authorities" in e for e in hits[0]["evidence"]), str(hits[0]["evidence"]))

print()
print("=" * 70)
print("2. the same defect wearing an early exit")
print("=" * 70)
SKIP = '''
import onchain
def enrich(rows):
    for row in rows:
        if row.get("score", 0) < 70:
            continue
        row["can_mint"] = onchain.authorities(row["addr"]).get("can_mint")
'''
sk = EG.audit_skips([write("skip.py", SKIP)])
check("a verdict-gated `continue` that skips a fetch is flagged", len(sk) == 1, str(sk))
if sk:
    check("classified as a VERDICT skip, not a budget one", sk[0]["kind"] == "VERDICT",
          sk[0]["kind"])

print()
print("=" * 70)
print("3. the fixed shape is NOT flagged, and it is judged by derivation")
print("=" * 70)
FIXED = '''
import onchain, paper
def enrich(row):
    _act = paper.wants_authority_check(row)
    if _act and row.get("addr"):
        row["can_mint"] = onchain.authorities(row["addr"]).get("can_mint")
    return row
'''
check("a gate derived from a fact predicate is clean",
      EG.audit([write("fixed.py", FIXED)]) == [], str(EG.audit([write("fixed.py", FIXED)])))
# ...but rename the predicate and reintroduce a score read, and it must fire again
SNEAKY = '''
import onchain
def enrich(row):
    worth_it = row.get("score", 0) >= 70
    _act = worth_it
    if _act:
        row["can_mint"] = onchain.authorities(row["addr"]).get("can_mint")
'''
check("a verdict laundered through two variables is still caught",
      len(EG.audit([write("sneaky.py", SNEAKY)])) == 1,
      str(EG.audit([write("sneaky.py", SNEAKY)])))

print()
print("=" * 70)
print("4. decisions gated on verdicts are NOT flagged - only measurements")
print("=" * 70)
ALERT = '''
import findings
def announce(row, gate_ok):
    if gate_ok and row.get("mult", 0) >= 3.0:
        findings.record("outcome-win", row["token"], "a win")
'''
check("gating an ANNOUNCEMENT on a verdict is correct, not flagged",
      EG.audit([write("alert.py", ALERT)]) == [], str(EG.audit([write("alert.py", ALERT)])))

print()
print("=" * 70)
print("5. the live scan path is clean right now")
print("=" * 70)
live = EG.audit()
check("no measurement in the scan path is gated on a verdict", live == [],
      "; ".join(f"{f['file']}:{f['line']}" for f in live))
skips = EG.audit_skips()
verdict_skips = [f for f in skips if f["kind"] == "VERDICT"]
check("no measurement is skipped by a verdict-gated early exit",
      verdict_skips == [],
      "; ".join(f"{f['file']}:{f['line']}" for f in verdict_skips))
print(f"  ({len(skips)} BUDGET early-exit site(s) remain - resource decisions, "
      f"reported separately)")

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
