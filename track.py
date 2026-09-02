"""
Outcome tracking and learning.

The loop that makes this system improve rather than just alert:

  1. scanner sees a pair          -> journal.record()      (features, at t0)
  2. hours later, check it again  -> score_horizon()       (what actually happened)
  3. once labelled data exists    -> analyse()             (which features predicted)

Step 3 is the whole point. Until there are enough labelled outcomes the honest
answer is "not enough data", and this module says so rather than inventing a
signal from twelve rows.

Horizons: 1h catches the initial pump, 6h catches whether it held, 24h catches
whether it was real, 168h catches whether anything survived a week.
"""
import math, time, statistics as st
import journal, sources as S

HORIZONS = [1, 6, 24, 168]
MIN_WINS_TO_TRUST = 10            # wins, not rows. Rows are cheap; wins are scarce.


# ---------------------------------------------------------------- scoring ---
def score_horizon(horizon_h, limit=80, verbose=True):
    """Re-check pairs first seen ~horizon_h ago and record what happened."""
    todo = journal.pending(horizon_h)[:limit]
    if verbose:
        print(f"  {horizon_h}h horizon: {len(todo)} pairs due")
    done = 0
    for o in todo:
        try:
            pair = S.dexscreener_pair(o.get("network", "solana"), o["pair"])
        except Exception:
            pair = None
        if pair:
            price = float(pair.get("priceUsd") or 0) or None
            liq   = float((pair.get("liquidity") or {}).get("usd") or 0)
            vol24 = float((pair.get("volume") or {}).get("h24") or 0)
        else:
            price = liq = vol24 = None       # delisted / no longer indexed
        status, mult = journal.record_outcome(
            o["pair"], o["ts"], horizon_h, price, liq, vol24,
            o.get("price_usd"), o.get("liq"), o.get("symbol", ""),
            token=o.get("token", ""))
        done += 1
        if verbose and mult and mult >= 2:
            ok, why = journal.realizable(status, liq, mult)
            if ok:
                print(f"    {o.get('symbol','?'):<12} {mult:>6.2f}x  ({status})")
            else:
                print(f"    {o.get('symbol','?'):<12} {mult:>6.2f}x  NOT REALIZABLE - {why}")
        S.pace()
    return done


def score_all(verbose=True):
    return {h: score_horizon(h, verbose=verbose) for h in HORIZONS}


# --------------------------------------------------------------- analysis ---
def _joined(horizon_h):
    """Observations joined to their outcome at one horizon."""
    outs = {o["pair"]: o for o in journal.outcomes() if o["horizon_h"] == horizon_h}
    first = {}
    for o in journal.observations():
        p = o.get("pair")
        if p and (p not in first or o["ts"] < first[p]["ts"]):
            first[p] = o
    return [(first[p], outs[p]) for p in outs if p in first]


def wilson(k, n, z=1.96):
    """95% confidence interval for a rate. Every number this module prints rests
    on a handful of wins, and a bare point estimate at n=13 reads as if it had
    been measured. The interval is the honesty."""
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    centre = (p + z * z / (2 * n)) / d
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (max(0.0, centre - half), min(1.0, centre + half))


def analyse(horizon_h=1, win_mult=2.0):
    """Which observed features actually separated winners from losers.

    THE DENOMINATOR IS EVERY PAIR THAT CAME DUE, not the survivors.

    Filtering the sample down to realizable rows and measuring the hit rate
    inside it answers "given the token survived with exit liquidity, did it
    double" - which is not the question. It discards every dead, gone and
    rugged token, 98.5% of the data, and those are precisely the outcomes the
    score exists to avoid. Measured that way the score looked barely better
    than a coin flip and actively worse at 3x. Measured on the full sample the
    same score separates winners from losers by roughly 19x at 1h, because
    nearly all of its power is in predicting SURVIVAL rather than the size of
    the multiple given survival.

    So: a win is realizable AND mult >= win_mult. Everything else, including
    going to zero, is a loss. `realizable` gates the WIN, never the SAMPLE.
    """
    rows = _joined(horizon_h)
    if not rows:
        return {"ok": False, "msg": f"no labelled pairs at {horizon_h}h yet"}

    def _won(r):
        return bool(r.get("realizable")) and (r.get("mult") or 0) >= win_mult

    wins = [(o, r) for o, r in rows if _won(r)]
    rest = [(o, r) for o, r in rows if not _won(r)]
    rugs = [r for _, r in rows if r["status"] in ("rugged", "gone")]

    feats = ["score", "liq", "vol_h24", "vol_h1", "txns_h1", "age_hours", "chg_h1"]
    table = {}
    for f in feats:
        w = [o[f] for o, _ in wins if o.get(f) is not None]
        l = [o[f] for o, _ in rest if o.get(f) is not None]
        if len(w) >= 5 and len(l) >= 5:
            mw, ml = st.median(w), st.median(l)
            table[f] = {"winners_median": round(mw, 4), "others_median": round(ml, 4),
                        "ratio": round(mw / ml, 2) if ml else None}

    # The filter's own record, on the SAME definition of a win as the base rate
    # it is compared against. This line used to count any mult >= win_mult while
    # the base rate counted only realizable ones, so the filter was graded
    # against a softer test than its own baseline and looked better than it was.
    # Both sides are realizable-gated now.
    passed = [(o, r) for o, r in rows if o.get("passed")]
    pw = [1 for o, r in passed if _won(r)]
    base_rate = len(wins) / len(rows)
    f_rate = (len(pw) / len(passed)) if passed else None
    blo, bhi = wilson(len(wins), len(rows))
    flo, fhi = wilson(len(pw), len(passed)) if passed else (None, None)

    return {"ok": True, "horizon_h": horizon_h, "win_mult": win_mult,
            "labelled": len(rows), "winners": len(wins),
            "win_rate": round(base_rate, 5), "win_rate_ci": (blo, bhi),
            "rug_rate": round(len(rugs) / len(rows), 3),
            "filter_fired": len(passed), "filter_wins": len(pw),
            "filter_win_rate": round(f_rate, 5) if f_rate is not None else None,
            "filter_win_rate_ci": (flo, fhi),
            "filter_lift": round(f_rate / base_rate, 1) if (f_rate and base_rate) else None,
            # Below this many wins nothing here is a finding, however many losers
            # the sample holds. Rows are cheap; wins are what is scarce.
            "thin": len(pw) < MIN_WINS_TO_TRUST,
            "features": table}


def leaders(limit=10, min_mult=2.0):
    """Best REALIZABLE outcomes. This is what a findings report should quote;
    quoting raw `mult` is what produced a leaderboard of rugged pools."""
    rows = [o for o in journal.outcomes()
            if o.get("realizable") and (o.get("mult") or 0) >= min_mult]
    rows.sort(key=lambda o: -(o.get("mult") or 0))
    return rows[:limit]


def blocked_leaders(limit=10):
    """What the old code would have reported, and why each is rejected."""
    rows = [o for o in journal.outcomes()
            if not o.get("realizable") and (o.get("mult") or 0) >= 2]
    rows.sort(key=lambda o: -(o.get("mult") or 0))
    return rows[:limit]


def report():
    """The scoreboard.

    Centred on 2x at 1h and 6h: those are the horizons with enough closed
    outcomes to say anything, and 2x is the bar the data supports. 3x is
    printed alongside rather than dropped, because the earlier finding that the
    score had no edge at 3x came from measuring inside the survivor subset; on
    the full sample 3x at 1h separates too. 24h and 168h are shown for
    completeness and are too thin to read.
    """
    s = journal.stats()
    print("\n  JOURNAL")
    print(f"  {s['observations']} observations, {s['unique_pairs']} pairs, "
          f"{s['passed']} passed filter, {s['outcomes']} outcomes, "
          f"{s['hours_covered']}h covered")
    if s["by_status"]:
        print(f"  outcome status: {s['by_status']}")
    print("\n  A win is REALIZABLE and >= the multiple. Everything else, including")
    print("  going to zero, is a loss. The denominator is every pair that came due.")

    for h in HORIZONS:
        head = False
        for m in (2.0, 3.0):
            a = analyse(h, win_mult=m)
            if not a["ok"]:
                if not head:
                    print(f"\n  {h}h: {a['msg']}")
                    head = True
                continue
            if not head:
                print(f"\n  {h}h horizon, {a['labelled']} pairs came due, "
                      f"rug/gone rate {a['rug_rate']:.1%}")
                head = True
            lo, hi = a["win_rate_ci"]
            print(f"    {m:.0f}x  base {a['win_rate']:.2%} [{lo:.2%},{hi:.2%}] "
                  f"({a['winners']} of {a['labelled']})")
            if a["filter_win_rate"] is None:
                continue
            flo, fhi = a["filter_win_rate_ci"]
            lift = f"{a['filter_lift']}x" if a['filter_lift'] else "n/a (no wins)"
            print(f"        filter fired {a['filter_fired']}x -> "
                  f"{a['filter_win_rate']:.2%} [{flo:.2%},{fhi:.2%}] "
                  f"({a['filter_wins']} wins), lift {lift}")
            if a["thin"]:
                print(f"        THIN: {a['filter_wins']} wins is under the "
                      f"{MIN_WINS_TO_TRUST} needed to call this a finding")
            elif a["filter_lift"] and a["filter_lift"] <= 1:
                print("        NOTE: the filter is not beating random selection here.")
        a2 = analyse(h, win_mult=2.0)
        if a2["ok"]:
            for f, v in a2["features"].items():
                if v["ratio"] and (v["ratio"] > 1.3 or v["ratio"] < 0.77):
                    print(f"    {f:<10} winners {v['winners_median']:>12,.2f}  "
                          f"others {v['others_median']:>12,.2f}  ({v['ratio']}x)")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "score":
        score_all()
    report()
