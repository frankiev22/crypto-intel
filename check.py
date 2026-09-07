"""One coin, one answer: is this pool one we can prove is fake?

    python check.py <contract_address>

WHAT THIS IS. The fraud detector, pointed at a single token on demand. It runs
D1 and D2 - the only validated measurements in this repo - plus the capability
checks and a measured exit depth, and prints what it found with the interval
attached.

WHAT THIS IS NOT, and the order matters:

    NOT FLAGGED IS NOT A BUY SIGNAL. It is not even a safety signal. D1's recall
    is 50% - it misses HALF of the one-sided pools it is scored against. A clean
    result means "none of two specific frauds was detected", nothing more. This
    system has never had a profitable entry rule and five attempts to build one
    have been retracted.

    IT REFUSES RATHER THAN GUESSES. If the token is not indexed, if no pool has
    readable reserves, or if the inputs a detector needs are missing, the answer
    is REFUSED or INCONCLUSIVE - never a quiet "not flagged". A missing input
    reading as clean is the exact failure that made four systems in this repo
    look like they worked while doing nothing.

COST. Free. One Dexscreener token lookup and one Solana public-RPC call for the
mint authorities. No key required.

Exit codes: 0 not flagged, 1 FLAGGED, 2 refused/inconclusive.
"""
import json
import os
import sys

import detector
import resolve
import sources as S

try:
    import onchain
except Exception:                       # pragma: no cover
    onchain = None

# Slippage rule of thumb: a constant-product pool moves ~5% when the trade is
# about 1/20th of the quote-side depth. Used only to state what size the pool
# can absorb - a liquidity fact, not advice about whether to take it.
SLIPPAGE_DIVISOR = 20

# What Frank is actually going to trade. He starts with $1,000 and sizes around
# $100, so the number that matters at the moment he decides is what a $100
# ROUND TRIP costs in this specific pool - not a table in a report he read once.
# Constant-product impact paid twice, plus the pool fee twice.
DEFAULT_CLIP_USD = float(os.environ.get("CRYPTO_CLIP_USD", "100"))
POOL_FEE = 0.0025          # Raydium-class. pump.fun AMM is nearer 1%.

# Below this much quote-side depth the pool cannot be exited at ANY size, so
# there is nothing to assess. Caught in testing 2026-09-07: a dead pool with $0
# exitable depth returned "NOT FLAGGED", exit code 0 - which reads as clean.
# A detector answer about a pool nobody can trade is worse than no answer, and
# the labelled set both detectors were characterised on contains only pools with
# measurable depth. Refuse instead.
MIN_CHECKABLE_DEPTH = float(os.environ.get("CRYPTO_MIN_CHECKABLE_DEPTH", "100"))


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _pick_pair(pairs):
    """The pool a real order would hit: the deepest AMM by measured quote side.

    Deliberately NOT the first result. Dexscreener returns a token's pools in
    no guaranteed order, and pricing one pool while holding another is the WOFI
    failure that put a fake 333x in the record.
    """
    scored = []
    for p in pairs or []:
        if (p or {}).get("chainId") != "solana":
            continue
        d = resolve.exit_depth_usd(p)
        if d is not None:
            scored.append((d, p))
    scored.sort(key=lambda t: t[0], reverse=True)
    return scored


def analyse(contract):
    """Returns a dict. Never raises, never guesses a missing input."""
    out = {"contract": contract, "verdict": None, "reasons": [],
           "refusals": [], "warnings": [], "pair": None, "symbol": None,
           "exit_depth_usd": None, "liq_usd": None, "fdv_usd": None,
           "pools_seen": 0, "d1": None, "d2": None, "authorities": None,
           "max_size_5pct": None, "round_trip_pct": None,
           "clip_usd": DEFAULT_CLIP_USD, "concentration": None}

    if not contract or len(contract) < 32:
        out["verdict"] = "REFUSED"
        out["refusals"].append("that does not look like a Solana contract "
                               "address. Key on the contract, never the ticker - "
                               "tickers are not unique and are trivially cloned.")
        return out

    try:
        pairs = S.dexscreener_token(contract)
    except Exception as e:
        out["verdict"] = "REFUSED"
        out["refusals"].append(f"price source unreachable ({type(e).__name__}). "
                               f"No answer is better than a stale one.")
        return out

    out["pools_seen"] = len(pairs or [])
    scored = _pick_pair(pairs)
    if not scored:
        out["verdict"] = "REFUSED"
        out["refusals"].append(
            "no Solana pool with readable reserves. Either the token is not "
            "indexed yet, or every pool hides its quote side. Exit depth is the "
            "one number this whole check rests on and it cannot be measured.")
        return out

    depth, pair = scored[0]
    if depth is None or depth < MIN_CHECKABLE_DEPTH:
        out["verdict"] = "REFUSED"
        out["symbol"] = ((pair.get("baseToken") or {}).get("symbol") or "")[:16]
        out["exit_depth_usd"] = depth
        out["refusals"].append(
            f"the deepest pool holds ${depth:,.0f} on the quote side. That is "
            f"below ${MIN_CHECKABLE_DEPTH:,.0f} and cannot be exited at any "
            f"size - the pool is dead or drained. Both detectors were "
            f"characterised on pools with measurable depth, so neither has "
            f"anything to say here. This is NOT a clean result.")
        return out
    out["pair"] = pair.get("pairAddress")
    out["symbol"] = ((pair.get("baseToken") or {}).get("symbol") or "")[:16]
    out["exit_depth_usd"] = depth
    out["liq_usd"] = _f((pair.get("liquidity") or {}).get("usd"))
    out["fdv_usd"] = _f(pair.get("fdv")) or _f(pair.get("marketCap"))
    out["max_size_5pct"] = depth / SLIPPAGE_DIVISOR if depth else 0.0
    # Round-trip cost at his actual clip. Only ever computed from a MEASURED
    # depth - if depth is unknown this stays None and renders as "cannot be
    # measured", never as a default number.
    if depth and depth > 0:
        x = DEFAULT_CLIP_USD
        out["clip_usd"] = x
        out["round_trip_pct"] = 100.0 * ((x / (depth + x)) * 2 + 2 * POOL_FEE)
    else:
        out["clip_usd"] = DEFAULT_CLIP_USD
        out["round_trip_pct"] = None

    if len(scored) > 1:
        out["warnings"].append(
            f"{len(scored)} priced pools exist. This reads the DEEPEST "
            f"(${depth:,.0f} quote side). A different pool will quote a "
            f"different price, and they are not interchangeable.")

    # ---- the row the detectors score, built only from observation-time fields
    t1 = (pair.get("txns") or {}).get("h1") or {}
    row = {"liq": out["liq_usd"], "fdv": out["fdv_usd"],
           "sells_h1": t1.get("sells"), "buys_h1": t1.get("buys"),
           "txns_h1": (_f(t1.get("sells"), 0) + _f(t1.get("buys"), 0))
                      if (t1.get("sells") is not None or t1.get("buys") is not None)
                      else None}

    # D1 needs liq, fdv, sells_h1 and buys_h1. A missing input must read as
    # INCONCLUSIVE, never as a clean pass.
    d1_missing = [k for k in ("liq", "fdv", "sells_h1", "buys_h1")
                  if row.get(k) is None]
    if d1_missing:
        out["d1"] = {"verdict": "INCONCLUSIVE", "missing": d1_missing}
        out["warnings"].append(
            f"D1 could not run: {', '.join(d1_missing)} not reported. "
            f"That is NOT a pass - the strongest detector had no inputs.")
    else:
        hit = detector.d1(row)
        out["d1"] = {"verdict": "FLAGGED" if hit else "clear",
                     "liq_over_fdv": (row["liq"] / row["fdv"]) if row["fdv"] else None,
                     "sells_h1": row["sells_h1"], "buys_h1": row["buys_h1"]}
        if hit:
            out["reasons"].append(
                f"D1 SILENCE: the supply IS the pool (liq/fdv "
                f"{row['liq']/row['fdv']:.2f} >= 0.95) and nobody has ever sold "
                f"into it ({row['buys_h1']} buys, {row['sells_h1']} sells in 1h). "
                f"A price nobody has tested by leaving is not a price.")

    d2_missing = [k for k in ("liq", "txns_h1") if row.get(k) is None]
    if d2_missing:
        out["d2"] = {"verdict": "INCONCLUSIVE", "missing": d2_missing}
    else:
        hit = detector.d2(row)
        out["d2"] = {"verdict": "FLAGGED" if hit else "clear",
                     "liq": row["liq"], "txns_h1": row["txns_h1"]}
        if hit:
            out["reasons"].append(
                f"D2 MAGNITUDE+INACTIVITY: ${row['liq']:,.0f} of reported "
                f"liquidity with {row['txns_h1']:.0f} transactions in an hour. "
                f"NOTE: D2 is IN SAMPLE and unvalidated - treat as a prompt to "
                f"look harder, not as evidence.")

    # ---- capability checks. What the contract PERMITS, not an estimate.
    if onchain is not None:
        try:
            a = onchain.authorities(contract)
            out["authorities"] = a
            if a.get("authorities_error"):
                out["warnings"].append(
                    f"mint authorities unreadable ({a['authorities_error']}). "
                    f"Cannot confirm the deployer cannot print or freeze.")
            else:
                if a.get("can_mint"):
                    out["reasons"].append(
                        "MINT AUTHORITY LIVE: the deployer can print new supply "
                        "into your bid at any time.")
                if a.get("can_freeze"):
                    out["reasons"].append(
                        "FREEZE AUTHORITY LIVE: the deployer can stop you "
                        "selling. No amount of liquidity survives this.")
        except Exception as e:
            out["warnings"].append(f"authority check failed ({type(e).__name__}).")

    # ---- holder concentration. Unblocked 2026-09-07 when SOL_RPC was finally
    # routed through the Helius key that had been in .env since 08-23. The
    # public endpoint refuses getTokenLargestAccounts at any spacing, which is
    # why this never ran before. One holder sitting on most of the supply is a
    # fact Frank should see at the moment he decides.
    if onchain is not None:
        try:
            c = onchain.concentration(contract)
            out["concentration"] = c
            if c.get("concentration_error"):
                out["warnings"].append(
                    f"holder concentration unreadable ({c['concentration_error']}). "
                    f"Not a pass - it means we do not know.")
            else:
                t1 = c.get("top1_share")
                ex = c.get("top10_share_ex_largest")
                if t1 is not None and t1 >= 0.50:
                    out["warnings"].append(
                        f"TOP HOLDER HOLDS {100*t1:.1f}% of the sampled supply"
                        + (" (may be the pool itself - "
                           f"{100*ex:.1f}% excluding the largest account)"
                           if ex is not None else "")
                        + ". One wallet that size can end the price at will.")
        except Exception as e:
            out["warnings"].append(f"concentration check failed ({type(e).__name__}).")

    # ---- the depth sanity check, independent of either detector
    if out["liq_usd"] and depth is not None and out["liq_usd"] > 0:
        share = depth / out["liq_usd"]
        out["depth_over_liq"] = share
        if share < 0.10:
            out["reasons"].append(
                f"ONE-SIDED POOL: only {100*share:.2f}% of the ${out['liq_usd']:,.0f} "
                f"reported liquidity is on the side you would be paid in. The "
                f"headline figure overstates what you could sell into by "
                f"{1/share:.0f}x.")

    out["verdict"] = "FLAGGED" if out["reasons"] else "not flagged"
    return out


def render(r):
    L = []
    sym = f" {r['symbol']}" if r.get("symbol") else ""
    L.append(f"CONTRACT {r['contract'][:20]}...{sym}")
    L.append("")
    if r["verdict"] == "REFUSED":
        L.append("  >>> REFUSED - no answer given <<<")
        for x in r["refusals"]:
            L.append(f"      {x}")
        L.append("")
        L.append("  A refusal is the correct output when the data is not there.")
        L.append("  Do not read it as 'probably fine'.")
        return "\n".join(L)

    if r["verdict"] == "FLAGGED":
        L.append("  >>> FLAGGED <<<")
    else:
        L.append("  >>> NOT FLAGGED <<<")
    for x in r["reasons"]:
        L.append(f"      - {x}")
    L.append("")
    d = r.get("exit_depth_usd")
    L.append(f"  measured exit depth   ${d:,.0f}   (quote side only - what you"
             f" could be paid in)" if d is not None else
             "  measured exit depth   UNAVAILABLE")
    if r.get("liq_usd") is not None:
        L.append(f"  reported liquidity    ${r['liq_usd']:,.0f}"
                 + (f"   ({100*r['depth_over_liq']:.1f}% is really exitable)"
                    if (r.get("depth_over_liq") is not None
                        and (r.get("liq_usd") or 0) >= 1000) else ""))
    rt = r.get("round_trip_pct")
    if rt is None:
        L.append(f"  ${r.get('clip_usd', 100):,.0f} round trip     CANNOT BE MEASURED"
                 f" - no depth, so no estimate is given")
    else:
        verdict = ("cheap" if rt < 2 else "tolerable" if rt < 5
                   else "EXPENSIVE" if rt < 20 else "PROHIBITIVE")
        # A slippage number on a FLAGGED pool is arithmetic about a trade that
        # may not be completable at all. Never let it read as reassurance.
        if r["verdict"] == "FLAGGED":
            verdict += " -- but this pool is FLAGGED; the cost of leaving a"
            verdict += " fraud is not its quoted slippage"
        L.append(f"  ${r['clip_usd']:,.0f} round trip     {rt:.2f}%   {verdict}"
                 f"   (in + out, incl. {100*POOL_FEE:.2f}% fee each way)")
    c = r.get("concentration") or {}
    if c.get("top1_share") is not None:
        L.append(f"  top holder            {100*c['top1_share']:.1f}% of sampled supply"
                 + (f"   ({100*c['top10_share_ex_largest']:.1f}% excluding it)"
                    if c.get("top10_share_ex_largest") is not None else ""))
    elif c.get("concentration_error"):
        L.append(f"  top holder            UNREADABLE ({c['concentration_error']})")
    a = r.get("authorities") or {}
    if a.get("can_mint") is not None:
        L.append(f"  mint / freeze auth    "
                 f"{'CAN MINT' if a.get('can_mint') else 'revoked'} / "
                 f"{'CAN FREEZE' if a.get('can_freeze') else 'revoked'}")
    elif a.get("authorities_error"):
        L.append(f"  mint / freeze auth    UNREADABLE ({a['authorities_error']})")
    if r.get("max_size_5pct"):
        L.append(f"  size before ~5% slip  ${r['max_size_5pct']:,.0f}"
                 f"   (pool absorbs about 1/20th of quote depth)")
    L.append(f"  pools seen            {r['pools_seen']}")
    for k in ("d1", "d2"):
        s = r.get(k) or {}
        v = s.get("verdict")
        if v == "INCONCLUSIVE":
            L.append(f"  {k.upper()}                  INCONCLUSIVE - missing "
                     f"{', '.join(s.get('missing') or [])}")
        elif v:
            L.append(f"  {k.upper()}                  {v}")
    for w in r.get("warnings", []):
        L.append(f"  ! {w}")
    L.append("")
    L.append("  HOW MUCH THIS IS WORTH:")
    L.append("    D1 precision 97.3% [86.2, 99.5], recall 50.0% [38.7, 61.3],")
    L.append("    n=37 flagged, out of sample. D2 is IN SAMPLE and unvalidated.")
    L.append("    NOT FLAGGED MEANS 'NEITHER OF TWO FRAUDS WAS DETECTED'.")
    L.append("    D1 misses half. This says nothing about whether it goes up -")
    L.append("    there is no validated entry rule in this system, and five")
    L.append("    attempts to build one have been retracted.")
    return "\n".join(L)


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    r = analyse(argv[1].strip())
    if "--json" in argv:
        print(json.dumps(r, indent=1, default=str))
    else:
        print(render(r))
    return {"FLAGGED": 1, "REFUSED": 2}.get(r["verdict"], 0)


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main(sys.argv))
