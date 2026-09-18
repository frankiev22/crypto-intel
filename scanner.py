"""
New-pair scanner. Pulls the newest pools on a chain, enriches them, scores them,
and returns a ranked shortlist.

Design principle: this is built to REJECT things. On a busy day thousands of
tokens launch and almost all go to zero. A scanner that surfaces 200 candidates
is worthless. The job is to throw away 99% and be honest about the survivors.

Nothing here is a recommendation. It is a filter over public data.
"""
import os, time, math, json, datetime as dt
import venue
import plausibility
import sources as S
import namecheck
import paper
import paperv2
import watchlist
import onchain
import weights
import paperv3
import chainfields

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
    keep the scanner free of a circular import.

    ⛔ EVERY _f HERE PASSES None EXPLICITLY, AND THAT IS THE WHOLE POINT.
    This module's `_f` defaults to 0.0 while resolve's and watchlist's default
    to None, so this copy - the one that writes `exit_depth_usd` onto every
    journalled row - was turning a MISSING field into a measured zero. Measured
    2026-09-18: 11,490 of 15,222 rows (75.5%) carry exactly 0.0, essentially all
    bonding-curve pools, and live re-reads confirm those pairs ship no
    `liquidity` block at all - no usd, no quote, no base, 30 of 30.

    ⚠️ So the honest answer was "not measured" and we wrote "measured, empty".
    Standing rule 5, in the module that produces the permanent record: five
    separate failures in this project came from an absent measurement rendering
    as a real value.

    ⛔ No gate changed - 0.0 and None both fail MIN_EXIT_DEPTH, and a
    bonding-curve row is refused on venue anyway - and no number was lost: 0 of
    30 pairs had a depth that resolve could compute and this returned 0.0 for.
    What was wrong was the KIND of the recorded value, on three quarters of the
    journal. Rule 8 means those rows stay; this stops new ones.

    ⚠️ `_f`'s 0.0 default is left alone elsewhere in this file. It is load-
    bearing for scoring, where a missing volume genuinely is zero for the
    arithmetic, and changing it globally would move scores.
    """
    liq = pair.get("liquidity") or {}
    q = _f(liq.get("quote"), None)
    pu, pn = _f(pair.get("priceUsd"), None), _f(pair.get("priceNative"), None)
    if q is not None and pu and pn:
        return q * (pu / pn)
    total, base = _f(liq.get("usd"), None), _f(liq.get("base"), None)
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

# ---------------------------------------------------------------------------
# ⛔ THE SCANNER MUST NOT STOP EARLY ON THE HOSTED RUNNER. "The scanner cannot
# be stopping." - Frank, 2026-09-18.
#
# The 150s above was sized for the Claude dispatch sandbox's ~178s command cap.
# That cap does not exist on GitHub Actions - `sources.seconds_left()` returns
# None there, so the STAGE-deadline break never fires. But SCAN_BUDGET_S is a
# scanner-local constant with no such condition, so it kept truncating anyway.
#
# ⚠️ MEASURED, and this is why the sandbox explanation was not enough: today's
# two hosted runs covered 87.8% (72/82) and 83.1% (69/83). The truncation on
# Actions was NEVER the sandbox. It was this constant.
#
# The job has a 15-minute timeout and the two runs took 533s and 602s end to
# end, so there is ~300s of headroom. A row costs ~2.2s, so a 90-pool batch
# needs ~200s. RUNNER_SCAN_BUDGET_S is generous enough to finish every batch
# seen so far and still bounded, because an unbounded loop inside a job with a
# hard timeout is how you lose the whole pass instead of part of it.
# ---------------------------------------------------------------------------
RUNNER_SCAN_BUDGET_S = float(os.environ.get("CRYPTO_RUNNER_SCAN_BUDGET_S", "540"))


def scan_budget(budget_s=None):
    """Seconds this scan may spend. The runner gets the generous one."""
    if budget_s is not None:
        return budget_s
    if os.environ.get("GITHUB_ACTIONS"):
        return RUNNER_SCAN_BUDGET_S
    return SCAN_BUDGET_S


# ---------------------------------------------------------------------------
# ⛔ NOTHING IS SILENTLY DISCARDED. If a batch still cannot finish, the pools it
# did not reach are CARRIED to the next pass, not dropped.
#
# Before this, a truncated pass lost its tail permanently - and because
# `new_pools` is newest-first, the tail was always the oldest pools in the
# batch, so the loss was systematic rather than random. Shuffling would have
# made it unbiased and would still have lost it. Carrying loses nothing.
#
# Bounded on purpose: a carry that grows without limit turns one slow pass into
# a permanent backlog that never drains. At the cap the OLDEST carried entries
# are dropped, and that drop is recorded and alarmed rather than silent.
# ---------------------------------------------------------------------------
CARRY_PATH = os.path.join("data", "_scan_carry.json")
CARRY_MAX = int(os.environ.get("CRYPTO_SCAN_CARRY_MAX", "400"))

# ⭐ HOLDER COUNTS, AT THE DECISION POINT ONLY.
#
# `holders` is the sharpest separator this project has measured - median 1,350
# on contracts that can actually be sold against 3 on contracts that return
# nothing (docs/TRUSTED_FIELDS.md section 1) - and it was on ZERO of the last
# 400 observation rows. paperv3's gate requires it, so with no holder count on
# the row that gate could never pass: wiring v3 into the collector without this
# would have entered nothing, for ever, and looked like a quiet market.
#
# ⚠️ It is not free, so it is not per-row. Only rows that have already cleared
# every free condition of RULE_V3 get one, which measured 92 of 1,003 rows over
# three days - roughly 7 a pass, the same order as the authority checks beside
# it. Helius DAS, not Jupiter: the 55/min bucket never comes near this path.
HOLDER_BUDGET = int(os.environ.get("CRYPTO_HOLDER_BUDGET", "25"))

# ⚠️ And the same for the v3 round trip, which costs two Jupiter quotes. Only
# rows that already cleared holders>=100 ever reach it, so this is a ceiling on
# a pathological pass rather than a normal-day limit.
V3_QUOTE_BUDGET = int(os.environ.get("CRYPTO_V3_QUOTE_BUDGET", "15"))


def _carry_load():
    try:
        with open(CARRY_PATH, encoding="utf-8") as f:
            d = json.load(f)
        return d.get("pools") or []
    except Exception:
        return []


def _carry_save(pools, dropped=0):
    try:
        os.makedirs(os.path.dirname(CARRY_PATH), exist_ok=True)
        with open(CARRY_PATH, "w", encoding="utf-8") as f:
            json.dump({"ts": int(time.time()), "n": len(pools),
                       "dropped_at_cap": dropped, "pools": pools}, f)
    except Exception as e:
        print(f"  [carry] could not persist {len(pools)} pools: {e}")


def _addr(p):
    return (p.get("attributes") or {}).get("address")


def _truncate(pools, i, why, verbose=True):
    """Record a truncation AND carry the unreached pools to the next pass.

    ⛔ The only place either break site may stop the loop. Both used to drop the
    remainder on the floor; a pass that cannot finish now owes the rest forward
    rather than losing it.
    """
    rest = pools[i:]
    LAST_SCAN["budget_hit"] = True
    LAST_SCAN["reached"] = i          # i pools behind us; pools[i:] carried
    LAST_SCAN["skipped"] = [_addr(q) for q in rest]
    LAST_SCAN["coverage"] = (i / len(pools)) if pools else 1.0
    LAST_SCAN["truncate_reason"] = why
    dropped = 0
    if len(rest) > CARRY_MAX:
        # Drop the OLDEST (the tail), keep what we can still act on. Recorded,
        # never silent - LAST_SCAN carries it and collect.py alarms on it.
        dropped = len(rest) - CARRY_MAX
        rest = rest[:CARRY_MAX]
    LAST_SCAN["carried_forward"] = len(rest)
    LAST_SCAN["carry_dropped"] = dropped
    _carry_save(rest, dropped)
    if verbose:
        print(f"  ⛔ TRUNCATED at {i}/{len(pools)} ({100.0 * LAST_SCAN['coverage']:.1f}%): {why}")
        print(f"     {len(rest)} pools CARRIED to the next pass"
              + (f", {dropped} dropped at the {CARRY_MAX} cap" if dropped else ""))
    return rest



# Only rows at or above this score get an authority check, plus anything the
# paper log would enter. Bounds the RPC spend to the rows we would act on.
AUTHORITY_CHECK_SCORE = int(os.environ.get("CRYPTO_AUTHORITY_SCORE", "70"))
# `skipped` carries the ADDRESSES we never looked at, not just a count.
# Measured 2026-09-18 across 399 passes: coverage is 97.0% overall and 99% at the
# median, but 55% of passes truncate and the worst saw 19%. The drop is always
# the TAIL, and sources.new_pools() returns newest-first, so the pools we skip
# are systematically the OLDEST in the batch. A truncated pass that records only
# a count is indistinguishable from a complete one at analysis time - which is
# how a 3% directional bias becomes invisible. See docs/SAMPLING_BIAS.md.
LAST_SCAN = {"pools": 0, "enriched": 0, "failed": 0, "budget_hit": False,
             "skipped": [], "coverage": 1.0}


def socials_of(pair):
    """Telegram / Twitter / website presence, from the payload we already hold.

    `social_count` counts DISTINCT link kinds, with the website as one kind, so
    3 means "telegram + twitter + website" - the exact configuration the
    published 17.4x figure is measured on. Two Telegram links are one kind.

    An absent `info` block and an empty one are not distinguished, and that is
    deliberate: Dexscreener omits `info` entirely for a token with no links, so
    "no info" IS "no links". This is the one place in this file where absence is
    allowed to render as False rather than None.
    """
    info = (pair or {}).get("info") or {}
    kinds = set()
    for s in (info.get("socials") or []):
        t = (s or {}).get("type")
        if t:
            kinds.add(str(t).strip().lower())
    has_site = any((w or {}).get("url") for w in (info.get("websites") or []))
    return {
        "has_telegram": "telegram" in kinds,
        # Dexscreener has used both spellings across the rename.
        "has_twitter": bool(kinds & {"twitter", "x"}),
        "has_website": has_site,
        "social_count": len(kinds) + (1 if has_site else 0),
    }


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
    fresh_n = len(pools)
    # ⭐ CARRIED POOLS GO FIRST. They are already the oldest thing we owe, and
    # putting them at the front is what stops a backlog from forming: if this
    # pass truncates again, it truncates the NEW tail, which is carried in turn.
    carried = _carry_load()
    carry_n = 0
    if carried:
        have = {_addr(p) for p in pools}
        carried = [p for p in carried if _addr(p) and _addr(p) not in have]
        carry_n = len(carried)
        pools = carried + pools
        if verbose and carry_n:
            print(f"  [carry] {carry_n} pools owed from a previous pass, processed first")
    if verbose: print(f"pulled {fresh_n} new pools on {network}"
                      + (f" (+{carry_n} carried)" if carry_n else ""))
    budget = scan_budget(budget_s)
    started = time.time()
    LAST_SCAN.update(pools=len(pools), pools_fresh=fresh_n, pools_carried=carry_n,
                     enriched=0, failed=0, reached=0, budget_hit=False,
                     skipped=[], coverage=1.0, carried_forward=0, carry_dropped=0,
                     holders_fetched=0, holders_deferred=0,
                     v3_quotes=0, v3_deferred=0, v3_refusals={})
    rows = []
    row_s, _t_prev = [], None       # measured cost of a row, this pass
    for i, p in enumerate(pools):
        # THE STAGE DEADLINE, NOT ONLY THIS FUNCTION'S OWN CONSTANT. On
        # 2026-09-15 the unattended scan enriched for ~140s under a 110s stage
        # budget, because this loop only knew SCAN_BUDGET_S (150); it ran 164s
        # against a ~178s kill. Stop when there is not time for another row of
        # what rows have actually cost this pass. No deadline (the runner) means
        # no change.
        if _t_prev is not None:
            row_s.append(time.time() - _t_prev)
        _t_prev = time.time()
        _left = S.seconds_left()
        _row = (sorted(row_s)[int(0.75 * (len(row_s) - 1))] if row_s
                else 3 * S.per_call_estimate())
        if _left is not None and _left <= 1.5 * _row:
            _truncate(pools, i,
                      f"stage deadline: {_left:.0f}s left, a row costs ~{_row:.1f}s",
                      verbose)
            break
        if time.time() - started > budget:
            _truncate(pools, i,
                      f"enrichment budget {budget:.0f}s spent", verbose)
            break
        # ⭐ HOW FAR THE LOOP GOT, which is the ONLY thing truncation changes.
        # Set AFTER both break checks: a pass that stops at i has NOT reached
        # pool i - _truncate carries pools[i:] forward, that pool included.
        #
        # ⛔ Not `enriched`, which counts pools that produced a ROW. A pool can
        # be reached and produce none (no address, a failed fetch). Conflating
        # them made the alarm fire on a complete pass, printing "processed 80
        # of 83 pools (100.0%)" - a contradiction that trains people to ignore
        # the alarm. Reached is reached; enrichment failure is a separate
        # number, recorded separately.
        LAST_SCAN["reached"] = i + 1
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
        # SOCIALS. `info.socials` and `info.websites` have been in the
        # Dexscreener payload on every enriched row since the first pass and
        # were read by nothing until 2026-09-17 - not dropped by the whitelist
        # like vol_to_liq was, simply never looked at. The published effect is
        # the largest in this space: a Telegram link in launch metadata carries
        # an 8.94x lift on graduation (1.485% vs 0.166%, Kamat n=832,941), and
        # Telegram + Twitter + website together 17.4x.
        #
        # Booleans, not URLs. A stored link rots, bloats every row and drags
        # personal data into an append-only file we never delete. Presence is
        # the whole signal. The raw blob stays available to the on-demand
        # analyser, which fetches live.
        #
        # THIS IS FORWARD-ONLY. Nothing backfills; rows written before today
        # have no socials and never will. See docs/PRELAUNCH_SIGNAL.md.
        row.update(socials_of(pair))
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

        # ⭐ HOLDER COUNT, ONLY WHEN EVERY FREE CONDITION HAS ALREADY PASSED.
        #
        # The gate is not re-implemented here. paperv3.qualifies() is run for
        # nothing and asked what it wants next; NEEDS_HOLDERS means the row
        # cleared venue, both authorities and the sell side, and the float is
        # the only thing left that is free to check. A caller that copied the
        # conditions instead would drift from the rule the day the rule moved.
        row["holders_checked"] = False
        if row.get("addr"):
            try:
                _ok3, _why3 = paperv3.qualifies(row)
            except Exception:
                _ok3, _why3 = False, ""
            if _why3 == paperv3.NEEDS_HOLDERS:
                if LAST_SCAN.get("holders_fetched", 0) >= HOLDER_BUDGET:
                    # ⛔ NOT SILENT. Standing rule 15: a truncated sample records
                    # WHAT it missed, not just that it stopped.
                    LAST_SCAN["holders_deferred"] =                         LAST_SCAN.get("holders_deferred", 0) + 1
                    row["holders_error"] = "holder budget spent this pass"
                else:
                    LAST_SCAN["holders_fetched"] =                         LAST_SCAN.get("holders_fetched", 0) + 1
                    row["holders_checked"] = True
                    try:
                        _h = chainfields.holder_count(row["addr"])
                        row["holders"] = _h.get("holders")
                        row["holders_truncated"] = bool(_h.get("truncated"))
                        row["holders_error"] = _h.get("error")
                    except Exception as e:
                        # Unknown stays unknown. ⛔ Never 0 - a failed read that
                        # renders as a real count is standing rule 5, and v3
                        # fails closed on None by design.
                        row["holders"] = None
                        row["holders_truncated"] = None
                        row["holders_error"] = f"{type(e).__name__}"

        # WHAT SURFACES IS THE GRADE, NOT THE SCORE. PTN scored 100 on 2026-09-14
        # with mint AND freeze authority live and went out as "scored 100". The
        # score is left exactly as the scorer made it - v1's pinned gate and v2's
        # B_high/B_low split both read it - and every human-facing surface reads
        # `grade` instead. PRECOMMIT_surface_grade.md.
        row["grade"], row["grade_label"] = surface_grade(row)

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
        # ⭐ RULE_V3, IN THE SAME LOOP, ON THE SAME ROW, IN THE SAME PASS.
        #
        # ⛔ It belongs HERE and not in a later stage, for the reason written
        # above v1: a forward paper log records a decision with no knowledge of
        # what happens next, and every retrospective finding in this project has
        # died of leakage. Three filters, one market, one hour - which is also
        # standing rule 14, two conditions opened simultaneously rather than in
        # sequence.
        #
        # ⚠️ This is the ONE place Jupiter touches the scan loop, and it is a
        # decision point, not a per-row call: the round trip is bought only for
        # a row that has already cleared venue, both authorities, the sell side
        # and holders>=100. Measured at ~7 candidates a pass against a 55/min
        # bucket and a 540s budget. The budget below is the hard stop, and it
        # is RECORDED when it bites - never a silent skip.
        try:
            _ok3, _why3 = paperv3.qualifies(row)
            if _why3 == paperv3.NEEDS_QUOTE and row.get("addr"):
                if LAST_SCAN.get("v3_quotes", 0) >= V3_QUOTE_BUDGET:
                    LAST_SCAN["v3_deferred"] = LAST_SCAN.get("v3_deferred", 0) + 1
                    row["paper_v3_skipped"] = "v3 quote budget spent this pass"
                else:
                    LAST_SCAN["v3_quotes"] = LAST_SCAN.get("v3_quotes", 0) + 1
                    _rt3 = chainfields.round_trip(row["addr"], paperv3.SIZE_TRADED)
                    _ok3, _why3 = paperv3.qualifies(row, _rt3)
                    if _ok3:
                        _v3, _v3why = paperv3.open_entry(row, _rt3)
                        if _v3 is not None:
                            row["paper_v3_entry"] = _v3["hash"][:12]
                            if verbose:
                                print(f"  [v3] entered {row.get('name')} "
                                      f"{str(row.get('addr'))[:12]} at a REAL "
                                      f"fill: {_rt3.get('rt_cost_pct')}% round trip, "
                                      f"{row.get('holders')} holders")
                        else:
                            row["paper_v3_skipped"] = str(_v3why)[:120]
                    else:
                        row["paper_v3_skipped"] = str(_why3)[:120]
            elif not _ok3 and row.get("holders_checked"):
                # ⭐ ON THE ROW ONLY FOR ROWS THAT GOT PAST THE FREE CHECKS.
                # Those are the interesting refusals - we spent a call on them.
                # Writing a reason onto all ~80 rows a pass would bloat every
                # row with "venue=curve, not amm" and teach nobody anything.
                row["paper_v3_skipped"] = str(_why3)[:120]
            if not _ok3:
                # ⭐ BUT THE TALLY IS KEPT FOR EVERY ROW, ONCE PER PASS.
                # "The v3 ledger is empty" is not a finding until it comes with
                # the reason distribution behind it. Bucketed on a prefix
                # because the reasons carry counts ("4 holders < 100").
                _b = str(_why3).split(":")[0].strip()
                _b = _b.split(" - ")[0].strip()
                if _b[:1].isdigit():
                    _b = "holders below the floor"
                LAST_SCAN.setdefault("v3_refusals", {})
                LAST_SCAN["v3_refusals"][_b] =                     LAST_SCAN["v3_refusals"].get(_b, 0) + 1
        except Exception as e:
            print(f"  [v3] {type(e).__name__}: {str(e)[:90]}")
            row["paper_v3_skipped"] = f"{type(e).__name__}"
        rows.append(row)
        LAST_SCAN["enriched"] += 1
        if on_row:
            on_row(row)          # journal NOW, not after the loop
        S.pace()
    # ⭐ A pass that finished owes nothing. Clearing is as important as saving:
    # a carry file left behind would be re-processed every pass forever.
    if not LAST_SCAN.get("budget_hit"):
        LAST_SCAN["carried_forward"] = 0
        _carry_save([], 0)
    rows.sort(key=lambda r: (r.get("grade", 0), r["score"]), reverse=True)
    return rows


# PASS_SCORE - 1 (collect.PASS_SCORE is 70), so an unverified contract can never
# "pass the launch filter". Derived from the existing constant, not tuned.
GRADE_UNVERIFIED_CEILING = 69
LABEL_TRAP = "TRAP - authority live"
LABEL_UNVERIFIED = "authorities unverified"


def surface_grade(row):
    """(grade, label): the only number a human is shown. Never changes `score`.

    Live mint or freeze authority is a capability, not a statistic - grade 0.
    Unknown authority (never checked, or the check failed) is capped below the
    pass line. Both revoked: the grade is the score.
    """
    score = row.get("score") or 0
    if row.get("can_mint") or row.get("can_freeze"):
        return 0, LABEL_TRAP
    if row.get("can_mint") is None or row.get("can_freeze") is None:
        return min(score, GRADE_UNVERIFIED_CEILING), LABEL_UNVERIFIED
    return score, None


def report(rows, min_score=70, show=10):
    passed = [r for r in rows if r.get("grade", 0) >= min_score]
    print(f"\n{len(rows)} scanned -> {len(passed)} cleared {min_score}\n")
    for r in passed[:show]:
        print(f"  [{r.get('grade', 0):3d}] {r['name']:<14} liq {r['liq']:>10,.0f}  "
              f"24h vol {r['v24']:>12,.0f}  {r['age_h']:.1f}h  1h {r['chg_h1']:+.1f}%")
        print(f"        {', '.join(r['reasons'])}")
        if r["flags"]: print(f"        WARN: {'; '.join(r['flags'])}")
        print(f"        {r['url']}")
    if not passed:
        print("  Nothing cleared the bar. That is the normal result and it is the point.")
        near = [r for r in rows if r.get("grade", 0) >= min_score - 20][:5]
        if near:
            print(f"\n  Closest misses:")
            for r in near:
                print(f"   [{r.get('grade', 0):3d}] {r['name']:<14} rejected: {r['flags'][0] if r['flags'] else '-'}")
    return passed

if __name__ == "__main__":
    import sys
    net = sys.argv[1] if len(sys.argv) > 1 else "solana"
    rows = scan(net, pages=2)
    report(rows)
