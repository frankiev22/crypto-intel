"""Grade the caller, not the calls. Does following Gorilla beat the base rate?

Frank is about to treat this archive as a shopping list, so the honest thing to
establish BEFORE he does is whether the person picking has an edge at all.

⛔ THE TRAP THIS FILE EXISTS TO AVOID. A flat "X% of his calls are still alive"
is meaningless here, because half the archive is from the last two weeks and a
token called yesterday has not had time to die. Survival MUST be stratified by
how long ago the call was, or recency alone manufactures an edge. Same family as
standing rule 13: a measurement taken at the wrong moment does not describe the
moment you care about.

⭐ The control arm is every token OUR OWN milestone ledger saw cross $1m in the
same window, scored today with the identical rules off the identical endpoint
(`control_cohort.py`). That is the matched question: given a token that reached
$1m on day D, is it still alive now, and does his picking beat that?

Every proportion carries n and a Wilson interval (standing rule 6). Nothing is
reported below n=30 per arm without saying so (standing rule 7).
"""
import io
import json
import math
import os
from collections import Counter, defaultdict
from datetime import date

HERE = os.path.dirname(os.path.abspath(__file__))
TODAY = date(2026, 9, 22)
MIN_N = 30


def wilson(k, n, z=1.96):
    if n == 0:
        return (0.0, 0.0, 0.0)
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return (100 * p, 100 * max(0.0, c - h), 100 * min(1.0, c + h))


def pct(k, n):
    if n == 0:
        return "no data"
    p, lo, hi = wilson(k, n)
    return f"{p:.1f}% [{lo:.1f}, {hi:.1f}] n={n}"


def age_days(d):
    if not d:
        return None
    y, m, dd = (int(x) for x in d.split("-"))
    return (TODAY - date(y, m, dd)).days


def bucket(days):
    if days is None:
        return None
    if days >= 35:
        return "35+ days ago"
    if days >= 21:
        return "21-34 days ago"
    if days >= 8:
        return "8-20 days ago"
    return "0-7 days ago"


def median(xs):
    xs = sorted(x for x in xs if x is not None)
    if not xs:
        return None
    n = len(xs)
    return xs[n // 2] if n % 2 else (xs[n // 2 - 1] + xs[n // 2]) / 2.0


def main():
    rows = json.load(io.open(os.path.join(HERE, "dataset.json"), encoding="utf-8"))
    # ⭐ the round-trip scoring, not the search scoring. See control_roundtrip.py
    # for why the search-based version was withdrawn.
    try:
        ctrl = json.load(io.open(os.path.join(HERE, "control_roundtrip.json"), encoding="utf-8"))
        for c in ctrl:
            c["outcome"] = "alive" if c["state"] == "alive_tradeable" else "gone"
    except Exception:
        ctrl = []

    scored = [r for r in rows if r["outcome"] in ("alive", "faded", "rugged")]
    oc = Counter(r["outcome"] for r in rows)
    n = len(scored)

    # ⛔ His arm cannot produce a survival number. See the note below and the
    # header of build.py: dead tokens are absent from the search endpoints, so a
    # ticker always resolves to a living namesake if one exists.
    arms = [
        {"label": "tokens he called, 49 days", "value": f"{len(rows)}"},
        {"label": "contract resolved with confidence", "value": f"{n} ({100*n/len(rows):.0f}%)"},
        {"label": "ticker has several live namesakes", "value": f"{oc['unverifiable']}"},
        {"label": "no contract found at all", "value": f"{oc['unresolved']}"},
        {"label": "HIS HIT RATE", "value": "NOT COMPUTABLE (see note)"},
        {"label": "why we know that", "value": "ticker survival is FLAT with age"},
    ]

    # ⭐ stratified survival. Without this the headline is just a recency artifact.
    by_age = defaultdict(list)
    for r in scored:
        b = bucket(age_days(r["first_seen"]))
        if b:
            by_age[b].append(r)
    strat = {}
    for b in ("0-7 days ago", "8-20 days ago", "21-34 days ago", "35+ days ago"):
        g = by_age.get(b) or []
        a = sum(1 for r in g if r["outcome"] == "alive")
        strat[b] = {"n": len(g), "alive": a, "alive_pct": pct(a, len(g)),
                    "rugged": sum(1 for r in g if r["outcome"] == "rugged"),
                    "below_min_n": len(g) < MIN_N}

    # Control arm, same rules, same endpoint, same hour.
    # ⭐ "unresolved" here is NOT a measurement failure. The listings simply stop
    # returning a token once it has no liquidity, so absence IS the dead state.
    # Verified by round trip on a random sample (notfound_verification.json):
    # every one came back NO_BUY_ROUTE, NO_SELL_ROUTE or TOTAL_LOSS, with zero
    # Dexscreener pairs. So absent rows are counted as gone, not dropped, which
    # is the whole reason this arm can see what the ticker arm cannot.
    cs = ctrl
    cc = Counter(c["outcome"] for c in cs)
    cby = defaultdict(list)
    for c in cs:
        b = bucket(age_days(c["date"]))
        if b:
            cby[b].append(c)
    cstrat = {}
    for b in ("0-7 days ago", "8-20 days ago", "21-34 days ago", "35+ days ago"):
        g = cby.get(b) or []
        a = sum(1 for c in g if c["outcome"] == "alive")
        cstrat[b] = {"n": len(g), "alive": a, "alive_pct": pct(a, len(g)),
                     "below_min_n": len(g) < MIN_N}

    # ⛔ NOT a like-for-like comparison, and must never be printed as one.
    # This is EVIDENCE THAT THE TICKER ARM IS AN ARTIFACT: a real population of
    # memecoins decays with age, and the control does exactly that (10% -> 13%
    # -> 3%). The ticker arm is FLAT at 60-69% in every bucket, including tokens
    # called 35+ days ago, which is impossible. A flat curve is the signature of
    # measuring "is some live token using this ticker today", which is roughly
    # constant in time, rather than "did his pick survive".
    comp = []
    for b in cstrat:
        g, c = strat.get(b, {}), cstrat.get(b, {})
        if g.get("n", 0) >= MIN_N and c.get("n", 0) >= MIN_N:
            comp.append({"bucket": b, "ticker_arm_ARTIFACT": g["alive_pct"],
                         "control_real": c["alive_pct"],
                         "gorilla_n": g["n"], "control_n": c["n"]})

    if cs:
        arms.append({"label": "— the real base rate, keyed on ADDRESSES —", "value": ""})
        arms.append({"label": "our own $1m crossings, still tradeable",
                     "value": pct(cc["alive"], len(cs))})
        arms.append({"label": "… cannot round trip $100 today",
                     "value": pct(cc["gone"], len(cs))})
        for b in ("21-34 days ago", "8-20 days ago", "0-7 days ago"):
            v = cstrat.get(b) or {}
            if v.get("n"):
                arms.append({"label": f"   crossed {b}, alive",
                             "value": v["alive_pct"] + ("  (under n=30)" if v["below_min_n"] else "")})

    by_cat = {}
    for cat in sorted({r["category"] for r in scored}):
        g = [r for r in scored if r["category"] == cat]
        a = sum(1 for r in g if r["outcome"] == "alive")
        by_cat[cat] = {"n": len(g), "alive": a, "alive_pct": pct(a, len(g)),
                       "rugged": sum(1 for r in g if r["outcome"] == "rugged"),
                       "median_mult": median([r["mult_vs_first_reported"] for r in g]),
                       "below_min_n": len(g) < MIN_N}

    note = (
        "His hit rate is NOT COMPUTABLE from this archive, and reporting one would "
        "be a fabrication. The archive gives tickers, not contract addresses, and "
        "the endpoints that turn a ticker into an address only return tokens that "
        "still have liquidity. A token that died is absent from them entirely, so "
        "every ticker resolves to a living namesake if one exists. Proof: EMBER. "
        "The real contract FLCr9vGM…HTsh had its LP withdrawn at 11:09:37Z on "
        "2026-09-22 leaving $20.36 of depth, and it appears nowhere in the search "
        "results; the resolver picked a different, living EMBER and graded it "
        "alive. The base rate below therefore keys on ADDRESSES from our own "
        "milestone ledger, where the dead are still visible, and it is stratified "
        "by how long ago the crossing was because recency alone would manufacture "
        "an edge.")

    out = {"arms": arms, "note": note, "by_age": strat, "control_by_age": cstrat,
           "artifact_evidence": comp, "by_category": by_cat,
           "counts": dict(oc), "control_counts": dict(cc),
           "n_scored": n, "n_total": len(rows), "n_control": len(cs)}
    json.dump(out, io.open(os.path.join(HERE, "hitrate.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False)

    print(f"GORILLA  n={n} of {len(rows)}   {dict(oc)}")
    for k, v in strat.items():
        print(f"  {k:16s} alive {v['alive_pct']}"
              + ("   (under n=30)" if v["below_min_n"] else ""))
    print(f"CONTROL  n={len(cs)}   {dict(cc)}")
    for k, v in cstrat.items():
        print(f"  {k:16s} alive {v['alive_pct']}"
              + ("   (under n=30)" if v["below_min_n"] else ""))
    print("⛔ ARTIFACT EVIDENCE (this is NOT an edge, it is a flat curve):")
    for c in comp:
        print(f"  {c['bucket']:16s} ticker-arm {c['ticker_arm_ARTIFACT']}"
              f"   real {c['control_real']}")
    print("BY CATEGORY:")
    for k, v in sorted(by_cat.items(), key=lambda x: -x[1]["n"]):
        print(f"  {k:13s} n={v['n']:4d} alive {v['alive_pct']:28s} "
              f"rugged {v['rugged']:3d} median {v['median_mult']}"
              + ("  (under n=30)" if v["below_min_n"] else ""))


if __name__ == "__main__":
    main()
