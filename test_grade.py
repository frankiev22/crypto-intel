"""A live or unverified authority can never surface as a high number.

PTN (PTNzAfFAB4LvoUQEUUGrFMyUoRLExMYjH6CcfyQfsVP) went out on 2026-09-14 as
"scored 100" with mint and freeze authority both live. The score is left alone -
v1's pinned gate and v2's arm split read it - and every surface reads `grade`.
PRECOMMIT_surface_grade.md.

Run: python test_grade.py    (offline; writes nothing)
"""
import inspect
import io
import sys

import collect
import journal
import notify
import paper
import scanner

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


def section(t):
    print("=" * 70)
    print(t)
    print("=" * 70)


section("1. the rule, exactly as pre-committed")
g = scanner.surface_grade
check("live mint authority -> grade 0, TRAP", g({"score": 100, "can_mint": True, "can_freeze": False}) == (0, scanner.LABEL_TRAP))
check("live freeze authority -> grade 0, TRAP", g({"score": 100, "can_mint": False, "can_freeze": True})[0] == 0)
check("both live, unknown other fields -> still 0", g({"score": 100, "can_mint": True, "can_freeze": None})[0] == 0)
check("unknown authority caps at 69", g({"score": 100, "can_mint": None, "can_freeze": None}) == (69, scanner.LABEL_UNVERIFIED))
check("one unknown is unknown", g({"score": 95, "can_mint": False, "can_freeze": None})[0] == 69)
check("unknown below the cap keeps its score", g({"score": 50})[0] == 50)
check("both revoked -> grade is the score, no label", g({"score": 91, "can_mint": False, "can_freeze": False}) == (91, None))
check("the ceiling is PASS_SCORE - 1, not a tuned number",
      scanner.GRADE_UNVERIFIED_CEILING == collect.PASS_SCORE - 1)
row = {"score": 100, "can_mint": True, "can_freeze": True}
g(row)
check("surface_grade never writes score", row["score"] == 100)

section("2. every surface reads grade")
check("the scanner stamps grade on every enriched row",
      'row["grade"], row["grade_label"] = surface_grade(row)' in inspect.getsource(scanner.scan))
_ss = inspect.getsource(collect.scan_stage)
check("alerts go out on grade", 'r.get("grade", 0) >= PASS_SCORE' in _ss and "for r in surfaced:" in _ss)
check("the recorded series still counts score", 'r["score"] >= PASS_SCORE' in _ss)
check("journal persists grade beside score",
      '"grade": r.get("grade")' in io.open(journal.__file__, encoding="utf-8").read())
check("scanner.report prints grade, not score", "r['score']:3d" not in inspect.getsource(scanner.report))

notify.evidence.band_line = lambda *a, **k: "Band history line"
BASE = {"name": "PTN", "url": "u", "liq": 1.0, "v24": 1.0, "age_h": 0.2, "chg_h1": 0.0,
        "reasons": [], "flags": ["MINT AUTHORITY LIVE"], "score": 100}
trap = dict(BASE, grade=0, grade_label=scanner.LABEL_TRAP)
e = notify.candidate_embed(trap)
check("a trap embed never shows the score", "100" not in e["title"] and "TRAP" in e["title"], e["title"])
check("...is red", e["color"] == 0xE74C3C)
check("...and carries no score-band history", "Band history" not in e["description"])
unv = dict(BASE, flags=[], score=95, grade=69, grade_label=scanner.LABEL_UNVERIFIED)
e = notify.candidate_embed(unv)
check("an unverified embed shows grade 69 and says why",
      "grade 69" in e["title"] and "unverified" in e["title"] and "95" not in e["title"], e["title"])
ok = dict(BASE, flags=[], score=90, grade=90, grade_label=None)
e = notify.candidate_embed(ok)
check("a verified embed shows its grade and history",
      e["title"].endswith("grade 90 of 100") and "Band history" in e["description"], e["title"])

section("3. the ledgers cannot see any of this")
check("v1's pinned gate has not moved", paper.gate_drift() == [])
clean = {"venue_type": "amm", "exit_depth_usd": 5000.0, "sells_h1": 5, "buys_h1": 20}
for label, auth in (("live", {"can_mint": True, "can_freeze": False}),
                    ("unknown", {"can_mint": None, "can_freeze": None})):
    r = dict(clean, score=90, **auth)
    gr, _ = scanner.surface_grade(r)
    a = paper.qualifies(r)[0]
    b = paper.qualifies(dict(r, score=gr))[0]
    check(f"v1: {label} authority is refused whether it reads score or grade", a is False and b is False)

section("4. the dashboard calls it a graduation only where a pool exists")
import dashboard
NOW = 2_000_000_000
_cs = [{"symbol": "REAL", "real_pool": True, "fdv_cross": True, "crossed_ts": NOW - 3600},
       {"symbol": "Minecraft", "real_pool": False, "fdv_cross": True,
        "crossed_ts": NOW - 60, "liq_at_crossing": 0.49, "exit_depth_at_crossing": 0.26},
       {"symbol": "OLD", "real_pool": True, "crossed_ts": NOW - 8 * 86400}]
_g, _f = dashboard.graduated_split(_cs, NOW)
check("a real pool is a graduation", [c["symbol"] for c in _g] == ["REAL"], _g)
check("an FDV print on a $0.49 pool is not", [c["symbol"] for c in _f] == ["Minecraft"], _f)
check("older than 7 days is in neither list", all(c["symbol"] != "OLD" for c in _g + _f))
check("gather() uses the split", "graduated_split(" in inspect.getsource(dashboard.gather))

ok_n = sum(1 for _, c, _ in R if c)
print(f"\n{ok_n}/{len(R)} passed")
sys.exit(0 if ok_n == len(R) else 1)
