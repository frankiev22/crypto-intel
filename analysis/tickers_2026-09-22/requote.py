"""Re-quote Frank's named tokens RIGHT NOW, at the sizes he is actually deploying.

⛔ A depth quote is perishable. He has a Ledger plugged in, so a number measured
hours ago is not the number he will get. This re-reads everything at call time:

  chain   mint account again (authorities can be re-enabled, fees can be changed
          by a live transferFeeConfigAuthority, so this is not a constant)
  jupiter live round trip at $100 / $500 / $2,000, realizable, both directions
  hl      HyperCore order book walked level by level for HYPE and PURR

⛔ Analysis only. Nothing here signs, and nothing here recommends a buy.

usage: python -u requote.py
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "analysis", "daily_2026-09-22", "pushback"))
import chainfields  # noqa: E402
from pool_probe import UA, WSOL, asset_usd  # noqa: E402
import hyperliquid as hl  # noqa: E402

SIZES = (100, 500, 2000)

# resolved and vetted 2026-09-22, data/findings/TICKERS_2026-09-22.md
SOLANA = [
    ("SOL",      WSOL,                                           "wrapped SOL, the reference"),
    ("STONK",    "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx", "stonk.fun platform token"),
    ("CATE",     "Ai66LHZG9MCzg1WKdawwqduVAXpNDUuV8M3uyq5ppump", "pump.fun memecoin"),
    ("ZCAT",     "HcRLc9VDgjLeK154xDawfb1dmVJ98DoSqcwTHGqiDeJR", "stonk.fun, paired to ZEC"),
    ("KNOTS",    "8RVBk8vxLiUHueLUW1f4izFVqN3nWippLhkohKg6EGkS", "stonk.fun reward token"),
    ("LOOP",     "HunmXDXMNQYVoDnUL6PNnSYEtFaTZA2WzGh1HJTW7aoV", "stonk.fun reward token"),
    ("PURR-sol", "8RNUw4N655VSrZKuhGdywhbSMDTrheguFPfxbpE2NZHQ", "stonk.fun, NOT the Hyperliquid PURR"),
    ("STONKCAT", "9h5AzEQzYu9CV5K6uLtFRMD1KcbxZSFNxZEgBTNfw5Na", "stonk.fun, 1% fee"),
]
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"


def mint_now(mint):
    """Re-read the mint. Authorities and fees are state, not constants."""
    res, err = chainfields._rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    v = (res or {}).get("value") if res else None
    if not v:
        return {"error": err or "no account"}
    info = v["data"]["parsed"]["info"]
    out = {"is_token_2022": v.get("owner") == TOKEN22,
           "mint_authority": info.get("mintAuthority"),
           "freeze_authority": info.get("freezeAuthority"),
           "fee_bps": None, "fee_config_authority": None}
    for e in (info.get("extensions") or []):
        if e.get("extension") == "transferFeeConfig":
            st = e.get("state") or {}
            out["fee_bps"] = ((st.get("newerTransferFee") or {})
                              .get("transferFeeBasisPoints"))
            out["fee_config_authority"] = st.get("transferFeeConfigAuthority")
    return out


def main():
    ts = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())
    out = {"quoted_at_utc": ts, "sol_usd": asset_usd(WSOL), "solana": [], "hyperliquid": {}}
    print(f"quoted at {ts}, SOL ${out['sol_usd']:.2f}\n")

    for sym, mint, what in SOLANA:
        row = {"ticker": sym, "address": mint, "what": what}
        row["mint"] = mint_now(mint)
        st, b = chainfields._get("https://lite-api.jup.ag/tokens/v2/search?query=" + mint,
                                 headers=UA, timeout=25)
        jt = b[0] if isinstance(b, list) and b else {}
        row["price_usd"] = jt.get("usdPrice")
        row["mcap_usd"] = jt.get("mcap")
        row["holders"] = jt.get("holderCount")
        row["rt"] = {}
        for usd in SIZES:
            r = chainfields.round_trip(mint, usd)
            row["rt"][usd] = {k: r.get(k) for k in
                              ("verdict", "usd_back", "rt_cost_pct", "price_impact_pct",
                               "venues", "error")}
            time.sleep(0.4)
        out["solana"].append(row)

        m = row["mint"]
        fee = f"fee {m.get('fee_bps')}bp" if m.get("fee_bps") else "no fee"
        auth = []
        if m.get("mint_authority"):
            auth.append("MINT LIVE")
        if m.get("freeze_authority"):
            auth.append("FREEZE LIVE")
        if m.get("fee_config_authority"):
            auth.append("FEE CHANGEABLE")
        print(f"{sym:9s} {mint}")
        print(f"          price {row['price_usd']} mcap ${(row['mcap_usd'] or 0):,.0f} "
              f"holders {row['holders']} | {fee} | {', '.join(auth) or 'authorities revoked'}")
        for usd in SIZES:
            q = row["rt"][usd]
            back = q.get("usd_back")
            print(f"          ${usd:>5}: {str(q['verdict']):<14} back "
                  f"{('$%.2f' % back) if isinstance(back, (int, float)) else 'unknown':>10} "
                  f"cost {q['rt_cost_pct']}%  {q.get('error') or ''}")
        print()

    # HyperCore: an order book, so walk it. "Depth" is visible levels only.
    for want in ("HYPE", "PURR"):
        try:
            meta = hl.info({"type": "spotMetaAndAssetCtxs"})
            spot, ctxs = meta[0], meta[1]
            by_i = {t["index"]: t for t in spot["tokens"]}
            # ⛔ ctxs is NOT positionally aligned with universe; key on u["index"]
            cands = []
            for i, u in enumerate(spot["universe"]):
                names = [by_i.get(x, {}).get("name") for x in u["tokens"]]
                if want in names:
                    c = ctxs[u["index"]] if u["index"] < len(ctxs) else {}
                    cands.append((float(c.get("dayNtlVlm") or 0), u["name"], c, u))
            cands.sort(reverse=True)
            vol, pair, c, u = cands[0]
            book = hl.book_cost(pair, usd_sizes=SIZES)
            circ = float(c.get("circulatingSupply") or 0)
            mid = float(c.get("midPx") or 0) or book.get("mid")
            out["hyperliquid"][want] = {
                "pair": pair, "token_index": u["tokens"], "mid": mid,
                "vol24_usd": vol, "circulating": circ,
                "mcap_usd": mid * circ if mid else None, "book": book,
                "note": "order book, not a pool: totals are VISIBLE LEVELS only"}
            print(f"{want}-hl   market {pair}  mid ${mid}  24h vol ${vol:,.0f}  "
                  f"mcap ${(mid*circ if mid else 0):,.0f}")
            print(f"          book: bid ${book['best_bid']} ask ${book['best_ask']} "
                  f"visible bids ${book['bid_depth_usd']:,.0f}")
            for usd in SIZES:
                s = book["sizes"].get(usd, {})
                if "round_trip_realized_pct" in s:
                    print(f"          ${usd:>5}: round trip {s['round_trip_realized_pct']:+.3f}% "
                          f"back ${s['usd_back_on_immediate_sell']:,.2f}")
                else:
                    sell = s.get("sell") or {}
                    print(f"          ${usd:>5}: ⛔ DOES NOT FILL, sell stops at "
                          f"${sell.get('filled_usd')} of visible bids")
            print()
        except Exception as e:
            out["hyperliquid"][want] = {"error": f"{type(e).__name__}: {str(e)[:160]}"}
            print(f"{want}-hl   FAILED {type(e).__name__}: {str(e)[:160]}\n")

    p = os.path.join(HERE, "requote_latest.json")
    with io.open(p, "w", encoding="utf-8") as f:
        json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("written", p)
    return out


if __name__ == "__main__":
    main()
