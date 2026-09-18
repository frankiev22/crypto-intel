"""Inferred total-loss labels must never manufacture a win.

26 of the first 40 paper closes were `unpriceable`: the pool was delisted
before the 24h hold expired. Their last witness says 15 rugged, 5 dead, 4
alive, median last-known liquidity $0. Those are losses we declined to label,
not unknown outcomes.

The trap, and the only reason this needs tests: the last-known MULTIPLE on
those positions has a median of 0.967x and 8 of 24 printed >= 2x - on pools
holding $0. Adopting them moves the >=2x rate from 21% to 29%. That is the
rug-that-pumps-on-the-way-out shape, and it has fooled this project five
times. A label must assert zero from LIQUIDITY and never read a price off a
corpse.

Run: python test_labels.py    (offline, sandboxed, writes to a temp ledger)
"""
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

import paper

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"   <- {detail}" if detail and not cond else ""))


# A sandboxed ledger with one unpriceable close per witness shape.
paper.LEDGER = os.path.join(tempfile.mkdtemp(), "ledger.jsonl")

WITNESS = {}


def fake_witness(entry):
    return WITNESS.get(entry.get("contract"))


paper._witness = fake_witness

CASES = [
    # contract, symbol, witness status, witness liq, last-known price
    ("DEADaaa1111111111111111111111111111111111111", "DEADRUG", "rugged", 0.0, 9.99),
    ("DEADbbb2222222222222222222222222222222222222", "DEADDED", "dead", 0.74, 0.5),
    ("ALIVEcc3333333333333333333333333333333333333", "STILLUP", "alive", 0.0, 1.0),
    ("RICHddd4444444444444444444444444444444444444", "HASLIQ", "rugged", 1425.04, 1.0),
    ("NOWITee5555555555555555555555555555555555555", "NOWIT", None, None, None),
]
for ca, sym, status, liq, px in CASES:
    e = paper.open_entry(ca, symbol=sym, price=1.0, exit_depth=5000, liq=1, fdv=1,
                         score=80, venue_type="amm", dex_id="t", pair="p" + sym)
    paper.close_entry(e["hash"], price=None, exit_depth=None,
                      reason=paper.CLOSE_UNPRICEABLE + ": source dropped the pair")
    if status is not None:
        # A last-known price far above entry is the whole point: it must be
        # recorded as evidence and never adopted as the outcome.
        WITNESS[ca] = {"status": status, "liq": liq, "price_usd": px,
                       "checked_ts": 1788000000, "horizon_h": 24,
                       "actual_elapsed_h": 24.1}

print("=" * 70)
print("1. only unambiguously dead positions get labelled")
print("=" * 70)
made, skipped = paper.label_unpriceable(dry_run=False, verbose=False)
by = {r["symbol"]: r for r in made}
check("a rugged pool at $0 is labelled", "DEADRUG" in by)
check("a dead pool at $0.74 is labelled", "DEADDED" in by)
check("an ALIVE pool is NOT labelled", "STILLUP" not in by)
check("a rugged pool still holding $1,425 is NOT labelled", "HASLIQ" not in by)
check("a position with no witness is NOT labelled", "NOWIT" not in by)
check("2 labelled, 3 left unpriceable", len(made) == 2 and len(skipped) == 3,
      f"{len(made)} / {len(skipped)}")

print()
print("=" * 70)
print("2. THE TRAP: the last-known multiple is never adopted")
print("=" * 70)
r = by["DEADRUG"]
check("mult_effective is exactly 0.0", r["mult_effective"] == 0.0, str(r["mult_effective"]))
check("multiple_adopted is null, explicitly", r["multiple_adopted"] is None)
check("the 9.99x last price is recorded as EVIDENCE", r["witness_price_usd"] == 9.99)
check("...but never becomes the outcome",
      r["mult_effective"] == 0.0 and r["witness_price_usd"] == 9.99)
s_inc = paper.summary(include_inferred=True)
check("including inferred cannot add a win", s_inc["wins"] == 0, str(s_inc["wins"]))
check("including inferred lowers the median, never raises it",
      s_inc["median_mult"] == 0.0, str(s_inc.get("median_mult")))

print()
print("=" * 70)
print("3. provenance survives, and the chain is intact")
print("=" * 70)
check("labelled as inferred, not measured", r["label"] == paper.LABEL_INFERRED_LOSS)
check("inferred flag is set", r["inferred"] is True)
check("the witness timestamp is recorded", r["witness_checked_ts"] == 1788000000)
check("the criteria used are recorded on the row",
      r["criteria"]["max_liq_usd"] == paper.DEAD_LIQ_USD)
check("the basis says it was inferred, not measured", "INFERRED" in r["basis"])
check("no exit row was edited - labels are their own type",
      all(x.get("type") != "label" or "exit_id" in x for x in paper._read()))
exits = [x for x in paper._read() if x.get("type") == "exit"]
check("every exit still has mult=None (untouched)",
      all(x.get("mult") is None for x in exits))
ok, _, msg = paper.verify()
check("the hash chain still verifies", ok, msg[:60])

print()
print("=" * 70)
print("4. reporting both ways, and idempotence")
print("=" * 70)
a = paper.summary(include_inferred=False)
b = paper.summary(include_inferred=True)
check("measured-only n excludes inferred", a["n"] == 0, str(a["n"]))
check("inferred view adds exactly the 2 labelled", b["n"] == a["n"] + 2, str(b["n"]))
check("both report their basis", a["basis"] == "measured only"
      and b["basis"] == "measured + inferred")
check("unlabelled unpriceable are still counted separately",
      b["unpriceable_unlabelled"] == 3, str(b["unpriceable_unlabelled"]))
again, _ = paper.label_unpriceable(dry_run=False, verbose=False)
check("re-running labels nothing twice", len(again) == 0, str(len(again)))
check("and the chain still verifies", paper.verify()[0])

print()
bad = [x for x in R if not x[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
