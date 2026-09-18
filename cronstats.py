"""Did widening the cron to 4x/hour actually help? Run: python cronstats.py

⛔ THE BAR WAS PRE-COMMITTED BEFORE THE DATA EXISTED (docs/BACKLOG.md C4a), and
this file is written before the data exists too, so neither can be moved to fit
a result:

    baseline        median gap 3.24h over n=99, 2026-09-03 -> 2026-09-18
    SUCCESS         median gap <= 1.5h over >= 30 consecutive scheduled runs
    PARTIAL         1.5h - 2.5h: keep it, note it, do not celebrate it
    FAILURE         > 2.5h: the cron approach is EXHAUSTED. The answer is an
                    always-on box (BACKLOG C5), not more cron lines.

⚠️ AND THE RULE THAT MATTERS MOST: do not re-tune the minutes and re-measure.
Trying ':3,:18,:33,:48' after this one disappoints is how a pre-commitment turns
into a search for a number that agrees with you. One experiment, one verdict.

⛔ NO VERDICT BELOW n=30. Standing rule 7 exists because this project has twice
reported a rate off a handful of observations and had to retract it - and the
24% truncation claim came from ONE pass. An under-powered sample prints its n
and refuses, rather than printing a number nobody should act on.

⚠️ WHAT THIS CAN AND CANNOT SAY. It measures the gap between scheduled runs that
GitHub actually started. It says nothing about whether those runs collected
anything - that is liveness.unattended_rows(), and the two questions are
different. A cron that fires perfectly into a broken collector scores well here.
"""
import json
import os
import subprocess
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# --------------------------------------------------------------------------
# PRE-COMMITTED, docs/BACKLOG.md C4a. Changing these numbers is changing the
# experiment, and the experiment was fixed on 2026-09-18 before any post-change
# run had fired.
# --------------------------------------------------------------------------
BASELINE_MEDIAN_H = 3.24
BASELINE_N = 99
SUCCESS_H = 1.5
PARTIAL_H = 2.5
MIN_N = 30

# When the 4x/hour cron reached the default branch. Runs before this are the
# old schedule and belong to the baseline, not the experiment.
CHANGE_TS = "2026-09-18T13:17:03Z"

REPO = os.environ.get("CRYPTO_REPO", "frankiev22/crypto-intel")
WORKFLOW = "collect.yml"


def _ts(s):
    """ISO-8601 Z -> epoch seconds. Returns None on anything unparseable."""
    import datetime as dt
    try:
        return dt.datetime.strptime(s, "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc).timestamp()
    except (TypeError, ValueError):
        return None


def median(xs):
    if not xs:
        return None
    s = sorted(xs)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


def gaps_h(starts):
    """Hours between consecutive scheduled starts, oldest first."""
    # ⛔ `is not None`, not truthiness. A timestamp of 0 is falsy and would be
    # silently dropped - the same class as rendering unknown as zero, run
    # backwards. Caught by test_cronstats.py using epoch 0 as a fixture.
    s = sorted(t for t in starts if t is not None)
    return [(b - a) / 3600.0 for a, b in zip(s, s[1:])]


def verdict(gs):
    """(label, median_h, n) against the pre-committed bar. n is gaps, not runs.

    ⛔ Refuses below MIN_N rather than reporting a median nobody should act on.
    """
    n = len(gs)
    m = median(gs)
    if n < MIN_N:
        return "UNDER-POWERED", m, n
    if m <= SUCCESS_H:
        return "SUCCESS", m, n
    if m <= PARTIAL_H:
        return "PARTIAL", m, n
    return "FAILURE", m, n


def fetch(limit=200):
    """Every scheduled run of the workflow, newest first. [] if gh is absent."""
    cmd = ["gh", "run", "list", "--workflow", WORKFLOW, "--repo", REPO,
           "--limit", str(limit), "--json",
           "databaseId,event,status,conclusion,createdAt"]
    try:
        out = subprocess.run(cmd, capture_output=True, text=True,
                             encoding="utf-8", errors="replace", timeout=120)
    except Exception as e:
        print(f"⛔ could not run gh: {type(e).__name__}: {e}")
        return []
    if out.returncode != 0:
        print(f"⛔ gh failed: {(out.stderr or '').strip()[:200]}")
        return []
    try:
        return [r for r in json.loads(out.stdout) if r.get("event") == "schedule"]
    except Exception as e:
        print(f"⛔ could not parse gh output: {type(e).__name__}")
        return []


def report(runs=None):
    runs = fetch() if runs is None else runs
    change = _ts(CHANGE_TS)
    # ⛔ Same `is not None` rule as gaps_h(), and parsed ONCE per run rather
    # than three times per run in a comprehension that also hid the bug.
    stamps = [t for t in (_ts(r.get("createdAt")) for r in runs) if t is not None]
    before = [t for t in stamps if t < change]
    after = [t for t in stamps if t >= change]

    print("=" * 72)
    print("C4a - did 4x/hour change the cadence?")
    print("=" * 72)
    print(f"  pre-committed bar   SUCCESS <= {SUCCESS_H}h · "
          f"PARTIAL <= {PARTIAL_H}h · FAILURE > {PARTIAL_H}h")
    print(f"  baseline            median {BASELINE_MEDIAN_H}h over n={BASELINE_N}")
    print(f"  cron widened        {CHANGE_TS}")
    print()
    print(f"  scheduled runs seen {len(runs)}  "
          f"({len(before)} before the change, {len(after)} after)")

    gb, ga = gaps_h(before), gaps_h(after)
    if gb:
        print(f"  before   median {median(gb):.2f}h over n={len(gb)} gaps")
    lab, m, n = verdict(ga)
    if m is None:
        print("  after    no gaps yet - a single run has no gap")
    else:
        le = sum(1 for g in ga if g <= SUCCESS_H)
        print(f"  after    median {m:.2f}h over n={n} gaps, "
              f"{le} of {n} were <= {SUCCESS_H}h")
    print()
    if lab == "UNDER-POWERED":
        need = MIN_N - n
        print(f"  ⛔ NO VERDICT. n={n} gaps, and the bar needs {MIN_N}. "
              f"{need} more scheduled run{'s' if need != 1 else ''} to go.")
        print("     Reporting a median here is how a rate gets quoted and then "
              "retracted. It has happened twice.")
    else:
        mark = {"SUCCESS": "⭐", "PARTIAL": "⚠️", "FAILURE": "⛔"}[lab]
        print(f"  {mark} {lab}: median {m:.2f}h against a {SUCCESS_H}h bar, n={n}")
        if lab == "FAILURE":
            print("     ⛔ The cron approach is exhausted. ⚠️ DO NOT re-tune the "
                  "minutes and re-measure -")
            print("     that turns a pre-commitment into a search. The answer is "
                  "BACKLOG C5, an always-on box.")
    print()
    print("  ⚠️ This measures whether GitHub STARTED runs, not whether they "
          "collected anything.")
    print("     For that: python liveness.py, last line.")
    return {"label": lab, "median_h": m, "n": n,
            "before_median_h": median(gb), "before_n": len(gb)}


if __name__ == "__main__":
    r = report()
    # 0 only on a decided, passing experiment. UNDER-POWERED is not a pass.
    sys.exit(0 if r["label"] == "SUCCESS" else 1)
