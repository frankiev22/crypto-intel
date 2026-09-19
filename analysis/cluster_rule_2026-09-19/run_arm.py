"""Price one arm of PRECOMMIT_cluster_rule.md from chain.

usage: python run_arm.py <arm> <input.json> <output.jsonl>
input: [{"token","pair","T", ...sample fields}]  T = the moment the arm starts
(arm B: our first sighting; arm D: the fire).

Per token: entry = the first swap on OUR pool after T (within 6h); if the pool
never swaps in that window, entry = its state at T and `dead_after_T` is set
(the multiple is then 1.0 by construction - a non-win, reported both ways).
Outcomes at entry +6h and +24h: price from the last swap, depth from the latest
transaction touching the quote vault. Resumable: skips tokens already written.
"""
import json
import os
import statistics
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor

import cluster_chain as C

ARM, INP, OUT = sys.argv[1], sys.argv[2], sys.argv[3]
REPO = r"C:\Users\Frankie\Desktop\Projects\crypto-intel"

# SOL/USD by hour, from our own observation rows (price_usd / price_native on
# SOL-quoted pairs; the median of each hour discards the USDC-quoted ones).
_sol = {}
for fn in sorted(os.listdir(os.path.join(REPO, "data", "observations"))):
    if not fn.startswith("2026-09"):
        continue
    for line in open(os.path.join(REPO, "data", "observations", fn), encoding="utf-8"):
        try:
            r = json.loads(line)
            pu, pn = float(r.get("price_usd") or 0), float(r.get("price_native") or 0)
        except Exception:
            continue
        if pu > 0 and pn > 0 and 20 < pu / pn < 2000:
            _sol.setdefault(int(r["ts"]) // 3600, []).append(pu / pn)
SOLH = {h: statistics.median(v) for h, v in _sol.items() if len(v) >= 3}


def sol_usd(t):
    h = int(t) // 3600
    for d in range(0, 48):
        for k in (h - d, h + d):
            if k in SOLH:
                return SOLH[k]
    return None


def usd(qmint, amount, t):
    if amount is None:
        return None
    if qmint in (C.USDC, C.USDT):
        return amount
    s = sol_usd(t)
    return None if s is None else amount * s


done = set()
if os.path.exists(OUT):
    done = {json.loads(l)["token"] for l in open(OUT, encoding="utf-8")}
items = [x for x in json.load(open(INP, encoding="utf-8")) if x["token"] not in done]
lock = threading.Lock()
t_start = time.time()
count = {"n": 0}


def one(x):
    pool, token, T = x["pair"], x["token"], int(x["T"])
    rec = {"arm": ARM, "token": token, "pair": pool, "T": T, "dex_id": x.get("dex_id"),
           "pool_owner": x.get("pool_owner")}
    try:
        newest = C.rpc("getSignaturesForAddress", [pool, {"limit": 10}]) or []
        v = C.vaults(pool, token, [s["signature"] for s in newest])
        if not v:
            a, _ = C.anchor_sig(T + 3600)
            near = C.sigs_before(pool, a, limit=10)
            v = C.vaults(pool, token, [s["signature"] for s in near])
        if not v:
            rec["status"] = "unpriced: no SOL/USDC/USDT vault pair found in the pool's own data"
            return rec
        base_v, quote_v, qmint = v
        rec["quote_mint"] = qmint
        e = C.first_swap_after(pool, base_v, quote_v, T, max_window=6 * 3600)
        if e:
            entry_ts, entry_px = e["ts"], e["price"]
            rec.update(entry_sig=e["sig"], entry_ts=entry_ts, entry_delay_s=entry_ts - T,
                       dead_after_T=False)
        else:
            st = C.state_at(pool, base_v, quote_v, T, T - 30 * 86400)
            if st["price"] is None:
                rec["status"] = "unpriced: no swap found before or after T"
                return rec
            entry_ts, entry_px = T, st["price"]
            rec.update(entry_ts=T, entry_delay_s=None, dead_after_T=True)
        rec["entry_price"] = entry_px
        for h in (6, 24):
            if entry_ts + h * 3600 > time.time() - 120:
                rec[f"x{h}"] = rec[f"quote{h}"] = rec[f"depth{h}_usd"] = rec[f"last_tx{h}_ts"] = None
                rec[f"h{h}_not_elapsed"] = True
                continue
            st = C.state_at(pool, base_v, quote_v, entry_ts + h * 3600, entry_ts)
            px = st["price"]
            rec[f"x{h}"] = None if px is None else px / entry_px
            rec[f"quote{h}"] = st["quote"]
            rec[f"depth{h}_usd"] = usd(qmint, st["quote"], entry_ts + h * 3600)
            rec[f"last_tx{h}_ts"] = st["last_tx_ts"]
        rec["status"] = "priced"
    except Exception as ex:
        rec["status"] = f"error: {repr(ex)[:160]}"
    return rec


def run(x):
    r = one(x)
    with lock:
        with open(OUT, "a", encoding="utf-8") as f:
            f.write(json.dumps(r) + "\n")
        count["n"] += 1
        if count["n"] % 20 == 0:
            print(f"{count['n']}/{len(items)} done, {C.CALLS['n']} calls, "
                  f"{time.time() - t_start:.0f}s", flush=True)


with ThreadPoolExecutor(max_workers=3) as ex:
    list(ex.map(run, items))
print(f"finished {count['n']} tokens, {C.CALLS['n']} calls, {time.time() - t_start:.0f}s")
