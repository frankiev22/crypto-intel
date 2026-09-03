"""
Multi-source token resolution, and the difference between "our source went
quiet" and "the token died".

WHY. On 2026-09-03 ten tokens we were tracking returned no pairs from
Dexscreener and the system recorded them as gone. Frank's correction: coins do
not stop existing, nothing gets deleted from a blockchain. He is right. Probed
live, every one of them still resolved:

    RETA    dexscreener NO PAIRS | geckoterminal $0.0000375, reserve $0.10
    Wojak   dexscreener NO PAIRS | geckoterminal $0.0088,    reserve $0.00019
    SOLDOG  dexscreener NO PAIRS | geckoterminal $0.000157,  reserve $0.0000004
    SXS     dexscreener NO PAIRS | geckoterminal $0.092,     reserve $0.000023

All four have supply on chain. Dexscreener stops INDEXING pairs whose reserves
collapse; the token itself is untouched. Recording that as "gone" destroyed the
outcome label and hid the real fact, which is that liquidity was pulled while
the price was still non-zero.

THREE DIFFERENT FACTS, never again collapsed into one:

    source_dropped    the primary index went quiet. Says nothing about value.
    liquidity_pulled  the pool drained. You cannot exit. Price may be anything.
    price_to_zero     the price actually went to zero.

A token can be any combination. The fourth above is source_dropped AND
liquidity_pulled with an FDV of $92,195,183 - a market cap with twenty-three
thousandths of a dollar behind it. That is the number an exit model has to
refuse to believe.

Everything here is free and keyless: Dexscreener, GeckoTerminal and the public
Solana RPC. GeckoTerminal is rate-limited hard (~10-15 calls/min measured), so
it is a FALLBACK only, reached when the primary is silent.
"""
import json, os, time, datetime as dt

import sources as S
from scanner import CFG as _CFG

SOL_MINT = "So11111111111111111111111111111111111111112"

# Below this a pool cannot be exited in any size worth having. Same floor the
# scanner uses to enter, so entry and exit stop disagreeing with each other.
MIN_EXIT_LIQ_USD = _CFG["min_liquidity_usd"]
DUST_LIQ_USD = 100.0          # below this, "liquidity" is a rounding error
ZERO_PRICE = 1e-12

BASE = os.path.dirname(os.path.abspath(__file__))
SRC_LOG = os.path.join(BASE, "data", "source_health")

HEALTH = {"dexscreener_ok": 0, "dexscreener_dropped": 0,
          "geckoterminal_ok": 0, "geckoterminal_fail": 0,
          "onchain_ok": 0, "onchain_fail": 0, "unresolved": 0}


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _dexscreener(chain, token):
    """Primary. Richest payload, and the one that goes quiet."""
    pairs = S.dexscreener_token(token)
    if not pairs:
        return None
    # Sum liquidity across ALL pairs, do not take the deepest one. A token can
    # be split across pump.fun, PumpSwap and Raydium at once, and reading only
    # the top pool understates what is actually exitable.
    total_liq = sum(_f((p.get("liquidity") or {}).get("usd"), 0) or 0 for p in pairs)
    best = max(pairs, key=lambda p: _f((p.get("liquidity") or {}).get("usd"), 0) or 0)
    return {"price_usd": _f(best.get("priceUsd")),
            "liq_usd": total_liq,
            "liq_top_pair": _f((best.get("liquidity") or {}).get("usd"), 0),
            "pairs": len(pairs),
            "fdv": _f(best.get("fdv")),
            "mcap": _f(best.get("marketCap")),
            "dex": best.get("dexId"),
            "source": "dexscreener"}


def _geckoterminal(chain, token):
    """Fallback. Proved on 2026-09-03 to still answer for every token
    Dexscreener had dropped."""
    d = S._get(f"https://api.geckoterminal.com/api/v2/networks/{chain}/tokens/{token}",
               tries=1, timeout=15)
    a = (d.get("data") or {}).get("attributes") or {}
    if not a:
        return None
    return {"price_usd": _f(a.get("price_usd")),
            "liq_usd": _f(a.get("total_reserve_in_usd"), 0),
            "liq_top_pair": None,
            "pairs": None,
            "fdv": _f(a.get("fdv_usd")),
            "mcap": _f(a.get("market_cap_usd")),
            "dex": None,
            "source": "geckoterminal"}


def _on_chain(token):
    """Existence, from the chain itself. Free public RPC, no key."""
    r = S._post(S.SOL_RPC, {"jsonrpc": "2.0", "id": 1,
                            "method": "getTokenSupply", "params": [token]})
    v = (r.get("result") or {}).get("value")
    if not v:
        return None
    return {"supply": _f(v.get("uiAmountString")), "decimals": v.get("decimals")}


def resolve(token, chain="solana", want_onchain=True):
    """Best available truth about a token, with the reason recorded distinctly.

    Never raises. `reasons` is a LIST because a token can be source_dropped and
    liquidity_pulled at the same time and both facts matter.
    """
    out = {"token": token, "chain": chain,
           "checked_at": dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds"),
           "source": None, "reasons": [], "price_usd": None, "liq_usd": None,
           "fdv": None, "mcap": None, "on_chain": None, "exitable": False,
           "pairs": None, "liq_top_pair": None}

    data = None
    try:
        data = _dexscreener(chain, token)
        if data:
            HEALTH["dexscreener_ok"] += 1
        else:
            HEALTH["dexscreener_dropped"] += 1
            out["reasons"].append("source_dropped")
    except Exception:
        HEALTH["dexscreener_dropped"] += 1
        out["reasons"].append("source_dropped")

    if not data:
        try:
            data = _geckoterminal(chain, token)
            if data:
                HEALTH["geckoterminal_ok"] += 1
            else:
                HEALTH["geckoterminal_fail"] += 1
        except Exception:
            HEALTH["geckoterminal_fail"] += 1

    if data:
        for k in ("price_usd", "liq_usd", "fdv", "mcap", "source",
                  "pairs", "liq_top_pair"):
            out[k] = data.get(k)
        liq = out["liq_usd"] or 0
        px = out["price_usd"] or 0
        if px <= ZERO_PRICE:
            out["reasons"].append("price_to_zero")
        if liq < DUST_LIQ_USD:
            out["reasons"].append("liquidity_pulled")
        out["exitable"] = liq >= MIN_EXIT_LIQ_USD and px > ZERO_PRICE
    else:
        HEALTH["unresolved"] += 1
        out["reasons"].append("unresolved")

    if want_onchain and chain == "solana":
        try:
            oc = _on_chain(token)
            out["on_chain"] = bool(oc and oc.get("supply"))
            if oc:
                out["supply"] = oc["supply"]
                HEALTH["onchain_ok"] += 1
            else:
                HEALTH["onchain_fail"] += 1
        except Exception:
            HEALTH["onchain_fail"] += 1

    if not out["reasons"]:
        out["reasons"].append("ok")
    return out


def log_health():
    """Append the per-source tally. If Dexscreener is a single point of failure
    it should at least be a measured one."""
    os.makedirs(SRC_LOG, exist_ok=True)
    row = {"ts": int(time.time()), **HEALTH}
    fp = os.path.join(SRC_LOG,
                      dt.datetime.now(dt.timezone.utc).strftime("%Y-%m") + ".jsonl")
    try:
        with open(fp, "a", encoding="utf-8") as f:
            f.write(json.dumps(row, separators=(",", ":")) + "\n")
    except OSError:
        pass
    return row


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ca in sys.argv[1:]:
        r = resolve(ca)
        print(f"\n  {ca}")
        print(f"    source   : {r['source']}   reasons: {', '.join(r['reasons'])}")
        print(f"    price    : {r['price_usd']}")
        print(f"    liquidity: {r['liq_usd']}   exitable: {r['exitable']}")
        print(f"    fdv      : {r['fdv']}   on chain: {r['on_chain']}")
