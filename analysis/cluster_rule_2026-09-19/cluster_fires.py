"""Arm D fires from degentape's tape, per PRECOMMIT_cluster_rule.md (declared 19:09Z).

A fire: a tracked-wallet buy landing such that the buys of the preceding 10
minutes (inclusive) come from >= 3 distinct wallets (`solana`) and sum to
>= $1,500. Writes armD_input.json: sample tokens whose first fire falls in
[first sighting, first sighting + 2h], with T = the fire.
Also reports how many sample tokens degentape's wallets touched at all.
"""
import collections
import json
import os

HERE = os.path.dirname(os.path.abspath(__file__))
tape = [json.loads(l) for l in open(os.path.join(HERE, "degentape", "tape_sol_0912.jsonl"), encoding="utf-8")]
samp = json.load(open(os.path.join(HERE, "cluster_sample.json")))
S = {s["token"]: s for s in samp}

buys = collections.defaultdict(list)
touched = collections.defaultdict(int)
for r in tape:
    if r.get("token") in S:
        touched[r["token"]] += 1
    if r.get("side") == "buy" and r.get("usd") is not None and r.get("solana") and r.get("ts"):
        buys[r["token"]].append((int(r["ts"]), r["solana"], float(r["usd"])))

def fires(rows):
    rows.sort()
    out = []
    j = 0
    for i, (t, w, u) in enumerate(rows):
        while rows[j][0] < t - 600:
            j += 1
        win = rows[j:i + 1]
        if len({x[1] for x in win}) >= 3 and sum(x[2] for x in win) >= 1500:
            out.append((t, len({x[1] for x in win}), round(sum(x[2] for x in win), 2)))
    return out

all_fire_tokens = 0
armD, before_only, after_window = [], 0, 0
for tok, rows in buys.items():
    f = fires(rows)
    if not f:
        continue
    all_fire_tokens += 1
    if tok not in S:
        continue
    t0 = int(S[tok]["ts"])
    inwin = [x for x in f if t0 <= x[0] <= t0 + 7200]
    if inwin:
        t, nw, usd = inwin[0]
        d = dict(S[tok]); d.update(T=t, fire_wallets=nw, fire_usd=usd, fire_delay_s=t - t0)
        armD.append(d)
    elif any(x[0] < t0 for x in f):
        before_only += 1
    else:
        after_window += 1

tmin = min(int(r["ts"]) for r in tape); tmax = max(int(r["ts"]) for r in tape)
print(f"tape rows {len(tape)}, ts {tmin} .. {tmax}")
print(f"tokens with any fire anywhere on the tape: {all_fire_tokens}")
print(f"sample tokens (409) touched by any tracked-wallet fill: {len(touched)}")
print(f"sample tokens with a buy by a tracked wallet: {sum(1 for t in S if t in buys)}")
print(f"ARM D: sample tokens whose first fire is in [sighting, +2h]: {len(armD)}")
print(f"   fired only before our sighting: {before_only}; fired only later than +2h: {after_window}")
json.dump(armD, open(os.path.join(HERE, "armD_input.json"), "w"))
