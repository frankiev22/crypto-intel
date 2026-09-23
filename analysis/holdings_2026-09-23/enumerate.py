"""Enumerate every Solana token wearing a ticker, and match on NUMBERS not names.

⛔ Frank's screenshot is the specification, not the ticker. Hypurr/PURR shows
price 0.00827, mcap $7.9M, 24h volume $1.7M, NETWORK SOLANA. A candidate that
does not sit near those numbers is not his token, however well its ticker reads.

⭐ Every candidate is measured with `allpairs.token()`, so liquidity and volume
are summed across EVERY pair. Reading one pool is the bug that produced a whole
day of wrong EMBER analysis.

Free endpoints only.
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import allpairs  # noqa: E402
import chainfields  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}


def candidates(ticker):
    """Every mint carrying this ticker, from two independent searches."""
    seen = {}
    st, b = chainfields._get(
        "https://api.dexscreener.com/latest/dex/search?q=" + ticker, headers=UA, timeout=25)
    for p in ((b or {}).get("pairs") or []) if isinstance(b, dict) else []:
        bt = p.get("baseToken") or {}
        if (bt.get("symbol") or "").upper() != ticker.upper():
            continue
        seen.setdefault((p.get("chainId"), bt.get("address")),
                        {"chain": p.get("chainId"), "address": bt.get("address"),
                         "name": bt.get("name"), "symbol": bt.get("symbol")})
    time.sleep(0.4)
    st, b = chainfields._get(
        "https://lite-api.jup.ag/tokens/v2/search?query=" + ticker, headers=UA, timeout=25)
    for t in (b if isinstance(b, list) else []):
        if (t.get("symbol") or "").upper() != ticker.upper():
            continue
        seen.setdefault(("solana", t.get("id")),
                        {"chain": "solana", "address": t.get("id"),
                         "name": t.get("name"), "symbol": t.get("symbol")})
    time.sleep(0.4)
    return [v for v in seen.values() if v["address"]]


def score(t, want):
    """How well do the measured numbers match the screenshot?"""
    if not t.get("ok"):
        return None, "lookup failed"
    bits = []
    ok = 0
    for key, label, tol in (("price_usd", "price", 0.45),
                            ("mcap_usd", "mcap", 0.60),
                            ("total_vol24_usd", "vol24", 0.60)):
        w = want.get(label)
        v = t.get(key)
        if w is None or not v:
            bits.append(f"{label}=unknown")
            continue
        rel = abs(v - w) / w
        if rel <= tol:
            ok += 1
            bits.append(f"{label} MATCH ({v:,.6g} vs {w:,.6g})")
        else:
            bits.append(f"{label} off {rel*100:.0f}% ({v:,.6g} vs {w:,.6g})")
    return ok, "; ".join(bits)


def run(ticker, want, out_name):
    print(f"\n{'='*78}\n{ticker}: enumerating every candidate, measuring ALL pairs\n{'='*78}")
    rows = []
    for c in candidates(ticker):
        t = allpairs.token(c["address"]) if c["chain"] == "solana" else {"ok": False,
                                                                        "error": "not solana"}
        if c["chain"] != "solana":
            t = allpairs.token(c["address"])  # dexscreener keys by address on any chain
        s, why = score(t, want) if c["chain"] == "solana" else (None, "different chain")
        rows.append({**c, "measured": t, "match_score": s, "match_why": why,
                     "verdict": allpairs.verdict(t)})
        time.sleep(0.25)
    rows.sort(key=lambda r: (-(r["match_score"] or -1), -((r["measured"] or {}).get("total_liq_usd") or 0)))
    for r in rows[:14]:
        m = r["measured"] or {}
        print(f"  {str(r['chain'])[:9]:9s} {str(r['address'])[:44]:44s} "
              f"{str(r.get('name'))[:16]:16s} {r['verdict']:<12s} "
              f"pairs={str(m.get('pair_count')):>3s} "
              f"liq=${(m.get('total_liq_usd') or 0):>12,.0f} "
              f"mcap=${(m.get('mcap_usd') or 0):>14,.0f} match={r['match_score']}")
        if r["match_score"] is not None and r["match_score"] >= 2:
            print(f"      -> {r['match_why']}")
        if m.get("phantom"):
            print(f"      -> PHANTOM: {m['phantom_why']}")
    json.dump(rows, io.open(os.path.join(HERE, out_name), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, default=str)
    return rows


if __name__ == "__main__":
    os.makedirs(HERE, exist_ok=True)
    run("PURR", {"price": 0.00827, "mcap": 7_900_000, "vol24": 1_700_000}, "purr.json")
    run("HYPE", {"price": None, "mcap": None, "vol24": None}, "hype.json")
    run("JEANPHIL", {"price": None, "mcap": None, "vol24": None}, "jeanphil.json")
    run("FONE", {"price": None, "mcap": None, "vol24": None}, "fone.json")
