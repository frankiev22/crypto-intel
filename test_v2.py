"""RULE_V2 must be v1 minus the score, and must not be able to touch v1.

Two ledgers running in parallel over one observation stream is only a
controlled comparison if the arms are assigned correctly and the ledgers stay
separate. The dangerous failure is silent: a v2 entry landing in v1's ledger
would corrupt the measurement Frank has been waiting on since 9/04, and it
would still verify, because both chains use the same hash function.

Run: python test_v2.py    (offline, sandboxed, writes to a temp ledger)
"""
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
import tempfile

import paper
import paperv2

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


TMP = tempfile.mkdtemp()
paperv2.LOG_DIR = TMP
paperv2.LEDGER = os.path.join(TMP, "ledger_v2.jsonl")
V1_LEDGER = os.path.join(TMP, "ledger_v1.jsonl")
paper.LEDGER = V1_LEDGER

CLEAN = {"venue_type": "amm", "exit_depth_usd": 5000.0, "can_mint": False,
         "can_freeze": False, "sells_h1": 5, "buys_h1": 20,
         "price_usd": 0.001, "liq": 10000.0, "fdv": 10000.0,
         "pair": "P" * 43}


def row(**kw):
    r = dict(CLEAN)
    r.update(kw)
    r.setdefault("token", "C" * 43)
    return r


print("=" * 70)
print("1. v2 is v1 with the score band deleted, and NOTHING else")
print("=" * 70)
check("pinned constants have not drifted", not paperv2.gate_drift(),
      str(paperv2.gate_drift()))
for sc in (0, 10, 44, 69, 70, 95, 100, None):
    ok, why = paperv2.qualifies(row(score=sc))
    if not ok:
        check(f"score {sc} qualifies under v2", False, why)
        break
else:
    check("every score qualifies under v2, including None and 100", True)

# ...and every fraud check still refuses, at v1's constant
check("a curve row is refused", paperv2.qualifies(row(venue_type="bonding_curve"))[0] is False)
check("depth under $1,000 is refused", paperv2.qualifies(row(exit_depth_usd=999.0))[0] is False)
check("unknown authority is refused (fails closed)",
      paperv2.qualifies(row(can_mint=None))[0] is False)
check("live mint authority is refused", paperv2.qualifies(row(can_mint=True))[0] is False)
check("live freeze authority is refused", paperv2.qualifies(row(can_freeze=True))[0] is False)
check("no sell side is refused",
      paperv2.qualifies(row(sells_h1=0, buys_h1=10))[0] is False)
check("v2's depth floor equals v1's", paperv2.MIN_EXIT_DEPTH == paper.MIN_EXIT_DEPTH,
      f"{paperv2.MIN_EXIT_DEPTH} vs {paper.MIN_EXIT_DEPTH}")
check("v2's target equals v1's", paperv2.TARGET_MULT == paper.TARGET_MULT)

# The rule may not consult a score at the AST level - a comment is not a lock.
import ast
fn = next(n for n in ast.walk(ast.parse(io.open("paperv2.py", encoding="utf-8").read()))
          if isinstance(n, ast.FunctionDef) and n.name == "qualifies")
consts = {n.value for n in ast.walk(fn) if isinstance(n, ast.Constant)
          and isinstance(n.value, str)}
check("paperv2.qualifies never mentions score", "score" not in consts, str(consts)[:80])

print()
print("=" * 70)
print("2. the arms are assigned by v1's verdict, at entry time")
print("=" * 70)
a, _ = paperv2.open_entry(row(token="A" * 43, score=85))
check("a token v1 also accepts is ARM A", a and a["arm"] == "A", str(a and a["arm"]))
check("and records that it also qualifies under v1", a and a["also_qualifies_v1"] is True)
b, _ = paperv2.open_entry(row(token="B" * 43, score=10))
check("a token v1 rejects on score is ARM B", b and b["arm"] == "B", str(b and b["arm"]))
check("and records WHY v1 rejected it", b and "score" in str(b["v1_reason"]), str(b and b["v1_reason"]))
check("the score is kept as an observed fact, not a decision",
      b and b["score_at_entry"] == 10)
check("a below-band rejection is stamped B_low at entry",
      b and b["sub_arm"] == "B_low", str(b and b.get("sub_arm")))
hi, _ = paperv2.open_entry(row(token="H" * 43, score=100))
check("a score-100 rejection is stamped B_high at entry",
      hi and hi["sub_arm"] == "B_high", str(hi and hi.get("sub_arm")))
check("...and it is arm B, since v1 still rejects it", hi and hi["arm"] == "B")
c, why = paperv2.open_entry(row(token="C" * 43, can_mint=True))
check("a token BOTH rules reject is not entered at all", c is None, str(why))

print()
print("=" * 70)
print("3. v2 cannot touch v1's ledger")
print("=" * 70)
check("v1's ledger does not exist - v2 wrote nothing to it",
      not os.path.exists(V1_LEDGER), "v1 ledger was created by a v2 entry")
check("the two ledger paths differ", paperv2.LEDGER != paper.LEDGER)
rows = paperv2._read()
check("every v2 row is stamped rule=v2", all(r.get("rule") == "v2" for r in rows),
      str([r.get("rule") for r in rows]))
check("every v2 row carries the epoch", all(r.get("epoch") == "2026-09-10"
                                            for r in rows if r.get("type") == "entry"))
ok, n, msg = paperv2.verify()
check("the v2 chain verifies independently", ok, msg)
check("v2 has its own seq, starting at 0",
      [r["seq"] for r in rows] == list(range(len(rows))), str([r.get("seq") for r in rows]))

# The scanner must enter v1 and v2 in SEPARATE try blocks, so a v2 exception
# can never abort a v1 entry that has already been decided.
ssrc = io.open("scanner.py", encoding="utf-8").read()
check("scanner calls paperv2.open_entry", "paperv2.open_entry(row)" in ssrc)
check("v1 and v2 entries are in separate try blocks",
      ssrc.count("except Exception as e:\n            print(f\"  [paper]") == 1
      and "[v2] {type(e).__name__}" in ssrc)

print()
print("=" * 70)
print("4. summary reports the arms separately and withholds below MIN_N")
print("=" * 70)
s = paperv2.summary()
check("three arms are reported, not two",
      set(s["arms"]) == {"A", "B_high", "B_low"}, str(sorted(s["arms"])))
check("arm A is labelled as the score's acceptances",
      "accepted" in s["arms"]["A"]["label"])
check("B_high is labelled as ABOVE the band",
      "ABOVE" in s["arms"]["B_high"]["label"], s["arms"]["B_high"]["label"])
check("B_low is labelled as BELOW the band",
      "BELOW" in s["arms"]["B_low"]["label"], s["arms"]["B_low"]["label"])
check("rates are WITHHELD below MIN_N distinct tokens",
      all("WITHHELD" in v["rate"] for v in s["arms"].values()),
      str({k: v["rate"] for k, v in s["arms"].items()}))

# The split must be recoverable for the 90 entries written before the field
# existed - otherwise the amendment would have cost the sample.
old_row = {"arm": "B", "score_at_entry": 100}
check("a pre-amendment score-100 row recovers as B_high",
      paperv2._sub_arm(old_row) == "B_high", str(paperv2._sub_arm(old_row)))
check("a pre-amendment score-50 row recovers as B_low",
      paperv2._sub_arm({"arm": "B", "score_at_entry": 50}) == "B_low")
check("an arm-A row has no sub-arm",
      paperv2._sub_arm({"arm": "A", "score_at_entry": 85}) is None)
check("B_high and B_low are never pooled in the summary",
      s["arms"]["B_high"] is not s["arms"]["B_low"])
check("no pooled rate is reported anywhere", "rate" not in s and "hit_rate" not in s,
      str(sorted(s)))

print()
print("=" * 70)
print("5. v2 closes on EXACTLY v1's decision logic")
print("=" * 70)
check("v2 calls paper.close_decision, not a copy of it",
      "paper.close_decision(" in io.open("paperv2.py", encoding="utf-8").read())

# A raised lookup is a failed lookup, never evidence of a delisted pool.
def boom(network, pa):
    raise OSError("network down")

before = len(paperv2.open_positions())
st = paperv2.sweep(boom, verbose=False)
check("a fetch that RAISES leaves the position open",
      st["closed"] == 0 and st["still_open"] == before, str(st))
check("nothing was appended on a failed lookup",
      len(paperv2.open_positions()) == before)

# A target hit needs BOTH the multiple and the depth - the Grogu rule.
# priceNative is required: exit depth is the QUOTE side valued in USD, which
# needs the quote token's price (priceUsd / priceNative), never liquidity.usd.
def rich(network, pa):
    return {"priceUsd": "0.010", "priceNative": "0.00005",
            "liquidity": {"usd": 40000.0, "base": 1.0, "quote": 100.0}}

def pumped_corpse(network, pa):
    # 10x on the price, $0.0007 of quote side. This is the Grogu shape.
    return {"priceUsd": "0.010", "priceNative": "0.00005",
            "liquidity": {"usd": 0.0000014, "base": 1.0, "quote": 0.0000035}}

e = paperv2.open_positions()[0]
act, px, d, code, _ = paper.close_decision(e, pumped_corpse(None, None), 1.0,
                                           target_mult=2.0, min_depth=1000.0,
                                           max_hold_h=24.0)
check("a 10x on $0.0000007 of depth is NOT a target close", act != "target", act)
act2, _, _, _, _ = paper.close_decision(e, rich(None, None), 1.0,
                                        target_mult=2.0, min_depth=1000.0,
                                        max_hold_h=24.0)
check("the same multiple WITH depth is a target close", act2 == "target", act2)

# and an actual v2 close lands in v2's ledger, stamped, chained
n_before = len(paperv2._read())
st2 = paperv2.sweep(rich, verbose=False)
check("v2 closed its open positions", st2["closed"] >= 1, str(st2))
exits = [r for r in paperv2._read() if r.get("type") == "exit"]
check("every exit is stamped rule=v2", all(r.get("rule") == "v2" for r in exits))
check("every exit carries its arm", all(r.get("arm") in ("A", "B") for r in exits))
check("the chain still verifies after closing", paperv2.verify()[0])
check("v1's ledger STILL does not exist", not os.path.exists(V1_LEDGER),
      "a v2 close wrote into v1")
s2 = paperv2.summary()
check("closes are attributed to the right arms",
      sum(v["closed_priceable"] for v in s2["arms"].values()) == len(exits),
      str({k: v["closed_priceable"] for k, v in s2["arms"].items()}))


print()
print("=" * 70)
print("6. a rate is never quoted on entries - only on CLOSES")
print("=" * 70)
# 75 entries with 2 closes printed "100.00%" on 2026-09-11. Entering is not an
# outcome, and MIN_N has always meant closed distinct tokens.
s6 = paperv2.summary()
for arm, a in s6["arms"].items():
    if a["closed_tokens"] < paperv2.MIN_N:
        check(f"{arm}: rate WITHHELD while closed tokens < {paperv2.MIN_N}",
              "WITHHELD" in a["rate"],
              f"closed={a['closed_tokens']} entered={a['distinct_tokens']} rate={a['rate']}")
check("conclusiveness is computed from CLOSED tokens, not entered",
      all(a["conclusive"] == (a["closed_tokens"] >= paperv2.MIN_N)
          for a in s6["arms"].values()),
      str({k: (v["conclusive"], v["closed_tokens"], v["distinct_tokens"])
           for k, v in s6["arms"].items()}))
check("the withheld message names the CLOSED count first",
      all("CLOSED" in a["rate"] for a in s6["arms"].values() if not a["conclusive"]))

# The live ledger is the case that actually shipped the leak.
import importlib
live = importlib.import_module("paperv2")
saved = live.LEDGER
live.LEDGER = "data/paper/ledger_v2.jsonl"
ls = live.summary()
leaks = {k: v["rate"] for k, v in ls["arms"].items()
         if v["closed_tokens"] < live.MIN_N and "WITHHELD" not in v["rate"]}
check("the LIVE v2 ledger quotes no rate below MIN_N closed tokens",
      not leaks, str(leaks))
live.LEDGER = saved


print()
print("=" * 70)
print("7. a v2 win requires exit depth, exactly as v1's does")
print("=" * 70)
import json as _json
_saved = paperv2.LEDGER
paperv2.LEDGER = "data/paper/ledger_v2.jsonl"
_rows = [_json.loads(l) for l in open(paperv2.LEDGER, encoding="utf-8") if l.strip()]
_ents = {r["hash"]: r for r in _rows if r.get("type") == "entry"}
_s7 = paperv2.summary()
for _arm in ("A", "B_high", "B_low"):
    _gated = 0
    _price = 0
    for _x in _rows:
        if _x.get("type") != "exit" or _x.get("mult") is None:
            continue
        _e = _ents.get(_x.get("entry_id"))
        if not _e or (paperv2._sub_arm(_e) or _e.get("arm")) != _arm:
            continue
        if _x["mult"] >= paperv2.TARGET_MULT:
            _price += 1
            if (_x.get("exit_depth_usd") is not None
                    and _x["exit_depth_usd"] >= paperv2.MIN_EXIT_DEPTH):
                _gated += 1
    check(f"{_arm}: counted wins equal DEPTH-GATED wins on the live ledger",
          _s7["arms"][_arm]["wins"] == _gated,
          f"summary={_s7['arms'][_arm]['wins']} gated={_gated} price_only={_price}")
    check(f"{_arm}: price-only wins are reported beside, never instead",
          _s7["arms"][_arm]["wins_price_only"] == _price)
paperv2.LEDGER = _saved

bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
