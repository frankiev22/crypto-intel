"""Rebuild degentape's closed Solana positions from its own tape, 09-12 onward.

Their rule, inferred and checked on 16 wallets by the assessment agent: one
wallet's position in one token opens at a buy and closes when that wallet's
sells cover its buys (token amount). Win = proceeds > cost.

We re-derive THEIR rate from THEIR fills (the fills themselves verified on chain,
182/182 sampled), then score the same closed trades on OUR definition: realized
proceeds / cost >= 2.0.

Exclusions, all counted: pairs whose first fill is a sell or before 09-12 00:00Z
(opened before the window); positions with a fill lacking usd; positions with a
fill over $5M (their data holds fills priced at 1e26); positions still open.
"""
import collections
import datetime as dt
import json
import math
import os

HERE = os.path.dirname(os.path.abspath(__file__))
START = int(dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc).timestamp())
tape = [json.loads(l) for l in open(os.path.join(HERE, "degentape", "tape_sol_0912.jsonl"), encoding="utf-8")]


def wilson(k, n, z=1.96):
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return round(max(0, c - h), 4), round(min(1, c + h), 4)


fills = collections.defaultdict(list)
for r in tape:
    if r.get("solana") and r.get("token") and r.get("side") in ("buy", "sell") and not r.get("is_stock"):
        fills[(r["solana"], r["token"])].append(r)

ex = collections.Counter()
closed = []
for key, fs in fills.items():
    fs.sort(key=lambda r: (r["ts"], r["id"]))
    if fs[0]["side"] == "sell" or fs[0]["ts"] < START:
        ex["opened before the window (first fill a sell, or before 09-12)"] += 1
        continue
    pos = None
    for r in fs:
        if pos is None:
            if r["side"] != "buy":
                continue  # a stray sell after a close: not a new position
            pos = {"bq": 0.0, "sq": 0.0, "cost": 0.0, "proc": 0.0, "bad": None, "open": r["ts"]}
        amt = float(r.get("token_amt") or 0)
        u = r.get("usd")
        if u is None:
            pos["bad"] = "a fill without usd"
        elif float(u) > 5e6:
            pos["bad"] = "a fill over $5M (mispriced)"
        if r["side"] == "buy":
            pos["bq"] += amt
            pos["cost"] += float(u or 0)
        else:
            pos["sq"] += amt
            pos["proc"] += float(u or 0)
        if pos["bq"] > 0 and pos["sq"] >= pos["bq"] * (1 - 1e-6):
            if pos["bad"]:
                ex[f"excluded: {pos['bad']}"] += 1
            elif pos["cost"] <= 0:
                ex["excluded: zero cost"] += 1
            else:
                closed.append({"wallet": key[0], "token": key[1], "cost": pos["cost"],
                               "proc": pos["proc"], "open": pos["open"], "close": r["ts"]})
            pos = None
    if pos is not None:
        ex["still open at the end of the tape"] += 1

n = len(closed)
w = sum(1 for c in closed if c["proc"] > c["cost"])
x2 = sum(1 for c in closed if c["proc"] >= 2 * c["cost"])
mult = sorted(c["proc"] / c["cost"] for c in closed)
tok = {c["token"] for c in closed}
print(f"tape rows {len(tape)}; wallet-token pairs {len(fills)}")
print(f"closed positions rebuilt: {n} ({len({c['wallet'] for c in closed})} wallets, {len(tok)} tokens)")
for k, v in ex.most_common():
    print(f"   {k}: {v}")
print(f"THEIR definition (proceeds > cost): {w}/{n} = {w/n:.4f} {wilson(w, n)}")
print(f"OUR definition (proceeds >= 2x cost): {x2}/{n} = {x2/n:.4f} {wilson(x2, n)}")
print("realized multiple p10/p25/median/p75/p90:",
      [round(mult[int(f * (n - 1))], 3) for f in (0.1, 0.25, 0.5, 0.75, 0.9)])
# by distinct token: first closed position per token, so one busy token cannot dominate
first = {}
for c in sorted(closed, key=lambda c: c["close"]):
    first.setdefault(c["token"], c)
fx2 = sum(1 for c in first.values() if c["proc"] >= 2 * c["cost"])
fw = sum(1 for c in first.values() if c["proc"] > c["cost"])
print(f"per distinct token (first close each): profit {fw}/{len(first)} {wilson(fw, len(first))}, "
      f">=2x {fx2}/{len(first)} {wilson(fx2, len(first))}")
hold = sorted((c["close"] - c["open"]) / 60 for c in closed)
print("hold minutes p25/median/p75:", [round(hold[int(f * (n - 1))], 1) for f in (0.25, 0.5, 0.75)])
json.dump(closed, open(os.path.join(HERE, "degentape", "closed_rebuilt.json"), "w"))
