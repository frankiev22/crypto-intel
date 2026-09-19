"""docs/BACKLOG.md must stay verifiable. Run: python test_backlog.py

⛔ WHY. The file's own rule 2 is "nothing leaves NOT STARTED without verification
evidence", and the evidence is a SHA. Ten minutes after writing two of them I
rebased onto origin to push, git rewrote both commits, and the backlog was left
citing SHAs that exist in nobody's repository - including, shortly, mine. A
citation that does not resolve is not weaker evidence, it is no evidence, and it
fails silently: the row still reads SHIPPED.

So: every SHA in that file must be an ANCESTOR OF HEAD. Not merely an object
that exists - a dangling pre-rebase commit satisfies `cat-file` and is garbage
two weeks later.

⚠️ This checks that the citation resolves. It cannot check that the commit does
what the row says it does. That is what the evidence column is for, and no test
can replace reading it.
"""
import io
import os
import re
import subprocess
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
PATH = os.path.join(HERE, "docs", "BACKLOG.md")


def git(*args):
    return subprocess.run(["git"] + list(args), cwd=HERE, capture_output=True,
                          text=True, encoding="utf-8", errors="replace")


print("=" * 70)
print("1. the file exists and is the first stop after CLAUDE.md")
print("=" * 70)
check("docs/BACKLOG.md exists", os.path.exists(PATH))
if not os.path.exists(PATH):
    sys.exit(1)
text = io.open(PATH, encoding="utf-8").read()
claude = io.open(os.path.join(HERE, "CLAUDE.md"), encoding="utf-8").read()
check("CLAUDE.md points at it", "BACKLOG.md" in claude)
check("it states the append-only rule", "APPEND-ONLY" in text)
check("and the no-evidence-no-status rule",
      "without verification evidence" in text)

print()
print("=" * 70)
print("2. ⛔ every cited SHA is REACHABLE FROM HEAD, not just an object")
print("=" * 70)

shallow = os.path.exists(os.path.join(HERE, ".git", "shallow"))
# ⚠️ NOT "anything hex". Two tokens in this file look like commits and are not:
# `35356362447` is a GitHub run id cited as evidence in its own right. But
# filtering on "contains a hex letter" ALSO dropped `4949874`, a real 7-digit
# commit - the test would then have skipped a real citation and still printed
# PASS. Silently checking less than you claim is the failure this whole suite
# is about, so nothing is filtered blind: git is asked about every candidate,
# and whatever is not a commit is REPORTED rather than quietly dropped.
cands = sorted(set(re.findall(r"`([0-9a-f]{7,40})`", text)))
known, orphan, notcommit = [], [], []
for c in cands:
    kind = git("cat-file", "-t", c).stdout.strip()
    if kind == "commit":
        known.append(c)
        if git("merge-base", "--is-ancestor", c, "HEAD").returncode != 0:
            orphan.append(f"{c} (dangling - rebased or amended away)")
    elif re.search(r"[a-f]", c):
        # Hex letters and git has never heard of it: a commit that was rewritten
        # and then garbage-collected, or a typo. Either way the row cites
        # nothing.
        orphan.append(f"{c} (unknown to this repository)")
    else:
        notcommit.append(c)

check(f"the file cites {len(known)} commit(s)", len(known) > 0, str(len(known)))
if notcommit:
    print(f"  ..    not commits, not checked as such: {', '.join(notcommit)}")
if shallow:
    print("  SKIP  shallow clone - history is not present to check against")
else:
    check("⛔ none was orphaned by a rebase or amend", not orphan,
          "; ".join(orphan) if orphan else f"all {len(known)} reachable from HEAD")

print()
print("=" * 70)
print("3. ⛔ no status outside the four, and no weasel word")
print("=" * 70)

# [a-z]? because C4a exists: \d+ alone skipped it, so one row was never checked.
rows = [l for l in text.splitlines()
        if l.startswith("| ") and re.match(r"\|\s*[A-E]\d+[a-z]?\s*\|", l)]
check(f"the table parses into {len(rows)} commitment rows", len(rows) >= 30,
      str(len(rows)))

# ⛔ "No 'designed,' no 'specced,' no 'ready.' Those are NOT STARTED." - Frank.
# Checked in the STATUS cell only: the evidence column legitimately says things
# like "designed but not built", which is the honest phrasing, not the weasel.
WEASEL = ("designed", "specced", "spec'd", "ready", "written up", "complete-ish",
          "mostly done", "basically done", "nearly")
ALLOWED = ("SHIPPED", "IN PROGRESS", "BLOCKED", "NOT STARTED", "DROPPED")
bad_status, weasel_rows = [], []
for l in rows:
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if len(cells) < 4:
        continue
    num, status = cells[0], cells[2]
    if not any(a in status for a in ALLOWED):
        bad_status.append(f"{num}: {status[:40]}")
    low = status.lower()
    for w in WEASEL:
        if w in low:
            weasel_rows.append(f"{num}: {w}")
check("⛔ every status is one of the four (or DROPPED)", not bad_status,
      "; ".join(bad_status) if bad_status else f"{len(rows)} rows")
check("⛔ and none says designed / specced / ready", not weasel_rows,
      "; ".join(weasel_rows) if weasel_rows else "clean")

def status_of(cell):
    """The FIRST status word in the cell: "IN PROGRESS - SHIPPED-row audit" is
    in progress, "SHIPPED - the measurement; D1 stays IN PROGRESS" is shipped."""
    hits = [(cell.find(a), a) for a in ALLOWED if a in cell]
    return min(hits)[1] if hits else None


counted = {a: 0 for a in ALLOWED}
for l in rows:
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if len(cells) >= 4 and status_of(cells[2]):
        counted[status_of(cells[2])] += 1
board = {}
if "## Scoreboard" in text:
    for a, n in re.findall(r"^\|\s*\S+\s+(SHIPPED|IN PROGRESS|BLOCKED|NOT STARTED|DROPPED)\s*\|\s*\*\*(\d+)\*\*",
                           text.split("## Scoreboard", 1)[1], re.M):
        board[a] = int(n)
check("⛔ the scoreboard equals the rows, counted (it said 18 SHIPPED against 48 once, "
      "and went stale again when B5 moved)", board == counted,
      f"board {board} vs rows {counted}")

print()
print("=" * 70)
print("4. ⭐ SHIPPED means observed, not written")
print("=" * 70)

thin = []
for l in rows:
    cells = [c.strip() for c in l.strip().strip("|").split("|")]
    if len(cells) < 4 or "SHIPPED" not in cells[2]:
        continue
    num, evidence = cells[0], cells[3]
    # A SHA in the status column with an empty evidence cell is the exact
    # failure rule 2 names: "A SHA alone is not evidence".
    # Rule 2: "A SHA alone is not evidence." So the bar is that the cell says
    # something beyond the citation - not an arbitrary length, which flagged a
    # one-line knowledge-doc row that was perfectly honest.
    stripped = re.sub(r"`[0-9a-f]{7,40}`|[\s,.;·]", "", evidence)
    if not stripped:
        thin.append(f"{num}: {evidence[:30]!r}")
check("⛔ no SHIPPED row rests on a bare SHA", not thin,
      "; ".join(thin) if thin else "every SHIPPED row carries an observation")

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
