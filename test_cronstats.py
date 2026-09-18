"""The C4a verdict cannot be fudged. Run: python test_cronstats.py

⛔ The bar in `cronstats.py` was pre-committed in docs/BACKLOG.md before any
post-change run had fired. These checks exist because a pre-commitment is only
worth anything if the thing that applies it is fixed too - a boundary that
quietly moves, or a median reported off n=3, is the same failure as moving the
bar by hand.

⚠️ The one that matters most is the REFUSAL. This project has twice reported a
rate off a handful of observations and retracted it, and the 24% truncation
claim came from a single pass. Under n=30 the tool must print its n and decline.
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import cronstats as C

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


print("=" * 70)
print("1. the pre-committed constants are what BACKLOG C4a says")
print("=" * 70)

check("SUCCESS bar is 1.5h", C.SUCCESS_H == 1.5, str(C.SUCCESS_H))
check("PARTIAL ceiling is 2.5h", C.PARTIAL_H == 2.5, str(C.PARTIAL_H))
check("⛔ the floor is n=30", C.MIN_N == 30, str(C.MIN_N))
check("the baseline is recorded as measured", C.BASELINE_MEDIAN_H == 3.24
      and C.BASELINE_N == 99)
doc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "docs", "BACKLOG.md"), encoding="utf-8").read()
check("⭐ and the SAME numbers are in docs/BACKLOG.md C4a",
      "1.5h" in doc and "2.5h" in doc and "3.24h" in doc,
      "the file and the code cannot drift apart silently")

print()
print("=" * 70)
print("2. ⛔ it REFUSES a verdict below n=30")
print("=" * 70)

for n in (0, 1, 5, 29):
    lab, m, got = C.verdict([0.5] * n)          # every gap a clean pass
    check(f"n={n} gaps -> UNDER-POWERED even when every gap passes",
          lab == "UNDER-POWERED", f"{lab} {m}")
lab, m, got = C.verdict([0.5] * 30)
check("⭐ n=30 is the first sample that gets a verdict", lab == "SUCCESS",
      f"{lab} median {m}")

print()
print("=" * 70)
print("3. the boundaries land where the commitment put them")
print("=" * 70)

cases = [([1.5] * 31, "SUCCESS", "exactly 1.5h is a PASS, not a near miss"),
         ([1.51] * 31, "PARTIAL", "a hair over 1.5h is PARTIAL"),
         ([2.5] * 31, "PARTIAL", "exactly 2.5h is still PARTIAL"),
         ([2.51] * 31, "FAILURE", "a hair over 2.5h is FAILURE"),
         ([3.24] * 31, "FAILURE", "⛔ the BASELINE itself scores FAILURE")]
for gs, want, why in cases:
    lab, m, n = C.verdict(gs)
    check(f"{why}", lab == want, f"{m}h -> {lab}, wanted {want}")

# ⚠️ The verdict is on the MEDIAN, so a handful of fast gaps must not carry it.
mixed = [0.2] * 15 + [6.0] * 16
lab, m, n = C.verdict(mixed)
check("⚠️ 15 fast gaps cannot rescue 16 slow ones - it is a median, not a best",
      lab == "FAILURE", f"median {m}h -> {lab}")

print()
print("=" * 70)
print("4. gaps and the before/after split")
print("=" * 70)

H = 3600.0
check("gaps are the differences between consecutive starts",
      C.gaps_h([0, 1 * H, 3 * H]) == [1.0, 2.0], str(C.gaps_h([0, 1 * H, 3 * H])))
check("⚠️ and they are sorted first - gh returns newest first",
      C.gaps_h([3 * H, 0, 1 * H]) == [1.0, 2.0])
check("one run has no gap, and that is not zero",
      C.gaps_h([5 * H]) == [], str(C.gaps_h([5 * H])))
check("⛔ an unparseable timestamp is dropped, never treated as epoch 0",
      C._ts("not a date") is None and C._ts(None) is None)

change = C._ts(C.CHANGE_TS)
check("the change timestamp parses", change is not None)
runs = [{"event": "schedule", "createdAt": "2026-09-18T12:00:00Z"},
        {"event": "schedule", "createdAt": "2026-09-18T13:00:00Z"},
        {"event": "schedule", "createdAt": "2026-09-18T14:00:00Z"},
        {"event": "schedule", "createdAt": "2026-09-18T15:00:00Z"},
        {"event": "workflow_dispatch", "createdAt": "2026-09-18T14:30:00Z"}]
out = C.report(runs=[r for r in runs if r["event"] == "schedule"])
check("⛔ two post-change runs is ONE gap, and no verdict",
      out["label"] == "UNDER-POWERED" and out["n"] == 1, str(out))
check("and the pre-change runs are measured separately",
      out["before_n"] == 1 and abs(out["before_median_h"] - 1.0) < 1e-9,
      str(out))

print()
print("=" * 70)
print("4b. ⚠️ it reports OUR OWN interference, scoped to the window")
print("=" * 70)

# ⛔ collect.yml uses a concurrency group, so a manual dispatch still running
# when cron fires can cost that scheduled slot. Every hand-run during the
# measurement window is a thumb on the scale, against the cron. The tool has to
# say so - and the count has to be scoped, because the first version of it
# printed "6 scheduled run(s) cancelled" from 09-08 to 09-10 beside a sentence
# about today. A caveat that is itself unscoped is worse than no caveat.
import contextlib as _ctx
import io as _io2

OLD = "2026-09-01T00:00:00Z"                       # well before CHANGE_TS
NEW = "2026-09-18T15:00:00Z"                       # well after


def _say(runs):
    b = _io2.StringIO()
    with _ctx.redirect_stdout(b):
        C.report(runs=runs)
    return b.getvalue()

out = _say([{"event": "schedule", "createdAt": OLD, "conclusion": "cancelled"},
            {"event": "schedule", "createdAt": NEW, "conclusion": "success"}])
# ⚠️ With nothing inside the window the tool takes the clean branch, so the
# assertion is on that, not on a "0 cancelled" string it never prints.
check("⛔ a cancellation from BEFORE the change is not contamination",
      "CONTAMINATION" not in out and "the window is clean" in out,
      [l.strip() for l in out.splitlines() if "CONTAMINATION" in l
       or "clean" in l] or "none")

out = _say([{"event": "schedule", "createdAt": NEW, "conclusion": "cancelled"}])
check("⚠️ one from inside the window IS reported",
      "1 scheduled run(s) cancelled" in out,
      [l.strip() for l in out.splitlines() if "CONTAMINATION" in l] or "none")

out = _say([{"event": "workflow_dispatch", "createdAt": NEW, "conclusion": "success"},
            {"event": "schedule", "createdAt": NEW, "conclusion": "success"}])
check("⚠️ a manual dispatch inside the window is counted",
      "1 manual dispatch" in out,
      [l.strip() for l in out.splitlines() if "CONTAMINATION" in l] or "none")

out = _say([{"event": "schedule", "createdAt": NEW, "conclusion": "success"}])
check("⭐ and a clean window says so instead of staying silent",
      "the window is clean" in out)

print()
print("=" * 70)
print("5. ⚠️ it says what it cannot say")
print("=" * 70)

src = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                        "cronstats.py"), encoding="utf-8").read()
# ⛔ CHECK THE OUTPUT, NOT THE SOURCE. The first version of this grepped
# cronstats.py for the sentence and failed because the string is split across
# two lines - a false alarm about a caveat that was printed correctly all along.
# Verifying the source instead of the output is the mistake this whole suite is
# named after.
import io as _io
import contextlib
_buf = _io.StringIO()
with contextlib.redirect_stdout(_buf):
    C.report(runs=[{"event": "schedule", "createdAt": "2026-09-18T15:00:00Z"}])
_printed = _buf.getvalue()
check("⚠️ the REPORT says starting a run is not collecting anything",
      "not whether they collected anything" in " ".join(_printed.split()),
      _printed.strip().splitlines()[-1][:70])
check("...and points the reader at the tool that answers it",
      "liveness.py" in _printed)
check("⛔ and forbids re-tuning the minutes and re-measuring",
      "re-tune the minutes" in src)
check("⭐ and points at C5 on failure, not at another cron line",
      "C5" in src and "always-on" in src)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
