"""Bonding curve or AMM pool. The dimension the dataset never had.

WHY, established 2026-09-05. Pump.fun's graduation threshold is about $69,000 of
market cap and only 1-2% of launches reach it. Below that a token is on a
BONDING CURVE, not in a constant-product pool, and the two are different
instruments that happen to share a price field.

Our own record puts the graduation rate at **2.10%** - 397 of 18,920 tokens
ever reached $69,000 of reported liquidity - which lands inside pump.fun's
published band and is the first honest base rate this project has had. For a
year we have quoted hit rates with no idea what random looks like. Random looks
like two per cent.

WHAT DEXSCREENER ACTUALLY DOES WITH A CURVE, measured live rather than assumed:

    MOON       dex=pumpfun    liq=$0   base=None  quote=None   fdv=$24
    DRIP       dex=pumpfun    liq=$0   base=None  quote=None   fdv=$2,896
    DGAF       dex=meteora    liq=$1   base=1313.358  quote=0.003412

It reports **liquidity.usd = 0 with no reserve split** for a bonding-curve
pair. So the feared category error - reading curve reserve as AMM depth - is
not what happened. The opposite did: curve tokens arrive with zero liquidity,
fail the liquidity floor, and are scored and journalled anyway.

**84.6% of every token we have ever observed had zero liquidity at every
observation** - 16,002 of 18,920. That is the curve population, and the entire
scan budget spent on it produces rows that cannot clear any exit floor by
construction.

WHERE THE VENUE COMES FROM, free: GeckoTerminal's new-pools discovery response
already carries it at `relationships.dex.data.id`, in a payload the scanner
fetches and discards. No extra call. Measured mix of one live launch stream:

    pump-fun         37     (bonding curve)
    meteora-damm-v2   9     (AMM)
    pumpswap          8     (AMM - graduated pump.fun)
    meteora-dbc       6     (dynamic bonding curve)

72% of the stream is pre-graduation.
"""
import os

# Venues that are bonding curves, not pools. A position here cannot be exited
# into depth because there is no depth - there is a curve.
CURVE_DEXES = {
    "pump-fun", "pumpfun", "pump_fun",
    "meteora-dbc", "meteoradbc", "meteora_dbc",
    "launchlab", "raydium-launchlab", "boop", "moonshot", "believe",
    "heaven", "bags", "bonk-fun", "bonkfun", "letsbonk",
}

# Constant-product or concentrated-liquidity pools: real two-sided depth.
AMM_DEXES = {
    "pumpswap", "raydium", "raydium-clmm", "raydium-cpmm", "raydium-amm",
    "meteora", "meteora-damm-v2", "meteora-damm", "meteoradbc-amm",
    "orca", "whirlpool", "fluxbeam", "lifinity", "saber", "invariant",
    "solfi", "obric", "stabble", "aldrin", "cropper", "dooar", "byreal",
}

CURVE = "bonding_curve"
AMM = "amm"
UNKNOWN = "unknown"

# Pump.fun's published graduation threshold, in USD of market cap.
GRADUATION_MCAP_USD = float(os.environ.get("CRYPTO_GRADUATION_MCAP", "69000"))


def _norm(dex):
    return (dex or "").strip().lower().replace("_", "-")


def venue_type(dex):
    """Classify a dexId. Unknown is recorded as unknown, never guessed into a
    class - a wrong venue label would silently mis-split every analysis."""
    d = _norm(dex)
    if not d:
        return UNKNOWN
    if d in CURVE_DEXES or d.replace("-", "") in {x.replace("-", "") for x in CURVE_DEXES}:
        return CURVE
    if d in AMM_DEXES or d.replace("-", "") in {x.replace("-", "") for x in AMM_DEXES}:
        return AMM
    return UNKNOWN


def from_discovery(record):
    """Venue id out of a GeckoTerminal new-pools record. Free - already fetched."""
    try:
        return ((record.get("relationships") or {}).get("dex") or {}).get("data", {}).get("id")
    except Exception:
        return None


def assess(dex=None, liq=None, liq_base=None, liq_quote=None, fdv=None):
    """{venue, venue_type, has_amm_pool, is_graduated}.

    `has_amm_pool` means exactly what it says: there is a real two-sided pool
    here right now. It is a VENUE FACT, not a graduation event.

    IT WAS CALLED `is_graduated` UNTIL 2026-09-10, AND THAT NAME WAS FALSE.
    Of 1,730 contracts we have ever seen on an AMM, only 86 - 5.0% - were first
    seen on a bonding curve, which is the only way we could have watched one
    graduate. The other 95% appeared already on an AMM and were never on a curve
    in our data at all. So the flag was overwhelmingly answering "does this have
    a pool", while its name claimed the market's 1-2% graduation filter had been
    applied. Anything reasoning from the name was reasoning from a fiction.

    `graduated` now means one thing only, and it is the watchlist milestone: a
    contract we were already tracking in the approach band that later crossed.
    That is an observed transition with a before and an after.

    `is_graduated` is still returned, with the same value, because 100,000+
    persisted rows carry that key and nothing is ever deleted. New readers use
    `has_amm_pool`; `has_pool()` below accepts either.
    """
    vt = venue_type(dex)
    has_pool = bool(liq_base is not None and liq_quote is not None
                    and (liq or 0) > 0)
    if vt == CURVE:
        grad = False
    elif vt == AMM:
        grad = has_pool
    else:
        # No venue label. Fall back to the shape of the payload: a curve pair
        # comes back with zero liquidity and no reserve split.
        grad = has_pool if (liq is not None) else None
    return {"venue": _norm(dex) or None, "venue_type": vt,
            "has_amm_pool": grad,
            # Same value under the old key: the archive is written in it.
            "is_graduated": grad}


def has_pool(row):
    """Does this row have a real two-sided pool? Reads either key.

    Rows written before 2026-09-10 carry `is_graduated`; rows after carry
    `has_amm_pool`. Both mean the same thing and always did.
    """
    v = row.get("has_amm_pool")
    return row.get("is_graduated") if v is None else v


def annotate(row, dex=None):
    a = assess(dex if dex is not None else row.get("venue"),
               row.get("liq"), row.get("liq_base"), row.get("liq_quote"),
               row.get("fdv"))
    row.update(a)
    return row
