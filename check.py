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


PHANTOM_MCAP = 1_000_000
PHANTOM_LIQ = 1_000
# ⛔ Measured 2026-09-23: the Dexscreener token endpoint returns at most 30
# pairs for ANY mint. SOL returns 30. At 30, every sum below is a floor.
PAIR_CAP = 30


def _all_pairs(pairs):
    """The TOKEN, not one of its pools: every pair summed. Standing rule 18.

    ⚠️ Sums the same payload `analyse` already fetched, so this stays offline in
    the test suite and costs no extra call. `allpairs.token()` is the same
    arithmetic for callers that have only a mint.

    ⚠️ It is still a correct sum of an OVERSTATING field - Dexscreener's
    liquidity overstates by a median 781x. It is for shape, venue spread and
    phantom detection. The exit is `chainfields.round_trip()`, which already
    routes across every pool.
    """
    liq = vol = 0.0
    depths, mcaps, quotes = [], [], {}
    for p in pairs or []:
        if (p or {}).get("chainId") != "solana":
            continue
        liq += _f((p.get("liquidity") or {}).get("usd"), 0) or 0
        vol += _f((p.get("volume") or {}).get("h24"), 0) or 0
        d = resolve.exit_depth_usd(p)
        if d is not None:
            depths.append(d)
        for k in ("marketCap", "fdv"):
            v = _f(p.get(k))
            if v:
                mcaps.append(v)
                break
        q = (p.get("quoteToken") or {}).get("symbol") or "unknown"
        quotes[q] = quotes.get(q, 0.0) + (_f((p.get("liquidity") or {}).get("usd"), 0) or 0)
    n = sum(1 for p in (pairs or []) if (p or {}).get("chainId") == "solana")
    mcap = max(mcaps) if mcaps else None
    # ⛔ Dexscreener returns AT MOST 30 pairs per token, whatever the token: SOL
    # returns 30. At the cap the sums are FLOORS, and the missing pairs cannot be
    # bounded because the returned set is not ordered by size. The phantom rule
    # therefore needs a COMPLETE sample - 30 arbitrary pools summing to nothing
    # says nothing about a 31st. The mint that forced the rule had 3.
    truncated = len(pairs or []) >= PAIR_CAP
    return {"pair_count": n, "pairs_truncated": truncated,
            "liq_all_pairs_is_floor": truncated,
            "liq_usd_all_pairs": liq if n else None,
            "vol24_all_pairs_usd": vol if n else None,
            # unknown stays None, never 0 - rule 5
            "exit_depth_all_pairs_usd": sum(depths) if depths else None,
            "mcap_usd": mcap,
            "quote_assets": dict(sorted(quotes.items(), key=lambda kv: -kv[1])),
            "phantom": bool(mcap and mcap > PHANTOM_MCAP and liq < PHANTOM_LIQ
                            and not truncated)}


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


# Injection point so the offline suite stays offline. `test_check.py` says
# "offline by construction - sources are monkeypatched, so this makes no network
# calls"; wiring chainfields in directly broke that promise silently, which is
# its own small version of standing rule 16.
def _round_trip(contract, usd):
    import chainfields
    return chainfields.round_trip(contract, usd)


def analyse(contract):
    """Returns a dict. Never raises, never guesses a missing input."""
    out = {"contract": contract, "verdict": None, "reasons": [],
           "refusals": [], "warnings": [], "pair": None, "symbol": None,
           "exit_depth_usd": None, "liq_usd": None, "fdv_usd": None,
           "pools_seen": 0, "d1": None, "d2": None, "authorities": None,
           "max_size_5pct": None, "round_trip_pct": None,
           "clip_usd": DEFAULT_CLIP_USD, "concentration": None,
           # ⭐ THE REALIZABLE MEASUREMENT. Backlog A4: chainfields is the
           # trusted-field source and until now NOTHING in the production path
           # used it. Unknown stays None throughout - never 0.
           "realizable": None, "realizable_usd_back": None,
           "realizable_cost_pct": None, "realizable_venues": None,
           # ⛔⛔ ALL PAIRS, standing rule 18. Frank, 2026-09-22: "we have been
           # reading one pool on tokens that trade across thirty." Everything
           # above named `exit_depth_usd` / `liq_usd` describes the DEEPEST POOL
           # ONLY. These describe the TOKEN. On the real EMBER the deepest pool
           # holds $663,260 of $2,331,895 - a 3.52x understatement, and it is
           # worst exactly on the pairing-launchpad assets that matter most.
           "pair_count": 0, "liq_usd_all_pairs": None,
           "exit_depth_all_pairs_usd": None, "vol24_all_pairs_usd": None,
           "mcap_usd": None, "quote_assets": None, "phantom": None,
           "pairs_truncated": None, "liq_all_pairs_is_floor": None}

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
    out.update(_all_pairs(pairs))

    # ⛔ THE PHANTOM RULE, pre-committed (standing rule 18). A market cap over
    # $1,000,000 on under $1,000 of liquidity summed across EVERY pair is a
    # ghost, not a token, and must never produce a finding. The case that forced
    # it: a mint symbol'd EMBER claiming $1,314,046,208 on $1.39 of backing,
    # which we analysed for a full day as though it were real.
    if out["phantom"]:
        out["verdict"] = "REFUSED"
        out["refusals"].append(
            f"PHANTOM: a claimed market cap of ${out['mcap_usd']:,.0f} on "
            f"${out['liq_usd_all_pairs']:,.2f} of liquidity summed across all "
            f"{out['pair_count']} pairs. There is nothing behind the cap. This is "
            f"not a thin token, it is a number with no market under it - do not "
            f"price it, do not compare it, do not report a multiple on it.")
        return out

    scored = _pick_pair(pairs)
    if not scored:
        out["verdict"] = "REFUSED"
        out["refusals"].append(
            "no Solana pool with readable reserves. Either the token is not "
            "indexed yet, or every pool hides its quote side. Exit depth is the "
            "one number this whole check rests on and it cannot be measured.")
        return out

    depth, pair = scored[0]
    out["symbol"] = ((pair.get("baseToken") or {}).get("symbol") or "")[:16]

    # ---------------------------------------------------------------------
    # ⭐ ASK THE SELLER'S QUESTION BEFORE REFUSING. Backlog A4 + A13.
    #
    # ⛔ FOUND BY RUNNING THIS ON A REAL CONTRACT, 2026-09-18. `check.py`
    # refused OpenClaw as "dead or drained - $0 on the quote side" while
    # Jupiter round-tripped the same token at 0.77% in the same minute. The
    # refusal was firing on `resolve.exit_depth_usd()`, which failed 5 of 6
    # reads on 2026-09-17, and it returned BEFORE any trusted measurement ran.
    #
    # A refusal is the right output when nothing can be measured. It is the
    # WRONG output when something can be measured and we did not look. So the
    # realizable check now runs first, and a live route overrides a reserve
    # scan that found nothing.
    #
    # ⚠️ The override is one-directional. A working route can rescue a failed
    # reserve read; it can never suppress a refusal when BOTH say dead.
    # ---------------------------------------------------------------------
    try:
        rt = _round_trip(contract, DEFAULT_CLIP_USD)
        out["realizable"] = rt.get("verdict")
        out["realizable_usd_back"] = rt.get("usd_back")
        out["realizable_cost_pct"] = rt.get("rt_cost_pct")
        out["realizable_venues"] = rt.get("venues")
    except Exception as e:
        out["warnings"].append(
            f"realizable check unavailable ({type(e).__name__}) - the reported "
            f"and reserve-derived figures below are NOT corroborated.")

    _routable = out["realizable"] in ("TRADEABLE", "COSTLY")
    if depth is None or depth < MIN_CHECKABLE_DEPTH:
        if not _routable:
            out["verdict"] = "REFUSED"
            out["exit_depth_usd"] = depth
            out["refusals"].append(
                f"the deepest pool holds ${depth:,.0f} on the quote side, below "
                f"${MIN_CHECKABLE_DEPTH:,.0f}"
                + (f", and a live ${DEFAULT_CLIP_USD:,.0f} round trip returns "
                   f"{out['realizable']}" if out["realizable"]
                   else ", and no live quote could be obtained either")
                + ". Two independent measurements agree there is no exit. Both "
                  "detectors were characterised on pools with measurable depth, "
                  "so neither has anything to say here. NOT a clean result.")
            return out
        # ⭐ The reserve scan found nothing and Jupiter can route it anyway.
        out["warnings"].append(
            f"RESERVE SCAN DISAGREES WITH THE MARKET: exit_depth_usd read "
            f"${depth:,.0f} but a live ${DEFAULT_CLIP_USD:,.0f} round trip "
            f"returns {out['realizable']}"
            + (f" (${out['realizable_usd_back']:,.2f} back, "
               f"{out['realizable_cost_pct']:.2f}% cost)"
               if out["realizable_usd_back"] is not None else "")
            + ". Trusting the live route. ⛔ Every depth-derived number below is "
              "unreliable for this token - see docs/BACKLOG.md A13.")
    out["pair"] = pair.get("pairAddress")
    out["symbol"] = ((pair.get("baseToken") or {}).get("symbol") or "")[:16]
    out["exit_depth_usd"] = depth
    out["liq_usd"] = _f((pair.get("liquidity") or {}).get("usd"))
    out["fdv_usd"] = _f(pair.get("fdv")) or _f(pair.get("marketCap"))
    # ⭐ SIZED OFF ALL PAIRS, not the deepest one. A router reaches every pool,
    # so the depth a sell actually meets is the sum. Falls back to the deepest
    # pool when the per-pair reads failed, and stays None when nothing is
    # measurable - never 0 (rule 5).
    sizing_depth = out["exit_depth_all_pairs_usd"] or depth
    out["sizing_depth_usd"] = sizing_depth
    out["max_size_5pct"] = sizing_depth / SLIPPAGE_DIVISOR if sizing_depth else 0.0
    # Round-trip cost at his actual clip. Only ever computed from a MEASURED
    # depth - if depth is unknown this stays None and renders as "cannot be
    # measured", never as a default number.
    if sizing_depth and sizing_depth > 0:
        x = DEFAULT_CLIP_USD
        out["clip_usd"] = x
        out["round_trip_pct"] = 100.0 * ((x / (sizing_depth + x)) * 2 + 2 * POOL_FEE)
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
        # ⛔⛔ D1 compares ONE POOL'S liquidity against the WHOLE TOKEN'S fdv,
        # which is apples to oranges on a token with many pools and biases it
        # toward flagging. On a 30-pool asset the numerator is understated ~3.5x.
        # ⚠️ D1's recall was characterised on single-pair `liq`, so changing its
        # input silently would relabel the whole record. It is NOT changed here.
        # Instead the same detector is run on the all-pairs liquidity and the
        # disagreement is reported, so a flag that exists only because we read
        # one of N pools cannot reach Frank as a rug call. Pre-commit needed
        # before the input itself moves - BACKLOG A57.
        row_all = dict(row, liq=out["liq_usd_all_pairs"])
        hit_all = detector.d1(row_all) if out["liq_usd_all_pairs"] is not None else hit
        if hit and not hit_all:
            out["warnings"].append(
                f"⛔ D1's flag is an ARTIFACT OF READING ONE POOL. It fired on the "
                f"deepest pool's ${row['liq']:,.0f} against a token-wide fdv, but "
                f"this token has {out['pair_count']} Solana pools holding "
                f"${out['liq_usd_all_pairs']:,.0f} between them, and D1 does NOT "
                f"fire on that. Treat the flag as unproven.")
        out["d1"] = {"verdict": "FLAGGED" if hit else "clear",
                     "verdict_all_pairs": "FLAGGED" if hit_all else "clear",
                     "one_pool_artifact": bool(hit and not hit_all),
                     "liq_over_fdv_all_pairs": ((out["liq_usd_all_pairs"] / row["fdv"])
                                                if (row["fdv"] and out["liq_usd_all_pairs"]
                                                    is not None) else None),
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

    # ---------------------------------------------------------------------
    # ⭐ REALIZABLE LIQUIDITY - the only measure that asks the seller's question.
    #
    # Everything above this point rests on `resolve.exit_depth_usd()`, which
    # infers the quote side from pool reserves and FAILED 5 OF 6 READS on
    # 2026-09-17 ("scan missed the real vault", "no USD price for quote mint").
    # This asks Jupiter instead: buy $100 of the token, sell back exactly what
    # that returned, and report what comes back. No reserves, no pool layout,
    # no price feed - and nothing is executed.
    #
    # ⚠️ AFFORDABLE HERE AND NOWHERE ELSE. check.py is ONE contract per
    # invocation, which is a decision point. chainfields caps Jupiter at 55/min
    # process-wide, so this must never be copied into the per-row scan path.
    #
    # ⛔ A failure here NEVER becomes a number. If the quote cannot be had, the
    # field stays None and renders as "cannot be measured" (standing rule 5).
    # ---------------------------------------------------------------------
    # ⭐ Already measured above, BEFORE the refusal gate, so a live route can
    # rescue a failed reserve read. This block only turns that measurement into
    # a reason.
    if out["realizable"] in ("TOTAL_LOSS", "NO_SELL_ROUTE", "NO_BUY_ROUTE"):
        _b = out["realizable_usd_back"]
        out["reasons"].append(
            f"NOT EXITABLE: a live round trip at ${DEFAULT_CLIP_USD:,.0f} "
            f"returns {out['realizable']}"
            + (f" - ${_b:,.2f} back on ${DEFAULT_CLIP_USD:,.0f} in"
               if _b is not None else "")
            + ". This is what a seller actually experiences, measured now, "
              "not inferred from reserves.")
    # ⛔ NO "OVERSTATEMENT RATIO" HERE, and the reason is worth keeping. My
    # first version computed liq_usd / usd_back and flagged anything over 100x.
    # That is not a finding, it is arithmetic: usd_back from a $100 probe is
    # ~$100 for ANY healthy token, so the ratio is just liq/100 and it fires on
    # every pool above $10k. test_check.py caught it immediately by flagging two
    # deliberately-clean fixtures.
    #
    # The real 781x result compares reported liquidity against EXITABLE DEPTH -
    # the most that can be taken out - which a fixed $100 probe cannot measure.
    # Getting it right needs chainfields.depth_curve() and a defensible
    # definition of "exitable"; until then there is no number here, which is the
    # correct amount of number to have.

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


def _safe_sym(sym):
    """Strip bidi/zero-width controls and mark them. See docs/SYMBOL_ATTACKS.md.

    ⛔ 112 contracts in our corpus carry a text-direction override in the symbol;
    one renders as "USDC" and claimed $35M of liquidity with zero sells. A
    terminal honours U+202E exactly like a browser does, so this output is as
    exposed as the dashboard was.
    """
    BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E, 0x2066, 0x2067, 0x2068,
            0x2069, 0x200E, 0x200F, 0x200B, 0x200C, 0x200D, 0xFEFF}
    raw = str(sym or "")
    clean = "".join(c for c in raw if ord(c) not in BIDI)
    return clean + ("  [!BIDI]" if len(clean) != len(raw) else "")


def render(r):
    L = []
    sym = f" {_safe_sym(r['symbol'])}" if r.get("symbol") else ""
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
    # ⭐ THE TOKEN FIRST, one pool second. Standing rule 18: reading one pool on
    # a token that trades across thirty is a 3% sample presented as the whole,
    # so the summed line is the one that answers "what is this token".
    n = r.get("pair_count") or 0
    da = r.get("exit_depth_all_pairs_usd")
    L.append(f"  pools, this token     {n}"
             + ("   <- AT THE API CAP: 30 means '30 or more', so every figure "
                "below is a FLOOR" if r.get("pairs_truncated") else ""))
    L.append(f"  exit depth, ALL pools ${da:,.0f}   (quote side only - what you"
             f" could be paid in)" if da is not None else
             "  exit depth, ALL pools UNAVAILABLE")
    if r.get("liq_usd_all_pairs") is not None:
        L.append(f"  reported liq, ALL     ${r['liq_usd_all_pairs']:,.0f}"
                 + (f"   (claimed cap ${r['mcap_usd']:,.0f})"
                    if r.get("mcap_usd") else ""))
    qa = r.get("quote_assets") or {}
    if len(qa) > 1:
        L.append("  paired against        "
                 + ", ".join(f"{_safe_sym(k)} ${v:,.0f}"
                             for k, v in list(qa.items())[:5]))
    d = r.get("exit_depth_usd")
    L.append(f"  ...deepest pool alone ${d:,.0f}"
             + (f"   ({da/d:.2f}x less than the token)"
                if (da and d and d > 0) else "") if d is not None else
             "  ...deepest pool alone UNAVAILABLE")
    if r.get("liq_usd") is not None:
        L.append(f"  ...its reported liq   ${r['liq_usd']:,.0f}"
                 + (f"   ({100*r['depth_over_liq']:.1f}% is really exitable)"
                    if (r.get("depth_over_liq") is not None
                        and (r.get("liq_usd") or 0) >= 1000) else ""))
    # ⭐ The realizable line goes ABOVE the inferred ones: it is the only one
    # that asks what a seller gets, and it should be read first.
    _rv = r.get("realizable")
    if _rv is None:
        L.append("  realizable (Jupiter)  CANNOT BE MEASURED - no quote")
    else:
        _b, _c = r.get("realizable_usd_back"), r.get("realizable_cost_pct")
        L.append(f"  realizable (Jupiter)  {_rv}"
                 + (f"   ${_b:,.2f} back on ${r.get('clip_usd', 100):,.0f}"
                    f"  ({_c:.2f}% cost)" if _b is not None and _c is not None
                    else "   - no sell route at any size")
                 + (f"   via {'+'.join(r['realizable_venues'][:3])}"
                    if r.get("realizable_venues") else ""))
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
