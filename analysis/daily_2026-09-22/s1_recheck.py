"""Section 1: re-check recorded multiples against live Dexscreener.

Method pre-committed in PRECOMMIT.md before this ran. One call per contract,
never batched. Writes s1_results.json beside this file.
"""
import io
import json
import math
import os
import random
import subprocess
import sys
import time

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
os.chdir(ROOT)
sys.path.insert(0, ROOT)
import sources  # noqa: E402

RUN_TS = float(sys.argv[1]) if len(sys.argv) > 1 else time.time()

seen = {}
for p in ("data/outcomes/2026-09-21.jsonl", "data/outcomes/2026-09-22.jsonl"):
    texts = []
    try:
        texts.append(io.open(p, encoding="utf-8").read())
    except FileNotFoundError:
        pass
    r = subprocess.run(["git", "show", f"origin/master:{p}"], capture_output=True)
    if r.returncode == 0:
        texts.append(r.stdout.decode("utf-8"))
    for t in texts:
        for l in t.splitlines():
            if l.strip():
                seen[l.strip()] = 1
rows = []
for l in seen:
    try:
        rows.append(json.loads(l))
    except ValueError:
        pass
win = [o for o in rows if RUN_TS - 86400 <= (o.get("checked_ts") or 0) <= RUN_TS
       and o.get("token") and o.get("mult")]

big = [o for o in win if o["mult"] >= 2.0]
big_toks = sorted({o["token"] for o in big})
rest = sorted({o["token"] for o in win} - set(big_toks))
rng = random.Random(20260922)
rand_toks = rng.sample(rest, min(60, len(rest)))
rand_rows = [o for o in win if o["token"] in set(rand_toks)]
print(f"window rows with mult {len(win)}; >=2x rows {len(big)} on {len(big_toks)} "
      f"contracts; random {len(rand_toks)} contracts ({len(rand_rows)} rows)")

live = {}
t0 = time.time()
for i, tok in enumerate(big_toks + rand_toks):
    try:
        live[tok] = {"pairs": sources.dexscreener_token(tok), "ts": time.time(), "err": None}
    except Exception as e:
        live[tok] = {"pairs": [], "ts": time.time(), "err": f"{type(e).__name__}: {e}"}
    time.sleep(0.3)
    if (i + 1) % 50 == 0:
        print(f"  {i + 1} calls, {time.time() - t0:.0f}s")
print(f"{len(live)} calls in {time.time() - t0:.0f}s, "
      f"{sum(1 for v in live.values() if v['err'])} errors")


def qside(p):
    liq = p.get("liquidity") or {}
    q = liq.get("quote")
    try:
        pn = float(p.get("priceNative") or 0)
    except ValueError:
        pn = 0
    return float(q or 0), pn


def judge(o):
    L = live.get(o["token"]) or {}
    pairs = L.get("pairs") or []
    want = o.get("exit_pair") or o.get("pair")
    rec = next((p for p in pairs if p.get("pairAddress") == want), None)
    out = {"token": o["token"], "symbol": o.get("symbol"), "horizon_h": o.get("horizon_h"),
           "recorded_mult": o["mult"], "realizable": bool(o.get("realizable")),
           "pair": want, "checked_ts": o.get("checked_ts"),
           "elapsed_since_check_h": round(((L.get("ts") or RUN_TS) - (o.get("checked_ts") or 0)) / 3600, 2),
           "api_error": L.get("err"), "n_pairs_live": len(pairs)}
    if not pairs:
        out["verdict"] = "no_pairs_live"
        return out
    if rec is None:
        out["verdict"] = "pair_not_found"
        return out
    _, pn = qside(rec)
    base = o.get("base_price_native")
    if not base or not pn:
        out["verdict"] = "no_native_price"
        return out
    lm = pn / base
    ratio = lm / o["mult"]
    out.update(live_mult=lm, ratio=ratio, log_ratio=math.log(ratio))
    out["verdict"] = ("OVERSTATED" if ratio < 0.5 else "UNDERSTATED" if ratio > 2.0 else "agrees")
    # measurement-error signature: recorded pair vs the deepest same-quote pool, now
    qa = (rec.get("quoteToken") or {}).get("address")
    same = [p for p in pairs if (p.get("quoteToken") or {}).get("address") == qa]
    deep = max(same, key=lambda p: qside(p)[0]) if same else None
    if deep is not None and deep.get("pairAddress") != rec.get("pairAddress"):
        dq, dpn = qside(deep)
        if dpn:
            pr = pn / dpn
            out.update(deepest_pair=deep.get("pairAddress"), deepest_quote_liq=dq,
                       recorded_vs_deepest=pr,
                       measurement_error=(pr > 2.0 or pr < 0.5))
    out.setdefault("measurement_error", False)
    return out


res = {"big": [judge(o) for o in big], "random": [judge(o) for o in rand_rows],
       "run_ts": RUN_TS, "calls": len(live)}
json.dump(res, io.open(os.path.join(HERE, "s1_results.json"), "w", encoding="utf-8"),
          ensure_ascii=False, indent=1, default=str)
print("written s1_results.json")
