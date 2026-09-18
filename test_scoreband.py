"""No score may decide an entry, anywhere in this repo, ever again.

Run: python test_scoreband.py     (offline, writes nothing)

WHY THIS FILE EXISTS. `paper.qualifies()` contains `70 <= score <= 99`. A token
graded 100 - the cleanest grade the scorer can award - fails `100 <= 99` and is
rejected with "score 100 outside 70-99". The band was inferred from 4.55%
[2.62, 7.78] against 1.20% [0.64, 2.27]; those intervals OVERLAP, so the
separation was never significant, and the sample it was measured on had its
authority lookups gated on `score >= 70`, so the low-scoring arm was
structurally unable to qualify in the first place.

It was "fixed" once already and that fix only changed the WORDING. This file is
what makes the next one impossible to fake:

  1. The live v1 gate accepts a 100-grade token, at every score, including None.
  2. No entry gate in the repo may branch on a score term - checked at the AST
     level, because a comment promising it is not enforcement.

⭐ THE DISCRIMINATION THAT MATTERS: recording a score is fine, deciding on one
is not. `paperv2.open_entry` writes `score_at_entry` and a `sub_arm` computed
from the score into the record it appends, and that is correct - the score is an
observed fact about the row. What is banned is a score term inside a BRANCH that
can refuse or permit an entry. So this test flags score terms in `if`/`while`
tests and in returned expressions, and permits them in recorded values.
"""
import ast
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


HERE = os.path.dirname(os.path.abspath(__file__))

# Any function that can decide whether an entry is written, or write one.
ENTRY_GATES = {"qualifies", "qualifies_v1_historical", "open_entry",
               "wants_authority_check", "should_enter", "entry_gate"}

# A score term is anything a future author would reach for to resurrect the
# band. Substring match, case-insensitive, so SCORE_LO and `grade` are both
# caught without needing to be enumerated.
SCORE_WORDS = ("score", "grade")

# ⭐ THE ONE ALLOWLISTED SITE, with its justification recorded here rather than
# in a comment that can drift away from the code.
ALLOWED = {
    "paper.qualifies_v1_historical": (
        "AUDIT ONLY, and named so it cannot be mistaken for a live decision. "
        "409 rows in data/paper/ledger.jsonl each carry "
        "rule='amm+depth>=1000+score70-99', and RULE_V2's A/B arms are DEFINED "
        "as what that band accepted versus rejected. Deleting the band from "
        "every location would leave the repo unable to explain its own "
        "append-only record, which standing rule 8 forbids as surely as editing "
        "it would. Nothing in the live entry path calls this - asserted below by "
        "walking scanner.py's actual call site."),
}


def _strip_docstring(fn):
    """A copy of a function with its docstring removed.

    A docstring is prose about the code, not code. `wants_authority_check`'s own
    docstring says "Must never consult `score`" - a promise not to do the thing,
    which a substring scan would read as doing it.
    """
    body = list(fn.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    return ast.Module(body=body, type_ignores=[])


def scored(node):
    """Every score-ish token appearing anywhere under `node`."""
    hits = set()
    for n in ast.walk(node):
        text = None
        if isinstance(n, ast.Name):
            text = n.id
        elif isinstance(n, ast.Attribute):
            text = n.attr
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            text = n.value
        if text and any(w in text.lower() for w in SCORE_WORDS):
            hits.add(text)
    return hits


def deciding_subtrees(fn):
    """The parts of a function where a score would be DECIDING, not recorded.

    Branch tests, and returned expressions. A dict value inside a record being
    appended is neither, which is what lets `score_at_entry` through.
    """
    out = []
    for n in ast.walk(fn):
        if isinstance(n, (ast.If, ast.While)):
            out.append(n.test)
        elif isinstance(n, ast.Assert):
            out.append(n.test)
        elif isinstance(n, ast.Return) and n.value is not None:
            out.append(n.value)
    return out


print("=" * 70)
print("1. the live v1 gate no longer rejects anything for its score")
print("=" * 70)

import paper
import scanner

clean = {"venue_type": "amm", "exit_depth_usd": 50000.0, "can_mint": False,
         "can_freeze": False, "sells_h1": 40, "buys_h1": 60}

# ⭐ THE HEADLINE. A token graded 100 used to be refused with
# "score 100 outside 70-99". It must now pass.
ok100, why100 = paper.qualifies(dict(clean, score=100))
check("a 100-grade token QUALIFIES", ok100 is True, why100)

verdicts = {sc: paper.qualifies(dict(clean, score=sc))[0]
            for sc in (0, 1, 44, 69, 70, 85, 99, 100, None)}
check("the verdict is identical at every score, including None",
      set(verdicts.values()) == {True}, str(verdicts))

# No reason string anywhere in the live gate may mention a score.
reasons = {paper.qualifies(dict(clean, score=sc))[1]
           for sc in (0, 69, 100, None)}
check("no live rejection reason mentions a score",
      not any("score" in r.lower() for r in reasons), str(reasons))

check("the rule string no longer advertises a band",
      "score" not in paper.RULE_V1, paper.RULE_V1)

# The non-score clauses must be untouched - deleting the band is not licence to
# delete the filter. These are the clauses that have never been retracted.
check("a curve row is still refused",
      paper.qualifies(dict(clean, venue_type="bonding_curve"))[0] is False)
check("depth under $1,000 is still refused",
      paper.qualifies(dict(clean, exit_depth_usd=999.0))[0] is False)
check("unknown authority still FAILS CLOSED",
      paper.qualifies(dict(clean, can_mint=None))[0] is False)
check("live mint authority is still refused",
      paper.qualifies(dict(clean, can_mint=True))[0] is False)
check("live freeze authority is still refused",
      paper.qualifies(dict(clean, can_freeze=True))[0] is False)
check("buys with no sells is still refused",
      paper.qualifies(dict(clean, sells_h1=0, buys_h1=10))[0] is False)

# The band survives ONLY as the auditor of the frozen ledger.
h85 = paper.qualifies_v1_historical(dict(clean, score=85))
h100 = paper.qualifies_v1_historical(dict(clean, score=100))
check("the historical auditor still reproduces the old band: 85 in",
      h85[0] is True, h85[1])
check("...and 100 out, which is what the 409 rows were written under",
      h100[0] is False and "100" in h100[1], h100[1])
check("the historical rule string is preserved verbatim",
      paper.RULE_V1_HISTORICAL == "amm+depth>=1000+score70-99",
      paper.RULE_V1_HISTORICAL)

# ⛔ and the auditor must not be reachable from the live entry path.
ssrc = io.open(os.path.join(HERE, "scanner.py"), encoding="utf-8").read()
check("the scanner calls the live gate", "paper.qualifies(row)" in ssrc)
check("the scanner never calls the historical auditor",
      "qualifies_v1_historical" not in ssrc)

print()
print("=" * 70)
print("2. no entry gate in the repo branches on a score term")
print("=" * 70)

files = sorted(f for f in os.listdir(HERE)
               if f.endswith(".py") and not f.startswith("test_"))
violations = []
excused = set()
audited = 0

for fname in files:
    try:
        tree = ast.parse(io.open(os.path.join(HERE, fname), encoding="utf-8").read())
    except SyntaxError as e:
        violations.append((fname, "<parse>", f"SyntaxError: {e}"))
        continue
    mod = fname[:-3]
    for node in ast.walk(tree):
        if not isinstance(node, ast.FunctionDef) or node.name not in ENTRY_GATES:
            continue
        qual = f"{mod}.{node.name}"
        audited += 1
        hits = set()
        for sub in deciding_subtrees(_strip_docstring(node)):
            hits |= scored(sub)
        if not hits:
            continue
        if qual in ALLOWED:
            excused.add(qual)
            continue
        violations.append((fname, qual, ", ".join(sorted(hits))))

check(f"found entry gates to audit ({audited})", audited >= 4, str(audited))
for f, q, h in violations:
    print(f"        {f}: {q} branches on {h}")
check("no unallowlisted entry gate branches on a score",
      not violations, f"{len(violations)} violation(s)")

# The allowlist may not grow silently, and every entry in it must carry a
# written justification long enough to be a real one.
# ⛔ AN ALLOWLIST THAT NEVER FIRES IS NOT AN ALLOWLIST, IT IS DECORATION. The
# first version of this file allowlisted a function whose name was not in
# ENTRY_GATES, so it was never scanned and the entry excused nothing while
# looking like it did. Assert every allowlisted name was actually reached AND
# actually tripped the scan.
check("every allowlisted gate was actually audited and did trip the scan",
      excused == set(ALLOWED), f"excused={sorted(excused)}")

check("the allowlist has exactly one entry", len(ALLOWED) == 1,
      ", ".join(sorted(ALLOWED)))
check("and it is the historical auditor, not the live gate",
      "paper.qualifies_v1_historical" in ALLOWED
      and "paper.qualifies" not in ALLOWED)
check("and its justification is written out",
      all(len(v) > 200 for v in ALLOWED.values()))

# ⛔ An allowlisted auditor is only safe while nothing live calls it. Only
# paperv2 may, and only to label a frozen A/B whose arms are DEFINED by the band.
callers = set()
for fname in files:
    src = io.open(os.path.join(HERE, fname), encoding="utf-8").read()
    if "qualifies_v1_historical" in src and fname != "paper.py":
        callers.add(fname)
check("only paperv2.py calls the historical auditor", callers <= {"paperv2.py"},
      ", ".join(sorted(callers)) or "none")
import paperv2
check("and paperv2's ledger is frozen, so even that cannot write",
      paperv2.frozen() is True)

print()
print("=" * 70)
print("3. the score still never gates the EVIDENCE")
print("=" * 70)

# Same bug class as the band and the reason the band's sample was worthless:
# the authority lookup used to run only if score >= 70, so a low-scoring token
# could never be verified and therefore could never qualify.
fn = next(n for n in ast.walk(ast.parse(
    io.open(os.path.join(HERE, "paper.py"), encoding="utf-8").read()))
    if isinstance(n, ast.FunctionDef) and n.name == "wants_authority_check")
_body = _strip_docstring(fn)
check("wants_authority_check mentions no score term anywhere",
      not scored(_body), ", ".join(sorted(scored(_body))))

row = {"venue_type": "amm", "exit_depth_usd": 50000.0, "sells_h1": 40,
       "buys_h1": 60}
check("its verdict is identical at every score",
      {paper.wants_authority_check(dict(row, score=s))
       for s in (0, 44, 69, 70, 100, None)} == {True})

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
