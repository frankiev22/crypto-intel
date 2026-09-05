"""Is this liquidity reading physically possible, and is it a template pool?

Everything here reads FIELDS WE ALREADY STORE. No API call, no live lookup. The
template class was originally found by pulling base/quote reserves pool by pool
on 2026-09-04; this recovers the same population from `liq`, `fdv`, `age_hours`
and the buy/sell counts, which means every historical row can be classified for
free and every future one at write time.

THE ARITHMETIC, verified against a pool whose sides were measured live
('worthless', 2026-09-04):

    reported liq $1,285,629     fdv $1,298,827        liq/fdv = 0.9898
    base  981,744,468 tokens x $0.001299 = $1,275,286
    quote 98.73 SOL                      =    ~$10,236
                                           ----------
                                  base + quote = $1,285,522

So liq/fdv decomposes as (share of supply sitting in the pool) + (quote/fdv):
0.9817 + 0.0079 = 0.9896 against an observed 0.9898.

Three consequences, and the first two correct an instinct worth writing down:

1. `liq > fdv` IS NOT IMPOSSIBLE. It needs quote_usd > (supply - base) x price,
   and for a fresh launch with nearly all supply pooled that right-hand side is
   about zero, so any cash side at all clears it. 708 of 2,723 tokens (26.0%)
   are in that state and they are not defective.

2. `liq > 2 x fdv` IS impossible: it requires the cash side alone to be worth
   more than the entire token supply. Six tokens in the record do it, worst at
   2,729x on a $1 fdv. Those are corrupt rows, and three of them passed the
   filter.

3. liq/fdv NEAR 1 means all supply is in the pool - which is the one-sided
   signature. The template pools sit at 0.99, just UNDER one, so they never
   appear in the liq>fdv population at all.

MAGNITUDE, tuned from the distribution rather than guessed. Reported liquidity
for tokens under an hour old, n=20,292:

    p50 $0    p95 $21,136    p99 $207,140    p99.5 $344,813
    p99.9 $199,803,718       p99.95 $956,443,208     max $7,406,577,362

There is a 580x cliff between p99.5 and p99.9. And among pools that anyone has
actually sold into (>= 3 sells in the hour, n=13,424) the p99.9 is $607,779 and
the maximum ever seen is $9,089,748. So a sub-hour pool reporting eight figures
has no counterpart anywhere in the traded population.

WHAT DOES NOT WORK, measured: a plain "liq > $1M" gate catches 2 of the 53
verified template tokens. They report $160k-$360k AT ENTRY and only reach
~$1.26M by the outcome check, so a write-time gate never sees the big number.
Magnitude and template are two different populations - the $1M+ cohort mostly
carries real sell-side activity and a third of its top ten are right-to-left
override impersonations. Keep the two flags separate.

The detector that does work, against the 53 live-verified tokens:

    liq/fdv >= 0.95                     536 flagged   10% precision  100% recall
    zero sells with >= 10 buys           75 flagged   71% precision  100% recall
    both together                        61 flagged   87% precision  100% recall
"""
import os

# Above this, the cash side would have to be worth more than the whole supply.
IMPOSSIBLE_LIQ_FDV = float(os.environ.get("CRYPTO_IMPOSSIBLE_LIQ_FDV", "2.0"))

# At or above this, effectively the entire supply is sitting in the pool.
ONE_SIDED_LIQ_FDV = float(os.environ.get("CRYPTO_ONE_SIDED_LIQ_FDV", "0.95"))

# Magnitude ceilings for a token under MAX_YOUNG_H old. The hard ceiling sits
# above the largest pool with real sell-side activity ever recorded
# ($9,089,748); the soft one sits above p99.5 of the whole young population.
HARD_LIQ_CEILING = float(os.environ.get("CRYPTO_HARD_LIQ_CEILING", "10000000"))
SOFT_LIQ_CEILING = float(os.environ.get("CRYPTO_SOFT_LIQ_CEILING", "1000000"))
MAX_YOUNG_H = float(os.environ.get("CRYPTO_YOUNG_H", "1.0"))

# A pool nobody has sold out of, with enough buys that silence is a choice
# rather than an absence of traffic.
MIN_BUYS_FOR_SILENCE = int(os.environ.get("CRYPTO_MIN_BUYS_SILENCE", "10"))


def _f(x, d=None):
    try:
        v = float(x)
    except (TypeError, ValueError):
        return d
    return v


def assess(row):
    """Classify one observation. Never raises, never calls out.

    Returns {liq_to_fdv_ratio, flags, template_suspect, liquidity_plausible}.
    `row` may be a scanner row or a journalled observation - both spellings of
    the liquidity and supply fields are accepted.
    """
    liq = _f(row.get("liq"), _f(row.get("liquidity")))
    fdv = _f(row.get("fdv"))
    age = _f(row.get("age_hours"), _f(row.get("age_h")))
    buys = _f(row.get("buys_h1"), 0) or 0
    sells = _f(row.get("sells_h1"), 0) or 0

    ratio = (liq / fdv) if (liq is not None and fdv) else None
    flags = []

    if ratio is not None and ratio > IMPOSSIBLE_LIQ_FDV:
        # Not "unlikely" - arithmetically impossible. The cash side cannot be
        # worth more than every token in existence.
        flags.append("liq_exceeds_2x_fdv")

    young = age is not None and age < MAX_YOUNG_H
    if liq is not None and young and liq > HARD_LIQ_CEILING:
        flags.append("liq_implausible_for_age")
    elif liq is not None and young and liq > SOFT_LIQ_CEILING:
        flags.append("liq_large_for_age")

    silent = sells == 0 and buys >= MIN_BUYS_FOR_SILENCE
    if silent:
        flags.append("no_sell_side")

    one_sided = ratio is not None and ratio >= ONE_SIDED_LIQ_FDV
    if one_sided:
        flags.append("supply_is_the_liquidity")

    # The fingerprint is the INTERACTION. Either term alone is common and
    # innocent: 536 tokens have liq/fdv >= 0.95 because that is what a fresh
    # bonding curve looks like, and plenty of pools simply have not been sold
    # out of yet. Together they are the template.
    template = bool(one_sided and silent)

    plausible = not ({"liq_exceeds_2x_fdv", "liq_implausible_for_age"} & set(flags))

    return {"liq_to_fdv_ratio": (round(ratio, 6) if ratio is not None else None),
            "flags": flags,
            "template_suspect": template,
            "liquidity_plausible": plausible}


def annotate(row):
    """Attach the assessment to an observation dict in place, and return it."""
    a = assess(row)
    row["liq_to_fdv_ratio"] = a["liq_to_fdv_ratio"]
    row["template_suspect"] = a["template_suspect"]
    row["liquidity_plausible"] = a["liquidity_plausible"]
    existing = row.get("integrity_flags")
    row["integrity_flags"] = a["flags"] if not existing else list(
        dict.fromkeys(list(existing) + a["flags"]))
    return row


if __name__ == "__main__":
    import json
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for line in sys.stdin:
        line = line.strip()
        if not line:
            continue
        try:
            r = json.loads(line)
        except ValueError:
            continue
        a = assess(r)
        print(f"{str(r.get('symbol'))[:14]:<15} ratio="
              f"{a['liq_to_fdv_ratio']!s:<10} template={a['template_suspect']!s:<6} "
              f"plausible={a['liquidity_plausible']!s:<6} {','.join(a['flags'])}")
