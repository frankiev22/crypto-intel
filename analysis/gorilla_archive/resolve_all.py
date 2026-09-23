"""Resolve every ticker in the archive to a contract address, across chains.

⛔ 482 distinct tickers from 49 daily recaps, and ticker collision is this
project's defining failure mode: 398 contracts in our own data impersonate an
incumbent name, and one "DOGE" showed $86.5B FDV against $0.0002 of sellable
depth. So nothing here picks a winner silently. Every candidate is kept, every
choice carries a confidence, and the losers are counted.

⭐ The archive gives us a disambiguator we have never had before: **a date**.
Gorilla reports tokens that have ALREADY run, so the pool must exist by the day
he mentions it. A candidate whose earliest pool was created after the first
mention is the wrong contract, however much liquidity it has now. That single
rule does more work than liquidity ranking.

Resumable: every ticker's raw search result is cached to cache/, so a re-run
costs nothing for what is already done.

Free endpoints only, no key, no signup:
  lite-api.jup.ag/tokens/v2/search        Solana, carries holders + audit flags
  api.dexscreener.com/latest/dex/search   every chain, pair-level liq + created
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
CACHE = os.path.join(HERE, "cache")
BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068, 0x2069,
        0x200F, 0x200E}
DAY = 86400.0


def symbol_flags(s):
    s = s or ""
    scripts = set()
    for ch in s:
        if ch.isalpha():
            try:
                scripts.add(unicodedata.name(ch).split()[0])
            except ValueError:
                pass
    return {"bidi": any(ord(c) in BIDI for c in s),
            "mixed_script": len(scripts) > 1}


def cached(name, fn):
    os.makedirs(CACHE, exist_ok=True)
    safe = "".join(c if (c.isalnum() or c in "-_") else "_" for c in name)[:80]
    p = os.path.join(CACHE, safe + ".json")
    if os.path.exists(p):
        try:
            return json.load(io.open(p, encoding="utf-8"))
        except Exception:
            pass
    v = fn()
    tmp = p + ".tmp"
    json.dump(v, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, p)
    return v


def jup(ticker):
    def go():
        st, b = chainfields._get(
            "https://lite-api.jup.ag/tokens/v2/search?query=" + ticker,
            headers=UA, timeout=25)
        time.sleep(0.35)
        return b if isinstance(b, list) else []
    rows = cached("jup_" + ticker, go)
    out = []
    for t in rows or []:
        if (t.get("symbol") or "").upper() != ticker.upper():
            continue
        out.append({
            "src": "jupiter", "chain": "solana", "address": t.get("id"),
            "symbol": t.get("symbol"), "name": t.get("name"),
            "liquidity": t.get("liquidity"), "mcap": t.get("mcap"),
            "fdv": t.get("fdv"), "price": t.get("usdPrice"),
            "holders": t.get("holderCount"), "verified": t.get("isVerified"),
            "organic": t.get("organicScoreLabel"), "launchpad": t.get("launchpad"),
            "first_pool": ((t.get("firstPool") or {}).get("createdAt")),
            "audit": t.get("audit"),
            "vol24": sum(((t.get("stats24h") or {}).get(k) or 0)
                         for k in ("buyVolume", "sellVolume")),
        })
    return out


def dex(ticker):
    def go():
        st, b = chainfields._get(
            "https://api.dexscreener.com/latest/dex/search?q=" + ticker,
            headers=UA, timeout=25)
        time.sleep(0.35)
        return (b or {}).get("pairs") if isinstance(b, dict) else []
    pairs = cached("dex_" + ticker, go)
    agg = {}
    for p in pairs or []:
        bt = p.get("baseToken") or {}
        if (bt.get("symbol") or "").upper() != ticker.upper():
            continue
        k = (p.get("chainId"), bt.get("address"))
        a = agg.setdefault(k, {"src": "dexscreener", "chain": p.get("chainId"),
                               "address": bt.get("address"),
                               "symbol": bt.get("symbol"), "name": bt.get("name"),
                               "liquidity": 0.0, "vol24": 0.0, "pairs": 0,
                               "mcap": p.get("marketCap"), "fdv": p.get("fdv"),
                               "price": p.get("priceUsd"),
                               "first_pool_ms": p.get("pairCreatedAt")})
        a["liquidity"] += float((p.get("liquidity") or {}).get("usd") or 0)
        a["vol24"] += float((p.get("volume") or {}).get("h24") or 0)
        a["pairs"] += 1
        if p.get("pairCreatedAt") and (not a["first_pool_ms"]
                                       or p["pairCreatedAt"] < a["first_pool_ms"]):
            a["first_pool_ms"] = p["pairCreatedAt"]
    return list(agg.values())


def first_pool_epoch(c):
    if c.get("first_pool_ms"):
        return float(c["first_pool_ms"]) / 1000.0
    fp = c.get("first_pool")
    if fp:
        try:
            return time.mktime(time.strptime(fp[:19], "%Y-%m-%dT%H:%M:%S"))
        except Exception:
            return None
    return None


def merge(ticker):
    rows = jup(ticker) + dex(ticker)
    m = {}
    for r in rows:
        k = (r["chain"], r["address"])
        if not r["address"]:
            continue
        cur = m.setdefault(k, {"chain": r["chain"], "address": r["address"],
                               "sources": []})
        cur["sources"].append(r["src"])
        for f in ("symbol", "name", "mcap", "fdv", "price", "holders", "verified",
                  "organic", "launchpad", "audit", "first_pool", "first_pool_ms",
                  "pairs"):
            if r.get(f) not in (None, "", [], 0) and cur.get(f) in (None, "", [], 0):
                cur[f] = r.get(f)
        for f in ("liquidity", "vol24"):
            if r.get(f):
                cur[f] = max(cur.get(f) or 0, float(r[f]))
    return list(m.values())


def resolve(ticker, first_mention_date):
    """Choose a contract. Date first, then liquidity. Never silently."""
    cands = merge(ticker)
    cutoff = None
    if first_mention_date:
        cutoff = time.mktime(time.strptime(first_mention_date, "%Y-%m-%d")) + DAY
    for c in cands:
        c["symbol_flags"] = symbol_flags(c.get("symbol"))
        fp = first_pool_epoch(c)
        c["first_pool_epoch"] = fp
        # ⛔ a token called on Aug 14 cannot have been created in September
        c["created_after_mention"] = bool(cutoff and fp and fp > cutoff)
        c["age_unknown"] = fp is None
    eligible = [c for c in cands if not c["created_after_mention"]]
    pool = eligible or cands
    pool.sort(key=lambda c: -(c.get("liquidity") or 0))

    chosen, conf, why = None, "NONE", "no candidate found on either source"
    if pool:
        chosen = pool[0]
        top = chosen.get("liquidity") or 0
        second = (pool[1].get("liquidity") or 0) if len(pool) > 1 else 0
        if not eligible:
            conf, why = "LOW", "every candidate's pool postdates the first mention"
        elif len(eligible) == 1 and top >= 25000:
            conf, why = "HIGH", "single dated candidate with real liquidity"
        elif top >= 50000 and top >= 10 * max(second, 1):
            conf, why = "HIGH", "dominant by liquidity among dated candidates"
        elif top >= 25000 and top >= 3 * max(second, 1):
            conf, why = "MEDIUM", "leads dated candidates by liquidity"
        elif top > 0:
            conf, why = "LOW", "several live candidates of similar size"
        else:
            conf, why = "LOW", "candidate has no measurable liquidity left"
    return {"ticker": ticker, "n_candidates": len(cands),
            "n_eligible_by_date": len(eligible), "confidence": conf,
            "why": why, "chosen": chosen,
            "rejected_newer": [c["address"] for c in cands
                               if c["created_after_mention"]][:8],
            "others": [{"chain": c["chain"], "address": c["address"],
                        "liq": c.get("liquidity"), "mcap": c.get("mcap")}
                       for c in pool[1:6]]}


def main():
    mentions = json.load(io.open(os.path.join(HERE, "mentions.json"), encoding="utf-8"))
    first = {}
    for m in mentions:
        t = m["ticker"]
        if t not in first or (m["date"] or "9") < first[t]:
            first[t] = m["date"]
    tickers = sorted(first)
    out, t0 = [], time.time()
    for i, t in enumerate(tickers):
        try:
            out.append(resolve(t, first[t]))
        except Exception as e:
            out.append({"ticker": t, "confidence": "ERROR",
                        "why": f"{type(e).__name__}: {str(e)[:120]}",
                        "chosen": None, "n_candidates": 0})
        if (i + 1) % 25 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(tickers)}  {el:.0f}s elapsed, "
                  f"{el/(i+1)*(len(tickers)-i-1):.0f}s left", flush=True)
            json.dump(out, io.open(os.path.join(HERE, "resolved.json"), "w",
                                   encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(out, io.open(os.path.join(HERE, "resolved.json"), "w",
                           encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    c = Counter(r["confidence"] for r in out)
    print("confidence:", dict(c))
    print("rejected as created-after-mention:",
          sum(len(r.get("rejected_newer") or []) for r in out))


if __name__ == "__main__":
    main()
