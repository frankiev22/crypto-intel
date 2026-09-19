"""A crossing carries the depth measured AT the crossing. Run: python test_crossingdepth.py

⛔ The site verified 0 of 12 mcap crossings because the claim row had no depth
and the only join available was a scanner reading 7.8-16.7 hours older than the
crossing. Two fixes, both checked here on their OUTPUT:

  1. forward - journal.record_outcome() writes the same exit depth onto the
     claim that it writes onto the outcome row. Asserted by calling it and
     reading both files back, not by reading the source.
  2. history - crossingdepth.recover() re-links claims to the outcome row that
     made them, refuses to guess when two rows disagree, and never rewrites.
"""
import json
import os
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
testsandbox.activate()

# ⛔ _push() posts to Supabase when these are set. A test must never write to
# the real mirror, so they are removed before journal is exercised.
for _k in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "CRYPTO_JOURNAL_SECRET"):
    os.environ.pop(_k, None)

import crossingdepth as CD
import journal
import milestones

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def rows(path):
    if not os.path.exists(path):
        return []
    with open(path, encoding="utf-8") as f:
        return [json.loads(l) for l in f if l.strip()]


def ledger_rows():
    out = []
    for n in sorted(os.listdir(milestones.DIR)):
        if n.endswith(".jsonl"):
            out += rows(os.path.join(milestones.DIR, n))
    return out


print("=" * 70)
print("1. ⭐ forward: the claim carries the SAME depth as the outcome row")
print("=" * 70)

TOK = "TestMintForCrossingDepth1111111111111111pump"
st, mult, ok, failed = journal.record_outcome(
    "TestPairAddr1111111111111111111111111111111", time.time() - 3700, 1,
    price=2.0, liq=60000.0, vol24=5000.0, base_price=1.0, base_liq=50000.0,
    symbol="TST", token=TOK, exit_depth=12345.0,
    exit_pair="TestPairAddr1111111111111111111111111111111",
    sells_h24=40, buys_h24=60, mcap=250000.0)
out = [r for n in sorted(os.listdir(journal.OUT)) if n.endswith(".jsonl")
       for r in rows(os.path.join(journal.OUT, n)) if r.get("token") == TOK]
claims = [r for r in ledger_rows() if r.get("token") == TOK and r.get("kind") == "mcap"]
check("the outcome row was written", len(out) == 1, f"{len(out)} rows")
check("mcap_100k and mcap_200k were claimed from a $250k mcap",
      sorted(c["milestone"] for c in claims) == ["mcap_100k", "mcap_200k"],
      [c["milestone"] for c in claims])
o = out[0] if out else {}
for c in claims:
    check(f"{c['milestone']}: exit_depth_at_crossing == the outcome row's exit_depth_usd",
          c.get("exit_depth_at_crossing") == o.get("exit_depth_usd") == 12345.0,
          f"{c.get('exit_depth_at_crossing')} vs {o.get('exit_depth_usd')}")
    check(f"{c['milestone']}: realizable and depth_unmeasured match the row",
          c.get("realizable_at_crossing") == o.get("realizable")
          and c.get("depth_unmeasured_at_crossing") == o.get("depth_unmeasured"))
    check(f"{c['milestone']}: it names the measurement it came from",
          c.get("outcome_checked_ts") == o.get("checked_ts")
          and c.get("horizon_h") == 1 and c.get("exit_pair_at_crossing") == o.get("exit_pair"))
    check(f"{c['milestone']}: ⭐ crossed_ts IS that measurement's time, so depth is at the crossing",
          c["crossed_ts"] == o["checked_ts"], c["crossed_ts"] - o["checked_ts"])
    check(f"{c['milestone']}: the write time is kept separately, never before the crossing",
          c.get("claimed_ts") is not None and 0 <= c["claimed_ts"] - c["crossed_ts"] <= 2,
          c.get("claimed_ts"))

check("a claim with no measurement behind it (graduation) is stamped at write time",
      milestones.claim("TestMintNoCheck33333333333333333333333333pump", "graduated", kind="graduation")
      and next(r for r in ledger_rows() if r.get("token", "").startswith("TestMintNoCheck"))["crossed_ts"]
      == next(r for r in ledger_rows() if r.get("token", "").startswith("TestMintNoCheck"))["claimed_ts"])
check("⛔ a future outcome_checked_ts cannot date a crossing after it was written",
      milestones.claim("TestMintFuture4444444444444444444444444pump", "mcap_100k", kind="mcap",
                       outcome_checked_ts=int(time.time()) + 3600)
      and next(r for r in ledger_rows() if r.get("token", "").startswith("TestMintFuture"))["crossed_ts"]
      <= next(r for r in ledger_rows() if r.get("token", "").startswith("TestMintFuture"))["claimed_ts"])

print()
print("=" * 70)
print("2. ⛔ unknown depth stays unknown on the claim")
print("=" * 70)
TOK2 = "TestMintNoDepth22222222222222222222222222pump"
journal.record_outcome("TestPairAddr2", time.time() - 3700, 1, price=2.0, liq=60000.0,
                       vol24=5000.0, base_price=1.0, base_liq=50000.0, symbol="ND",
                       token=TOK2, exit_depth=None, exit_pair="TestPairAddr2",
                       mcap=150000.0)
c2 = [r for r in ledger_rows() if r.get("token") == TOK2 and r.get("kind") == "mcap"]
check("a crossing with no depth reading was still claimed", len(c2) == 1, len(c2))
check("⛔ and its depth is None, not 0",
      c2 and "exit_depth_at_crossing" in c2[0] and c2[0]["exit_depth_at_crossing"] is None,
      c2[0].get("exit_depth_at_crossing") if c2 else "no claim")

print()
print("=" * 70)
print("3. history: recover() re-links, refuses to guess, never rewrites")
print("=" * 70)
d = tempfile.mkdtemp(prefix="crossdepth-")
ms, oc = os.path.join(d, "ms"), os.path.join(d, "oc")
os.makedirs(ms)
os.makedirs(oc)
dest = os.path.join(ms, "depth_at_crossing.jsonl")
T = 1789000000                                   # 2026-09-10, after the epoch
with open(os.path.join(ms, "2026-09.jsonl"), "w", encoding="utf-8") as f:
    for r in ({"token": "A", "milestone": "mcap_1m", "kind": "mcap", "crossed_ts": T + 1},
              {"token": "B", "milestone": "mcap_1m", "kind": "mcap", "crossed_ts": T + 1},
              {"token": "C", "milestone": "mcap_1m", "kind": "mcap", "crossed_ts": T},
              {"token": "D", "milestone": "mcap_1m", "kind": "mcap", "crossed_ts": 1788000000},
              {"token": "E", "milestone": "mcap_1m", "kind": "mcap", "crossed_ts": T,
               "exit_depth_at_crossing": 9.0},
              {"token": "F", "milestone": "graduated", "kind": "graduation", "crossed_ts": T}):
        f.write(json.dumps(r) + "\n")
with open(os.path.join(oc, "2026-09-10.jsonl"), "w", encoding="utf-8") as f:
    for r in ({"token": "A", "checked_ts": T, "exit_depth_usd": 777.0, "realizable": True,
               "depth_unmeasured": False, "exit_pair": "pa", "horizon_h": 6},
              {"token": "A", "checked_ts": T - 3600, "exit_depth_usd": 5.0},
              {"token": "B", "checked_ts": T, "exit_depth_usd": 1.0, "exit_pair": "x"},
              {"token": "B", "checked_ts": T, "exit_depth_usd": 2.0, "exit_pair": "y"},
              {"token": "C", "checked_ts": T - 60, "exit_depth_usd": 3.0}):
        f.write(json.dumps(r) + "\n")
rep = CD.recover(ms_dir=ms, out_dir=oc, dest=dest)
got = {r["token"]: r for r in rows(dest)}
check("A is recovered from the row in its claiming second, not the older one",
      got.get("A", {}).get("exit_depth_at_crossing") == 777.0
      and got["A"]["delta_s"] == 1 and got["A"]["provenance"] == "recovered", got.get("A"))
check("⛔ B has two rows in the claiming second that disagree - not guessed",
      "B" not in got and rep.get("ambiguous") == 1, rep)
check("C's only row is 60s early - outside one function call, not recovered",
      "C" not in got and rep.get("no_measurement_at_crossing") == 1, rep)
check("D is a pre-epoch replay and is not even considered",
      "D" not in got and rep.get("claims_considered") == 4, rep.get("claims_considered"))
check("E already carries its depth (a forward claim) and is left alone",
      "E" not in got and rep.get("carries_it_already") == 1)
check("F is a graduation - it has its own depth and is out of scope", "F" not in got)
rep2 = CD.recover(ms_dir=ms, out_dir=oc, dest=dest)
check("⭐ a second run appends nothing - append-only, idempotent",
      len(rows(dest)) == 1 and rep2.get("already_recovered") == 1 and not rep2.get("recovered"),
      rep2)
check("the recovered file keys on the contract, never the symbol",
      all("token" in r and "symbol" not in r for r in rows(dest)))

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
