"""paperv3 invariants. Run: python test_paperv3.py   (offline, writes nothing real)

PRECOMMIT_paper_v3.md section 8 names four things this file must prove:

  1. the $0-recovered close
  2. the no-route exit
  3. the drift refusal
  4. ⭐ that NO MID PRICE CAN REACH THE P&L

(4) is the one that matters. v1 and v2 are worthless for exactly one reason -
their multiple was `exit_price_usd / entry_price_usd`, a mid-to-mid ratio with
zero price impact, while `notional_usd` sat in every row unused. A test that
only checks arithmetic would have passed on v1 too. So this file also walks the
module at the AST level and fails if a price-like field can reach a recorded
multiple.
"""
import ast
import datetime as dt
import io
import json
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

# ⛔ Before anything that writes. A full suite run was appending rows to
# data/liveness/ - the file that answers "is the collector alive" - so the
# tests were writing into the health signal they are meant to check.
# run_tests.py fails if data/ changes at all; this is how a suite complies.
import testsandbox
testsandbox.activate()
import tempfile

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


HERE = os.path.dirname(os.path.abspath(__file__))
import paperv3

# Never touch the real ledger.
paperv3.LEDGER = os.path.join(tempfile.mkdtemp(), "ledger_v3.jsonl")
paperv3.LOG_DIR = os.path.dirname(paperv3.LEDGER)

CLEAN = {"addr": "So11111111111111111111111111111111111111112", "symbol": "T",
         "venue_type": "amm", "can_mint": False, "can_freeze": False,
         "sells_h1": 40, "buys_h1": 60, "holders": 500,
         "holders_truncated": False, "pair": "PAIR1"}
RT_OK = {"verdict": "TRADEABLE", "token_qty_raw": 1_000_000_000,
         "price_impact_pct": 0.42, "rt_cost_pct": 3.1,
         "venues": ["Meteora"], "ts": 1789000000}


def fresh():
    paperv3.LEDGER = os.path.join(tempfile.mkdtemp(), "ledger_v3.jsonl")
    paperv3.LOG_DIR = os.path.dirname(paperv3.LEDGER)


print("=" * 70)
print("1. the entry gate, clause for clause against the frozen pre-commit")
print("=" * 70)

check("a clean AMM row qualifies", paperv3.qualifies(CLEAN, rt=RT_OK)[0] is True,
      paperv3.qualifies(CLEAN, rt=RT_OK)[1])
check("a curve row is refused",
      paperv3.qualifies(dict(CLEAN, venue_type="bonding_curve"), rt=RT_OK)[0] is False)
for v in ("COSTLY", "TOTAL_LOSS", "NO_SELL_ROUTE", "NO_BUY_ROUTE", None):
    ok, why = paperv3.qualifies(CLEAN, rt=dict(RT_OK, verdict=v))
    check(f"exit verdict {v} is refused", ok is False, why[:52])
check("⛔ unknown mint authority FAILS CLOSED",
      paperv3.qualifies(dict(CLEAN, can_mint=None), rt=RT_OK)[0] is False)
check("⛔ unknown freeze authority FAILS CLOSED",
      paperv3.qualifies(dict(CLEAN, can_freeze=None), rt=RT_OK)[0] is False)
check("live mint authority is refused",
      paperv3.qualifies(dict(CLEAN, can_mint=True), rt=RT_OK)[0] is False)
check("live freeze authority is refused",
      paperv3.qualifies(dict(CLEAN, can_freeze=True), rt=RT_OK)[0] is False)
check("buys with no sells is refused",
      paperv3.qualifies(dict(CLEAN, sells_h1=0, buys_h1=10), rt=RT_OK)[0] is False)
check("holders below 100 is refused",
      paperv3.qualifies(dict(CLEAN, holders=99), rt=RT_OK)[0] is False)
check("holders exactly 100 qualifies",
      paperv3.qualifies(dict(CLEAN, holders=100), rt=RT_OK)[0] is True)
check("⛔ unknown holder count is refused, not treated as 0",
      paperv3.qualifies(dict(CLEAN, holders=None), rt=RT_OK)[0] is False)
check("⭐ a TRUNCATED holder count is refused - a bound is not a count",
      paperv3.qualifies(dict(CLEAN, holders=5000, holders_truncated=True),
                        rt=RT_OK)[0] is False)
check("no round_trip supplied is refused, never assumed",
      paperv3.qualifies(CLEAN, rt=None)[0] is False)
check("a round_trip with no token quantity is refused",
      paperv3.qualifies(CLEAN, rt=dict(RT_OK, token_qty_raw=None))[0] is False)

print()
print("=" * 70)
print("2. ⛔ the drift refusal - the gate cannot be widened from the outside")
print("=" * 70)

check("no drift as shipped", not paperv3.gate_drift(), str(paperv3.gate_drift()))
_old = paperv3.MIN_HOLDERS
paperv3.MIN_HOLDERS = 10
try:
    check("moving MIN_HOLDERS is DETECTED", bool(paperv3.gate_drift()),
          str(paperv3.gate_drift()))
    ok, why = paperv3.qualifies(CLEAN, rt=RT_OK)
    check("and every entry is refused while it is drifted", ok is False, why[:60])
    check("the refusal names the drifted constant", "MIN_HOLDERS" in why, why[:60])
finally:
    paperv3.MIN_HOLDERS = _old
check("restored", not paperv3.gate_drift())

for name, val in (("TARGET_MULT", 1.1), ("MAX_HOLD_H", 999.0),
                  ("NOTIONAL_USD", 10.0), ("MIN_N", 3)):
    old = getattr(paperv3, name)
    setattr(paperv3, name, val)
    try:
        check(f"moving {name} is DETECTED", bool(paperv3.gate_drift()))
    finally:
        setattr(paperv3, name, old)

print()
print("=" * 70)
print("3. ⭐ the $0-recovered close and the no-route exit")
print("=" * 70)

fresh()
e, why = paperv3.open_entry(dict(CLEAN), rt=RT_OK, shadows=False)
check("an entry is written", e is not None, why)
check("it records the MONEY and the QUANTITY, not a price",
      e["usd_in"] == 100.0 and e["token_qty_raw"] == 1_000_000_000)
check("⭐ it records entry price impact", e["entry_price_impact_pct"] == 0.42)
check("it declares the exit rule AT ENTRY", "realizable 2.0x" in e["exit_rule"])
check("no entry_price_usd field exists at all", "entry_price_usd" not in e,
      ", ".join(k for k in e if "price" in k))

# ⛔ the exit route has vanished
x = paperv3.close_entry(e, sq={"usd_out": None, "verdict": "NO_SELL_ROUTE",
                               "error": "no route", "ts": 1789000100,
                               "venues": None, "price_impact_pct": None},
                        shadows=False)
check("⛔ a vanished exit route CLOSES the position, never skips it",
      x is not None and x["type"] == "exit")
check("...at $0 recovered", x["usd_out"] == 0.0)
check("...as a 0.0x multiple, i.e. a total loss", x["realizable_multiple"] == 0.0)
check("...with the reason recorded", x["exit_reason"] == "NO_SELL_ROUTE")
check("...and it is NOT a void", not x.get("void"))
check("the position is no longer open", paperv3.has_open(CLEAN["addr"]) is False)

fresh()
e2, _ = paperv3.open_entry(dict(CLEAN), rt=RT_OK, shadows=False)
x2 = paperv3.close_entry(e2, sq={"usd_out": 250.0, "verdict": "QUOTED",
                                 "ts": 1789000100, "venues": ["Raydium"],
                                 "price_impact_pct": 1.5, "error": None},
                         shadows=False)
check("a real 2.5x is recorded from the quoted dollars",
      x2["realizable_multiple"] == 2.5, str(x2["realizable_multiple"]))
check("and reported as TARGET", x2["exit_reason"] == "TARGET")
check("⭐ exit price impact is recorded too", x2["exit_price_impact_pct"] == 1.5)

fresh()
e3, _ = paperv3.open_entry(dict(CLEAN), rt=RT_OK, shadows=False)
x3 = paperv3.close_entry(e3, sq={"usd_out": 41.0, "verdict": "QUOTED",
                                 "ts": 1789000100, "venues": ["Raydium"],
                                 "price_impact_pct": 9.0, "error": None},
                         shadows=False)
check("⭐ a LOSS is recorded, not dropped", x3["realizable_multiple"] == 0.41)
check("and it is not a void either", not x3.get("void"))

# the one permitted void
fresh()
e4, _ = paperv3.open_entry(dict(CLEAN), rt=RT_OK, shadows=False)
v4 = paperv3.close_void(e4, "quote API returned 503")
check("a RECORDING failure is the only permitted void", v4.get("void") is True)
check("it carries no multiple", v4["realizable_multiple"] is None)
check("and it names the reason", "503" in v4["void_reason"])

print()
print("=" * 70)
print("4. ⭐⭐ NO MID PRICE CAN REACH THE P&L - checked at the AST level")
print("=" * 70)

src = io.open(os.path.join(HERE, "paperv3.py"), encoding="utf-8").read()
tree = ast.parse(src)

# The multiple must be computed from usd_out / usd_in and nothing else.
fn = next(n for n in ast.walk(tree)
          if isinstance(n, ast.FunctionDef) and n.name == "close_entry")
body = [n for n in fn.body if not (isinstance(n, ast.Expr)
                                   and isinstance(n.value, ast.Constant))]
mod = ast.Module(body=body, type_ignores=[])
names = {n.id for n in ast.walk(mod) if isinstance(n, ast.Name)}
attrs = {n.attr for n in ast.walk(mod) if isinstance(n, ast.Attribute)}
strs = {n.value for n in ast.walk(mod)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)}

# ⭐ THE PRECISE RULE, not an enumerated blocklist: any token that talks about a
# PRICE is forbidden UNLESS it is an IMPACT measurement. price_impact_pct is
# required by the pre-commit and is not a mid; entry_price_usd is exactly the
# thing that made v1 fictional. An enumerated list would miss the next name
# somebody invents, so this inverts it - "price" is guilty until it says impact.
def price_like(tok):
    t = str(tok).lower()
    return ("price" in t or "mid" in t) and "impact" not in t
hits = sorted(str(x) for x in (names | attrs | strs) if price_like(x))
check("close_entry references no mid-price field", not hits, ", ".join(hits))

# and prove the rule actually bites, so it is not vacuous
check("...and that check would catch entry_price_usd", price_like("entry_price_usd"))
check("...while still permitting price_impact_pct", not price_like("price_impact_pct"))

# and the multiple is literally usd_out over usd_in
div = [n for n in ast.walk(mod)
       if isinstance(n, ast.BinOp) and isinstance(n.op, ast.Div)]
check("close_entry contains exactly one division", len(div) == 1, str(len(div)))
d = div[0]
check("⭐ and it is usd_out / usd_in",
      isinstance(d.left, ast.Name) and d.left.id == "usd_out"
      and isinstance(d.right, ast.Name) and d.right.id == "usd_in",
      ast.dump(d)[:80])

# Nothing in the module may write a *_price_usd field into a record.
allp = {n.value for n in ast.walk(tree)
        if isinstance(n, ast.Constant) and isinstance(n.value, str)}
bad = sorted(s for s in allp if s.endswith("price_usd"))
check("no *_price_usd field is written anywhere in paperv3",
      not bad, ", ".join(bad))

# ⛔ and no score may gate an entry - same rule as test_scoreband.py
gate = next(n for n in ast.walk(tree)
            if isinstance(n, ast.FunctionDef) and n.name == "qualifies")
gbody = ast.Module(body=[n for n in gate.body
                         if not (isinstance(n, ast.Expr)
                                 and isinstance(n.value, ast.Constant))],
                   type_ignores=[])
gtok = {n.id for n in ast.walk(gbody) if isinstance(n, ast.Name)} \
    | {n.attr for n in ast.walk(gbody) if isinstance(n, ast.Attribute)} \
    | {n.value for n in ast.walk(gbody)
       if isinstance(n, ast.Constant) and isinstance(n.value, str)}
sc = sorted(x for x in gtok if "score" in str(x).lower() or "grade" in str(x).lower())
check("⛔ the v3 entry gate mentions no score term", not sc, ", ".join(sc))

print()
print("=" * 70)
print("5. the chain, and the n floor that was fixed before any data existed")
print("=" * 70)

fresh()
a, _ = paperv3.open_entry(dict(CLEAN, addr="AAA1111111111111111111111111111111111111111",
                               pair="pA"), rt=RT_OK, shadows=False)
b, _ = paperv3.open_entry(dict(CLEAN, addr="BBB2222222222222222222222222222222222222222",
                               pair="pB"), rt=RT_OK, shadows=False)
ok, idx, msg = paperv3.verify()
check("a clean chain verifies", ok, msg)
check("seq increments", a["seq"] == 0 and b["seq"] == 1)
check("b chains to a", b["prev"] == a["hash"])

rows = [json.loads(l) for l in io.open(paperv3.LEDGER, encoding="utf-8")]
rows[0]["usd_in"] = 999999.0
with io.open(paperv3.LEDGER, "w", encoding="utf-8") as f:
    for r in rows:
        f.write(json.dumps(r, sort_keys=True) + "\n")
ok2, _, msg2 = paperv3.verify()
check("⛔ editing a row in place is CAUGHT", not ok2, msg2[:60])
check("and named as an in-place edit", "EDITED IN PLACE" in msg2)

fresh()
s = paperv3.summary()
check("summary refuses a headline below MIN_N", s["median_realizable_multiple"] is None)
check("and says how far short it is", "need 30" in s["verdict"], s["verdict"])
check("MIN_N is 30 distinct CONTRACTS, not rows", paperv3.MIN_N == 30)
check("the epoch is pinned", paperv3.EPOCH == "2026-09-17")

print()
print("=" * 70)
print("6. the shipped constants match PRECOMMIT_paper_v3.md exactly")
print("=" * 70)

spec = io.open(os.path.join(HERE, "PRECOMMIT_paper_v3.md"), encoding="utf-8").read()
for label, val in (("NOTIONAL_USD", "100.0"), ("TARGET_MULT", "2.0"),
                   ("MAX_HOLD_H", "24.0"), ("MIN_HOLDERS", "100"),
                   ("MIN_N", "30")):
    check(f"the pre-commit still states {label} {val}",
          label in spec and val.rstrip("0").rstrip(".") in spec)
check("SIZES_RECORDED matches the pre-commit",
      paperv3.SIZES_RECORDED == (100, 250, 500))
check("SIZE_TRADED is 100 - Frank's real clip", paperv3.SIZE_TRADED == 100)
check("ENTRY_VERDICT is TRADEABLE", paperv3.ENTRY_VERDICT == "TRADEABLE")
check("the degraded set is the three the pre-commit names",
      set(paperv3.DEGRADED) == {"TOTAL_LOSS", "NO_SELL_ROUTE", "NO_BUY_ROUTE"})

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
