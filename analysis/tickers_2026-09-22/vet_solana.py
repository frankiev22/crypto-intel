"""Full vet of one Solana contract, at Frank's real clip.

He is sizing around $5,000 total, so the number that matters is the round-trip
cost at $500 and $2,000, not theoretical depth. Everything here is either a
chain read or a live Jupiter quote; third-party fields are kept under their own
key and never mixed into the chain figures.

  chain:    mint account (decimals, supply, mint + freeze authority, token
            program, Token-2022 extensions), largest holders, pool vaults
  jupiter:  $100 / $500 / $2,000 round trips, price, liquidity, organic score
  rugcheck: LP locked %, markets, risk names (third party, labelled)

⛔ Concentration excludes pool vaults. A pool holding 40% of supply is not a
whale, and counting it as one is how you scare yourself off a normal AMM token.
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
import onchain_reserves  # noqa: E402
from pool_probe import (PROGRAMS, AUTHORITIES, QUOTES, WSOL, TOKEN, TOKEN22, SYSTEM,
                        asset_usd, quote_usd, bonding_curve, UA)  # noqa: E402


def rpc(m, p, timeout=60):
    return chainfields._rpc(m, p, timeout=timeout)


def get(u):
    return chainfields._get(u, headers=UA, timeout=25)


def mint_account(mint):
    res, err = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    v = (res or {}).get("value") if res else None
    if not v:
        return {"error": err or "no account"}
    info = v["data"]["parsed"]["info"]
    dec = info.get("decimals") or 0
    out = {"token_program": v.get("owner"),
           "is_token_2022": v.get("owner") == TOKEN22,
           "decimals": dec,
           "supply_ui": float(info.get("supply") or 0) / (10 ** dec),
           "mint_authority": info.get("mintAuthority"),
           "freeze_authority": info.get("freezeAuthority"),
           "extensions": [e.get("extension") for e in (info.get("extensions") or [])]}
    for e in (info.get("extensions") or []):
        if e.get("extension") == "transferFeeConfig":
            st = (e.get("state") or {})
            out["transfer_fee_bps"] = (((st.get("newerTransferFee") or {})
                                        .get("transferFeeBasisPoints")))
    return out


def largest_holders(mint, supply_ui, dec):
    """Top 20 token accounts, owners classified, pools excluded from concentration."""
    res, err = rpc("getTokenLargestAccounts", [mint])
    vals = (res or {}).get("value") if res else None
    if not vals:
        return {"error": err or "none"}
    accts = [{"account": v["address"], "ui": float(v.get("uiAmountString") or 0)} for v in vals]
    owners = {}
    info = {}
    for i in range(0, len(accts), 100):
        r2, e2 = rpc("getMultipleAccounts", [[a["account"] for a in accts[i:i + 100]],
                                             {"encoding": "jsonParsed"}])
        for a, v in zip(accts[i:i + 100], ((r2 or {}).get("value") or [])):
            if v and isinstance(v.get("data"), dict):
                owners[a["account"]] = v["data"]["parsed"]["info"].get("owner")
    ow = sorted({o for o in owners.values() if o})
    for i in range(0, len(ow), 100):
        r3, e3 = rpc("getMultipleAccounts", [ow[i:i + 100],
                                             {"encoding": "base64",
                                              "dataSlice": {"offset": 0, "length": 0}}])
        for o, v in zip(ow[i:i + 100], ((r3 or {}).get("value") or [])):
            info[o] = (v or {}).get("owner")
    pools, wallets = [], []
    for a in accts:
        o = owners.get(a["account"])
        prog = info.get(o)
        is_pool = (o in AUTHORITIES) or (prog in PROGRAMS) or (prog not in (SYSTEM, None))
        rec = dict(a, owner=o, owner_program=PROGRAMS.get(prog, prog),
                   pct_of_supply=(100.0 * a["ui"] / supply_ui) if supply_ui else None)
        (pools if is_pool else wallets).append(rec)
    top10 = sum(w["ui"] for w in wallets[:10])
    return {"top20": accts and (pools + wallets),
            "pool_accounts": pools[:8], "top_wallets": wallets[:10],
            "top1_wallet_pct": (100.0 * wallets[0]["ui"] / supply_ui) if (wallets and supply_ui) else None,
            "top10_wallet_pct": (100.0 * top10 / supply_ui) if supply_ui else None,
            "note": "pool vaults excluded from the wallet concentration figures"}


def pools_from_pairs(mint, pair_addresses, sol):
    """Read each candidate pool account's vaults from chain. Any quote asset."""
    rows = []
    for pair in pair_addresses:
        res, err = rpc("getAccountInfo", [pair, {"encoding": "base64",
                                                 "dataSlice": {"offset": 0, "length": 0}}])
        v = (res or {}).get("value") if res else None
        if not v:
            rows.append({"pool": pair, "exists": False, "error": err})
            continue
        prog = v.get("owner")
        r = {"pool": pair, "exists": True, "venue": PROGRAMS.get(prog, prog)}
        if prog == "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P":
            res2, _ = rpc("getAccountInfo", [pair, {"encoding": "base64"}])
            import base64
            raw = base64.b64decode(res2["value"]["data"][0])
            bc = bonding_curve(raw)
            r.update(bonding_curve=bc,
                     quote_usd=(bc["real_sol_reserves_sol"] * sol) if bc else None,
                     quote_asset="SOL")
            rows.append(r)
            continue
        vaults, verr = onchain_reserves.vaults(pair)
        r["vault_error"] = verr
        base_ui = (vaults or {}).get(mint)
        q = {m: a for m, a in (vaults or {}).items() if m != mint and a > 0}
        best = None
        for m, a in q.items():
            usd = quote_usd(m, a, sol)
            if usd is not None and (best is None or usd > best[1]):
                best = (m, usd, a)
        if best:
            r.update(quote_asset=QUOTES.get(best[0], best[0][:8]), quote_ui=best[2],
                     quote_usd=best[1])
        else:
            r.update(quote_asset=None, quote_usd=None,
                     other_vaults={m: a for m, a in list(q.items())[:4]})
        r["base_in_pool_ui"] = base_ui
        rows.append(r)
    rows.sort(key=lambda r: -(r.get("quote_usd") or 0))
    return rows


def vet(mint, label=""):
    t0 = time.time()
    sol = asset_usd(WSOL)
    out = {"mint": mint, "label": label, "ts": int(time.time()), "sol_usd": sol}
    out["chain_mint"] = mint_account(mint)
    dec = out["chain_mint"].get("decimals") or 0
    sup = out["chain_mint"].get("supply_ui") or 0
    out["chain_holders"] = largest_holders(mint, sup, dec)

    # third party, each labelled, used only to POINT at pools
    st, b = get("https://lite-api.jup.ag/tokens/v2/search?query=" + mint)
    jt = b[0] if isinstance(b, list) and b else {}
    out["jupiter_token"] = {k: jt.get(k) for k in
                            ("symbol", "name", "usdPrice", "mcap", "fdv", "liquidity",
                             "holderCount", "organicScore", "organicScoreLabel",
                             "isVerified", "launchpad", "graduatedAt", "audit", "tags")}
    out["jupiter_token"]["vol24"] = sum(((jt.get("stats24h") or {}).get(k) or 0)
                                        for k in ("buyVolume", "sellVolume"))
    st, b = get("https://api.dexscreener.com/latest/dex/tokens/" + mint)
    dxp = (b or {}).get("pairs") or [] if isinstance(b, dict) else []
    out["dexscreener"] = [{"pair": p.get("pairAddress"), "dex": p.get("dexId"),
                           "quote": (p.get("quoteToken") or {}).get("symbol"),
                           "liq_usd": (p.get("liquidity") or {}).get("usd"),
                           "vol24": (p.get("volume") or {}).get("h24"),
                           "price_usd": p.get("priceUsd")} for p in dxp]
    st, b = get(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint}/pools?page=1")
    gtp = [d["attributes"].get("address") for d in ((b or {}).get("data") or [])] if isinstance(b, dict) else []

    cands = []
    for a in [p.get("pairAddress") for p in dxp] + gtp:
        if a and a not in cands:
            cands.append(a)
    out["chain_pools"] = pools_from_pairs(mint, cands[:14], sol)
    out["chain_quote_usd_total"] = sum(r.get("quote_usd") or 0 for r in out["chain_pools"])

    # the number that matters: what a real exit costs at his clip
    out["round_trips"] = {}
    for usd in (100, 500, 2000):
        rt = chainfields.round_trip(mint, usd)
        out["round_trips"][usd] = {k: rt.get(k) for k in
                                   ("verdict", "usd_back", "rt_cost_pct", "venues",
                                    "price_impact_pct", "error")}
        time.sleep(0.3)

    st, b = get(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report")
    if isinstance(b, dict):
        out["rugcheck"] = {"rugged": b.get("rugged"), "score": b.get("score_normalised"),
                           "totalMarketLiquidity": b.get("totalMarketLiquidity"),
                           "risks": [r.get("name") for r in (b.get("risks") or [])],
                           "markets": [{"pool": m.get("pubkey"), "type": m.get("marketType"),
                                        "lpLockedPct": (m.get("lp") or {}).get("lpLockedPct")}
                                       for m in (b.get("markets") or [])][:6]}
    else:
        out["rugcheck"] = {"status": st}
    out["seconds"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    targets = []
    for arg in sys.argv[1:]:
        if ":" in arg:
            a, l = arg.split(":", 1)
        else:
            a, l = arg, ""
        targets.append((a, l))
    os.makedirs(os.path.join(HERE, "vet"), exist_ok=True)
    for mint, label in targets:
        try:
            r = vet(mint, label)
        except Exception as e:
            print(f"{label or mint} FAILED {type(e).__name__}: {str(e)[:140]}")
            continue
        with io.open(os.path.join(HERE, "vet", mint + ".json"), "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1, ensure_ascii=False, default=str)
        cm = r["chain_mint"]
        rts = r["round_trips"]
        print(f"\n{label or mint}  {mint}")
        print(f"  supply {cm.get('supply_ui'):,.0f} dec {cm.get('decimals')} "
              f"program {'Token-2022' if cm.get('is_token_2022') else 'SPL'} "
              f"ext {cm.get('extensions')}")
        print(f"  mint authority: {cm.get('mint_authority') or 'REVOKED'} | "
              f"freeze authority: {cm.get('freeze_authority') or 'REVOKED'}")
        ch = r["chain_holders"]
        print(f"  top wallet {ch.get('top1_wallet_pct') and round(ch['top1_wallet_pct'],2)}% | "
              f"top10 wallets {ch.get('top10_wallet_pct') and round(ch['top10_wallet_pct'],2)}% of supply")
        print(f"  CHAIN pool depth total ${r['chain_quote_usd_total']:,.0f} "
              f"over {len(r['chain_pools'])} pools; jupiter says ${(r['jupiter_token'].get('liquidity') or 0):,.0f}")
        for p in r["chain_pools"][:4]:
            print(f"    {str(p.get('venue'))[:24]:24s} {p['pool'][:12]} "
                  f"{str(p.get('quote_asset')):8s} ${(p.get('quote_usd') or 0):,.0f}")
        for usd in (100, 500, 2000):
            q = rts[usd]
            print(f"  ${usd:>5} round trip: {q['verdict']:<14} back ${q['usd_back']} "
                  f"cost {q['rt_cost_pct']}% via {q['venues']}")
        print(f"  rugcheck: {r['rugcheck'].get('risks')} LP {[m.get('lpLockedPct') for m in (r['rugcheck'].get('markets') or [])]}")
