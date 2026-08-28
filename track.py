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
import time, statistics as st
import journal, sources as S

HORIZONS = [1, 6, 24, 168]
MIN_ROWS_TO_ANALYSE = 60          # below this, correlations are noise


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
            o.get("price_usd"), o.get("liq"), o.get("symbol", ""))
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


def analyse(horizon_h=24, win_mult=2.0):
    """Which observed features actually separated winners from losers.

    Deliberately simple: compare the median of each feature for winners vs
    everything else. With a few hundred rows that is about as much as the data
    honestly supports. Fancier modelling on a small sample is how you fool
    yourself.
    """
    rows = _joined(horizon_h)
    if len(rows) < MIN_ROWS_TO_ANALYSE:
        return {"ok": False,
                "msg": f"only {len(rows)} labelled pairs at {horizon_h}h; "
                       f"need {MIN_ROWS_TO_ANALYSE} before any of this means anything"}

    # A "win" must be realizable. Counting drained-pool multiples as wins made
    # the win rate, and therefore every feature comparison below it, meaningless.
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

    passed = [(o, r) for o, r in rows if o.get("passed")]
    pw = [1 for o, r in passed if (r.get("mult") or 0) >= win_mult]
    return {"ok": True, "horizon_h": horizon_h, "labelled": len(rows),
            "winners": len(wins), "win_rate": round(len(wins) / len(rows), 3),
            "rug_rate": round(len(rugs) / len(rows), 3),
            "filter_fired": len(passed),
            "filter_win_rate": round(len(pw) / len(passed), 3) if passed else None,
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
    s = journal.stats()
    print("\n  JOURNAL")
    print(f"  {s['observations']} observations · {s['unique_pairs']} pairs · "
          f"{s['passed']} passed filter · {s['outcomes']} outcomes · {s['hours_covered']}h covered")
    if s["by_status"]:
        print(f"  outcome status: {s['by_status']}")
    for h in HORIZONS:
        a = analyse(h)
        if not a["ok"]:
            print(f"\n  {h}h: {a['msg']}")
            continue
        print(f"\n  {h}h horizon · {a['labelled']} labelled")
        print(f"    base win rate (>=2x): {a['win_rate']:.1%}   rug rate: {a['rug_rate']:.1%}")
        if a["filter_win_rate"] is not None:
            edge = a["filter_win_rate"] - a["win_rate"]
            print(f"    filter fired {a['filter_fired']}x, win rate {a['filter_win_rate']:.1%} "
                  f"({edge:+.1%} vs base)")
            if edge <= 0:
                print("    NOTE: the filter is not beating random selection. "
                      "Change the thresholds, do not trust the score.")
        for f, v in a["features"].items():
            if v["ratio"] and (v["ratio"] > 1.3 or v["ratio"] < 0.77):
                print(f"    {f:<10} winners {v['winners_median']:>12,.2f}  "
                      f"others {v['others_median']:>12,.2f}  ({v['ratio']}x)")
    print()


if __name__ == "__main__":
    import sys
    if len(sys.argv) > 1 and sys.argv[1] == "score":
        score_all()
    report()
