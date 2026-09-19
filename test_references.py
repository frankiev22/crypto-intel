"""Every file the repo names must exist. Run: python test_references.py

⛔ WHY THIS EXISTS. docs/CONSOLIDATION_PLAN.md phase 5 moves ~30 root docs into
docs/. They are named from code comments, CLAUDE.md, the backlog and the site
README, and a move that misses one leaves a pointer to nothing - silently, the
failure class this repo keeps finding. This lands BEFORE any move (phase 0), so
a move is checked by a failing test, not by a reader who notices months later.

⭐ Its first run found two it was built to catch, and I wrote both:
`market.py` and `coverage_probe.py` pointed at `docs/COVERAGE.md`; the file is
at the repo root. One of them was inside a caveat string published to the site.

A reference resolves if it exists relative to the repo root, to the naming
file's directory, or to docs/. PLANNED names things deliberately not written
yet; each carries its reason, and an entry that starts to resolve must be
removed from the list (the last check), so the allowlist cannot rot.
"""
import os
import re
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


PLANNED = {
    # CLAUDE.md "Knowledge corpus": create on first substantive finding, never scaffold empty
    "docs/RUNNERS.md": "planned corpus file", "docs/SECTORS.md": "planned corpus file",
    "docs/NEWSFLOW.md": "planned corpus file", "docs/NEW_CHAINS.md": "planned corpus file",
    "docs/UPCOMING.md": "planned corpus file", "RUNNERS.md": "planned corpus file (BACKLOG E6)",
    "SECTORS.md": "planned corpus file (BACKLOG E6)", "NEWSFLOW.md": "planned corpus file (BACKLOG E6)",
    "NEW_CHAINS.md": "planned corpus file (BACKLOG E6)", "UPCOMING.md": "planned corpus file (BACKLOG E6)",
    # docs/CONSOLIDATION_PLAN.md phase 0 items not yet done
    "docs/reviews/2026-08-22_teardown.md": "consolidation phase 0, not yet copied",
    # outside the repo by design (the retired desktop task)
    "SKILL.md": "lives in Documents/Claude/Scheduled/crypto-collect-hourly, outside the repo",
    # a plan-table row that shipped under another name (chainfields.round_trip)
    "jupiter.py": "docs/LIQUIDITY.md plan row; shipped as chainfields.round_trip()",
}
# Fixture file names inside a test's own synthetic cases, not repo references.
FIXTURE_FILES = {"test_evidenceguard.py"}

PAT = re.compile(r"(?<![\w/.-])((?:docs|data|site|scripts|supabase|\.github)/[\w./-]+\."
                 r"(?:md|py|mjs|json|jsonl|yml|sql|html)|[A-Z][A-Z0-9_]+\.md|[a-z_][a-z0-9_]*\.py)(?![\w])")


def tracked():
    out = subprocess.run(["git", "ls-files"], cwd=HERE, capture_output=True, text=True).stdout
    return [f for f in out.splitlines()
            if f.endswith((".md", ".py", ".mjs", ".yml")) and not f.startswith("data/")]


def resolves(ref, naming_file):
    for c in (ref, os.path.join(os.path.dirname(naming_file), ref), os.path.join("docs", ref)):
        if os.path.exists(os.path.join(HERE, c)):
            return True
    return False


broken, used_planned = {}, set()
files = tracked()
for f in files:
    if os.path.basename(f) in FIXTURE_FILES or os.path.basename(f) == "test_references.py":
        continue
    try:
        txt = open(os.path.join(HERE, f), encoding="utf-8").read()
    except (OSError, UnicodeDecodeError):
        continue
    for ref in PAT.findall(txt):
        if any(x in ref for x in ("YYYY", "*", "<", "{")):
            continue
        if resolves(ref, f):
            continue
        if ref in PLANNED:
            used_planned.add(ref)
            continue
        broken.setdefault(ref, set()).add(f)

check(f"every file named in {len(files)} tracked sources exists (or is PLANNED, with a reason)",
      not broken, "; ".join(f"{r} <- {sorted(v)[:2]}" for r, v in sorted(broken.items())[:12]))
stale = sorted(r for r in PLANNED if resolves(r, "CLAUDE.md"))
check("⛔ no PLANNED entry has started to exist - remove it from the list when it does",
      not stale, ", ".join(stale))

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
