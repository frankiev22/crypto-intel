"""
New-pair scanner. Pulls the newest pools on a chain, enriches them, scores them,
and returns a ranked shortlist.

Design principle: this is built to REJECT things. On a busy day thousands of
tokens launch and almost all go to zero. A scanner that surfaces 200 candidates
is worthless. The job is to throw away 99% and be honest about the survivors.

Nothing here is a recommendation. It is a filter over public data.
"""
import os, time, math, datetime as dt
import sources as S
import namecheck
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

    return min(pts, 100), reasons, flags, gates, WVER

# Enrichment budget. Dexscreener answers in ~0.2s when healthy and was measured
# at 6.3s degraded on 2026-08-30, with read timeouts costing 20s x 3 tries.
# Without a ceiling one stalled pool eats the whole pass. When the budget is
# spent the loop stops and returns what it has, because a partial scan is worth
# enormously more than a lost hour.
SCAN_BUDGET_S = float(os.environ.get("CRYPTO_SCAN_BUDGET_S", "150"))
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
            v24    = _f((pair.get("volume") or {}).get("h24")),
            age_h  = age_hours(pair),
            chg_h1 = _f((pair.get("priceChange") or {}).get("h1")),
            url    = pair.get("url", ""),
            reasons= reasons, flags = flags,
            gates  = gates, weights_version = wver,
        )
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
