"""
Cross-source price validation, and the dust floor below which there is no price.

WHY. FLORK was recorded at 444x and reported as a 718x catch. Dissected pool by
pool on 2026-09-03:

    pool A  reserve $0.0727   price $0.000004906
    pool B  reserve $0.0000   price $0.0000000000046
    pool C  reserve $0.0036   price $0.04866    <- the one Dexscreener quotes

Dexscreener reads pool C, the second SMALLEST of the three, holding thirty-six
hundredths of a cent. Multiplied by supply that produced a $436,313,815 FDV.
GeckoTerminal, reading the same token, said $992,644 - a 490x disagreement.
FLORK went about 1.5x and died. It was never a 718x and never a $436M token.

Two rules come out of that, and they are cheap and free:

1. CROSS-SOURCE AGREEMENT GATES THE NUMBER. Where Dexscreener and
   GeckoTerminal agree, the price is probably real - verified on the same run:
   NIULAI 31.78 vs 31.74, MACHINE 13.09 vs 13.08, GRASS 10.78 vs 10.78. Where
   they diverge past a threshold, quarantine rather than record.

2. BELOW A DUST FLOOR THERE IS NO PRICE AT ALL. Picking the deepest pool is
   necessary but not sufficient: FLORK deepest pool prices at $0.0000049, which
   still does not match GeckoTerminal. At $0.07 of total reserve no quote is
   meaningful, from any source. The honest record is "no price", not a number
   with a caveat attached.

Validation costs one GeckoTerminal call, and that API is rate-limited to about
10-15 calls a minute, so it is spent only on multiples large enough to be
believed. A wrong price on a 1.02x changes nothing; a wrong price on a 444x
becomes the headline.
"""
import os

import resolve

# Ratio between two sources beyond which they are not describing the same
# thing. FLORK disagreed by 490x. Real agreement on the same run was inside
# 1.002x. Three is far outside the noise and far inside the fault.
DIVERGENCE_LIMIT = float(os.environ.get("CRYPTO_PRICE_DIVERGENCE", "3.0"))

# Total reserve below which no quote from any source is meaningful.
NO_PRICE_LIQ_USD = float(os.environ.get("CRYPTO_NO_PRICE_LIQ", "100.0"))

# Only multiples at or above this get a cross-source check, to stay inside the
# fallback API budget.
VALIDATE_ABOVE = float(os.environ.get("CRYPTO_VALIDATE_ABOVE", "2.0"))

CONFIRMED = "confirmed"
SINGLE = "single_source"
Q_DIVERGENT = "quarantined_divergent"
Q_DUST = "quarantined_no_liquidity"
Q_UNRESOLVED = "quarantined_unresolved"


def validate(token, chain="solana"):
    """Return a verdict on the token price.

    {price, confidence, dex_price, gt_price, ratio, liq_usd, trustworthy}

    trustworthy is False for anything quarantined. A caller must not record a
    multiple built on an untrustworthy price - that is how a $0.0036 pool
    became a $436M market cap.
    """
    out = {"token": token, "price": None, "confidence": Q_UNRESOLVED,
           "dex_price": None, "gt_price": None, "ratio": None,
           "liq_usd": None, "trustworthy": False, "detail": ""}

    dex = gt = None
    try:
        dex = resolve._dexscreener(chain, token)
    except Exception:
        dex = None
    try:
        gt = resolve._geckoterminal(chain, token)
    except Exception:
        gt = None

    if dex:
        out["dex_price"] = dex.get("price_usd")
    if gt:
        out["gt_price"] = gt.get("price_usd")

    # Liquidity: prefer the aggregated figure. Verified 2026-09-03 that
    # GeckoTerminal total_reserve_in_usd really does sum across pools - FLORK
    # pools summed to $0.0763 against a reported $0.0605.
    liq = None
    for cand in ((gt or {}).get("liq_usd"), (dex or {}).get("liq_usd")):
        if cand is not None:
            liq = cand
            break
    out["liq_usd"] = liq

    if not dex and not gt:
        out["detail"] = "neither source resolved the token"
        return out

    # Dust first: below the floor, no source is describing a tradeable price,
    # so agreement between them would prove nothing.
    if liq is not None and liq < NO_PRICE_LIQ_USD:
        out["confidence"] = Q_DUST
        out["detail"] = (f"total reserve ${liq:,.4f} is below the "
                         f"${NO_PRICE_LIQ_USD:,.0f} floor; no quote is meaningful")
        return out

    a, b = out["dex_price"], out["gt_price"]
    if a and b:
        hi, lo = max(a, b), min(a, b)
        ratio = (hi / lo) if lo else float("inf")
        out["ratio"] = ratio
        if ratio > DIVERGENCE_LIMIT:
            out["confidence"] = Q_DIVERGENT
            out["detail"] = (f"dexscreener ${a:.10g} vs geckoterminal ${b:.10g} "
                             f"= {ratio:,.1f}x apart, past the {DIVERGENCE_LIMIT}x limit")
            return out
        # Agreed. Take the lower of the two: if they differ at all, the smaller
        # number is the one that survives contact with an order book.
        out["price"] = lo
        out["confidence"] = CONFIRMED
        out["trustworthy"] = True
        out["detail"] = f"two sources within {ratio:.3f}x"
        return out

    only = a if a else b
    out["price"] = only
    out["confidence"] = SINGLE
    out["trustworthy"] = True
    out["detail"] = ("only dexscreener resolved it" if a else
                     "only geckoterminal resolved it")
    return out


def check_multiple(token, mult, chain="solana"):
    """Validate a multiple before it is recorded. Returns (ok, verdict_or_None).

    Small multiples pass without spending an API call - a wrong price on a
    1.02x changes nothing, and the GeckoTerminal budget is the scarce resource.
    """
    if mult is None or mult < VALIDATE_ABOVE:
        return True, None
    v = validate(token, chain)
    return bool(v["trustworthy"]), v


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for ca in sys.argv[1:]:
        v = validate(ca)
        print(f"\n  {ca}")
        print(f"    dexscreener  : {v['dex_price']}")
        print(f"    geckoterminal: {v['gt_price']}")
        print(f"    ratio        : {v['ratio']}")
        print(f"    liquidity    : {v['liq_usd']}")
        print(f"    verdict      : {v['confidence']}  trustworthy={v['trustworthy']}")
        print(f"    {v['detail']}")
