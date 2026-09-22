"""Hyperliquid reader: HyperCore spot facts and REAL slippage from the order book.

We are completely blind to this chain and Frank holds HYPE and PURR.

⚠️ HyperCore spot is an ORDER BOOK, not an AMM. "Liquidity" is not a pool
balance; the honest number is what the book fills at his size, so this walks the
L2 book and computes the actual cost of a $500 and a $2,000 market order, both
sides, plus the round trip.

⛔ Token NAMES on HyperCore are not unique - anyone can deploy a HIP-1 token and
call it what they like, which is the same ticker-collision problem as Solana. So
every name match is listed with its token index and tokenId, and the canonical
one is identified by which pair actually carries volume.

All endpoints are the free public api.hyperliquid.xyz/info POST API. No key, no
signup, read only.
"""
import io
import json
import os
import sys
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research)"}
URL = "https://api.hyperliquid.xyz/info"


def info(body):
    req = urllib.request.Request(URL, data=json.dumps(body).encode(),
                                headers={"Content-Type": "application/json", **UA})
    return json.loads(urllib.request.urlopen(req, timeout=30).read())


def book_cost(coin, usd_sizes=(500, 2000)):
    """Walk the L2 book. Returns the real cost of a market order at each size."""
    b = info({"type": "l2Book", "coin": coin})
    levels = b.get("levels") or []
    if len(levels) < 2:
        return {"error": "no book", "raw_keys": list(b)}
    bids, asks = levels[0], levels[1]

    def walk(side, usd):
        """Spend usd (buy) or receive usd worth (sell). Returns avg px and slip."""
        spent = 0.0
        qty = 0.0
        for lv in side:
            px = float(lv["px"])
            sz = float(lv["sz"])
            room = usd - spent
            if room <= 0:
                break
            take_usd = min(room, px * sz)
            qty += take_usd / px
            spent += take_usd
        if spent < usd * 0.999:
            return {"filled_usd": round(spent, 2), "incomplete": True,
                    "book_usd_total": round(sum(float(l["px"]) * float(l["sz"]) for l in side), 2)}
        return {"avg_px": spent / qty if qty else None, "qty": qty, "filled_usd": round(spent, 2)}

    best_bid = float(bids[0]["px"]) if bids else None
    best_ask = float(asks[0]["px"]) if asks else None
    mid = (best_bid + best_ask) / 2 if (best_bid and best_ask) else None
    out = {"coin": coin, "best_bid": best_bid, "best_ask": best_ask, "mid": mid,
           "spread_pct": (100 * (best_ask - best_bid) / mid) if mid else None,
           "bid_depth_usd": round(sum(float(l["px"]) * float(l["sz"]) for l in bids), 2),
           "ask_depth_usd": round(sum(float(l["px"]) * float(l["sz"]) for l in asks), 2),
           "sizes": {}}
    for usd in usd_sizes:
        buy = walk(asks, usd)
        sell = walk(bids, usd)
        rec = {"buy": buy, "sell": sell}
        if buy.get("avg_px") and sell.get("avg_px"):
            # buy then immediately sell the same notional: cost is the two slips
            rec["buy_slip_pct"] = 100 * (buy["avg_px"] - mid) / mid
            rec["sell_slip_pct"] = 100 * (mid - sell["avg_px"]) / mid
            rec["round_trip_cost_pct"] = rec["buy_slip_pct"] + rec["sell_slip_pct"]
            qty = buy["qty"]
            # value that quantity back out through the bid side
            got = 0.0
            left = qty
            for lv in bids:
                if left <= 0:
                    break
                take = min(left, float(lv["sz"]))
                got += take * float(lv["px"])
                left -= take
            rec["usd_back_on_immediate_sell"] = round(got, 2)
            rec["round_trip_realized_pct"] = 100 * (got - usd) / usd
        out["sizes"][usd] = rec
    return out


def main():
    out = {}
    meta = info({"type": "spotMetaAndAssetCtxs"})
    spot, ctxs = meta[0], meta[1]
    tokens = spot["tokens"]
    universe = spot["universe"]
    by_index = {t["index"]: t for t in tokens}
    # ⛔ name collisions, listed not resolved silently
    for want in ("HYPE", "PURR"):
        same = [t for t in tokens if t["name"].upper() == want]
        out.setdefault("name_matches", {})[want] = [
            {"index": t["index"], "name": t["name"], "fullName": t.get("fullName"),
             "tokenId": t.get("tokenId"), "evmContract": t.get("evmContract"),
             "deployerTradingFeeShare": t.get("deployerTradingFeeShare")} for t in same]
    # pairs, joined to their context BY POSITION (the API returns them aligned)
    rows = []
    for u, c in zip(universe, ctxs):
        names = [by_index.get(i, {}).get("name") for i in u["tokens"]]
        rows.append({"pair_name": u["name"], "pair_index": u.get("index"),
                     "tokens": u["tokens"], "token_names": names,
                     "mid": c.get("midPx"), "prevDay": c.get("prevDayPx"),
                     "vol24_usd": c.get("dayNtlVlm"), "circ": c.get("circulatingSupply"),
                     "total": c.get("totalSupply")})
    out["pairs_of_interest"] = [r for r in rows
                               if any(n in ("HYPE", "PURR") for n in (r["token_names"] or []))]
    # the canonical market for each is the one with real volume
    for want in ("HYPE", "PURR"):
        cands = [r for r in out["pairs_of_interest"] if want in (r["token_names"] or [])]
        cands.sort(key=lambda r: -(float(r["vol24_usd"] or 0)))
        if not cands:
            continue
        top = cands[0]
        coin = top["pair_name"]
        book = book_cost(coin)
        mid = float(top["mid"]) if top.get("mid") else book.get("mid")
        circ = float(top["circ"] or 0)
        out.setdefault("canonical", {})[want] = {
            "pair": coin, "tokens": top["token_names"], "mid": mid,
            "prev_day": top["prevDay"], "vol24_usd": top["vol24_usd"],
            "circulating": circ, "mcap_usd": (mid * circ) if mid else None,
            "book": book,
            "all_markets_by_volume": [{"pair": c["pair_name"], "names": c["token_names"],
                                       "mid": c["mid"], "vol24": c["vol24_usd"]}
                                      for c in cands[:6]]}
    # staking: where HYPE yield actually comes from
    try:
        vals = info({"type": "validatorSummaries"})
        act = [v for v in vals if not v.get("isJailed")]
        tot = sum(float(v.get("stake") or 0) for v in vals)
        act.sort(key=lambda v: -float(v.get("stake") or 0))
        out["staking"] = {"validators": len(vals), "active": len(act),
                          "total_staked_wei": tot,
                          "top5": [{"name": v.get("name"), "stake": v.get("stake"),
                                    "commission": v.get("commission"),
                                    "apr": v.get("stats", {}) if isinstance(v.get("stats"), dict) else None}
                                   for v in act[:5]]}
    except Exception as e:
        out["staking"] = {"error": f"{type(e).__name__}: {str(e)[:100]}"}
    return out


if __name__ == "__main__":
    r = main()
    with io.open(os.path.join(HERE, "hyperliquid.json"), "w", encoding="utf-8") as f:
        json.dump(r, f, indent=1, ensure_ascii=False, default=str)
    for want, v in (r.get("canonical") or {}).items():
        print(f"\n=== {want} on Hyperliquid HyperCore ===")
        print(f"  market {v['pair']} {v['tokens']}  mid ${v['mid']}  prev day ${v['prev_day']}")
        print(f"  24h volume ${float(v['vol24_usd'] or 0):,.0f}   circulating {v['circulating']:,.0f}"
              f"   mcap ${(v['mcap_usd'] or 0):,.0f}")
        b = v["book"]
        print(f"  book: bid ${b['best_bid']} / ask ${b['best_ask']} spread {b['spread_pct'] and round(b['spread_pct'],4)}%"
              f"  depth on book: bids ${b['bid_depth_usd']:,.0f} asks ${b['ask_depth_usd']:,.0f}")
        for usd, s in b["sizes"].items():
            if "round_trip_cost_pct" in s:
                print(f"  ${usd}: buy slip {s['buy_slip_pct']:.3f}% sell slip {s['sell_slip_pct']:.3f}% "
                      f"round trip {s['round_trip_realized_pct']:.3f}% (back ${s['usd_back_on_immediate_sell']:,.2f})")
            else:
                print(f"  ${usd}: INCOMPLETE FILL {s}")
        print("  other markets:", [(m['pair'], m['names'], m['vol24']) for m in v['all_markets_by_volume'][:4]])
    print("\nname collisions:", json.dumps(r.get("name_matches"), indent=1)[:900])
    st = r.get("staking") or {}
    print("\nstaking:", json.dumps({k: st.get(k) for k in ("validators", "active", "total_staked_wei")}),
          json.dumps(st.get("top5"), default=str)[:400])
