"""Does "gone" mean the pool stopped existing? Ask the chain, not the indexer.

Frank, 2026-09-22: "How are the pools no longer existing? That seems impossible
to me."

He is right to push. `journal.record_outcome` sets status="gone" when `liq is
None`, and `liq` is None when the Dexscreener pair lookup returned nothing AND
the token-level fallback also returned nothing. Neither of those is a chain
read. Four different states collapse into one label:

  a. the pool account is closed on chain
  b. the pool account exists with near-zero reserves
  c. the pool is fine and the indexer simply did not return it
  d. we asked about the wrong pool address

This samples "gone" rows at random (seeded) and asks, per contract:
  - does the recorded pair account still exist on chain, and who owns it
  - what is in its vaults right now
  - can Jupiter still sell $100 of the token (venue-agnostic realizability)

Pre-committed before running: I expect (b) to dominate. If (c) is material -
pools with real money that our label called gone - then the label is wrong in
the direction Frank suspects and every rate computed on it needs redoing.
"""
import io
import json
import glob
import os
import random
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import chainfields  # noqa: E402
import onchain_reserves  # noqa: E402
from pool_probe import PROGRAMS, QUOTES, WSOL, TOKEN, TOKEN22, SYSTEM  # noqa: E402

N = int(sys.argv[1]) if len(sys.argv) > 1 else 60
SEED = 20260922

cut = time.time() - 86400
rows = []
for p in sorted(glob.glob(os.path.join(ROOT, "data/outcomes/2026-09-2*.jsonl"))):
    for l in io.open(p, encoding="utf-8"):
        o = json.loads(l)
        if (o.get("checked_ts") or 0) >= cut and o.get("status") == "gone" and o.get("pair"):
            rows.append(o)
by_tok = {}
for o in rows:
    by_tok.setdefault(o["token"], o)
pool = sorted(by_tok.values(), key=lambda o: o["token"])
random.Random(SEED).shuffle(pool)
sample = pool[:N]
print(f"{len(rows)} gone rows in 24h on {len(by_tok)} distinct contracts; sampling {len(sample)}")

sol = None
st, b = chainfields._get("https://lite-api.jup.ag/price/v3?ids=" + WSOL)
try:
    sol = float(b[WSOL]["usdPrice"])
except Exception:
    sol = None
print("SOL", sol)

out = []
for i, o in enumerate(sample):
    tok, pair = o["token"], o["pair"]
    r = {"token": tok, "pair": pair, "symbol": o.get("symbol"), "horizon_h": o.get("horizon_h"),
         "reasons": o.get("reasons")}
    res, err = chainfields._rpc("getAccountInfo", [pair, {"encoding": "base64",
                                                          "dataSlice": {"offset": 0, "length": 0}}])
    v = (res or {}).get("value") if res else None
    r["pair_account_exists"] = bool(v) if res is not None else None
    r["pair_owner"] = PROGRAMS.get((v or {}).get("owner"), (v or {}).get("owner")) if v else None
    if v:
        vaults, verr = onchain_reserves.vaults(pair)
        r["vault_error"] = verr
        q = {m: a for m, a in (vaults or {}).items() if m in QUOTES}
        r["quote_ui"] = sum(q.values()) if q else None
        r["quote_mints"] = [QUOTES[m] for m in q]
        r["quote_usd"] = (sum(a * (sol or 0) if m == WSOL else a for m, a in q.items())
                          if q and sol else None)
        r["base_ui"] = (vaults or {}).get(tok)
    rt = chainfields.round_trip(tok, 100)
    r["jup_verdict"] = rt.get("verdict")
    r["jup_usd_back"] = rt.get("usd_back")
    # the four states, decided from what we just read
    if r["pair_account_exists"] is False:
        r["state"] = "a: pool account CLOSED on chain"
    elif r.get("quote_usd") is not None and r["quote_usd"] >= 1000:
        r["state"] = "c: pool ALIVE with real money, indexer dropped it"
    elif r.get("quote_usd") is not None and r["quote_usd"] >= 10:
        r["state"] = "c-minor: pool holds $10-$1000, indexer dropped it"
    elif r["pair_account_exists"]:
        r["state"] = "b: pool exists, near-zero reserves"
    else:
        r["state"] = "unread"
    out.append(r)
    if (i + 1) % 10 == 0:
        print(f"  {i+1}/{len(sample)}")
    json.dump(out, io.open(os.path.join(HERE, "gone_audit.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, default=str)

from collections import Counter  # noqa: E402
c = Counter(r["state"] for r in out)
j = Counter(r["jup_verdict"] for r in out)
print("\nSTATES:", json.dumps(dict(c), indent=1))
print("JUPITER:", json.dumps(dict(j), indent=1))
alive = [r for r in out if r["state"].startswith("c")]
print(f"\n{len(alive)} of {len(out)} labelled gone still hold quote-side money:")
for r in sorted(alive, key=lambda r: -(r.get("quote_usd") or 0))[:15]:
    print(" ", r["token"], r["symbol"], f"${r.get('quote_usd'):,.0f}" if r.get("quote_usd") else None,
          r["jup_verdict"], r.get("jup_usd_back"))
