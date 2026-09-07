"""Regression tests for check.py. Run: python test_check.py

THE RULE THESE ENFORCE: **absence of evidence must never render as evidence of
absence.** Every test here is a case where the tool could plausibly print
something reassuring while knowing nothing, and Frank is about to point this at
coins he is buying with his own money.

The first test is the bug that shipped: a drained pool with $0 exitable depth
returned "NOT FLAGGED", exit code 0. That reads as clean. It cost nothing only
because it was caught in testing rather than by a position.

Offline by construction - sources are monkeypatched, so this makes no network
calls, costs no rate budget, and can run in CI.
"""
import sys

import check


def _pair(depth_quote=5000.0, price_usd=0.001, price_native=0.00001,
          liq_usd=10000.0, fdv=10000.0, buys=20, sells=5, addr="PAIR1"):
    """A Dexscreener-shaped pair. exit_depth_usd = quote * (priceUsd/priceNative)."""
    return {"chainId": "solana", "pairAddress": addr,
            "baseToken": {"symbol": "TEST"},
            "priceUsd": str(price_usd), "priceNative": str(price_native),
            "liquidity": {"usd": liq_usd,
                          "quote": depth_quote / (price_usd / price_native)},
            "fdv": fdv, "marketCap": fdv,
            "txns": {"h1": {"buys": buys, "sells": sells}}}


RESULTS = []


def case(name, pairs, expect_verdict, must_contain=None, forbid=None):
    check.S.dexscreener_token = lambda c: pairs
    check.onchain = None                    # no RPC in tests
    r = check.analyse("So11111111111111111111111111111111111111112")
    txt = check.render(r)
    ok = r["verdict"] == expect_verdict
    why = "" if ok else f"verdict={r['verdict']} expected={expect_verdict}"
    if ok and must_contain:
        for m in must_contain:
            if m.lower() not in txt.lower():
                ok, why = False, f"missing {m!r} in output"
                break
    if ok and forbid:
        for m in forbid:
            if m.lower() in txt.lower():
                ok, why = False, f"output contained forbidden {m!r}"
                break
    RESULTS.append((name, ok, why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"   <- {why}" if why else ""))
    return r


print("=" * 72)
print("THE SHIPPED BUG: zero exitable depth must never read as safe")
print("=" * 72)

# A pool whose quote side is empty. This is the exact shape that returned
# "NOT FLAGGED" / exit 0 before the fix.
case("drained pool ($0 quote side) refuses, never 'not flagged'",
     [_pair(depth_quote=0.0, liq_usd=0.0)],
     "REFUSED",
     must_contain=["refused", "not a clean result"],
     forbid=["not flagged"])

case("dust pool ($40 quote side, under the $100 floor) refuses",
     [_pair(depth_quote=40.0, liq_usd=80.0)],
     "REFUSED",
     forbid=["not flagged"])

case("pool just over the floor ($150) is assessed, not refused",
     [_pair(depth_quote=150.0, liq_usd=300.0)],
     "not flagged")

print()
print("=" * 72)
print("THE CLASS: a missing input must never render as a pass")
print("=" * 72)

# fdv absent -> D1 cannot compute liq/fdv. Must say INCONCLUSIVE, not stay quiet.
p = _pair(); p["fdv"] = None; p["marketCap"] = None
case("D1 with no fdv says INCONCLUSIVE out loud",
     [p], "not flagged",
     must_contain=["inconclusive", "not a pass"])

# txns absent -> neither detector has inputs.
p = _pair(); p["txns"] = {}
case("no txn data says INCONCLUSIVE out loud",
     [p], "not flagged",
     must_contain=["inconclusive"])

# Unreadable reserves everywhere -> refuse.
p = _pair(); p["liquidity"] = {}; p["priceNative"] = None
case("no readable reserves refuses",
     [p], "REFUSED",
     forbid=["not flagged"])

case("empty pair list refuses",
     [], "REFUSED", forbid=["not flagged"])

print()
print("=" * 72)
print("DETECTION still works, and says how much it is worth")
print("=" * 72)

# The template shape: supply IS the pool, nobody has ever sold.
case("one-sided pool with no sells is FLAGGED",
     [_pair(depth_quote=3000.0, liq_usd=400000.0, fdv=400000.0,
            buys=64, sells=0)],
     "FLAGGED",
     must_contain=["d1 silence", "one-sided"])

# Every rendering must carry the honesty block - a flag is worth its interval.
r = case("output always states recall is 50% and there is no entry rule",
         [_pair()], "not flagged",
         must_contain=["recall 50.0", "no validated entry rule",
                       "not flagged means"])

print()
print("=" * 72)
print("PAIR SELECTION: the deepest pool, and say so")
print("=" * 72)

case("picks the DEEPEST pool and warns that others exist",
     [_pair(depth_quote=500.0, addr="SHALLOW"),
      _pair(depth_quote=9000.0, addr="DEEP")],
     "not flagged",
     must_contain=["priced pools exist", "deepest"])

check.S.dexscreener_token = lambda c: [_pair(depth_quote=500.0, addr="SHALLOW"),
                                       _pair(depth_quote=9000.0, addr="DEEP")]
r = check.analyse("So11111111111111111111111111111111111111112")
ok = r["pair"] == "DEEP"
RESULTS.append(("the pair reported is the deepest one", ok,
                "" if ok else f"picked {r['pair']}"))
print(f"  {'PASS' if ok else 'FAIL'}  the pair reported is the deepest one")

print()
print("=" * 72)
print("REFUSALS on bad input")
print("=" * 72)

check.S.dexscreener_token = lambda c: [_pair()]
r = check.analyse("PEPE")
ok = r["verdict"] == "REFUSED" and "ticker" in check.render(r).lower()
RESULTS.append(("a ticker is refused, not resolved", ok, ""))
print(f"  {'PASS' if ok else 'FAIL'}  a ticker is refused, not resolved")


def _boom(c):
    raise OSError("network down")


check.S.dexscreener_token = _boom
r = check.analyse("So11111111111111111111111111111111111111112")
ok = r["verdict"] == "REFUSED" and "not flagged" not in check.render(r).lower()
RESULTS.append(("an unreachable source refuses, never 'not flagged'", ok, ""))
print(f"  {'PASS' if ok else 'FAIL'}  an unreachable source refuses, never 'not flagged'")

print()
failed = [r for r in RESULTS if not r[1]]
print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
if failed:
    for n, _, w in failed:
        print(f"  FAILED: {n}  {w}")
sys.exit(1 if failed else 0)
