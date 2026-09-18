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

# ---------------------------------------------------------------------------
# ⛔ Jupiter's priceImpactPct is a SENTINEL for longtail tokens, not a number.
# Measured live 2026-09-18: OpenClaw round-tripped at 0.7643% while Jupiter
# reported priceImpactPct '1', i.e. 100% impact. Those cannot both be true.
# Real reference-priced tokens return small fractions:
#     SOL $100    '0.0000425409323578214859860615'
#     SOL $50,000 '0.0001166599206688746226102528'
#     BONK $100   '0.0014902943073434322217160682'
# ---------------------------------------------------------------------------
print()
print("6. the price-impact sentinel")
check(cf._impact_pct({"priceImpactPct": "1"}) is None,
      "⛔ exactly 1 is UNKNOWN, never recorded as 100%",
      repr(cf._impact_pct({"priceImpactPct": "1"})))
check(cf._impact_pct({"priceImpactPct": "1.0"}) is None, "'1.0' likewise")
check(cf._impact_pct({"priceImpactPct": "2"}) is None, "anything >= 1 likewise")
check(cf._impact_pct({"priceImpactPct": None}) is None, "missing -> None")
check(cf._impact_pct({}) is None, "absent -> None")
check(cf._impact_pct({"priceImpactPct": "not-a-number"}) is None, "garbage -> None")
check(cf._impact_pct({"priceImpactPct": "0.0000425409323578214859860615"}) == 0.004254,
      "⭐ a real SOL reading survives as 0.004254%",
      repr(cf._impact_pct({"priceImpactPct": "0.0000425409323578214859860615"})))
check(cf._impact_pct({"priceImpactPct": "0.0014902943073434322217160682"}) == 0.149029,
      "⭐ a real BONK reading survives as 0.149029%")
check(cf._impact_pct({"priceImpactPct": "0"}) == 0.0,
      "⚠️ a genuine ZERO is kept as 0.0, not coerced to None")

print()
print("holder_count survives an endpoint that spells `mint` differently")
print("-" * 70)

# ⛔ THE RUNNER HAS NO HELIUS KEY - .env is gitignored and stays that way - so
# config.helius_rpc() falls back to api.mainnet-beta.solana.com. That endpoint
# serves getTokenAccounts and returns the same shape, but wants `mintAddress`
# where Helius wants `mint` and REJECTS the other outright. Without the switch,
# every holder count on a scheduled run comes back None, and paperv3 - which
# refuses an unknown float by design - enters NOTHING on the runner while
# entering normally by hand. A capability that only works when a human runs it
# is precisely the failure this project keeps paying for.
#
# Probed live 2026-09-18 against both endpoints, both spellings; replayed here
# offline so the suite never needs the network.
_PAGE = {"token_accounts": [{"owner": "W1", "amount": "5"},
                            {"owner": "W2", "amount": "7"},
                            {"owner": "W1", "amount": "3"},
                            {"owner": "W3", "amount": "0"}],
         "cursor": None}


def _fake_endpoint(accepts):
    """Reject the wrong spelling exactly the way the real endpoints do."""
    seen = []

    def rpc(method, params, timeout=40, tries=3):
        seen.append(sorted(k for k in params if "mint" in k.lower()))
        if accepts not in params:
            wrong = next(k for k in params if "mint" in k.lower())
            return None, "{'code': -32602, 'message': 'unknown field `" + wrong + "`'}"
        return dict(_PAGE), None

    return rpc, seen


_real_rpc, _real_key = cf._rpc, cf._HOLDER_MINT_KEY[0]
try:
    for accepts, label in (("mint", "Helius"), ("mintAddress", "the public RPC")):
        cf._HOLDER_MINT_KEY[0] = "mint"          # always start Helius-first
        cf._rpc, seen = _fake_endpoint(accepts)
        r = cf.holder_count("MINT111")
        check(r.get("error") is None, f"{label}: no error", str(r.get("error")))
        check(r.get("holders") == 2,
              f"{label}: ⭐ counts DISTINCT owners with a balance",
              f"got {r.get('holders')} - W1 twice, W3 zero")
        check(cf._HOLDER_MINT_KEY[0] == accepts,
              f"{label}: settled on the spelling it accepts",
              cf._HOLDER_MINT_KEY[0])
    # ⚠️ And the switch must be paid ONCE, not on every page or every token.
    cf._HOLDER_MINT_KEY[0] = "mint"
    cf._rpc, seen = _fake_endpoint("mintAddress")
    cf.holder_count("MINT111")
    n_first = len(seen)
    cf.holder_count("MINT222")
    check(len(seen) - n_first == 1,
          "⚠️ the second token costs no extra probe - the switch is process-wide",
          f"{len(seen) - n_first} call(s) for the second token")
    # ⛔ A REAL error must still surface as None, never as 0 holders.
    cf._rpc = lambda *a, **k: (None, "503 Service Unavailable")
    r = cf.holder_count("MINT111")
    check(r.get("holders") is None and r.get("error"),
          "⛔ an unrelated failure is None with the reason, NEVER 0",
          repr(r.get("holders")))
finally:
    cf._rpc, cf._HOLDER_MINT_KEY[0] = _real_rpc, _real_key

print()
if FAIL:
    print(f"FAILED: {len(FAIL)}")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("all chainfields checks passed")
