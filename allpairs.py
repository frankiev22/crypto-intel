"""Read a token as a TOKEN, not as one of its pools.

⛔⛔ THE BUG THIS EXISTS TO KILL, found by Frank 2026-09-22.

Everything in this repo that priced a token read **one pair** and reported it as
the token. That is a 3% sample presented as the whole:

    EMBER 5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6
      one pair            some hundreds of dollars
      ALL 30 PAIRS        $2,335,971 liquidity, $6.86M 24h volume, $17.9M mcap
      venues              meteora 19, orca 6, raydium 3, pumpswap 1, meteoradbc 1

A token on a pairing launchpad has **one pool per paired asset**, so the more
interesting the token, the worse the single-pair error gets. Reading one pool is
worst exactly where it matters most.

⛔⛔ **CORRECTION TO THIS MODULE, measured 2026-09-23, hours after writing it.**
This file used to claim *"30 pairs is the signature of a pairing-launchpad
asset"*. **It is not. 30 is Dexscreener's hard cap.** Probed: SOL, which trades
in thousands of pools, returns exactly 30; so do USDC, BONK, EMBER and Hypurr; a
one-pool pump.fun token returns 1. ⚠️ **And the 30 are NOT the biggest 30** - the
returned liquidity order for EMBER was
`[521727, 357897, 664541, 109347, ...]`, not descending, so nothing about the
remainder can be bounded from what comes back.

⭐ **So `pair_count == 30` means "30 or more, truncated", and every total at 30 is
a FLOOR, never a total.** `truncated` is stored on every row for exactly this
reason: standing rule 15 says a truncated sample must record WHAT it missed, and
this one can only honestly record THAT it missed. Summing 30 is still strictly
better than reading 1, and it errs low, which is the safe direction for a
liquidity claim.

⭐ One thing does fall out and is stored rather than recomputed:

1. **`pair_count` is a signal at the LOW end only.** 1 to 3 pairs is an ordinary
   launch; a high count means "many pools" and nothing more precise.
2. ⛔ **THE PHANTOM RULE.** A market cap over $1,000,000 on total liquidity under
   $1,000 across ALL pairs is a ghost, not a token. It must never produce a
   finding again. The case that forced this:

    EMBER FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh
      3 pairs, TOTAL liquidity $1, "market cap" $1,314,046,208,
      "24h volume" $77,362,404.
      $1.31 BILLION of claimed cap on one dollar of backing.

⚠️ This module reads Dexscreener, whose `liquidity` field we have measured
overstating by a median 781x. Summing it correctly makes it a correct sum of an
overstating field. **It is for shape, venue spread and phantom detection. It is
NOT an exit price.** The exit price is `chainfields.round_trip()`, which routes
across venues and is what Frank would actually receive.
"""
import json
import time

import chainfields

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}
TOKENS_URL = "https://api.dexscreener.com/latest/dex/tokens/"

PHANTOM_MCAP = 1_000_000
PHANTOM_LIQ = 1_000
# ⛔ Measured 2026-09-23: /latest/dex/tokens/{mint} returns AT MOST 30 pairs,
# whatever the token. SOL returns 30. At 30 the answer is truncated.
PAIR_CAP = 30


def token(mint, timeout=25, retries=2):
    """Every pair for one mint, summed. Unknown stays None, never 0.

    Returns a dict with `ok` False when the lookup itself failed, so a network
    problem can never be mistaken for a dead token (the `gone` bug, journal.py:974).
    """
    body = None
    for i in range(retries + 1):
        st, b = chainfields._get(TOKENS_URL + mint, headers=UA, timeout=timeout)
        if isinstance(b, dict):
            body = b
            break
        if i < retries:
            time.sleep(0.8 * (i + 1))
    if body is None:
        return {"mint": mint, "ok": False, "error": "lookup failed",
                "pair_count": None, "total_liq_usd": None, "total_vol24_usd": None}

    pairs = body.get("pairs")
    if pairs is None:
        # a real answer that the indexer has no pairs for this mint
        return {"mint": mint, "ok": True, "pair_count": 0, "total_liq_usd": 0.0,
                "total_vol24_usd": 0.0, "mcap_usd": None, "price_usd": None,
                "venues": {}, "quote_assets": {}, "pairs": [], "phantom": False,
                "note": "indexer returned no pairs"}

    rows, venues, quotes = [], {}, {}
    liq = vol = 0.0
    mcaps, prices, created = [], [], []
    # ⚠️ DISPLAY ONLY, and it is taken from the pair rather than trusted as an
    # identity. Standing rule 2: the key is the address, always. A symbol can
    # render as a name it does not contain (112 contracts carry a bidi control),
    # so anything showing this must pass it through a symbol-flag check first.
    sym = name = None
    for p in pairs:
        if sym is None:
            # ⚠️ The mint can be the BASE or the QUOTE side. A major like USDC is
            # the quote asset in almost every pair it appears in, so checking
            # only baseToken leaves the most recognisable tokens nameless.
            for side in ("baseToken", "quoteToken"):
                tok = p.get(side) or {}
                if (tok.get("address") or "") == mint:
                    sym, name = tok.get("symbol"), tok.get("name")
                    break
        l = float((p.get("liquidity") or {}).get("usd") or 0)
        v = float((p.get("volume") or {}).get("h24") or 0)
        liq += l
        vol += v
        dex = p.get("dexId") or "unknown"
        venues[dex] = venues.get(dex, 0) + 1
        q = (p.get("quoteToken") or {}).get("symbol") or "unknown"
        qa = quotes.setdefault(q, {"pairs": 0, "liq_usd": 0.0,
                                   "mint": (p.get("quoteToken") or {}).get("address")})
        qa["pairs"] += 1
        qa["liq_usd"] += l
        if p.get("marketCap"):
            mcaps.append(float(p["marketCap"]))
        if p.get("priceUsd"):
            try:
                prices.append(float(p["priceUsd"]))
            except (TypeError, ValueError):
                pass
        if p.get("pairCreatedAt"):
            created.append(p["pairCreatedAt"])
        rows.append({"pair": p.get("pairAddress"), "dex": dex, "chain": p.get("chainId"),
                     "quote": q, "liq_usd": l, "vol24_usd": v,
                     "created_ms": p.get("pairCreatedAt")})

    rows.sort(key=lambda r: -(r["liq_usd"] or 0))
    mcap = max(mcaps) if mcaps else None
    # the deepest pool's price is the one a trade would actually touch first
    price = None
    for r in rows:
        for p in pairs:
            if p.get("pairAddress") == r["pair"] and p.get("priceUsd"):
                try:
                    price = float(p["priceUsd"])
                except (TypeError, ValueError):
                    price = None
                break
        if price is not None:
            break

    # ⛔ Dexscreener caps the response at PAIR_CAP. At the cap the sum is a FLOOR
    # and the missing pairs cannot be bounded, because the returned set is not
    # sorted by liquidity. The phantom rule therefore requires a COMPLETE sample:
    # 30 arbitrary pools summing to nothing says nothing about a 31st. The case
    # that forced the rule had 3 pairs, so it was complete.
    truncated = len(pairs) >= PAIR_CAP
    phantom = bool(mcap and mcap > PHANTOM_MCAP and liq < PHANTOM_LIQ
                   and not truncated)
    return {
        "mint": mint, "ok": True,
        "symbol_display": sym,
        "name_display": name,
        "pair_count": len(pairs),
        "truncated": truncated,
        "total_liq_usd": liq,
        "total_liq_is_floor": truncated,
        "total_vol24_usd": vol,
        "mcap_usd": mcap,
        "price_usd": price,
        "venues": dict(sorted(venues.items(), key=lambda kv: -kv[1])),
        "quote_assets": dict(sorted(quotes.items(), key=lambda kv: -kv[1]["liq_usd"])),
        "deepest": rows[0] if rows else None,
        "single_pair_would_have_said": rows[0]["liq_usd"] if rows else None,
        "single_pair_understates_by": (round(liq / rows[0]["liq_usd"], 2)
                                       if rows and rows[0]["liq_usd"] else None),
        "first_pair_ms": min(created) if created else None,
        "pairs": rows,
        "phantom": phantom,
        "phantom_why": (f"mcap ${mcap:,.0f} on ${liq:,.2f} of total liquidity "
                        f"across all {len(pairs)} pairs"
                        if phantom else None),
        "phantom_unevaluable": bool(mcap and mcap > PHANTOM_MCAP
                                    and liq < PHANTOM_LIQ and truncated),
        "chains": sorted({r["chain"] for r in rows if r["chain"]}),
    }


def verdict(t):
    """A one-word shape for a token, from all its pairs. Never an exit price.

    ⚠️ A LOW verdict needs a complete sample; a HIGH one does not, because the
    sum is a floor. So truncation can only ever turn a low verdict into UNKNOWN.
    """
    if not t.get("ok"):
        return "UNKNOWN"
    if t.get("phantom"):
        return "PHANTOM"
    liq = t.get("total_liq_usd")
    if liq is None:
        return "UNKNOWN"
    if liq < 25000 and t.get("truncated"):
        return "UNKNOWN_TRUNCATED"
    if liq < 1000:
        return "NO_LIQUIDITY"
    if liq < 25000:
        return "THIN"
    return "LIQUID"


if __name__ == "__main__":
    import sys
    for m in sys.argv[1:]:
        t = token(m)
        print(f"\n{m}")
        if not t["ok"]:
            print("  LOOKUP FAILED")
            continue
        print(f"  {verdict(t):<12} pairs={t['pair_count']}  "
              f"liq=${(t['total_liq_usd'] or 0):,.0f}  "
              f"vol24=${(t['total_vol24_usd'] or 0):,.0f}  "
              f"mcap=${(t['mcap_usd'] or 0):,.0f}  px={t['price_usd']}")
        print(f"  venues {t['venues']}")
        print(f"  quote assets {json.dumps({k: round(v['liq_usd']) for k, v in list(t['quote_assets'].items())[:8]})}")
        if t["phantom"]:
            print(f"  PHANTOM: {t['phantom_why']}")
        if t.get("truncated"):
            print(f"  ⚠ TRUNCATED at the {PAIR_CAP}-pair API cap: "
                  f"${t['total_liq_usd']:,.0f} is a FLOOR, and the missing pairs "
                  f"cannot be bounded (the returned set is not sorted by size)")
        if t.get("single_pair_understates_by"):
            print(f"  reading one pool would have shown "
                  f"${t['single_pair_would_have_said']:,.0f}, "
                  f"{t['single_pair_understates_by']}x too low")
