"""
Mint -> human symbol and USD price.

Whale lines are worthless without this. "swap on JUPITER" tells you nothing;
"sold $2,400 of BONK" is the whole point. Both lookups are cached on disk
because the same mints repeat constantly and Birdeye is rate limited to
roughly one request a second.

Symbols come from the Helius DAS getAsset call, prices from Birdeye (the paid
key). Either can fail, and when it does the caller is told it does not know
rather than being handed a placeholder.
"""
import json, os, time

import config
import sources as S

CACHE = "data/token_cache.json"
PRICE_TTL = 600          # seconds; prices go stale fast
SOL_MINT = "So11111111111111111111111111111111111111112"

_mem = None


def _load():
    global _mem
    if _mem is None:
        try:
            _mem = json.load(open(CACHE))
        except Exception:
            _mem = {"symbols": {}, "prices": {}}
        _mem.setdefault("symbols", {})
        _mem.setdefault("prices", {})
    return _mem


def _save():
    if _mem is None:
        return
    os.makedirs("data", exist_ok=True)
    tmp = CACHE + ".tmp"
    with open(tmp, "w") as f:
        json.dump(_mem, f)
    os.replace(tmp, CACHE)


def symbol(mint):
    """Ticker for a mint, or None if nothing authoritative is available.
    Never invents one from the address."""
    if not mint:
        return None
    if mint == SOL_MINT:
        return "SOL"
    c = _load()["symbols"]
    if mint in c:
        return c[mint] or None
    sym = None
    try:
        d = S._post(config.helius_rpc(), {
            "jsonrpc": "2.0", "id": 1, "method": "getAsset",
            "params": {"id": mint}})
        r = d.get("result") or {}
        sym = ((r.get("content") or {}).get("metadata") or {}).get("symbol") or None
        if sym:
            sym = sym.strip()[:12] or None
    except Exception:
        sym = None
    c[mint] = sym or ""
    _save()
    return sym


def price_usd(mint):
    """USD per whole token, or None. Birdeye only - no guessing."""
    if not mint or not config.have("birdeye"):
        return None
    c = _load()["prices"]
    hit = c.get(mint)
    if hit and time.time() - hit.get("at", 0) < PRICE_TTL:
        return hit.get("usd")
    usd = None
    try:
        # Birdeye allows roughly one request a second and answers 429 above that.
        # tries=3 lets sources._get back off instead of us treating a rate limit
        # as "this token has no price".
        d = S._get(f"https://public-api.birdeye.so/defi/price?address={mint}",
                   tries=3, headers={"X-API-KEY": config.key("birdeye"), "x-chain": "solana"})
        if d.get("success"):
            usd = (d.get("data") or {}).get("value")
    except Exception:
        usd = None
    # Never cache a failure. A cached None is indistinguishable from "worthless"
    # and silently suppressed a $7,400 alert the first time this ran.
    if usd is not None:
        c[mint] = {"usd": usd, "at": time.time()}
        _save()
    return usd


def usd_value(mint, amount):
    """Dollar value of `amount` whole tokens, or None when unknown."""
    if amount is None:
        return None
    p = price_usd(mint)
    return None if p is None else p * amount


def money(usd):
    """Compact dollar string for a phone screen."""
    if usd is None:
        return None
    a = abs(usd)
    if a >= 1_000_000: return f"${usd/1e6:.1f}M"
    if a >= 1_000:     return f"${usd/1e3:.1f}k"
    if a >= 1:         return f"${usd:,.0f}"
    return f"${usd:.2f}"
