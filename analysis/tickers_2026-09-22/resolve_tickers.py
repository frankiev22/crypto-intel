"""Resolve Frank's named TICKERS to contract addresses, across chains.

⛔ These are unverified strings from chat and ticker collision is the exact
failure mode this project exists around: 398 contracts in our data impersonate
an incumbent name, one "DOGE" showed $86.5B FDV against $0.0002 of sellable
depth, and 112 carry a bidi control that makes the symbol RENDER as something
it does not contain.

So: enumerate EVERY candidate per ticker from two independent search paths,
score them, and name the impersonators. Nothing here picks a winner silently.

  Jupiter tokens/v2/search  - Solana only, but carries holderCount, liquidity,
                              organicScore, isVerified, launchpad, audit flags
  Dexscreener latest/dex/search - every chain, pair-level liquidity and volume

Both are third-party and LABELLED as such. The chain read comes next, in
vet_solana.py, only for the finalists.

Free endpoints, no key, no signup.
"""
import io
import json
import os
import sys
import time
import unicodedata

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import chainfields  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}
TICKERS = ["STONK", "CATE", "PURR", "HYPE", "SOL", "ZCAT", "LOOP", "STONKCAT", "KNOTS"]

BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069, 0x200F, 0x200E}


def symbol_flags(s):
    """The same checks dashboard.safe_sym exists for."""
    s = s or ""
    scripts = set()
    for ch in s:
        if ch.isalpha():
            try:
                n = unicodedata.name(ch)
            except ValueError:
                continue
            scripts.add(n.split()[0])
    return {"bidi": any(ord(c) in BIDI for c in s),
            "mixed_script": len(scripts) > 1,
            "scripts": sorted(scripts)}


def get(url):
    return chainfields._get(url, headers=UA, timeout=25)


def jupiter(ticker):
    st, b = get("https://lite-api.jup.ag/tokens/v2/search?query=" + ticker)
    if not isinstance(b, list):
        return [], f"status {st}"
    out = []
    for t in b:
        out.append({"source": "jupiter", "chain": "solana", "address": t.get("id"),
                    "symbol": t.get("symbol"), "name": t.get("name"),
                    "liquidity": t.get("liquidity"), "mcap": t.get("mcap"),
                    "fdv": t.get("fdv"), "price": t.get("usdPrice"),
                    "holders": t.get("holderCount"), "verified": t.get("isVerified"),
                    "organic": t.get("organicScore"), "launchpad": t.get("launchpad"),
                    "tags": t.get("tags"),
                    "vol24": sum(((t.get("stats24h") or {}).get(k) or 0)
                                 for k in ("buyVolume", "sellVolume")),
                    "audit": t.get("audit")})
    return out, None


def dexscreener(ticker):
    st, b = get("https://api.dexscreener.com/latest/dex/search?q=" + ticker)
    pairs = (b or {}).get("pairs") if isinstance(b, dict) else None
    if pairs is None:
        return [], f"status {st}"
    agg = {}
    for p in pairs:
        bt = p.get("baseToken") or {}
        if (bt.get("symbol") or "").upper() != ticker.upper():
            continue
        k = (p.get("chainId"), bt.get("address"))
        a = agg.setdefault(k, {"source": "dexscreener", "chain": p.get("chainId"),
                               "address": bt.get("address"), "symbol": bt.get("symbol"),
                               "name": bt.get("name"), "liquidity": 0.0, "vol24": 0.0,
                               "pairs": 0, "mcap": p.get("marketCap"), "fdv": p.get("fdv"),
                               "price": p.get("priceUsd"), "dexes": set(),
                               "oldest_pair_ms": p.get("pairCreatedAt")})
        a["liquidity"] += float((p.get("liquidity") or {}).get("usd") or 0)
        a["vol24"] += float((p.get("volume") or {}).get("h24") or 0)
        a["pairs"] += 1
        a["dexes"].add(p.get("dexId"))
        if p.get("pairCreatedAt") and (not a["oldest_pair_ms"] or p["pairCreatedAt"] < a["oldest_pair_ms"]):
            a["oldest_pair_ms"] = p["pairCreatedAt"]
    for a in agg.values():
        a["dexes"] = sorted(x for x in a["dexes"] if x)
    return list(agg.values()), None


if __name__ == "__main__":
    out = {"ts": int(time.time()), "tickers": {}}
    for tk in TICKERS:
        j, je = jupiter(tk)
        time.sleep(0.4)
        d, de = dexscreener(tk)
        time.sleep(0.4)
        # merge on (chain, address)
        merged = {}
        for row in j + d:
            k = (row["chain"], row["address"])
            m = merged.setdefault(k, {"chain": row["chain"], "address": row["address"],
                                      "sources": [], "symbols": set()})
            m["sources"].append(row["source"])
            m["symbols"].add(row.get("symbol") or "")
            for f in ("name", "liquidity", "mcap", "fdv", "price", "holders", "verified",
                      "organic", "launchpad", "vol24", "pairs", "dexes", "tags", "audit",
                      "oldest_pair_ms"):
                if row.get(f) not in (None, "", [], 0) and m.get(f) in (None, "", [], 0):
                    m[f] = row.get(f)
                elif f in ("liquidity", "vol24") and row.get(f):
                    m[f] = max(m.get(f) or 0, row[f])
        rows = []
        for m in merged.values():
            m["symbols"] = sorted(x for x in m["symbols"] if x)
            m["symbol_flags"] = symbol_flags(m["symbols"][0] if m["symbols"] else "")
            rows.append(m)
        rows.sort(key=lambda r: -(r.get("liquidity") or 0))
        out["tickers"][tk] = {"candidates": rows, "jupiter_error": je, "dexscreener_error": de}
        print(f"\n=== {tk} === {len(rows)} candidates "
              f"{'(jup: ' + je + ')' if je else ''}{'(dex: ' + de + ')' if de else ''}")
        for r in rows[:8]:
            flags = []
            if r["symbol_flags"]["bidi"]:
                flags.append("BIDI")
            if r["symbol_flags"]["mixed_script"]:
                flags.append("MIXED-SCRIPT")
            if r.get("verified"):
                flags.append("jup-verified")
            print(f"  {str(r['chain'])[:9]:9s} {str(r['address'])[:44]:44s} "
                  f"liq ${(r.get('liquidity') or 0):>13,.0f} "
                  f"mcap ${(r.get('mcap') or 0):>14,.0f} "
                  f"vol24 ${(r.get('vol24') or 0):>13,.0f} "
                  f"hold {str(r.get('holders') or '-'):>7s} "
                  f"{','.join(r.get('sources') or [])} {r.get('launchpad') or ''} "
                  f"{' '.join(flags)}")
    p = os.path.join(HERE, "candidates.json")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("\nwritten", p)
