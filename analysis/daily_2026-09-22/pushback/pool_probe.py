"""Venue-agnostic pool finder: try to FALSIFY "drained" for a mint.

Frank, 2026-09-22: "I highly doubt ember is completely dead ... How are the pools
no longer existing? That seems impossible to me."

This morning's "every pool under $100" came from ONE source: Dexscreener's
/latest/dex/tokens `liquidity.usd`. This reads the chain instead, two
independent ways, and does not need to know the venue in advance:

  A. EVERY token account for the mint (Helius DAS getTokenAccounts, all pages).
     A pool must hold the token in a token account, so every pool for the mint,
     on any venue, is in this list. Each account's OWNER is then looked up and
     classified by the program that owns it: an AMM program = the owner is a
     pool; a known AMM authority PDA = a vault; System = a wallet; anything else
     is reported raw, never dropped.
  B. getProgramAccounts memcmp on the mint at each AMM's pool-layout offsets
     (PumpSwap, Raydium v4/CPMM/CLMM, Orca Whirlpool, Meteora DLMM/DAMM v1/v2).
     Finds a pool even if it holds zero of the token.

For every pool found: does the account exist, which program owns it, and what
sits in its quote-side vault (SOL/USDC/USDT) right now, from chain.

Third-party reads alongside, LABELLED as such and never mixed into the chain
figures: Jupiter round trip + price + token stats, Dexscreener, GeckoTerminal,
RugCheck (all keyless GETs except Jupiter, which uses our free key if present).

Prints no key. Writes one JSON per mint under ./probe/.
"""
import base64
import io
import json
import os
import struct
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import chainfields  # noqa: E402
import onchain_reserves  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; +https://github.com)"}
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrJKsWFsFd8e25wJdkX8DBMLoMKNfuLDQy2Ae4Z"
QUOTES = {WSOL: "SOL", USDC: "USDC", USDT: "USDT"}
TOKEN = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSTEM = "11111111111111111111111111111111"

PROGRAMS = {
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pump.fun bonding curve",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "PumpSwap AMM",
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "Raydium AMM v4",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "Raydium CPMM",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "Raydium CLMM",
    "LanMV9sAd7wArD4vJFi2qDdfnVhFxYSUg6eADduJ3uj": "Raydium LaunchLab",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "Orca Whirlpool",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "Meteora DLMM",
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": "Meteora DAMM v1",
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "Meteora DAMM v2",
    "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN": "Meteora DBC",
    "24Uqj9JCLxUeoC3hGfh5W3s9FM9uCHDS2SG3LYwBpyTi": "Meteora vault (DAMM v1)",
    "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG": "Moonshot",
    "boop8hVGQGqehUK2iVEMEnMrL5RbjywRzHKBmBE7ry4": "Boop",
    "2wT8Yq49kHgDzXuPxZSaeLaH1qbmGXtEyPy64bL7aD3c": "Lifinity v2",
    "PhoeNiXZ8ByJGLkxNfZRnkUfjvmuYqLR89jjFHGqdXY": "Phoenix",
    "opnb2LAfJYbRMAHHvqjCwQxanZn7ReEHp1k81EohpZb": "OpenBook v2",
}
# Vaults on these venues are owned by one shared authority PDA, not the pool.
AUTHORITIES = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "Raydium AMM v4",
    "GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL": "Raydium CPMM",
    "WLHv2UAZm6z4KyaaELi5pjdbJh6RESMva1Rnn8pJVVh": "Raydium LaunchLab",
    "HLnpSz9h2S4hiLQ43rnSD9XkcUThA7B8hQMKmDaiTLcC": "Meteora DAMM v2",
    "FhVo3mqL8PW5pH5U2CN4XE33DokiyZnUwuGpH2hmHLuM": "Meteora DBC",
}
# (program, [(mint offset, other-mint offset, base-vault off, quote-vault off)])
# Offsets are the published Anchor/Borsh layouts. A layout I have wrong returns
# nothing, which is why method A exists: B can miss, A cannot.
GPA = [
    ("pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA", [(43, 75, 139, 171), (75, 43, 171, 139)]),
    ("675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8", [(400, 432, 336, 368), (432, 400, 368, 336)]),
    ("CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C", [(168, 200, 72, 104), (200, 168, 104, 72)]),
    ("CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK", [(73, 105, 137, 169), (105, 73, 169, 137)]),
    ("whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc", [(101, 181, 133, 213), (181, 101, 213, 133)]),
    ("LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo", [(88, 120, 152, 184), (120, 88, 184, 152)]),
    ("cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG", [(168, 200, 232, 264), (200, 168, 264, 232)]),
    ("Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB", [(40, 72, None, None), (72, 40, None, None)]),
]

CALLS = {"rpc": 0, "http": 0}


def rpc(method, params, timeout=60):
    CALLS["rpc"] += 1
    return chainfields._rpc(method, params, timeout=timeout)


def get(url, headers=None):
    CALLS["http"] += 1
    return chainfields._get(url, headers=headers or UA, timeout=20)


def b58(raw):
    return onchain_reserves.b58(raw)


def all_token_accounts(mint, max_pages=60):
    out, cursor, pages = [], None, 0
    key = chainfields._HOLDER_MINT_KEY[0]
    while True:
        p = {key: mint, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        res, err = rpc("getTokenAccounts", p)
        if err:
            return out, f"page {pages}: {err}", pages >= max_pages
        accts = (res or {}).get("token_accounts") or []
        out.extend(accts)
        pages += 1
        cursor = (res or {}).get("cursor")
        if not cursor or not accts or pages >= max_pages:
            return out, None, bool(cursor) and pages >= max_pages


def multi_accounts(addrs):
    """addr -> {exists, owner, lamports, data_len, data(b64 bytes or None)}"""
    info = {}
    for i in range(0, len(addrs), 100):
        chunk = addrs[i:i + 100]
        res, err = rpc("getMultipleAccounts", [chunk, {"encoding": "base64"}])
        vals = (res or {}).get("value") if res else None
        if vals is None:
            for a in chunk:
                info[a] = {"exists": None, "error": err}
            continue
        for a, v in zip(chunk, vals):
            if v is None:
                info[a] = {"exists": False}
            else:
                raw = base64.b64decode(v["data"][0]) if v.get("data") else b""
                info[a] = {"exists": True, "owner": v.get("owner"),
                           "lamports": v.get("lamports"), "data_len": len(raw),
                           "raw": raw}
    return info


def token_balance(acct):
    res, err = rpc("getTokenAccountBalance", [acct])
    if err or not res:
        return None, err
    v = res.get("value") or {}
    try:
        return float(v.get("uiAmountString") or 0), None
    except ValueError:
        return None, "unparseable"


def token_accounts_of(owner):
    """Every SPL token account an owner holds (both token programs)."""
    rows = []
    for prog in (TOKEN, TOKEN22):
        res, err = rpc("getTokenAccountsByOwner",
                       [owner, {"programId": prog}, {"encoding": "jsonParsed"}])
        for v in ((res or {}).get("value") or []):
            info = v["account"]["data"]["parsed"]["info"]
            rows.append({"account": v["pubkey"], "mint": info["mint"],
                         "ui": float(info["tokenAmount"].get("uiAmountString") or 0)})
    return rows


def sol_usd():
    st, b = get("https://lite-api.jup.ag/price/v3?ids=" + WSOL)
    try:
        return float(b[WSOL]["usdPrice"]), "jupiter price v3"
    except Exception:
        st, b = get("https://api.coingecko.com/api/v3/simple/price?ids=solana&vs_currencies=usd")
        return float(b["solana"]["usd"]), "coingecko"


_PX = {}


def asset_usd(mint):
    """USD price of ANY quote asset, cached. ⛔ A pool quoted in a memecoin is
    still a pool: STONKBROS' only real market is a Raydium CPMM quoted in STONK,
    and valuing only SOL/USDC/USDT read it as $0.03 while Jupiter sold $100 of
    it for $94. Depth in a quote asset that is not money is reported with the
    asset named, never silently dropped."""
    if mint in _PX:
        return _PX[mint]
    st, b = get("https://lite-api.jup.ag/price/v3?ids=" + mint)
    px = None
    try:
        px = float(b[mint]["usdPrice"])
    except Exception:
        px = None
    _PX[mint] = px
    return px


def quote_usd(mint, ui, sol):
    if mint == WSOL:
        return ui * sol
    if mint in (USDC, USDT):
        return ui
    px = asset_usd(mint)
    return (ui * px) if px is not None else None


def bonding_curve(raw):
    """pump.fun BondingCurve: real_sol_reserves @32, complete @48."""
    if len(raw) < 49:
        return None
    vt, vs, rt, rs, ts = struct.unpack_from("<QQQQQ", raw, 8)
    return {"real_sol_reserves_sol": rs / 1e9, "real_token_reserves_raw": rt,
            "complete": bool(raw[48])}


def gpa_pools(mint):
    found = {}
    errors = []
    for prog, layouts in GPA:
        for (moff, ooff, bvo, qvo) in layouts:
            res, err = rpc("getProgramAccounts",
                           [prog, {"encoding": "base64",
                                   "filters": [{"memcmp": {"offset": moff, "bytes": mint}}]}],
                           timeout=90)
            if err:
                errors.append(f"{PROGRAMS[prog]} @{moff}: {err}")
                continue
            for v in res or []:
                raw = base64.b64decode(v["account"]["data"][0])
                other = b58(raw[ooff:ooff + 32]) if len(raw) >= ooff + 32 else None
                rec = {"venue": PROGRAMS[prog], "program": prog, "pool": v["pubkey"],
                       "other_mint": other, "data_len": len(raw),
                       "lamports": v["account"].get("lamports")}
                if bvo is not None and len(raw) >= max(bvo, qvo) + 32:
                    rec["mint_vault"] = b58(raw[bvo:bvo + 32])
                    rec["other_vault"] = b58(raw[qvo:qvo + 32])
                found[v["pubkey"]] = rec
    return found, errors


def probe(mint, recorded_pairs=()):
    t0 = time.time()
    sol, sol_src = sol_usd()
    out = {"mint": mint, "ts": int(time.time()), "sol_usd": sol, "sol_usd_src": sol_src,
           "recorded_pairs": list(recorded_pairs)}

    # --- the mint itself
    res, err = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    v = (res or {}).get("value") if res else None
    if v:
        info = v["data"]["parsed"]["info"]
        out["mint_account"] = {"program": v["owner"], "decimals": info.get("decimals"),
                               "supply_ui": float(info.get("supply") or 0) / 10 ** info.get("decimals", 0),
                               "mint_authority": info.get("mintAuthority"),
                               "freeze_authority": info.get("freezeAuthority")}
    else:
        out["mint_account"] = {"exists": False if res else None, "error": err}

    # --- A: every token account, owners classified
    accts, err, trunc = all_token_accounts(mint)
    out["token_accounts"] = {"n": len(accts), "error": err, "truncated": trunc}
    owners = {}
    for a in accts:
        try:
            amt = float(a.get("amount") or 0)
        except (TypeError, ValueError):
            amt = 0.0
        o = a.get("owner")
        d = owners.setdefault(o, {"amount_raw": 0.0, "accounts": []})
        d["amount_raw"] += amt
        d["accounts"].append(a.get("address"))
    out["holders_nonzero"] = sum(1 for d in owners.values() if d["amount_raw"] > 0)
    oinfo = multi_accounts(list(owners))
    pools, wallets, other, unclassified = {}, 0, {}, {}
    dec = (out.get("mint_account") or {}).get("decimals") or 0
    for o, d in owners.items():
        i = oinfo.get(o) or {}
        prog = i.get("owner")
        ui = d["amount_raw"] / 10 ** dec
        if o in AUTHORITIES:
            pools[o] = {"kind": "authority-held vault", "venue": AUTHORITIES[o],
                        "mint_ui": ui, "vaults": d["accounts"]}
        elif prog in PROGRAMS:
            pools[o] = {"kind": "pool-owned vault", "venue": PROGRAMS[prog], "program": prog,
                        "mint_ui": ui, "vaults": d["accounts"], "raw": i.get("raw")}
        elif prog == SYSTEM:
            wallets += 1
        else:
            # ⛔ ANY other program that owns a token account holding this mint is
            # a pool on a venue this script does not have hardcoded. Treating
            # unknown as "not a pool" is what made STONKBROS read $0.03 on chain
            # while Jupiter sold $100 of it for $94: its venue (stonk.fun) was
            # not in PROGRAMS. Unknown venues are now probed the same way, and
            # the program id is reported raw so the gap is visible.
            key = prog if i.get("exists") else ("no account" if i.get("exists") is False else "unread")
            other.setdefault(key, {"owners": 0, "mint_ui": 0.0})
            other[key]["owners"] += 1
            other[key]["mint_ui"] += ui
            if ui > 0 and i.get("exists"):
                # ⚠️ AND IT IS A CANDIDATE, NOT A POOL. Counting every
                # program-owned account that holds the mint plus some WSOL put
                # EMBER at $37,220 when its real pools hold $20: MEV bot vaults
                # and aggregator accounts match the same shape. These are
                # reported and totalled SEPARATELY, and Jupiter's round trip is
                # the arbiter of whether any of it is sellable.
                unclassified[o] = {"kind": "UNCLASSIFIED owner holding the mint",
                                   "venue": f"unknown program {key}", "program": prog,
                                   "mint_ui": ui, "vaults": d["accounts"]}
    out["owner_classes"] = {"system_wallets": wallets,
                            "other": {PROGRAMS.get(k, k): v for k, v in other.items()}}

    # --- B: ask each AMM program directly
    gp, gerr = gpa_pools(mint)
    out["gpa_errors"] = gerr

    # --- merge, then read every pool's quote side from chain
    merged = {}
    for owner, p in pools.items():
        merged[owner] = dict(p)
        merged[owner]["found_by"] = ["token-account owner"]
    for pk, g in gp.items():
        m = merged.setdefault(pk, {"kind": "pool (gPA)", "venue": g["venue"], "found_by": []})
        m["found_by"].append("getProgramAccounts")
        m.update({k: g[k] for k in ("program", "other_mint", "mint_vault", "other_vault")
                  if k in g})
    for rp in recorded_pairs:
        if rp and rp not in merged:
            merged[rp] = {"kind": "recorded pair", "found_by": ["our outcome row"]}
    ainfo = multi_accounts(list(merged))
    rows = []
    for pk, m in merged.items():
        a = ainfo.get(pk) or {}
        r = {"pool": pk, "venue": m.get("venue"), "kind": m["kind"], "found_by": m["found_by"],
             "exists": a.get("exists"), "owner_program": PROGRAMS.get(a.get("owner"), a.get("owner")),
             "data_len": a.get("data_len"), "recorded": pk in recorded_pairs,
             "mint_in_pool_ui": m.get("mint_ui")}
        if m["kind"] == "authority-held vault":
            r["note"] = "shared authority PDA; the pool itself is found by gPA if its layout is right"
            rows.append(r)
            continue
        if a.get("owner") == "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P":
            bc = bonding_curve(a.get("raw") or b"")
            r["bonding_curve"] = bc
            if bc:
                r["quote"] = "SOL"
                r["quote_ui"] = bc["real_sol_reserves_sol"]
                r["quote_usd"] = bc["real_sol_reserves_sol"] * sol
        elif m.get("other_vault") and m.get("other_mint"):
            ui, e = token_balance(m["other_vault"])
            mv, _ = token_balance(m["mint_vault"]) if m.get("mint_vault") else (None, None)
            r.update(quote=QUOTES.get(m["other_mint"], "asset " + m["other_mint"][:8]),
                     quote_vault=m["other_vault"], quote_ui=ui,
                     quote_usd=quote_usd(m["other_mint"], ui, sol) if ui is not None else None,
                     mint_in_pool_ui=mv if mv is not None else r["mint_in_pool_ui"],
                     read_error=e)
        elif a.get("exists"):
            held = token_accounts_of(pk)
            q = [h for h in held if h["mint"] != mint and h["ui"] > 0]
            mt = [h for h in held if h["mint"] == mint]
            if q:
                r["quote"] = "+".join(QUOTES.get(h["mint"], "asset " + h["mint"][:8]) for h in q)
                r["quote_ui"] = sum(h["ui"] for h in q)
                r["quote_usd"] = sum(quote_usd(h["mint"], h["ui"], sol) or 0 for h in q)
            else:
                r["quote"] = [h["mint"] for h in held if h["mint"] != mint] or None
                r["quote_usd"] = None
                r["note"] = "no SOL/USDC/USDT vault owned by this account"
            if mt:
                r["mint_in_pool_ui"] = sum(h["ui"] for h in mt)
        if r.get("quote_usd") is not None and r.get("mint_in_pool_ui"):
            r["implied_price_usd"] = r["quote_usd"] / r["mint_in_pool_ui"]
        rows.append(r)
    rows.sort(key=lambda r: -(r.get("quote_usd") or 0))
    out["pools"] = rows
    out["chain_quote_usd_total"] = sum(r.get("quote_usd") or 0 for r in rows)
    # Unclassified owners: reported, never added to the headline figure.
    urows = []
    for owner, u in sorted(unclassified.items(), key=lambda kv: -kv[1]["mint_ui"])[:12]:
        held = token_accounts_of(owner)
        q = [h for h in held if h["mint"] in QUOTES]
        urows.append({"owner": owner, "program": u["program"], "mint_ui": u["mint_ui"],
                      "quote_usd": sum(quote_usd(h["mint"], h["ui"], sol) or 0 for h in q) or None,
                      "n_token_accounts": len(held)})
    out["unclassified_owners"] = urows
    out["unclassified_quote_usd"] = sum(r.get("quote_usd") or 0 for r in urows)

    # --- third parties, labelled
    tp = {}
    try:
        tp["jupiter_round_trip_100"] = chainfields.round_trip(mint, 100)
    except Exception as e:
        tp["jupiter_round_trip_100"] = {"error": str(e)[:120]}
    st, b = get("https://lite-api.jup.ag/tokens/v2/search?query=" + mint)
    if isinstance(b, list) and b:
        j = b[0]
        tp["jupiter_token"] = {k: j.get(k) for k in ("symbol", "name", "holderCount", "liquidity",
                                                        "mcap", "fdv", "usdPrice", "organicScore",
                                                        "graduatedPool", "graduatedAt", "launchpad")}
        tp["jupiter_token"]["volume24h"] = sum(
            ((j.get("stats24h") or {}).get(k) or 0) for k in ("buyVolume", "sellVolume"))
    else:
        tp["jupiter_token"] = {"status": st}
    st, b = get("https://api.dexscreener.com/latest/dex/tokens/" + mint)
    tp["dexscreener"] = [{"pair": p.get("pairAddress"), "dex": p.get("dexId"),
                          "labels": p.get("labels"),
                          "liq_usd": (p.get("liquidity") or {}).get("usd"),
                          "liq_quote": (p.get("liquidity") or {}).get("quote"),
                          "vol24": (p.get("volume") or {}).get("h24"),
                          "price_usd": p.get("priceUsd"),
                          "quote": (p.get("quoteToken") or {}).get("symbol")}
                         for p in ((b or {}).get("pairs") or [])] if isinstance(b, dict) else {"status": st}
    st, b = get(f"https://api.geckoterminal.com/api/v2/networks/solana/tokens/{mint}/pools?page=1")
    if isinstance(b, dict) and b.get("data") is not None:
        tp["geckoterminal"] = [{"pool": d["attributes"].get("address"),
                                "dex": ((d.get("relationships") or {}).get("dex") or {}).get("data", {}).get("id"),
                                "reserve_usd": d["attributes"].get("reserve_in_usd"),
                                "vol24": (d["attributes"].get("volume_usd") or {}).get("h24")}
                               for d in b["data"]]
    else:
        tp["geckoterminal"] = {"status": st}
    st, b = get(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report")
    if isinstance(b, dict):
        tp["rugcheck"] = {"totalHolders": b.get("totalHolders"),
                          "totalMarketLiquidity": b.get("totalMarketLiquidity"),
                          "rugged": b.get("rugged"),
                          "markets": [{"pool": m.get("pubkey"), "type": m.get("marketType"),
                                       "lpLockedPct": (m.get("lp") or {}).get("lpLockedPct"),
                                       "lpLockedUSD": (m.get("lp") or {}).get("lpLockedUSD"),
                                       "quoteUSD": (m.get("lp") or {}).get("quoteUSD")}
                                      for m in (b.get("markets") or [])],
                          "risks": [r.get("name") for r in (b.get("risks") or [])]}
    else:
        tp["rugcheck"] = {"status": st}
    out["third_party"] = tp
    out["calls"] = dict(CALLS)
    out["seconds"] = round(time.time() - t0, 1)
    return out


if __name__ == "__main__":
    mint = sys.argv[1]
    rec = sys.argv[2:]
    r = probe(mint, rec)
    os.makedirs(os.path.join(HERE, "probe"), exist_ok=True)
    p = os.path.join(HERE, "probe", mint + ".json")
    tmp = p + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(r, f, indent=1, ensure_ascii=False, default=str)
    os.replace(tmp, p)
    print(json.dumps({k: r[k] for k in ("mint_account", "token_accounts", "holders_nonzero",
                                        "owner_classes", "gpa_errors", "chain_quote_usd_total",
                                        "calls", "seconds")}, indent=1, default=str))
    for row in r["pools"][:15]:
        print({k: row.get(k) for k in ("pool", "venue", "found_by", "exists", "owner_program",
                                       "quote", "quote_ui", "quote_usd", "mint_in_pool_ui",
                                       "implied_price_usd", "recorded", "note", "bonding_curve")})
    print(json.dumps(r["third_party"], indent=1, default=str)[:4000])
