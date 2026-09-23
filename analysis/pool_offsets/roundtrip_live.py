"""The only measure that answers "can he sell it": a live Jupiter round trip.

⛔ `pool_live` means a derived pool holds >= $10 of quote side. It does NOT mean
sellable - measured: a pool holding $41.07 of WSOL returned NO_SELL_ROUTE. So
every contract the backfill calls `pool_live` is put through
`chainfields.round_trip()`, which routes a real $100 quote across every pool.

⚠️ Quotes, not fills. Nothing is signed and nothing is ever traded here.

Run: python analysis/pool_offsets/roundtrip_live.py
"""
import glob
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import chainfields  # noqa: E402

SIDECAR = os.path.join(ROOT, "data", "pools", "state.jsonl")
OUT = os.path.join(HERE, "roundtrip_pool_live.json")


def latest_rows():
    """The LAST row per contract. The sidecar is append-only, so rows repeat."""
    seen = {}
    for ln in io.open(SIDECAR, encoding="utf-8"):
        ln = ln.strip()
        if not ln:
            continue
        try:
            r = json.loads(ln)
        except ValueError:
            continue
        seen[r.get("token")] = r
    return seen


def main(argv):
    rows = latest_rows()
    live = sorted((r for r in rows.values() if r["pool_state"] == "pool_live"),
                  key=lambda r: -(r.get("quote_usd_max") or 0))
    print("%d of %d contracts are pool_live. Quoting $100 round trips.\n"
          % (len(live), len(rows)))
    out = []
    for r in live:
        t0 = time.time()
        try:
            rt = chainfields.round_trip(r["token"], usd=100.0)
        except Exception as e:
            rt = {"verdict": "ERROR", "error": "%s: %s"
                  % (type(e).__name__, str(e)[:90])}
        row = {
            "token": r["token"], "symbol": r["symbol"],
            "pool_state": r["pool_state"],
            "quote_reserves_usd": r.get("quote_usd_max"),
            "venues": r.get("venues"),
            "round_trip": rt,
            "measured_at": int(time.time()),
            # ⛔ said on every row, because this is the field most likely misread
            "note": ("a QUOTE, not a fill. Nothing was signed. Reserves are not "
                     "an exit price; this line is the exit measure."),
        }
        out.append(row)
        print("%-12s reserves $%9.2f  ->  %-14s back $%s  cost %s%%  (%.1fs)"
              % ((r["symbol"] or "")[:12], r.get("quote_usd_max") or 0,
                 rt.get("verdict"), rt.get("usd_back"), rt.get("rt_cost_pct"),
                 time.time() - t0))
        sys.stdout.flush()
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1, sort_keys=True)
    ok = [x for x in out if (x["round_trip"] or {}).get("verdict") == "TRADEABLE"]
    print("\nTRADEABLE on a live $100 round trip: %d of %d pool_live"
          % (len(ok), len(out)))
    print("wrote", OUT)
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
