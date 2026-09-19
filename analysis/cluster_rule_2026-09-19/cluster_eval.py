"""Score an arm under PRECOMMIT_cluster_rule.md. usage: python cluster_eval.py armB.jsonl [armD.jsonl]"""
import json
import math
import os
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
AUTH = json.load(open(os.path.join(HERE, "cluster_auth.json")))
RESOLVED = {}
p = os.path.join(HERE, "cluster_auth_resolved.json")
if os.path.exists(p):
    RESOLVED = json.load(open(p))


def wilson(k, n, z=1.96):
    if n == 0:
        return (None, None)
    ph = k / n
    d = 1 + z * z / n
    c = (ph + z * z / (2 * n)) / d
    h = z * math.sqrt(ph * (1 - ph) / n + z * z / (4 * n * n)) / d
    return (max(0, c - h), min(1, c + h))


def q(xs, f):
    xs = sorted(xs)
    if not xs:
        return None
    k = (len(xs) - 1) * f
    lo, hi = math.floor(k), math.ceil(k)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def auth(tok):
    a = RESOLVED.get(tok) or AUTH.get(tok, {}).get("authority_at_entry", "unknown")
    return a


def score(path):
    rows = [json.loads(l) for l in open(path, encoding="utf-8")]
    pr = [r for r in rows if r["status"] == "priced"]
    unp = [r for r in rows if r["status"] != "priced"]
    out = {"file": os.path.basename(path), "tokens": len(rows), "priced": len(pr), "unpriced": len(unp),
           "unpriced_reasons": {}}
    for r in unp:
        k = r["status"].split(":")[0] + ": " + r["status"].split(":", 1)[-1][:60]
        out["unpriced_reasons"][k] = out["unpriced_reasons"].get(k, 0) + 1

    def price_win(r):
        for h in (6, 24):
            x, d = r.get(f"x{h}"), r.get(f"depth{h}_usd")
            if x is not None and x >= 2.0 and d is not None and d >= 500:
                return True
        return False

    def died(r):
        d = r.get("depth24_usd")
        return r.get("dead_after_T") or d is None or d < 500

    cands = [r["token"] for r in pr if price_win(r)]
    out["price_and_depth_wins_before_authority"] = len(cands)
    out["candidates_authority"] = {t[:8]: auth(t) for t in cands}
    out["unresolved_unknown_among_candidates"] = sum(1 for t in cands if auth(t) == "unknown")

    variants = {}
    for live_in in (True, False):
        for died_in in (True, False):
            pop = [r for r in pr if (live_in or auth(r["token"]) != "live") and (died_in or not died(r))]
            k = sum(1 for r in pop if price_win(r) and auth(r["token"]) == "revoked")
            lo, hi = wilson(k, len(pop))
            variants[f"authority-live {'in' if live_in else 'out'}, died {'in' if died_in else 'out'}"] = {
                "wins": k, "n": len(pop), "rate": None if not pop else round(k / len(pop), 4),
                "wilson": None if lo is None else [round(lo, 4), round(hi, 4)]}
    out["variants"] = variants
    for h in (6, 24):
        xs = [r[f"x{h}"] for r in pr if r.get(f"x{h}") is not None]
        out[f"x{h}_p25_med_p75"] = [None if not xs else round(q(xs, f), 3) for f in (0.25, 0.5, 0.75)]
        out[f"x{h}_n"] = len(xs)
    out["dead_after_T"] = sum(1 for r in pr if r.get("dead_after_T"))
    out["depth24_below_500_or_unknown"] = sum(1 for r in pr if died(r))
    return out


for path in sys.argv[1:]:
    print(json.dumps(score(os.path.join(HERE, path)), indent=1))
