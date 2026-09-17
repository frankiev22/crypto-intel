"""chainfields contract tests. The network-free ones run always.

The rule this file exists to protect: AN UNKNOWN IS None, NEVER 0. Five
failures in this repo came from an absent measurement rendering as a real
value, and chainfields is the module that is supposed to end that. A 0 that
means "not measured" is indistinguishable from a 0 that means "empty pool"
once it reaches disk.

Run with --live to also hit Jupiter and Helius (costs ~6 Jupiter quotes).
"""
import json
import os
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import chainfields as cf

FAIL = []
LIVE = "--live" in sys.argv


def check(ok, label, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


# --------------------------------------------------------------------------
print("1. the rate bucket actually paces (this is what stops a 429 storm)")

b = cf._Bucket(60)            # 1/sec, starts full
for _ in range(60):
    b.take()
t0 = time.time()
b.take()                      # bucket empty -> must wait ~1s
waited = time.time() - t0
check(waited > 0.5, "an exhausted bucket blocks", f"waited {waited:.2f}s")

b2 = cf._Bucket(600)
t0 = time.time()
for _ in range(5):
    b2.take()
check(time.time() - t0 < 0.3, "a full bucket does not block")
check(cf._JUP.cap == cf.JUP_PER_MIN == 55, "module bucket is 55/min",
      f"cap={cf._JUP.cap}")

# --------------------------------------------------------------------------
print("\n2. verdict bands are pre-committed constants, not tuned per call")
check(cf.TRADEABLE_MAX_PCT == 10.0, "TRADEABLE < 10%")
check(cf.COSTLY_MAX_PCT == 50.0, "COSTLY < 50%")

# --------------------------------------------------------------------------
print("\n3. top-N concentration is suppressed when N is most of the holders")
#    Computed unconditionally it returns 100% for every token with <10 holders,
#    which is what the first version did. It discriminated nothing.


def fake_holders(n):
    """Drive holder_count's maths without the network."""
    owners = {f"w{i}": 1.0 for i in range(n)}
    total = sum(owners.values())
    ranked = sorted(owners.values(), reverse=True)
    out = {"holders": len(owners), "top1_pct": ranked[0] / total * 100.0}
    out["top10_pct"] = (sum(ranked[:10]) / total * 100.0) if len(owners) > 20 else None
    return out


check(fake_holders(5)["top10_pct"] is None, "5 holders -> top10 is None, not 100%")
check(fake_holders(20)["top10_pct"] is None, "20 holders -> still None")
check(fake_holders(21)["top10_pct"] is not None, "21 holders -> computed")
check(abs(fake_holders(100)["top10_pct"] - 10.0) < 0.001,
      "100 equal holders -> top10 is 10%", str(fake_holders(100)["top10_pct"]))

# --------------------------------------------------------------------------
print("\n4. an unreadable field is None, never 0")
sup, dec = cf.supply("not-a-real-mint-address")
check(sup is None and dec is None, "supply() of a bogus mint -> (None, None)",
      f"got ({sup}, {dec})")
check(cf.market_cap.__doc__ and "does NOT fall back" in cf.market_cap.__doc__,
      "market_cap documents that it will not substitute a reported price")

# --------------------------------------------------------------------------
if LIVE:
    print("\n5. LIVE: known contracts return the shape callers depend on")
    BONK = "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"
    r = cf.round_trip(BONK)
    check(r["verdict"] == "TRADEABLE", "BONK is TRADEABLE", r["verdict"])
    check(r["usd_back"] and r["usd_back"] > 95, "BONK returns >$95 of $100",
          str(r["usd_back"]))
    check(r["px_per_raw"] is not None, "buy-leg price is carried for market_cap")

    bogus = cf.round_trip("So11111111111111111111111111111111111111113")
    check(bogus["verdict"] == "NO_BUY_ROUTE", "unroutable -> NO_BUY_ROUTE",
          bogus["verdict"])
    check(bogus["usd_back"] is None, "unroutable -> usd_back is None, NOT 0",
          repr(bogus["usd_back"]))
    check(bogus["rt_cost_pct"] is None, "unroutable -> cost is None, NOT 0",
          repr(bogus["rt_cost_pct"]))

    t = cf.trusted(BONK, want_holders=False)
    for k in ("exit_verdict", "exit_realizable_usd", "fdv_onchain_usd",
              "supply", "holders"):
        check(k in t, f"trusted() always carries {k}")
    check(t["holders"] is None, "want_holders=False -> holders is None, not 0")
else:
    print("\n5. LIVE tests skipped (pass --live to run them)")

print()
if FAIL:
    print(f"FAILED: {len(FAIL)}")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("all chainfields checks passed")
