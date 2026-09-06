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

# Two sources may quote the same price and still disagree about whether there
# is a pool behind it. 2026-09-04: 景甜 recorded 29.53x, and the recomputed
# multiple agreed exactly - but Dexscreener showed $0 liquidity where
# GeckoTerminal showed $36,202. Price agreement was never evidence about depth.
LIQ_DIVERGENCE_LIMIT = float(os.environ.get("CRYPTO_LIQ_DIVERGENCE", "10.0"))

# How far a recorded multiple may sit from one recomputed against a fresh
# price before it is treated as a bookkeeping error rather than a return.
MULT_TOLERANCE = float(os.environ.get("CRYPTO_MULT_TOLERANCE", "1.25"))

CONFIRMED = "confirmed"
SINGLE = "single_source"
Q_DIVERGENT = "quarantined_divergent"
Q_LIQ_DIVERGENT = "quarantined_liquidity_divergent"
Q_DUST = "quarantined_no_liquidity"
Q_UNRESOLVED = "quarantined_unresolved"
Q_MULT_MISMATCH = "quarantined_multiple_mismatch"


def validate(token, chain="solana"):
    """Return a verdict on the token price.

    {price, confidence, dex_price, gt_price, ratio, liq_usd, trustworthy}

    trustworthy is False for anything quarantined. A caller must not record a
    multiple built on an untrustworthy price - that is how a $0.0036 pool
    became a $436M market cap.
    """
    out = {"token": token, "price": None, "confidence": Q_UNRESOLVED,
           "dex_price": None, "gt_price": None, "ratio": None,
           "liq_usd": None, "exit_depth_usd": None, "dex_liq": None,
           "gt_liq": None, "liq_ratio": None, "trustworthy": False,
           "detail": ""}

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
    out["dex_liq"] = (dex or {}).get("liq_usd")
    out["gt_liq"] = (gt or {}).get("liq_usd")
    out["exit_depth_usd"] = (dex or {}).get("exit_depth_usd")

    if not dex and not gt:
        out["detail"] = "neither source resolved the token"
        return out

    # Dust first: below the floor, no source is describing a tradeable price,
    # so agreement between them would prove nothing. Judge on the quote side
    # where it is visible - a pool holding a billion of its own token and
    # $10k of SOL reports over a million dollars of "liquidity".
    floor_on = out["exit_depth_usd"] if out["exit_depth_usd"] is not None else liq
    if floor_on is not None and floor_on < NO_PRICE_LIQ_USD:
        out["confidence"] = Q_DUST
        which = "exit depth" if out["exit_depth_usd"] is not None else "total reserve"
        out["detail"] = (f"{which} ${floor_on:,.4f} is below the "
                         f"${NO_PRICE_LIQ_USD:,.0f} floor; no quote is meaningful")
        return out

    # Sources can agree on price and still disagree on whether a pool exists.
    dl, gl = out["dex_liq"], out["gt_liq"]
    if dl is not None and gl is not None and max(dl, gl) >= NO_PRICE_LIQ_USD:
        hi_l, lo_l = max(dl, gl), min(dl, gl)
        lr = (hi_l / lo_l) if lo_l > 0 else float("inf")
        out["liq_ratio"] = lr
        if lr > LIQ_DIVERGENCE_LIMIT:
            out["confidence"] = Q_LIQ_DIVERGENT
            out["detail"] = (f"dexscreener liquidity ${dl:,.0f} vs geckoterminal "
                             f"${gl:,.0f}; the sources do not agree that there is "
                             f"a pool to exit into")
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


def check_multiple(token, mult, chain="solana", base_price=None):
    """Validate a multiple before it is recorded. Returns (ok, verdict_or_None).

    Small multiples pass without spending an API call - a wrong price on a
    1.02x changes nothing, and the GeckoTerminal budget is the scarce resource.

    When `base_price` is supplied the multiple itself is re-derived from the
    validated price, not just the price it was built on. That guards against a
    stored multiple drifting from the price it was computed against.

    IT DOES NOT CATCH WOFI, and it is worth being exact about why. WOFI
    recorded 333.33x on 2026-09-04 and the arithmetic was correct: entry
    $0.00004131, exit $0.01377, 333.33x. The two prices simply came from two
    DIFFERENT POOLS of the same token - we entered on a pool holding no
    liquidity at $0.00004131, that pool went quiet, and the token-level
    fallback priced the live pool at $0.01377. Re-deriving the multiple
    reproduces the same wrong number. Only pair identity catches it, which is
    why `resolve()` returns `pair_address` and `record_outcome` refuses any row
    carrying `cross_pair_fallback`. Measured across the record: 3 rows affected,
    1 of them a multiple over 2x. Rare, and fabricated.
    """
    if mult is None or mult < VALIDATE_ABOVE:
        return True, None
    v = validate(token, chain)
    if v["trustworthy"] and base_price:
        v = _check_arithmetic(v, mult, base_price)
    return bool(v["trustworthy"]), v


def _check_arithmetic(v, mult, base_price):
    """Re-derive the multiple from the validated price and compare."""
    px = v.get("price")
    if not px or not base_price:
        return v
    recomputed = px / base_price
    v["recomputed_mult"] = recomputed
    v["recorded_mult"] = mult
    hi, lo = max(mult, recomputed), min(mult, recomputed)
    off = (hi / lo) if lo > 0 else float("inf")
    v["mult_ratio"] = off
    if off > MULT_TOLERANCE:
        v["trustworthy"] = False
        v["confidence"] = Q_MULT_MISMATCH
        v["detail"] = (f"recorded {mult:,.2f}x but the validated price "
                       f"${px:.10g} against an entry of ${base_price:.10g} is "
                       f"{recomputed:,.2f}x - {off:,.1f}x apart")
    return v


def verify_multiple(token, base_price, recorded_mult, chain="solana"):
    """Standalone re-derivation, for auditing rows already on the record."""
    v = validate(token, chain)
    if not v["trustworthy"]:
        return False, v
    v = _check_arithmetic(v, recorded_mult, base_price)
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


# ---------------------------------------------------------------------------
# WRITE-TIME MULTIPLE VALIDATION. Free - no network call, no rate-limit spend.
#
# The longest-standing open item. The existing validator (`check_multiple`)
# only runs above VALIDATE_ABOVE=2.0 and costs a call to each source, so it
# cannot run on every row: GeckoTerminal sustains under 10 successful calls a
# minute and a pass already makes ~213 outcome lookups.
#
# THIS ONE COSTS NOTHING, because both inputs are already in the pair object.
# `price_usd / price_native` is the QUOTE TOKEN's price in USD. Measured across
# 3,043 observations carrying both fields:
#
#     94.71%  imply $50-400      -> SOL, median $104.04, tight
#      5.00%  imply $0.5-2       -> USDC
#      0.30%  imply neither      -> 9 rows, from $0.000015 to $79,770
#
# The 9 are not necessarily corrupt - AAPLx implies $79,770, which is simply a
# BTC-quoted pair. But a token quoted against another memecoin has no stable
# USD leg, and its "multiple" moves when the QUOTE moves.
#
# THE ACTIONABLE CHECK IS CONSISTENCY, NOT RANGE. If the entry implies SOL and
# the exit implies USDC, the two prices came from pools with different quote
# tokens and the ratio between them is not a return. That is the same defect
# class as the cross-pool division that fabricated FLORK's 444x, and it is
# detectable for free at the moment the row is written.
#
# FORWARD-ONLY. Historical outcome rows carry no `price_native`, so this cannot
# be backtested and no retrospective claim is made from it. Consistent with
# standing rule 14: prefer forward records.
# ---------------------------------------------------------------------------
QUOTE_TOLERANCE = float(os.environ.get("CRYPTO_QUOTE_TOLERANCE", "3.0"))
Q_QUOTE_MISMATCH = "quarantined_quote_token_mismatch"

# Known quote assets, by the USD price they imply. Descriptive only - a pair
# outside every band is RECORDED, never rejected for that alone.
QUOTE_BANDS = (("USDC/USDT", 0.5, 2.0), ("SOL", 50.0, 400.0),
               ("ETH", 800.0, 6000.0), ("BTC", 20000.0, 200000.0))


def implied_quote_usd(price_usd, price_native):
    """The quote token's USD price implied by one pair's own two price fields."""
    try:
        pu, pn = float(price_usd), float(price_native)
    except (TypeError, ValueError):
        return None
    return (pu / pn) if pn else None


def quote_asset(implied):
    if implied is None:
        return None
    for name, lo, hi in QUOTE_BANDS:
        if lo <= implied <= hi:
            return name
    return "unknown"


def check_quote_consistency(base_price, base_price_native, price, price_native):
    """Do entry and exit agree on what the pair is quoted in? Free.

    Returns a verdict shaped like the others: {trustworthy, confidence, detail}.
    `trustworthy` is True when the check cannot run - an absent field is not
    evidence of a fault, and must not be treated as one.
    """
    a = implied_quote_usd(base_price, base_price_native)
    b = implied_quote_usd(price, price_native)
    out = {"trustworthy": True, "confidence": None, "detail": None,
           "entry_quote_usd": a, "exit_quote_usd": b,
           "entry_quote_asset": quote_asset(a), "exit_quote_asset": quote_asset(b)}
    if a is None or b is None or a <= 0 or b <= 0:
        out["detail"] = "price_native missing at one end - check not run"
        return out
    hi, lo = max(a, b), min(a, b)
    ratio = hi / lo
    out["quote_ratio"] = ratio
    if ratio > QUOTE_TOLERANCE:
        out["trustworthy"] = False
        out["confidence"] = Q_QUOTE_MISMATCH
        out["detail"] = (
            f"entry priced against an asset worth ${a:,.4f} "
            f"({out['entry_quote_asset']}), exit against ${b:,.4f} "
            f"({out['exit_quote_asset']}) - {ratio:,.1f}x apart. The two "
            f"prices are not the same series, so their ratio is not a return.")
    return out
