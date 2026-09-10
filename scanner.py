"""
New-pair scanner. Pulls the newest pools on a chain, enriches them, scores them,
and returns a ranked shortlist.

Design principle: this is built to REJECT things. On a busy day thousands of
tokens launch and almost all go to zero. A scanner that surfaces 200 candidates
is worthless. The job is to throw away 99% and be honest about the survivors.

Nothing here is a recommendation. It is a filter over public data.
"""
import os, time, math, datetime as dt
import venue
import plausibility
import sources as S
import namecheck
import paper
import paperv2
import watchlist
import onchain
import weights

# ---- thresholds. tune these; they are the whole product ----
CFG = dict(
    min_liquidity_usd   = 8_000,    # below this you cannot exit
    max_liquidity_usd   = 2_000_000,# above this the move already happened
    min_volume_h1_usd   = 5_000,
    min_txns_h1         = 25,
    max_age_hours       = 24,
    min_vol_liq_ratio   = 0.35,     # real turnover vs parked liquidity
    max_vol_liq_ratio   = 40,       # absurd ratio = wash trading
    min_buy_sell_ratio  = 0.75,     # heavy sell pressure early = exit liquidity
    max_buy_sell_ratio  = 6.0,      # too perfect = likely bots
)

def _f(x, d=0.0):
    try: return float(x)
    except (TypeError, ValueError): return d

def age_hours(pair):
    ms = pair.get("pairCreatedAt")
    if not ms: return None
    return (time.time() - ms/1000) / 3600

def resolve_exit_depth(pair):
    """Quote-side USD for one pool. Local copy of resolve.exit_depth_usd() to
    keep the scanner free of a circular import."""
    liq = pair.get("liquidity") or {}
    q = _f(liq.get("quote"))
    pu, pn = _f(pair.get("priceUsd")), _f(pair.get("priceNative"))
    if q is not None and pu and pn:
        return q * (pu / pn)
    total, base = _f(liq.get("usd")), _f(liq.get("base"))
    if total is not None and base is not None and pu:
        return max(0.0, total - base * pu)
    return None


def score(pair):
    """Returns (score 0-100, reasons, flags, gates, weights_version).

    Points now come from weights.active(), which are derived from real outcomes
    rather than hand-picked. A gate weighted 0 still records whether it passed,
    so it stays measurable and can earn its weight back later - it just stops
    contributing to the score. buy/sell is currently 0 because tokens that FAIL
    it won nearly twice as often as tokens that pass it.
    """
    W, WVER, _ = weights.active()
    liq  = _f((pair.get("liquidity") or {}).get("usd"))
    v1   = _f((pair.get("volume") or {}).get("h1"))
    v24  = _f((pair.get("volume") or {}).get("h24"))
    t1   = pair.get("txns", {}).get("h1", {}) or {}
    buys, sells = _f(t1.get("buys")), _f(t1.get("sells"))
    txns = buys + sells
    age  = age_hours(pair)
    ch1  = _f((pair.get("priceChange") or {}).get("h1"))
    fdv  = _f(pair.get("fdv"))

    reasons, flags = [], []
    gates = {k: False for k in ('liquidity','txns','vol1h','volliq','buysell','age')}
    pts = 0

    if liq < CFG["min_liquidity_usd"]:
        flags.append(f"liquidity {liq:,.0f} below floor - cannot exit size")
    elif liq > CFG["max_liquidity_usd"]:
        flags.append(f"liquidity {liq:,.0f} - move likely already happened")
    else:
        pts += W.get("liquidity", 0); reasons.append(f"liquidity {liq:,.0f}"); gates["liquidity"] = True

    if txns < CFG["min_txns_h1"]:
        flags.append(f"only {txns:.0f} txns in the last hour - no real interest")
    else:
        pts += W.get("txns", 0); reasons.append(f"{txns:.0f} txns/h"); gates["txns"] = True

    if v1 < CFG["min_volume_h1_usd"]:
        flags.append(f"1h volume {v1:,.0f} too thin")
    else:
        pts += W.get("vol1h", 0); reasons.append(f"1h vol {v1:,.0f}"); gates["vol1h"] = True

    ratio = (v24 / liq) if liq else 0
    if ratio < CFG["min_vol_liq_ratio"]:
        flags.append(f"vol/liq {ratio:.2f} - liquidity parked, nothing trading")
    elif ratio > CFG["max_vol_liq_ratio"]:
        flags.append(f"vol/liq {ratio:.1f} - implausible, suspect wash trading")
    else:
        pts += W.get("volliq", 0); reasons.append(f"vol/liq {ratio:.1f}"); gates["volliq"] = True

    bs = (buys / sells) if sells else (buys if buys else 0)
    if sells and bs < CFG["min_buy_sell_ratio"]:
        flags.append(f"buy/sell {bs:.2f} - being distributed into")
    elif bs > CFG["max_buy_sell_ratio"]:
        flags.append(f"buy/sell {bs:.1f} - too clean, likely bot-driven")
    elif sells:
        pts += W.get("buysell", 0); reasons.append(f"buy/sell {bs:.2f}"); gates["buysell"] = True

    if age is not None:
        if age > CFG["max_age_hours"]:
            flags.append(f"{age:.1f}h old - outside the window")
        else:
            pts += W.get("age", 0); reasons.append(f"{age:.1f}h old"); gates["age"] = True

    if fdv and liq and fdv / liq > 250:
        flags.append(f"FDV/liq {fdv/liq:.0f} - valuation unsupported by liquidity")

    # WITHDRAWN 2026-09-05, same day it shipped. This block used to return 0
    # for a row failing plausibility.assess(). It was an unvalidated filter and
    # it had no business changing a score:
    #
    #   - `age_hours` is PAIR age, from pairCreatedAt, not token age. A new
    #     pool for an established token is indistinguishable from a new token,
    #     so a magnitude-for-age rule can zero a legitimate large token.
    #   - The magnitude ceiling was never tested against ground truth. When it
    #     finally was, only 1 of 12 sampled rows in that cohort could still be
    #     resolved at all, so it remains unmeasured.
    #   - A filter with an unmeasured false-positive rate is worse than none.
    #
    # The assessment is still ATTACHED to every observation as description, in
    # journal.record(). Nothing scores on it, nothing filters on it, and
    # nothing is excluded from the journal because of it.

    return min(pts, 100), reasons, flags, gates, WVER

# Enrichment budget. Dexscreener answers in ~0.2s when healthy and was measured
# at 6.3s degraded on 2026-08-30, with read timeouts costing 20s x 3 tries.
# Without a ceiling one stalled pool eats the whole pass. When the budget is
# spent the loop stops and returns what it has, because a partial scan is worth
# enormously more than a lost hour.
SCAN_BUDGET_S = float(os.environ.get("CRYPTO_SCAN_BUDGET_S", "150"))

# Only rows at or above this score get an authority check, plus anything the
# paper log would enter. Bounds the RPC spend to the rows we would act on.
AUTHORITY_CHECK_SCORE = int(os.environ.get("CRYPTO_AUTHORITY_SCORE", "70"))
LAST_SCAN = {"pools": 0, "enriched": 0, "failed": 0, "budget_hit": False}


def scan(network="solana", pages=None, verbose=True, on_row=None, budget_s=None):
    """Pull new pools, enrich and score each one.

    on_row is called with every scored row AS IT IS PRODUCED. The caller
    journals from there rather than waiting for the return value: on
    2026-08-30 three consecutive passes journalled zero observations because
    enrichment stalled and journal.record was only ever called after the loop
    finished. Incremental journalling turns that into a partial hour.
    """
    # pages=None defers to sources.PAGES, the CRYPTO_NEW_POOL_PAGES dial.
    # Hard-coding it here is what kept the funnel at 2 pages.
    pools = S.new_pools(network, pages=pages)
    if verbose: print(f"pulled {len(pools)} new pools on {network}")
    budget = SCAN_BUDGET_S if budget_s is None else budget_s
    started = time.time()
    LAST_SCAN.update(pools=len(pools), enriched=0, failed=0, budget_hit=False)
    rows = []
    for i, p in enumerate(pools):
        if time.time() - started > budget:
            LAST_SCAN["budget_hit"] = True
            if verbose:
                print(f"  enrichment budget {budget:.0f}s spent after {i}/{len(pools)} "
                      f"pools - stopping and keeping what we have")
            break
        addr = p.get("attributes", {}).get("address")
        if not addr: continue
        # GeckoTerminal already told us the venue in the discovery payload.
        # Reading it costs nothing and it is the dimension that decides whether
        # a "liquidity" figure means anything at all.
        gt_dex = venue.from_discovery(p)
        try:
            pair = S.dexscreener_pair(network, addr)
        except Exception:
            LAST_SCAN["failed"] += 1
            continue
        if not pair:
            LAST_SCAN["failed"] += 1
            continue
        sc, reasons, flags, gates, wver = score(pair)
        # Name-safety runs AFTER numeric scoring and can veto outright.
        # Impersonation tokens often have the best numbers - that is the bait.
        nf = namecheck.check(pair.get("baseToken", {}).get("symbol", ""),
                             pair.get("baseToken", {}).get("name", ""))
        if nf:
            flags = nf + flags
            if any("IMPERSONATION" in f for f in nf):
                sc = 0
        t1 = pair.get("txns", {}).get("h1", {}) or {}
        row = dict(
            name   = pair.get("baseToken", {}).get("symbol", "?"),
            price_usd = _f(pair.get("priceUsd")),
            fdv       = _f(pair.get("fdv")),
            vol_h1    = _f((pair.get("volume") or {}).get("h1")),
            chg_h24   = _f((pair.get("priceChange") or {}).get("h24")),
            txns_h1   = int(_f(t1.get("buys")) + _f(t1.get("sells"))),
            buys_h1   = int(_f(t1.get("buys"))),
            sells_h1  = int(_f(t1.get("sells"))),
            addr   = pair.get("baseToken", {}).get("address", ""),
            pair   = addr,
            score  = sc,
            liq    = _f((pair.get("liquidity") or {}).get("usd")),
            # THE RESERVES THEMSELVES, not a summary of them. `liq` counts both
            # sides with the base valued at its own price; only the quote side
            # can pay you. We already have this object in hand, so storing the
            # split costs nothing and turns exit depth into a recorded fact
            # instead of something that needs a live refetch later - by which
            # time Dexscreener has dropped 79% of the tokens worth labelling.
            liq_base  = _f((pair.get("liquidity") or {}).get("base")),
            liq_quote = _f((pair.get("liquidity") or {}).get("quote")),
            price_native = _f(pair.get("priceNative")),
            exit_depth_usd = resolve_exit_depth(pair),
            dex_id = pair.get("dexId") or gt_dex,
            gt_dex = gt_dex,
            v24    = _f((pair.get("volume") or {}).get("h24")),
            age_h  = age_hours(pair),
            chg_h1 = _f((pair.get("priceChange") or {}).get("h1")),
            url    = pair.get("url", ""),
            reasons= reasons, flags = flags,
            gates  = gates, weights_version = wver,
        )
        venue.annotate(row, dex=row.get("dex_id"))
        # VOLUME, DERIVED. vol_h1 and vol_h24 have been stored since day one and
        # used nowhere. Point-in-time volume is a level; these two are the shape.
        # vol/liq is turnover against parked liquidity - the same quantity the
        # scorer already gates on, now recorded per row so it can be analysed
        # rather than only thresholded. vol_h1/vol_h24 is the burst ratio: 1/24
        # is a token trading evenly, well above that is a token trading NOW.
        _v1, _v24, _lq = row.get("vol_h1"), row.get("v24"), row.get("liq")
        row["vol_to_liq"] = round(_v1 / _lq, 6) if (_v1 is not None and _lq) else None
        row["vol_burst"] = round(_v1 / _v24, 6) if (_v1 is not None and _v24) else None
        # APPROACH BAND. A token between $45k and $69k of FDV is inside the only
        # window where graduation is still ahead of it and observable. The
        # normal 1/6/24/168h schedule cannot see a crossing that takes minutes,
        # so these go on a watchlist checked every pass instead.
        try:
            if watchlist.consider(row):
                row["watchlisted"] = True
                if verbose:
                    print(f"  [watchlist] +{row.get('name')} {row['addr'][:12]} "
                          f"fdv ${(row.get('fdv') or 0):,.0f}")
        except Exception as e:
            print(f"  [watchlist] {type(e).__name__}: {str(e)[:90]}")
        # MINT / FREEZE AUTHORITY. One getAccountInfo on the mint, free and
        # keyless. This is not a statistical signal and is not treated as one:
        # it is a CAPABILITY. Live mint authority means the deployer can print
        # supply into your bid; live freeze authority means they can stop you
        # selling. Either one alone makes a position untakeable regardless of
        # how good the numbers look.
        #
        # Measured 2026-09-05 across 228 tokens: 227 had both already revoked,
        # because the launchpads revoke automatically. So as a FEATURE it has
        # near-zero variance and must never enter a score. As a DISQUALIFIER it
        # still earns its call, because the one token in 228 that keeps its
        # authority is exactly the one you must not hold.
        #
        # Run only on rows we would actually act on - anything clearing the pass
        # score or eligible for the paper log - which is ~2-8 per pass rather
        # than ~75, and keeps the public RPC well inside its limits.
        # Decided on facts, never on the score. See paper.wants_authority_check:
        # the old rule let the score gate the evidence, so a low-scoring token
        # could never be verified and therefore could never qualify.
        _act = paper.wants_authority_check(row)
        # A NON-ATTEMPT IS A FACT, AND IT HAS TO BE WRITTEN DOWN.
        # 201 rows on 2026-09-07..10 carried can_mint=None with no error beside
        # it, so "we never looked" and "we looked and it failed" read the same
        # downstream. That is the label corruption again, one level up: the
        # value is honestly absent, but WHY it is absent was not recorded.
        row["authorities_checked"] = bool(_act and row.get("addr"))
        if not row["authorities_checked"]:
            row["authorities_skipped"] = (
                "no address" if not row.get("addr")
                else "not amm" if (row.get("venue_type") or "") != "amm"
                else "exit depth below the entry floor"
                if (row.get("exit_depth_usd") or 0) < paper.MIN_EXIT_DEPTH
                else "no sell side")
        if _act and row.get("addr"):
            try:
                _a = onchain.authorities(row["addr"])
                row["mint_authority"] = _a.get("mint_authority")
                row["freeze_authority"] = _a.get("freeze_authority")
                row["can_mint"] = _a.get("can_mint")
                row["can_freeze"] = _a.get("can_freeze")
                row["authorities_error"] = _a.get("authorities_error")
                if _a.get("can_mint"):
                    row["flags"] = ["MINT AUTHORITY LIVE - deployer can print "
                                    "supply into your bid"] + list(row.get("flags") or [])
                if _a.get("can_freeze"):
                    row["flags"] = ["FREEZE AUTHORITY LIVE - deployer can stop "
                                    "you selling"] + list(row.get("flags") or [])
                time.sleep(onchain.RPC_PACE_S)
            except Exception as e:
                row["authorities_error"] = f"{type(e).__name__}"

        # FORWARD PAPER LOG. The one place in this codebase where a decision is
        # recorded with no knowledge of what happens next. Every retrospective
        # finding here has died of leakage - a feature read after the outcome
        # had already partly occurred - and no amount of care with historical
        # data fixes that, because history has no ordering we can trust. This
        # does. It must stay inside the enrichment loop, before any outcome
        # exists, and it must never be moved into a later pass.
        try:
            _ok, _why = paper.qualifies(row)
            if _ok and row.get("addr"):
                _e = paper.open_entry(
                    row["addr"], symbol=row.get("name"),
                    price=row.get("price_usd"),
                    exit_depth=row.get("exit_depth_usd"),
                    liq=row.get("liq"), fdv=row.get("fdv"),
                    score=row.get("score"), venue_type=row.get("venue_type"),
                    dex_id=row.get("dex_id"), pair=row.get("pair"))
                if _e is not None:
                    row["paper_entry"] = _e["hash"][:12]
                    if verbose:
                        print(f"  [paper] entered {row.get('name')} "
                              f"{row['addr'][:12]} @ ${row.get('price_usd')} "
                              f"depth ${row.get('exit_depth_usd'):,.0f}")
        except Exception as e:
            print(f"  [paper] {type(e).__name__}: {str(e)[:90]}")
        # RULE_V2 IN PARALLEL, over the same row, in the same pass. Sequential
        # would have confounded the filter change with the market change; this
        # is the same market, the same hour, two filters. v1 above is untouched
        # and stays pinned - a v2 failure can never affect a v1 entry, which is
        # why this is its own try block and its own ledger.
        try:
            _v2, _v2why = paperv2.open_entry(row)
            if _v2 is not None:
                row["paper_v2_entry"] = _v2["hash"][:12]
                row["paper_v2_arm"] = _v2["arm"]
                if verbose:
                    print(f"  [v2/{_v2['arm']}] entered {row.get('name')} "
                          f"{str(row.get('addr'))[:12]} "
                          f"(score {row.get('score')}, "
                          f"{'also v1' if _v2['also_qualifies_v1'] else 'v1 REJECTED: ' + str(_v2['v1_reason'])[:40]})")
        except Exception as e:
            print(f"  [v2] {type(e).__name__}: {str(e)[:90]}")
        rows.append(row)
        LAST_SCAN["enriched"] += 1
        if on_row:
            on_row(row)          # journal NOW, not after the loop
        S.pace()
    rows.sort(key=lambda r: r["score"], reverse=True)
    return rows


def report(rows, min_score=70, show=10):
    passed = [r for r in rows if r["score"] >= min_score]
    print(f"\n{len(rows)} scanned -> {len(passed)} cleared {min_score}\n")
    for r in passed[:show]:
        print(f"  [{r['score']:3d}] {r['name']:<14} liq {r['liq']:>10,.0f}  "
              f"24h vol {r['v24']:>12,.0f}  {r['age_h']:.1f}h  1h {r['chg_h1']:+.1f}%")
        print(f"        {', '.join(r['reasons'])}")
        if r["flags"]: print(f"        WARN: {'; '.join(r['flags'])}")
        print(f"        {r['url']}")
    if not passed:
        print("  Nothing cleared the bar. That is the normal result and it is the point.")
        near = [r for r in rows if r["score"] >= min_score - 20][:5]
        if near:
            print(f"\n  Closest misses:")
            for r in near:
                print(f"   [{r['score']:3d}] {r['name']:<14} rejected: {r['flags'][0] if r['flags'] else '-'}")
    return passed

if __name__ == "__main__":
    import sys
    net = sys.argv[1] if len(sys.argv) > 1 else "solana"
    rows = scan(net, pages=2)
    report(rows)
