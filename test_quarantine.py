"""A quarantine at one horizon must bind every later horizon.

KPOP / pair E9HaVWoQ, 2026-09-07: quarantined at 1h and again at 6h because
dexscreener reported $1,315,074 of liquidity against geckoterminal's $41,842 -
a 31x disagreement about whether a pool existed. Eighteen hours later the same
pair at 24h came back trustworthy carrying the same 6.66x multiple, because the
fallback budget was spent so the check never ran. Only the unrelated
`sell_side` check kept a fabricated 6.66x win off the record.

Run: python test_quarantine.py    (offline, sandboxed, writes to a temp dir)
"""
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import tempfile

import pricecheck

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


d = tempfile.mkdtemp()
pricecheck.QUARANTINE = os.path.join(d, "quarantine.json")
pricecheck.QUARANTINE_LOG = os.path.join(d, "quarantine.jsonl")
pricecheck._Q_CACHE.update(mtime=None, data={})

KPOP = "E9HaVWoQipCDQoWmF1gsJzijDnC7yoYpdcdH9R1haoS1"
DIVERGENT = {"token": KPOP, "price": 0.001328, "trustworthy": False,
             "confidence": pricecheck.Q_LIQ_DIVERGENT,
             "detail": "dexscreener liquidity $1,315,074 vs geckoterminal "
                       "$41,842; the sources do not agree that there is a pool"}
CLEAN = {"token": KPOP, "price": 0.001328, "trustworthy": True,
         "confidence": pricecheck.SINGLE, "detail": "only dexscreener resolved it"}

print("=" * 70)
print("1. the KPOP sequence, replayed")
print("=" * 70)
pricecheck._validate_fresh = lambda t, c="solana": dict(DIVERGENT)
v1 = pricecheck.validate(KPOP, horizon_h=1)
check("1h: quarantined", v1["trustworthy"] is False, str(v1["confidence"]))
v6 = pricecheck.validate(KPOP, horizon_h=6)
check("6h: still quarantined", v6["trustworthy"] is False)

# 18 hours later the corroborating source is unavailable, so the fresh verdict
# is a single-source pass - exactly what happened on the record.
pricecheck._validate_fresh = lambda t, c="solana": dict(CLEAN)
fresh = pricecheck._validate_fresh(KPOP)
check("without stickiness the fresh verdict WOULD admit it",
      fresh["trustworthy"] is True)
v24 = pricecheck.validate(KPOP, horizon_h=24)
check("24h: sticky quarantine holds", v24["trustworthy"] is False,
      f"trustworthy={v24['trustworthy']}")
check("24h: keeps the ORIGINAL reason", v24["confidence"] == pricecheck.Q_LIQ_DIVERGENT,
      str(v24["confidence"]))
check("24h: is labelled as sticky", v24.get("sticky_quarantine") is True)
check("24h: names the horizon it was first rejected at",
      "1h horizon" in v24["detail"], v24["detail"][:70])

print()
print("=" * 70)
print("2. it is keyed on contract address, and does not leak")
print("=" * 70)
OTHER = "So11111111111111111111111111111111111111112"
vo = pricecheck.validate(OTHER, horizon_h=24)
check("a different contract is unaffected", vo["trustworthy"] is True)
check("the quarantined one is still held",
      pricecheck.validate(KPOP, horizon_h=24)["trustworthy"] is False)
check("quarantined() reports it", bool(pricecheck.quarantined(KPOP)))
check("quarantined() is None for the other", pricecheck.quarantined(OTHER) is None)
check("hits accumulate rather than overwrite",
      pricecheck.quarantined(KPOP)["hits"] >= 2,
      str(pricecheck.quarantined(KPOP)["hits"]))

print()
print("=" * 70)
print("3. an unreadable store does not un-quarantine anything")
print("=" * 70)
with open(pricecheck.QUARANTINE, "w", encoding="utf-8") as f:
    f.write("{truncated mid-write")
v = pricecheck.validate(KPOP, horizon_h=24)
check("corrupt store keeps the cached quarantine", v["trustworthy"] is False)
check("and does not silently empty the store", bool(pricecheck._Q_CACHE["data"]))

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
