"""`status = "gone"` must stop pretending to know why, and the row must SAY so.

⛔ ASSERTED ON OUTPUT, NOT EXECUTION (standing rule 16). Reading `journal.py` and
seeing a `status_reason` assignment is exactly what "computed but never persisted"
looks like from the inside - this repo has lost five fields to that gap, so this
suite calls `record_outcome()` in the sandbox and reads the row back off disk.
"""
import ast
import io
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import testsandbox
testsandbox.activate()

for _k in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "CRYPTO_JOURNAL_SECRET"):
    os.environ.pop(_k, None)

import journal  # noqa: E402

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print("  %s  %s%s" % ("PASS" if cond else "FAIL", name,
                          ("   <- %s" % detail) if detail and not cond else ""))


print("=" * 70)
print("1. a `gone` row carries WHAT WAS OBSERVED, read back off disk")
print("=" * 70)

TOK = "GoneLabelReasonMint11111111111111111111111111"
PAIR = "GoneLabelReasonPair11111111111111111111111111"

# liq=None is the only path that produces `gone`: two indexer lookups returned
# nothing. Nothing about the pool was measured.
journal.record_outcome(PAIR, time.time() - 3700, 1, price=None, liq=None,
                       vol24=None, base_price=1.0, base_liq=50_000.0,
                       symbol="GONEY", token=TOK)

rows = [o for o in journal.outcomes() if o.get("pair") == PAIR]
check("the sandbox wrote exactly one outcome row", len(rows) == 1, str(len(rows)))
row = rows[0] if rows else {}
check("its status is still `gone` (the word is NOT renamed here)",
      row.get("status") == "gone", str(row.get("status")))
check("⛔ `status_reason` IS PERSISTED, not merely computed",
      bool(row.get("status_reason")), repr(row.get("status_reason"))[:90])
reason = row.get("status_reason") or ""
check("⛔ it says the INDEXER LOOKUP failed, not that the pool closed",
      "indexer lookups" in reason and "not evidence" in reason.lower(), reason[:90])
check("⭐ it points at the sidecar that actually measures the state",
      "data/pools/state.jsonl" in reason, reason[:90])
check("⛔ it carries the measured counter-evidence (a round trip still works)",
      "round-trip" in reason or "round trip" in reason, reason[:90])

print()
print("=" * 70)
print("2. a row that is NOT `gone` must not carry a reason it did not measure")
print("=" * 70)

TOK2 = "GoneLabelAliveMint2222222222222222222222222222"
PAIR2 = "GoneLabelAlivePair2222222222222222222222222222"
journal.record_outcome(PAIR2, time.time() - 3700, 1, price=2.0, liq=60_000.0,
                       vol24=9_000.0, base_price=1.0, base_liq=50_000.0,
                       symbol="ALIVEY", token=TOK2)
rows2 = [o for o in journal.outcomes() if o.get("pair") == PAIR2]
row2 = rows2[0] if rows2 else {}
check("an `alive` row exists", row2.get("status") == "alive",
      str(row2.get("status")))
check("⛔ and its `status_reason` is None, never a leftover string",
      row2.get("status_reason") is None, repr(row2.get("status_reason")))

print()
print("=" * 70)
print("3. the source names the measurement, so the next reader cannot miss it")
print("=" * 70)

JSRC = io.open(os.path.join(HERE, "journal.py"), encoding="utf-8").read()
check("⛔ the `gone` branch cites the on-chain re-measurement",
      "PRECOMMIT_pool_state.md" in JSRC
      and "POOL_DERIVATION_2026-09-23.md" in JSRC)
check("⛔ and it states pool_closed was 0 of 120",
      "pool_closed   0" in JSRC or "pool_closed 0" in JSRC)
check("⛔ it says renaming the field needs its own pre-commit, not a patch",
      "needs its own pre-commit" in JSRC)

tree = ast.parse(JSRC)
fn = [n for n in ast.walk(tree)
      if isinstance(n, ast.FunctionDef) and n.name == "record_outcome"][0]
assigns = [n for n in ast.walk(fn)
           if isinstance(n, ast.Assign)
           and any(getattr(t, "id", None) == "status_reason" for t in n.targets)]
check("⭐ status_reason is assigned in record_outcome, initialised before the "
      "branch so it cannot leak between calls", len(assigns) >= 2,
      "found %d assignments" % len(assigns))

print()
failed = [x for x in R if not x[1]]
print("%d/%d passed" % (len(R) - len(failed), len(R)))
for n, _ in failed:
    print("  FAILED:", n)
sys.exit(1 if failed else 0)
