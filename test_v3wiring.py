"""The v3 ledger is actually WIRED, end to end. Run: python test_v3wiring.py

⛔ WHY THIS FILE EXISTS. paperv3 had 71 passing tests, a pre-committed rule and
a live hand-run entry, and `collect.py` never called it. The ledger recorded
nothing automatically for the whole time it existed. **Passing unit tests are
not evidence that a module is in the system**, and this is the third place that
pattern has shown up: `chainfields` was imported only by paperv3, `devwallet` by
nothing at all.

⚠️ AND THE SECOND HALF IS WORSE. Wiring v3 in while `holders` was on ZERO of the
last 400 observation rows would have produced a gate that could never pass: it
would have entered nothing, for ever, and read exactly like a quiet market. So
this drives the real `scanner.scan()` loop with the network stubbed and asserts
a LEDGER ROW comes out the other end - the output, not the execution.
"""
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

import testsandbox
testsandbox.activate()

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


import chainfields
import journal
import liveness
import onchain
import paperv3
import scanner
import sources as S

CA = "GOODPOOLcafebabe1111111111111111111111111111"
DEAD = "DEADPOOLcafebabe2222222222222222222222222222"

CALLS = {"holders": 0, "round_trip": 0, "sell_quote": 0}


def _pool(addr):
    return {"attributes": {"address": addr}}


def _pair(network, addr):
    # A pool that passes every free condition: amm venue, a sell side, depth.
    return {"chainId": "solana", "dexId": "raydium", "pairAddress": addr,
            "baseToken": {"address": addr, "symbol": "GOOD", "name": "Good Token"},
            "quoteToken": {"address": "So11111111111111111111111111111111111111112",
                           "symbol": "SOL"},
            "priceUsd": "0.0001", "fdv": 60000,
            # ⚠️ base * priceUsd must stay UNDER liquidity.usd, or
            # resolve_exit_depth() returns 0 and paper.wants_authority_check()
            # refuses the row - which is how the first run of this test found
            # that the whole v3 path hangs off the exit-depth floor.
            "liquidity": {"usd": 50000, "base": 1e8, "quote": 100},
            "txns": {"h1": {"buys": 40, "sells": 25}},
            "volume": {"h1": 9000, "h24": 40000},
            "priceChange": {"h1": 5.0},
            "pairCreatedAt": 1700000000000}


def _authorities(addr):
    return {"mint_authority": None, "freeze_authority": None,
            "can_mint": False, "can_freeze": False, "authorities_error": None}


def _holder_count(mint, max_pages=25):
    CALLS["holders"] += 1
    if mint == DEAD:
        return {"holders": 4, "truncated": False, "error": None}
    return {"holders": 812, "truncated": False, "error": None}


def _round_trip(mint, usd=100):
    CALLS["round_trip"] += 1
    return {"verdict": "TRADEABLE", "usd_in": float(usd), "usd_back": 99.2,
            "rt_cost_pct": 0.8, "token_qty_raw": "1234567890",
            "price_impact_pct": 0.4, "venues": ["Raydium"],
            "ts": "2026-09-18T15:00:00Z", "error": None}


def _sell_quote(mint, qty):
    CALLS["sell_quote"] += 1
    return {"usd_out": 250.0, "price_impact_pct": 0.6, "venues": ["Raydium"],
            "ts": "2026-09-18T15:10:00Z", "verdict": "TRADEABLE", "error": None}


def _low_quote(mint, qty):
    CALLS["sell_quote"] += 1
    return {"usd_out": 61.0, "price_impact_pct": 2.2, "venues": ["Raydium"],
            "ts": "2026-09-19T15:10:00Z", "verdict": "TRADEABLE", "error": None}


S.new_pools = lambda network, pages=None: [_pool(CA), _pool(DEAD)]
S.dexscreener_pair = _pair
S.pace = lambda *a, **k: None
S.seconds_left = lambda *a, **k: None
S.per_call_estimate = lambda *a, **k: 0.01
onchain.authorities = _authorities
onchain.RPC_PACE_S = 0
chainfields.holder_count = _holder_count
chainfields.round_trip = _round_trip
chainfields.sell_quote = _sell_quote

print("=" * 70)
print("1. a scan pass reaches the v3 gate and ENTERS")
print("=" * 70)

rows = scanner.scan("solana", verbose=False)
check("the stubbed pass produced rows", len(rows) == 2, str(len(rows)))
check("⭐ a holder count was fetched, and only for candidates",
      CALLS["holders"] == 2, str(CALLS["holders"]))
# ⚠️ AN ENTRY COSTS THREE ROUND TRIPS, NOT ONE, and that is a budget fact worth
# stating: the gate quote at $100, plus SHADOW quotes at $250 and $500 that are
# recorded and never traded so the depth cliff is measured at the moment of the
# trade rather than remembered. Six Jupiter calls per entry against a 55/min
# bucket. ⛔ The 4-holder pool must still cost ZERO - it was refused before the
# gate ever asked for a quote.
check("⭐ the 4-holder pool cost no quote at all",
      CALLS["round_trip"] == 1 + len(paperv3.SIZES_RECORDED) - 1,
      str(CALLS["round_trip"]) + " = 1 gate quote + "
      + str(len(paperv3.SIZES_RECORDED) - 1) + " shadow sizes, for ONE entry")

good = [r for r in rows if r.get("addr") == CA]
dead = [r for r in rows if r.get("addr") == DEAD]
check("both rows came back", len(good) == 1 and len(dead) == 1)
if good and dead:
    check("⛔ THE ENTRY LANDED IN THE LEDGER, not just in a return value",
          bool(good[0].get("paper_v3_entry")), str(good[0].get("paper_v3_skipped")))
    check("and the row carries the holder count",
          good[0].get("holders") == 812, str(good[0].get("holders")))
    check("⭐ the refused row says WHY, on the row we paid to evaluate",
          "holders" in str(dead[0].get("paper_v3_skipped")),
          str(dead[0].get("paper_v3_skipped")))
    check("⛔ and it was NOT entered", not dead[0].get("paper_v3_entry"))

led = paperv3.open_positions()
check("⛔ open_positions() sees it - the file, not the variable",
      len(led) == 1, str(len(led)))
if led:
    check("the fill is priced on the quote, not a mid",
          float(led[0]["usd_in"]) == paperv3.NOTIONAL_USD, str(led[0].get("usd_in")))
    # ⚠️ Stored as an int, not the quote's string. A raw token amount is an
    # integer of base units and must never be floated.
    check("and it recorded the token quantity it could actually sell",
          led[0].get("token_qty_raw") == 1234567890
          and isinstance(led[0].get("token_qty_raw"), int),
          repr(led[0].get("token_qty_raw")))

print()
print("=" * 70)
print("2. the per-pass tally explains an empty ledger")
print("=" * 70)

check("⭐ refusals are counted for EVERY row, not only the paid ones",
      sum(scanner.LAST_SCAN.get("v3_refusals", {}).values()) >= 1,
      str(scanner.LAST_SCAN.get("v3_refusals")))
check("quotes bought are recorded", scanner.LAST_SCAN.get("v3_quotes") == 1)
check("holder fetches are recorded", scanner.LAST_SCAN.get("holders_fetched") == 2)
cov = journal.record_coverage("solana", {"pools": 2}, 2, 70, 1,
                              scan=dict(scanner.LAST_SCAN))
for f in ("v3_quotes", "v3_refusals", "holders_fetched"):
    check("⛔ and " + f + " reaches the COVERAGE ROW, or it does not exist",
          cov.get(f) is not None, repr(cov.get(f)))

print()
print("=" * 70)
print("3. the sweep closes it, on a live quote for the exact holding")
print("=" * 70)

sw = paperv3.sweep(verbose=False, sell_quote=_sell_quote)
check("the sweep checked the open position", sw["checked"] == 1, str(sw))
check("⭐ and CLOSED it - $250 back on $100 in is past the 2.0x target",
      sw["closed"] == 1, str(sw["reasons"]))
check("the reason is TARGET, not a fabricated one",
      sw["reasons"].get("TARGET") == 1, str(sw["reasons"]))
check("⛔ nothing is left open", len(paperv3.open_positions()) == 0)


# ⛔ AND THE MAX_HOLD PATH MUST USE THE INJECTED QUOTE TOO. close_entry() will
# reach for chainfields.sell_quote itself when handed sq=None, walking straight
# past the injection point sweep() advertises - an offline suite that silently
# hits the network, which this project paid for once already today.
_ROW = dict(venue_type="amm", can_mint=False, can_freeze=False, sells_h1=3,
            buys_h1=12, token=CA + "X", holders=500, name="OLD")
_rt = _round_trip(CA + "X")
_old_entry, _ = paperv3.open_entry(_ROW, _rt, shadows=False)
check("a second position was opened for the MAX_HOLD case", _old_entry is not None)
if _old_entry:
    # age it past the hold limit by rewriting the ledger's entry timestamp
    import datetime as dt
    _stale = (dt.datetime.now(dt.timezone.utc)
              - dt.timedelta(hours=paperv3.MAX_HOLD_H + 1)).strftime("%Y-%m-%dT%H:%M:%SZ")
    _lines = [json.loads(l) for l in io.open(paperv3.LEDGER, encoding="utf-8") if l.strip()]
    for _l in _lines:
        if _l.get("hash") == _old_entry["hash"]:
            _l["ts"] = _stale
    with io.open(paperv3.LEDGER, "w", encoding="utf-8") as _f:
        for _l in _lines:
            _f.write(json.dumps(_l) + chr(10))

    _before = CALLS["sell_quote"]
    # $61 back on $100 in: a loss, well under the 2.0x target.
    _net = {"hit": False}
    _real_sq = chainfields.sell_quote
    chainfields.sell_quote = lambda *a, **k: _net.update(hit=True) or _real_sq(*a, **k)
    try:
        sw2 = paperv3.sweep(verbose=False, sell_quote=_low_quote)
    finally:
        chainfields.sell_quote = _real_sq
    check("⭐ the aged position closed", sw2["closed"] == 1, str(sw2["reasons"]))
    check("⛔ and the reason is MAX_HOLD, not a target it never hit",
          sw2["reasons"].get("MAX_HOLD") == 1, str(sw2["reasons"]))
    check("⛔ and it used the INJECTED quote, never chainfields directly",
          CALLS["sell_quote"] > _before and not _net["hit"],
          "close_entry must not fetch its own")

led = [json.loads(l) for l in io.open(paperv3.LEDGER, encoding="utf-8")
       if l.strip()]
ex = [r for r in led if r.get("type") == "exit"]
check("two exit rows were written - one per close", len(ex) == 2, str(len(ex)))
by = {r.get("exit_reason"): r for r in ex}
check("⛔ both reasons are recorded, and they differ",
      set(by) == {"TARGET", "MAX_HOLD"}, str(sorted(by)))
if "TARGET" in by:
    check("⭐ the multiple is a ratio of two real quoted dollar amounts",
          abs(by["TARGET"]["realizable_multiple"] - 2.5) < 1e-6,
          str(by["TARGET"].get("realizable_multiple")))
    check("and it records the exit quote's own impact and venues",
          by["TARGET"].get("exit_price_impact_pct") == 0.6
          and by["TARGET"].get("exit_route_venues") == ["Raydium"])
if "MAX_HOLD" in by:
    # ⚠️ A LOSS IS RECORDED AS A LOSS. $61 back on $100 in is 0.61x, and it is
    # written down - the v1 ledger's problem was never that it was pessimistic.
    check("⛔ a losing close records 0.61x, not a void and not a skip",
          abs(by["MAX_HOLD"]["realizable_multiple"] - 0.61) < 1e-6,
          str(by["MAX_HOLD"].get("realizable_multiple")))
    check("⚠️ and it is flagged as past its hold window",
          by["MAX_HOLD"].get("on_time") is False,
          str(by["MAX_HOLD"].get("elapsed_h")))

print()
print("=" * 70)
print("4. it is SCHEDULED, which is the thing tests never proved before")
print("=" * 70)

csrc = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "collect.py"), encoding="utf-8").read()
check("⛔ collect.py calls the v3 sweep", "paperv3.sweep(" in csrc)
import collect
check("⭐ paperv3.open is declared as firing in the scan stage",
      "paperv3.open" in collect.STAGE_FIRES["scan"])
check("⭐ paperv3.sweep and .close in the sweep stage",
      {"paperv3.sweep", "paperv3.close"} <= collect.STAGE_FIRES["sweep"])
for c in ("paperv3.open", "paperv3.close", "paperv3.sweep"):
    check(c + " is DECLARED in liveness.COMPONENTS", c in liveness.COMPONENTS)
check("⚠️ open/close are unmetered - an entry is a market event, not a schedule",
      liveness.COMPONENTS["paperv3.open"][0] is None
      and liveness.COMPONENTS["paperv3.close"][0] is None)
check("⛔ but the SWEEP has a real threshold - it runs every pass",
      liveness.COMPONENTS["paperv3.sweep"][0] == 12)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
