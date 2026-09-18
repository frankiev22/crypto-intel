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


# ⭐ The realizable stub is part of the FIXTURE now, because the two
# measurements are independent and a test has to say what each one found.
# A genuinely drained pool is not routable either; a pool where only the
# RESERVE READ failed is. Those are different scenarios and check.py is
# supposed to tell them apart - see the OpenClaw false refusal, 2026-09-18.
RT_OK = {"verdict": "TRADEABLE", "usd_back": 97.0, "rt_cost_pct": 3.0,
         "venues": ["StubAMM"], "token_qty_raw": 1_000_000, "error": None}
RT_DEAD = {"verdict": "NO_SELL_ROUTE", "usd_back": None, "rt_cost_pct": None,
           "venues": None, "token_qty_raw": None, "error": "no route"}


def case(name, pairs, expect_verdict, must_contain=None, forbid=None, rt=None):
    check.S.dexscreener_token = lambda c: pairs
    check.onchain = None                    # no RPC in tests
    # ⛔ OFFLINE BY CONSTRUCTION, and that now has to be enforced rather than
    # assumed: wiring chainfields into analyse() made this suite hit Jupiter
    # without anyone noticing. Stubbed to a realistic TRADEABLE response so the
    # fixtures below test the DETECTORS, not the network.
    check._round_trip = lambda c, usd, _r=(rt or RT_OK): _r
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
case("drained pool ($0 quote side, no route) refuses, never 'not flagged'",
     [_pair(depth_quote=0.0, liq_usd=0.0)],
     "REFUSED", rt=RT_DEAD,
     must_contain=["refused", "not a clean result"],
     forbid=["not flagged"])

case("dust pool ($40 quote side, no route) refuses",
     [_pair(depth_quote=40.0, liq_usd=80.0)],
     "REFUSED", rt=RT_DEAD,
     forbid=["not flagged"])

# ⛔ THE FALSE REFUSAL THIS FIXED, 2026-09-18. check.py refused OpenClaw as
# "dead or drained - $0 on the quote side" while Jupiter round-tripped the same
# token at 0.77% in the same minute. resolve.exit_depth_usd() failed 5 of 6
# reads on 09-17; the refusal ran before anything trusted was consulted.
case("⭐ $0 reserve read but a LIVE ROUTE is assessed, not refused",
     [_pair(depth_quote=0.0, liq_usd=0.0)],
     "not flagged", rt=RT_OK,
     must_contain=["reserve scan disagrees", "trusting the live route"],
     forbid=["dead or drained"])

case("⚠️ and the disagreement is stated, never silently papered over",
     [_pair(depth_quote=0.0, liq_usd=0.0)],
     "not flagged", rt=RT_OK,
     must_contain=["unreliable for this token"])

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

# ---------------------------------------------------------------------------
# ⭐ THE REALIZABLE CHECK (backlog A4). check.py is the FIRST production call
# site to use chainfields; before this, the trusted-field module was imported
# only by paperv3 and its own test.
# ---------------------------------------------------------------------------
def _rt_case(name, rt_stub, expect_verdict, must_contain=None, forbid=None):
    check.S.dexscreener_token = lambda c: [_pair()]
    check.onchain = None
    check._round_trip = lambda c, usd: rt_stub
    r = check.analyse("So11111111111111111111111111111111111111112")
    txt = check.render(r)
    ok = r["verdict"] == expect_verdict
    why = "" if ok else f"verdict={r['verdict']} expected={expect_verdict}"
    for m in (must_contain or []):
        if ok and m.lower() not in txt.lower():
            ok, why = False, f"missing {m!r}"
    for m in (forbid or []):
        if ok and m.lower() in txt.lower():
            ok, why = False, f"forbidden {m!r} present"
    RESULTS.append((name, ok, why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"  <- {why}" if why else ""))


print()
print("realizable liquidity")
_rt_case("⛔ NO_SELL_ROUTE flags as NOT EXITABLE",
         {"verdict": "NO_SELL_ROUTE", "usd_back": None, "rt_cost_pct": None,
          "venues": None, "error": "no route"},
         "FLAGGED", must_contain=["NOT EXITABLE", "NO_SELL_ROUTE"])
_rt_case("⛔ TOTAL_LOSS flags",
         {"verdict": "TOTAL_LOSS", "usd_back": 0.4, "rt_cost_pct": 99.6,
          "venues": ["X"], "error": None},
         "FLAGGED", must_contain=["NOT EXITABLE"])
_rt_case("a TRADEABLE pool is not flagged by this check",
         {"verdict": "TRADEABLE", "usd_back": 97.0, "rt_cost_pct": 3.0,
          "venues": ["Meteora"], "error": None},
         "not flagged", must_contain=["realizable", "TRADEABLE", "Meteora"],
         forbid=["NOT EXITABLE"])
_rt_case("⚠️ COSTLY is reported but does NOT flag on its own",
         {"verdict": "COSTLY", "usd_back": 70.0, "rt_cost_pct": 30.0,
          "venues": ["Y"], "error": None},
         "not flagged", must_contain=["COSTLY"], forbid=["NOT EXITABLE"])

# ⛔ unknown must never render as a number, and must never flag
def _explode(c, usd):
    raise OSError("jupiter down")


check.S.dexscreener_token = lambda c: [_pair()]
check.onchain = None
check._round_trip = _explode
r = check.analyse("So11111111111111111111111111111111111111112")
txt = check.render(r)
_conds = {
    "realizable is None": r["realizable"] is None,
    "usd_back is None": r["realizable_usd_back"] is None,
    "renders CANNOT BE MEASURED": "CANNOT BE MEASURED" in txt,
    "not FLAGGED": r["verdict"] != "FLAGGED",
    "warns not corroborated": any("not corroborated" in w.lower()
                                  for w in r["warnings"]),
}
ok = all(_conds.values())
if not ok:
    print("      sub-conditions:", {k: v for k, v in _conds.items()})
    print("      verdict:", r["verdict"], "| warnings:", r["warnings"][:1])
RESULTS.append(("⛔ a dead quote API renders 'cannot be measured', never 0", ok, ""))
print(f"  {'PASS' if ok else 'FAIL'}  ⛔ a dead quote API renders 'cannot be measured', never 0")

# and the suite must stay OFFLINE - analyse() may not import the network module
# on its own account during these tests.
import inspect
_src = inspect.getsource(check.analyse)
ok = "chainfields.round_trip(" not in _src and "_round_trip(" in _src
RESULTS.append(("⭐ analyse() goes through the injection point, so tests stay offline", ok, ""))
print(f"  {'PASS' if ok else 'FAIL'}  ⭐ analyse() goes through the injection point, so tests stay offline")

print()
failed = [r for r in RESULTS if not r[1]]
print(f"{len(RESULTS) - len(failed)}/{len(RESULTS)} passed")
if failed:
    for n, _, w in failed:
        print(f"  FAILED: {n}  {w}")
sys.exit(1 if failed else 0)
