"""Pull degentape's public Solana tape back to 2026-09-12 00:00Z (AGGREGATE, read-only).

GET /api/tape?window=all&limit=1000&chains=solana&stocks=0&before=<id>, the
page's own request. No login, no cookies. Paced at 1 request/second. Dedupe on
`id` (pages are cut by id, sorted by time: duplicates happen). Keeps only the
fields the cluster test and the win-rate re-derivation need.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
OUT = os.path.join(HERE, "degentape", "tape_sol_0912.jsonl")
START = int(dt.datetime(2026, 9, 12, tzinfo=dt.timezone.utc).timestamp())
STOP_BELOW = START - 3 * 3600          # 3h past the start, for late-indexed rows
UA = "Mozilla/5.0 (crypto-intel research; read-only)"
KEEP = ("id", "tx", "solana", "wallet", "side", "token", "symbol", "token_amt", "quote",
        "quote_amt", "usd", "price", "ts", "created_at", "first_buy", "verified", "mcap",
        "is_stock", "source", "handle")


def get(url):
    for i in range(6):
        try:
            r = urllib.request.Request(url, headers={"User-Agent": UA, "Accept": "application/json"})
            with urllib.request.urlopen(r, timeout=60) as f:
                return json.load(f)
        except urllib.error.HTTPError as e:
            wait = 10 * (i + 1) if e.code in (429, 503) else 3 * (i + 1)
            print(f"  HTTP {e.code}, retry in {wait}s", flush=True)
            time.sleep(wait)
        except Exception as e:
            print(f"  {type(e).__name__}: {str(e)[:80]}, retry", flush=True)
            time.sleep(3 * (i + 1))
    raise RuntimeError("gave up: " + url)


seen = set()
if os.path.exists(OUT):
    for line in open(OUT, encoding="utf-8"):
        seen.add(json.loads(line)["id"])
before = min(seen) if seen else None
pages = dup = 0
t0 = time.time()
with open(OUT, "a", encoding="utf-8") as out:
    while True:
        url = "https://degentape.com/api/tape?window=all&limit=1000&chains=solana&stocks=0"
        if before:
            url += f"&before={before}"
        d = get(url)
        rows = d.get("rows") or []
        pages += 1
        if not rows:
            print("empty page, stopping", flush=True)
            break
        new = 0
        for r in rows:
            if r["id"] in seen:
                dup += 1
                continue
            seen.add(r["id"])
            out.write(json.dumps({k: r.get(k) for k in KEEP}) + "\n")
            new += 1
        before = min(r["id"] for r in rows)
        mts = min(r["ts"] for r in rows)
        if pages % 10 == 0 or mts < STOP_BELOW:
            print(f"page {pages}: {len(seen)} rows, oldest ts "
                  f"{dt.datetime.fromtimestamp(mts, dt.timezone.utc):%m-%d %H:%M}Z, "
                  f"dup {dup}, {time.time() - t0:.0f}s", flush=True)
        if mts < STOP_BELOW:
            break
        time.sleep(1.0)
print(f"done: {len(seen)} rows, {pages} pages, {dup} duplicates, {time.time() - t0:.0f}s")
