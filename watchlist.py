"""Approach-band tracking: the only place a graduation can actually be predicted.

WHY A SEPARATE CADENCE. The normal outcome schedule checks a token at 1h, 6h,
24h and 168h after first sight. A token crosses the ~$69,000 graduation
threshold in minutes, so that schedule cannot see the crossing - it sees a
before and an after separated by hours, with the event itself missing. Anything
in the approach band therefore gets checked EVERY PASS until it graduates or
dies, which is 24 checks a day instead of 3.

WHAT THE BAND IS. `$45,000` to `$69,000` of FDV. The upper edge is pump.fun's
published threshold; the lower edge is set wide enough to catch the feeder
population, because a token that enters at $56k and graduates 20 minutes later
was never observable in a narrower band.

THE COST, measured before building. 246 tokens have ever been first seen in
$55-69k and 892 in $40-55k, across 391.5 hours of record - about 70 entries per
day into the wider band. With a 24h TTL the active set sits near 70, so the
sweep costs ~70 Dexscreener calls per pass on top of the ~292 already spent.
Dexscreener answered 12/12 at a median 0.116s and publishes 300 req/min, so
this is affordable there. It spends NO GeckoTerminal budget, which is the
scarce one - measured at under 10 successful calls/min.

WHAT THIS FIXES, and what it does not. It does not fix the outcome-recording
deficit (see the module docstring in `journal.pending` and OUTCOMES.md): that
is a separate, structural problem where arrival exceeds capacity. This is a
targeted collection change for one small, high-information population.

NOTHING HERE SCORES OR FILTERS. It collects, and it records a milestone.
"""
import datetime as dt
import json
import os
import time

import milestones
import venue

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "data", "watchlist")
ACTIVE = os.path.join(DIR, "active.json")
LEDGER = os.path.join(DIR, "checks.jsonl")
RETIRED = os.path.join(DIR, "retired.jsonl")

BAND_LO = float(os.environ.get("CRYPTO_APPROACH_LO", "45000"))
BAND_HI = float(os.environ.get("CRYPTO_APPROACH_HI", "69000"))
GRADUATION_FDV = venue.GRADUATION_MCAP_USD

# Retire after this long without graduating. The token is not deleted - it is
# written to retired.jsonl with its whole check history and an outcome.
TTL_H = float(os.environ.get("CRYPTO_APPROACH_TTL_H", "24"))

# Hard ceiling on sweep cost. If the band ever floods, we spend a bounded
# number of calls and say so, rather than silently eating the pass budget.
MAX_ACTIVE = int(os.environ.get("CRYPTO_APPROACH_MAX", "120"))

# Do not re-read a member the current pass just added. The scan already has a
# fresh observation of it; a second read 60s later is a wasted call and a
# trajectory row measured over noise.
MIN_RECHECK_S = float(os.environ.get("CRYPTO_APPROACH_MIN_RECHECK_S", "900"))

LAST_SWEEP = {"checked": 0, "graduated": 0, "retired": 0, "added": 0,
              "capped": False}


def _f(x, d=None):
    try:
        return float(x)
    except (TypeError, ValueError):
        return d


def _now():
    return int(time.time())


def _load():
    try:
        with open(ACTIVE, encoding="utf-8") as f:
            d = json.load(f)
        return d if isinstance(d, dict) else {}
    except Exception:
        # Self-healing: a corrupt or conflict-marked state file must not stop
        # collection. The check ledger is the durable record; this is a cache.
        return {}


def _save(state):
    os.makedirs(DIR, exist_ok=True)
    tmp = ACTIVE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, sort_keys=True)
    os.replace(tmp, ACTIVE)


def _append(path, row):
    os.makedirs(DIR, exist_ok=True)
    with open(path, "a", encoding="utf-8") as f:
        f.write(json.dumps(row, sort_keys=True, separators=(",", ":")) + "\n")


def _exit_depth(pair):
    """Quote-side USD. Third local copy of resolve.exit_depth_usd(), for the
    same reason as scanner's: importing the scoring stack into a collection
    module drags in config, weights and the whole scorer to compute one
    ratio, and makes this untestable without an environment."""
    liq = pair.get("liquidity") or {}
    q = _f(liq.get("quote"))
    pu, pn = _f(pair.get("priceUsd")), _f(pair.get("priceNative"))
    if q is not None and pu and pn:
        return q * (pu / pn)
    total, base = _f(liq.get("usd")), _f(liq.get("base"))
    if total is not None and base is not None and pu:
        return max(0.0, total - base * pu)
    return None


def in_band(fdv):
    f = _f(fdv)
    return f is not None and BAND_LO <= f < BAND_HI


def consider(row):
    """Add an observation to the watchlist if it is in the approach band.

    Keyed on CONTRACT ADDRESS. Returns True if newly added.
    """
    ca = row.get("addr") or row.get("token")
    if not ca or not in_band(row.get("fdv")):
        return False
    state = _load()
    if ca in state:
        return False
    if len(state) >= MAX_ACTIVE:
        LAST_SWEEP["capped"] = True
        return False
    state[ca] = {
        "contract": ca,
        "pair": row.get("pair"),
        "symbol": row.get("name") or row.get("symbol"),
        "network": row.get("network", "solana"),
        "added_ts": _now(),
        "added_fdv": _f(row.get("fdv")),
        "added_vol_h1": _f(row.get("vol_h1")),
        "added_liq": _f(row.get("liq")),
        "added_venue": row.get("venue_type"),
        "checks": 0,
        "last_fdv": _f(row.get("fdv")),
        "last_vol_h1": _f(row.get("vol_h1")),
        "peak_fdv": _f(row.get("fdv")),
    }
    _save(state)
    _append(LEDGER, {"event": "added", "ts": _now(), **state[ca]})
    return True


def _graduated(pair_obj, fdv, liq, liq_quote, dex_id):
    """Has this token actually graduated?

    Two independent signatures, and BOTH are recorded because they can
    disagree and the disagreement is informative:

      fdv_cross  - FDV at or above the published threshold
      real_pool  - an AMM venue with a two-sided reserve split

    `real_pool` is the event that matters for an exit. A curve token whose FDV
    ticks over the threshold has not graduated until the pool exists.
    """
    fdv_cross = fdv is not None and fdv >= GRADUATION_FDV
    vt = venue.venue_type(dex_id)
    real_pool = bool(vt == venue.AMM and liq_quote is not None and (liq or 0) > 0)
    return fdv_cross, real_pool


def sweep(fetch_pair, on_observation=None, verbose=True):
    """Re-check every active member. One call per contract, never batched.

    `fetch_pair(network, pair_address) -> pair dict or None` is injected so this
    module stays free of a circular import and is testable without network.
    """
    state = _load()
    LAST_SWEEP.update(checked=0, graduated=0, retired=0, added=0, capped=False)
    if not state:
        return LAST_SWEEP
    now = _now()
    drop = []
    for ca, m in list(state.items()):
        # Added moments ago by this same pass's scan - we already have a fresh
        # read of it. Re-fetching costs a call and produces a trajectory row
        # over a ~60s gap, which is noise, not a trend.
        if now - m.get("added_ts", 0) < MIN_RECHECK_S:
            continue
        pair = None
        try:
            pair = fetch_pair(m.get("network", "solana"), m.get("pair"))
        except Exception:
            pair = None
        LAST_SWEEP["checked"] += 1

        if not pair:
            # Source dropped it. That is a fact about the source, not the
            # token, so it is recorded and the member stays until TTL.
            _append(LEDGER, {"event": "check", "ts": now, "contract": ca,
                             "symbol": m.get("symbol"), "resolved": False})
            if now - m["added_ts"] > TTL_H * 3600:
                drop.append((ca, "ttl_source_dropped"))
            continue

        fdv = _f(pair.get("fdv"))
        liq = _f((pair.get("liquidity") or {}).get("usd"))
        lq = _f((pair.get("liquidity") or {}).get("quote"))
        t1 = (pair.get("txns", {}) or {}).get("h1", {}) or {}
        v1 = _f((pair.get("volume") or {}).get("h1"))
        dex_id = pair.get("dexId")
        depth = _exit_depth(pair)

        prev_v = m.get("last_vol_h1")
        prev_f = m.get("last_fdv")
        rec = {
            "event": "check", "ts": now, "contract": ca,
            "symbol": m.get("symbol"), "resolved": True,
            "fdv": fdv, "liq": liq, "liq_quote": lq, "vol_h1": v1,
            "exit_depth_usd": depth, "dex_id": dex_id,
            "venue_type": venue.venue_type(dex_id),
            "buys_h1": t1.get("buys"), "sells_h1": t1.get("sells"),
            "check_n": m.get("checks", 0) + 1,
            "elapsed_h": round((now - m["added_ts"]) / 3600, 3),
            # THE TRAJECTORY FIELDS. Point-in-time volume has never shown lift;
            # the change between two observations of the SAME token is a
            # different quantity and is what mattered for liquidity.
            "vol_to_liq": (round(v1 / liq, 6) if (v1 is not None and liq) else None),
            "vol_change": (round((v1 - prev_v) / prev_v, 6)
                           if (v1 is not None and prev_v) else None),
            "fdv_change": (round((fdv - prev_f) / prev_f, 6)
                           if (fdv is not None and prev_f) else None),
        }
        _append(LEDGER, rec)
        if on_observation:
            try:
                on_observation(rec)
            except Exception:
                pass

        fdv_cross, real_pool = _graduated(pair, fdv, liq, lq, dex_id)
        if fdv_cross or real_pool:
            meta = {"symbol": m.get("symbol"), "kind": "graduation",
                    "value": fdv, "fdv_at_crossing": fdv,
                    "vol_h1_at_crossing": v1, "liq_at_crossing": liq,
                    "exit_depth_at_crossing": depth,
                    "venue": dex_id, "venue_type": venue.venue_type(dex_id),
                    "fdv_cross": fdv_cross, "real_pool": real_pool,
                    "entered_band_fdv": m.get("added_fdv"),
                    "hours_in_band": round((now - m["added_ts"]) / 3600, 3),
                    "checks_before_crossing": m.get("checks", 0) + 1}
            if milestones.claim(ca, "graduated", **meta):
                LAST_SWEEP["graduated"] += 1
                if verbose:
                    print(f"  [watchlist] GRADUATED {m.get('symbol')} {ca[:12]} "
                          f"fdv ${fdv:,.0f} after {meta['hours_in_band']:.2f}h "
                          f"in band ({'pool' if real_pool else 'fdv only'})")
            drop.append((ca, "graduated"))
            continue

        m["checks"] = m.get("checks", 0) + 1
        m["last_fdv"] = fdv
        m["last_vol_h1"] = v1
        if fdv is not None:
            m["peak_fdv"] = max(m.get("peak_fdv") or 0, fdv)
        if now - m["added_ts"] > TTL_H * 3600:
            drop.append((ca, "ttl_no_graduation"))

    for ca, why in drop:
        m = state.pop(ca, None)
        if m is None:
            continue
        LAST_SWEEP["retired"] += 1
        _append(RETIRED, {"retired_ts": now, "reason": why,
                          "graduated": why == "graduated", **m})
    _save(state)
    if verbose and LAST_SWEEP["checked"]:
        print(f"  [watchlist] {LAST_SWEEP['checked']} checked, "
              f"{LAST_SWEEP['graduated']} graduated, {LAST_SWEEP['retired']} retired, "
              f"{len(state)} still active")
    return LAST_SWEEP


def active():
    return _load()


def stats():
    st = _load()
    n_grad = n_ret = 0
    try:
        with open(RETIRED, encoding="utf-8") as f:
            for line in f:
                if not line.strip():
                    continue
                r = json.loads(line)
                n_ret += 1
                n_grad += bool(r.get("graduated"))
    except Exception:
        pass
    return {"active": len(st), "retired": n_ret, "graduated": n_grad,
            "graduation_rate": (f"{100.0 * n_grad / n_ret:.2f}%" if n_ret >= 30
                                else f"WITHHELD - {n_ret} retired, need 30"),
            "band": f"${BAND_LO:,.0f}-${BAND_HI:,.0f}", "ttl_h": TTL_H}


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    if len(sys.argv) > 1 and sys.argv[1] == "sweep":
        import sources as S
        sweep(S.dexscreener_pair)
    else:
        s = stats()
        print(f"  band      : {s['band']}  ttl {s['ttl_h']}h")
        print(f"  active    : {s['active']}")
        print(f"  retired   : {s['retired']}  graduated {s['graduated']}")
        print(f"  grad rate : {s['graduation_rate']}")
        for ca, m in list(active().items())[:15]:
            print(f"    {str(m.get('symbol'))[:12]:<13} {ca[:20]:<21} "
                  f"fdv ${(m.get('last_fdv') or 0):>10,.0f}  "
                  f"checks {m.get('checks', 0):>2}")
