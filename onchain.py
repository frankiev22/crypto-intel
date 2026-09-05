"""Causes, not symptoms. Mint authority, freeze authority, holder concentration.

WHY. Everything the scanner has ever scored - price, liquidity, volume,
transaction counts - is an OUTPUT of how a token was constructed and who holds
it. None of it is a cause. That is a plausible explanation for why no
point-in-time feature has ever shown lift out of sample.

These are the two cheapest causal features and they need one public-RPC call
each. Free, keyless, no account.

    mint authority still live   -> the deployer can print more supply at will
    freeze authority still live -> the deployer can stop YOU selling
    top-N holder concentration  -> whether "the community" is one wallet

A TRAP IN HOLDER CONCENTRATION, and the reason this module reports three
numbers instead of one. `getTokenLargestAccounts` returns the pool's own token
account, which for a fresh launch holds nearly the entire supply. A naive
"top 10 share" is therefore ~99% for every token, healthy or not, and would
look like a devastating signal while measuring nothing. So we report the raw
share, the share excluding the single largest account, and whether the largest
account looks like the pool (it matches `liq_base` when we have it).

AN ASYMMETRY WORTH KNOWING FOR BACKFILL. On-chain state does not disappear -
Frank's point, and it is why this can be checked for every token we have ever
seen, unlike Dexscreener which drops 79% of them. But it is CURRENT state, and
authorities can be revoked after the fact. So:

    mint authority live NOW      => it was live at observation.  Sound.
    mint authority revoked NOW   => says nothing about observation time.

Only the first direction may be used retrospectively. The second needs the
value captured at observation time, which is why this runs in the scan.
"""
import os

import sources as S

# The public RPC is free and rate-limited. One call per feature per token.
RPC_PACE_S = float(os.environ.get("CRYPTO_RPC_PACE_S", "0.25"))
TOP_N = int(os.environ.get("CRYPTO_TOP_N_HOLDERS", "10"))


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def authorities(mint):
    """{mint_authority, freeze_authority, supply, decimals, can_mint,
    can_freeze}. One getAccountInfo call. Never raises."""
    out = {"mint_authority": None, "freeze_authority": None, "supply": None,
           "decimals": None, "can_mint": None, "can_freeze": None,
           "authorities_error": None}
    try:
        r = S._post(S.SOL_RPC, {"jsonrpc": "2.0", "id": 1,
                                "method": "getAccountInfo",
                                "params": [mint, {"encoding": "jsonParsed"}]})
        info = (((r.get("result") or {}).get("value") or {})
                .get("data", {}).get("parsed", {}).get("info"))
        if not info:
            out["authorities_error"] = "mint account not parsed"
            return out
        out["mint_authority"] = info.get("mintAuthority")
        out["freeze_authority"] = info.get("freezeAuthority")
        out["decimals"] = info.get("decimals")
        out["supply"] = _f(info.get("supply"))
        out["can_mint"] = bool(info.get("mintAuthority"))
        out["can_freeze"] = bool(info.get("freezeAuthority"))
    except Exception as e:
        out["authorities_error"] = f"{type(e).__name__}"
    return out


def concentration(mint, supply=None, liq_base=None, top_n=TOP_N):
    """Holder concentration, with the pool account handled explicitly.

    Returns raw top-N share, the share with the single largest account removed,
    and whether that largest account plausibly IS the pool.
    """
    out = {"holders_sampled": None, "top1_share": None,
           f"top{top_n}_share": None, f"top{top_n}_share_ex_largest": None,
           "largest_is_pool": None, "concentration_error": None}
    try:
        r = S._post(S.SOL_RPC, {"jsonrpc": "2.0", "id": 1,
                                "method": "getTokenLargestAccounts",
                                "params": [mint]})
        vals = (r.get("result") or {}).get("value") or []
        if not vals:
            out["concentration_error"] = "no token accounts returned"
            return out
        amts = [_f((v or {}).get("uiAmountString"), 0) or 0 for v in vals]
        amts = [a for a in amts if a > 0]
        if not amts:
            out["concentration_error"] = "all balances zero"
            return out
        if supply is None:
            a = authorities(mint)
            supply = a.get("supply")
            dec = a.get("decimals")
            if supply is not None and dec is not None:
                supply = supply / (10 ** dec)
        if not supply:
            out["concentration_error"] = "supply unknown"
            return out
        out["holders_sampled"] = len(amts)
        amts.sort(reverse=True)
        out["top1_share"] = round(amts[0] / supply, 6)
        out[f"top{top_n}_share"] = round(sum(amts[:top_n]) / supply, 6)
        out[f"top{top_n}_share_ex_largest"] = round(
            sum(amts[1:top_n + 1]) / supply, 6)
        if liq_base:
            # Within 5% of the pool's own token balance: it is the pool.
            out["largest_is_pool"] = abs(amts[0] - liq_base) <= 0.05 * max(amts[0], liq_base)
    except Exception as e:
        out["concentration_error"] = f"{type(e).__name__}"
    return out


def assess(mint, liq_base=None, want_concentration=True):
    """Both features. Two RPC calls, or one if concentration is skipped."""
    out = authorities(mint)
    if want_concentration and out.get("supply") is not None:
        dec = out.get("decimals") or 0
        supply_ui = out["supply"] / (10 ** dec) if dec else out["supply"]
        out.update(concentration(mint, supply=supply_ui, liq_base=liq_base))
    return out


if __name__ == "__main__":
    import sys
    import time
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ca in sys.argv[1:]:
        a = assess(ca)
        print(f"\n  {ca}")
        print(f"    mint authority  : {a.get('mint_authority')}   can_mint={a.get('can_mint')}")
        print(f"    freeze authority: {a.get('freeze_authority')}   can_freeze={a.get('can_freeze')}")
        print(f"    supply          : {a.get('supply')}  decimals={a.get('decimals')}")
        print(f"    top1 share      : {a.get('top1_share')}")
        print(f"    top10 share     : {a.get('top10_share')}")
        print(f"    top10 ex-largest: {a.get('top10_share_ex_largest')}")
        print(f"    errors          : {a.get('authorities_error')} / {a.get('concentration_error')}")
        time.sleep(RPC_PACE_S)
