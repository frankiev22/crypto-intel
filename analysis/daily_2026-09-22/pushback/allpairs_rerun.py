"""Re-run the 15 gate-passing contracts with ALL PAIRS summed, and count the
verdicts that change.

Frank, 2026-09-22: *"Re-run yesterday's 15 contracts and this morning's accuracy
sample with all-pairs summing. Report how many verdicts change. I expect most of
the 'drained' calls to flip."*

⛔ What `recheck15.json` did wrong: it read ONE pool per mint (the deepest it
could find via getProgramAccounts) and reported that pool's quote-side depth as
the token's depth. On a token that trades across 30 pools that is a ~3% sample
presented as the whole. It is the same bug family as `journal.py:974` writing
`gone` because one indexer lookup came back empty.

⚠️ Two instruments, and they answer different questions. Keep them apart:
  - `allpairs.token()`  -> SHAPE. How many pools, which quote assets, is the
    claimed cap backed at all. Dexscreener's `liquidity`, which we have measured
    overstating by a median 781x, so it is never an exit price.
  - `chainfields.round_trip()` -> the EXIT. Jupiter routes across every venue, so
    it already sees all the pools. This is what Frank would actually receive.

⭐ Prediction worth recording before the run: the round trip was ALREADY
all-pairs, so if the single-pool read were the only error the exit verdicts
would not move. What should move is the *shape*: tokens called drained on one
pool's $20 while holding millions across 29 others.
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import allpairs        # noqa: E402
import chainfields     # noqa: E402

SIZES = (100, 2000)


def old_verdict(r):
    """What we said yesterday, from the single-pool read."""
    q = r.get("chain_quote_usd")
    if q is None:
        return "UNKNOWN"
    if q < 1:
        return "DEAD"
    if q < 1000:
        return "DRAINED"
    if q < 25000:
        return "THIN"
    return "LIQUID"


def main():
    rows = json.load(io.open(os.path.join(HERE, "recheck15.json"), encoding="utf-8"))
    out = {"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()), "rows": []}
    changed = same = 0
    print(f"re-run {out['ts']}  ALL PAIRS vs one pool\n")
    hdr = (f"{'sym':10s} {'mint':46s} {'OLD(1 pool)':>12s} {'NEW(all)':>12s} "
           f"{'pairs':>5s} {'liq ALL':>13s} {'one pool':>11s} {'x':>7s}")
    print(hdr)
    print("-" * len(hdr))
    for r in rows:
        m = r["mint"]
        t = allpairs.token(m)
        rts = {}
        for usd in SIZES:
            q = chainfields.round_trip(m, usd)
            rts[usd] = {k: q.get(k) for k in ("verdict", "usd_back", "rt_cost_pct", "error")}
            time.sleep(0.35)
        ov, nv = old_verdict(r), allpairs.verdict(t)
        flip = ov != nv
        changed += flip
        same += not flip
        out["rows"].append({"mint": m, "symbol": r.get("symbol"),
                            "old_single_pool_quote_usd": r.get("chain_quote_usd"),
                            "old_verdict": ov, "new_verdict": nv, "changed": flip,
                            "allpairs": t, "round_trips": rts,
                            "old_jup_verdict": r.get("jup_verdict"),
                            "old_jup_usd_back": r.get("jup_usd_back")})
        print(f"{str(r.get('symbol'))[:10]:10s} {m:46s} {ov:>12s} {nv:>12s} "
              f"{str(t.get('pair_count')):>5s} "
              f"${(t.get('total_liq_usd') or 0):>12,.0f} "
              f"${(r.get('chain_quote_usd') or 0):>10,.0f} "
              f"{('%.0fx' % (t['total_liq_usd']/r['chain_quote_usd'])) if (t.get('total_liq_usd') and r.get('chain_quote_usd')) else '-':>7s}"
              + ("   <- CHANGED" if flip else ""))
        for usd in SIZES:
            q = rts[usd]
            b = q.get("usd_back")
            print(f"           ${usd:>5} round trip: {str(q['verdict']):<14s} "
                  f"back {('$%.2f' % b) if isinstance(b,(int,float)) else 'unknown':>10s} "
                  f"cost {q.get('rt_cost_pct')}%  {q.get('error') or ''}")
    out["changed"] = changed
    out["unchanged"] = same
    json.dump(out, io.open(os.path.join(HERE, "allpairs_rerun.json"), "w", encoding="utf-8"),
              indent=1, ensure_ascii=False, default=str)
    print(f"\nverdicts changed: {changed} of {len(rows)}   unchanged: {same}")


if __name__ == "__main__":
    main()
