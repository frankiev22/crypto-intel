"""Frank's actual holdings: all pairs, full safety, exit at HIS size.

⛔ Every liquidity figure here is summed across EVERY pair for the mint
(`allpairs.token`). Reading one pool is the bug that produced a day of wrong
EMBER analysis: the real EMBER trades on 30 pools and one pool is a 3% sample.

⛔ The only number that is an exit price is `chainfields.round_trip()`, which
routes across venues. Dexscreener liquidity overstates by a median 781x and is
here for SHAPE (how many pools, which quote assets, is it a phantom), never for
sizing.

Sizes quoted: $165 (his actual PURR position), $500, $2,000.
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
import allpairs  # noqa: E402
import chainfields  # noqa: E402
import onchain_reserves  # noqa: E402
from pool_probe import PROGRAMS, AUTHORITIES, SYSTEM  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SIZES = (165, 500, 2000)

HOLDINGS = [
    ("SOL",      "So11111111111111111111111111111111111111112", "the reference"),
    ("HYPE",     "98sMhvDwXj1RQi5c5Mndm3vPe9cBqPrbLaufMXFNMh5g", "Solana HYPE, 30 pairs, tracks the real price"),
    ("PURR",     "8RNUw4N655VSrZKuhGdywhbSMDTrheguFPfxbpE2NZHQ", "Hypurr, HIS holding, matched on his own numbers"),
    ("STONK",    "6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx", "stonk.fun platform token"),
    ("CATE",     "Ai66LHZG9MCzg1WKdawwqduVAXpNDUuV8M3uyq5ppump", "pump.fun memecoin"),
    ("ZCAT",     "HcRLc9VDgjLeK154xDawfb1dmVJ98DoSqcwTHGqiDeJR", "paired to ZEC"),
    ("KNOTS",    "8RVBk8vxLiUHueLUW1f4izFVqN3nWippLhkohKg6EGkS", "stonk.fun reward token"),
    ("LOOP",     "HunmXDXMNQYVoDnUL6PNnSYEtFaTZA2WzGh1HJTW7aoV", "stonk.fun reward token"),
    ("JEANPHIL", "GTBxUiw6wJdmmkCGZgRHLyYxqu1vG4KtRpeox6yDpump", "30 pairs, Token-2022"),
    ("EMBER",    "5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6", "THE REAL EMBER, retracting yesterday"),
]


def mint_account(m):
    res, err = chainfields._rpc("getAccountInfo", [m, {"encoding": "jsonParsed"}])
    v = (res or {}).get("value") if res else None
    if not v:
        return {"error": err or "no account"}
    i = v["data"]["parsed"]["info"]
    dec = i.get("decimals") or 0
    out = {"program": "Token-2022" if v.get("owner") == TOKEN22 else "SPL",
           "decimals": dec, "supply": float(i.get("supply") or 0) / (10 ** dec),
           "mint_authority": i.get("mintAuthority"),
           "freeze_authority": i.get("freezeAuthority"),
           "extensions": [e.get("extension") for e in (i.get("extensions") or [])],
           "transfer_fee_bps": None, "fee_config_authority": None}
    for e in (i.get("extensions") or []):
        if e.get("extension") == "transferFeeConfig":
            st = e.get("state") or {}
            out["transfer_fee_bps"] = (st.get("newerTransferFee") or {}).get("transferFeeBasisPoints")
            out["fee_config_authority"] = st.get("transferFeeConfigAuthority")
            out["withdraw_authority"] = st.get("withdrawWithheldAuthority")
    return out


def concentration(m, supply):
    """Top holders with POOL VAULTS EXCLUDED. A pool is not a whale."""
    res, err = chainfields._rpc("getTokenLargestAccounts", [m])
    vals = (res or {}).get("value") if res else None
    if not vals:
        return {"error": err or "none"}
    accts = [{"acct": v["address"], "ui": float(v.get("uiAmountString") or 0)} for v in vals]
    owners = {}
    r2, _ = chainfields._rpc("getMultipleAccounts",
                             [[a["acct"] for a in accts], {"encoding": "jsonParsed"}])
    for a, v in zip(accts, ((r2 or {}).get("value") or [])):
        if v and isinstance(v.get("data"), dict):
            owners[a["acct"]] = v["data"]["parsed"]["info"].get("owner")
    ow = sorted({o for o in owners.values() if o})
    prog = {}
    if ow:
        r3, _ = chainfields._rpc("getMultipleAccounts",
                                 [ow, {"encoding": "base64",
                                       "dataSlice": {"offset": 0, "length": 0}}])
        for o, v in zip(ow, ((r3 or {}).get("value") or [])):
            prog[o] = (v or {}).get("owner")
    wallets, pools = [], []
    for a in accts:
        o = owners.get(a["acct"])
        p = prog.get(o)
        is_pool = (o in AUTHORITIES) or (p in PROGRAMS) or (p not in (SYSTEM, None))
        (pools if is_pool else wallets).append(a)
    tot = sum(w["ui"] for w in wallets[:10])
    return {"top1_wallet_pct": (100.0 * wallets[0]["ui"] / supply) if (wallets and supply) else None,
            "top10_wallet_pct": (100.0 * tot / supply) if supply else None,
            "n_pool_vaults_excluded": len(pools)}


def main():
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": []}
    print(f"measured {out['ts']}   (all liquidity summed across ALL pairs)\n")
    for sym, m, note in HOLDINGS:
        t = allpairs.token(m)
        mi = mint_account(m)
        con = concentration(m, mi.get("supply") or 0)
        rts = {}
        for usd in SIZES:
            r = chainfields.round_trip(m, usd)
            rts[usd] = {k: r.get(k) for k in ("verdict", "usd_back", "rt_cost_pct",
                                              "price_impact_pct", "venues", "error")}
            time.sleep(0.35)
        row = {"ticker": sym, "address": m, "note": note, "allpairs": t,
               "mint": mi, "concentration": con, "round_trips": rts,
               "shape": allpairs.verdict(t)}
        out["rows"].append(row)

        auth = []
        if mi.get("mint_authority"):
            auth.append("MINT LIVE")
        if mi.get("freeze_authority"):
            auth.append("FREEZE LIVE")
        if mi.get("fee_config_authority"):
            auth.append("FEE CHANGEABLE")
        fee = f"{mi.get('transfer_fee_bps')}bp tax" if mi.get("transfer_fee_bps") else "no tax"
        print(f"{sym:9s} {m}")
        print(f"          {row['shape']:<12s} pairs={t.get('pair_count')} "
              f"liq(ALL)=${(t.get('total_liq_usd') or 0):,.0f} "
              f"vol24=${(t.get('total_vol24_usd') or 0):,.0f} "
              f"mcap=${(t.get('mcap_usd') or 0):,.0f} px={t.get('price_usd')}")
        print(f"          {mi.get('program')} | {fee} | {', '.join(auth) or 'authorities revoked'}")
        c = con or {}
        t1 = c.get("top1_wallet_pct")
        t10 = c.get("top10_wallet_pct")
        print(f"          top wallet {('%.2f%%' % t1) if t1 is not None else 'unknown'}"
              f"  top10 {('%.2f%%' % t10) if t10 is not None else 'unknown'}"
              f"  ({c.get('n_pool_vaults_excluded')} pool vaults excluded)")
        qa = t.get("quote_assets") or {}
        print(f"          paired against: "
              f"{ {k: ('$%s' % format(round(v['liq_usd']), ',')) for k, v in list(qa.items())[:5]} }")
        for usd in SIZES:
            q = rts[usd]
            back = q.get("usd_back")
            bs = ("$%.2f" % back) if isinstance(back, (int, float)) else "unknown"
            print(f"          ${usd:>5}: {str(q['verdict']):<14s} back {bs:>10s} "
                  f"cost {q.get('rt_cost_pct')}%  {q.get('error') or ''}")
        print()
    json.dump(out, io.open(os.path.join(HERE, "holdings.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, default=str)
    print("written holdings.json")


if __name__ == "__main__":
    main()
