"""Descriptive liquidity columns. NOT a fraud verdict, and nothing filters on it.

READ THIS BEFORE USING ANY FIELD HERE TO EXCLUDE A ROW: don't. On 2026-09-05
this module briefly zeroed the score of any observation it judged implausible.
That gate was withdrawn the same day, because it had never been validated
against ground truth, and three things were wrong with it.

1. CIRCULARITY. It used Dexscreener's `liquidity.usd` to decide when
   Dexscreener's `liquidity.usd` was misleading. The template class was
   originally found from base/quote RESERVES pulled live - independent
   evidence. A summary field cannot audit itself.

2. `age_hours` IS PAIR AGE, from `pairCreatedAt`, NOT token age. A newly
   created pool for a long-established token looks exactly like a brand new
   token, so "implausible magnitude for age" can flag a legitimate large token
   as fraud. This scanner has repeatedly ingested multi-billion-dollar tokens
   that share a memecoin ticker.

3. IT WAS NEVER MEASURED. The precision and recall figures this module used to
   quote - 87% and 100% - were computed against another HEURISTIC
   (`liq/price ~ 1e9` plus silence), not against reserves. Detector-versus-
   detector agreement is not validation. Only three pools had ever been
   confirmed by pulling their sides: SUNCOIN, TIKZZZ and `worthless`.

When a proper labelled set was attempted, it could not be built: of 43 tokens
sampled across four strata, **only 9 could still be resolved at all** (21%).
Dexscreener stops indexing pools whose reserves collapse, which is precisely
the population that needs labelling, and GeckoTerminal's pools endpoint returns
`reserve_in_usd` with no base/quote split, so it cannot substitute.

WHAT THE 9 RESOLVABLE ROWS DID SHOW, as measurements rather than proxies:

    SUNCOIN   reported $1,260,745   exit depth $10,030   125.7x   0 sells/24h
    ZODL      reported $1,263,969   exit depth $10,061   125.6x   0 sells/24h
    CHAD      reported $1,261,985   exit depth $10,045   125.6x   0 sells/24h
    HASH      reported       $486   exit depth      $4   125.7x   0 sells/24h
    STUFFY    reported       $484   exit depth      $4   125.8x   0 sells/24h
    ---
    Solana    reported     $2,286   exit depth    $244     9.4x  1397 sells/24h
    minilyst  reported     $2,299   exit depth    $274     8.4x     2 sells/24h
    CYBERLEEK reported         $0   exit depth      $0     2.0x    51 sells/24h

Five pools at 125.6-125.8x with zero sells is a tight, real cluster. Three
controls with sell-side activity sit at 2-9x. That is suggestive and it is
nine rows. It is not a validated detector and must not be used as one.

THE FIX IS FORWARD, NOT RETROSPECTIVE. `scanner.score()` now stores
`liq_base`, `liq_quote`, `price_native` and a computed `exit_depth_usd` on
every observation, taken from the pair object already in hand. That is a real
measurement made cheap by caching rather than a proxy, and it is available at
the moment Dexscreener still indexes the pair. Fresh balanced pools measured
exactly 2.00x on the first pass that recorded it. Once enough rows carry it, a
detector can be validated properly - against reserves, with precision, recall
and counts reported before anything is allowed to filter.

WHAT REMAINS SOUND HERE:

`liq/fdv` decomposes as (share of supply sitting in the pool) + (quote/fdv),
verified arithmetically against a pool whose sides were measured:

    worthless   liq $1,285,629   fdv $1,298,827   liq/fdv = 0.9898
                base 981,744,468 x $0.001299 = $1,275,286   (0.9817 of supply)
                quote 98.73 SOL              =    ~$10,236   (0.0079 of fdv)

So `liq > fdv` is NOT impossible - it needs quote_usd > (supply - base) x price,
about zero for a fresh launch, and 708 of 2,723 tokens sit there legitimately.
`liq > 2 x fdv` IS impossible: the cash side alone would have to outweigh every
token in existence. Six rows do it, worst at 2,729x against a $1 fdv. Those are
data-integrity errors and are FLAGGED, not filtered - at least one of the two
numbers is corrupt, and we do not know which.

AND ON DESCRIBING THIS DATA AT ALL: report medians and distributions, never
bare means. Every field here is heavy-tailed. The zero-sell entry cohort has a
mean liquidity of $169,061,510 and a median of $256,219; across all entries the
mean is $22,296,205 against a median of $24,630. The best-realizable-multiple
column has a mean of 0.307 and a median of 0.000. Hit rates are counts and are
safe; mean columns are tail artifacts.
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
