"""The control arm: every token OUR OWN data saw cross $1m in the same window.

⛔ Without this, "X% of Gorilla's calls are still alive" is a number with nothing
to compare it to, and a reader will silently compare it to zero. Our published
base rate (0.27% for an AMM token reaching 2x with real depth) is the WRONG
control here: that is a launch-time population, and Gorilla's is a population of
tokens that had already reached $1m. Comparing them would flatter him enormously.

So the control is: tokens from `data/milestones/` that crossed **mcap_1m**
between 2026-08-21 and 2026-09-22, scored TODAY with the SAME outcome rules, in
the same hour, off the same endpoint.

⚠️ Two honest limits, stated rather than buried:
  - our milestone ledger starts 2026-08-21, so the earliest two weeks of the
    archive have no control and are reported separately;
  - both arms use the listings' reported liquidity, which overstates by a median
    781x. It is a coarse alive/dead split for BOTH arms, so the comparison is
    fair even though neither number is tradeable.
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import chainfields  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}
CACHE = os.path.join(HERE, "cache_ctrl")


def state_of(addr):
    os.makedirs(CACHE, exist_ok=True)
    p = os.path.join(CACHE, addr + ".json")
    if os.path.exists(p):
        try:
            return json.load(io.open(p, encoding="utf-8"))
        except Exception:
            pass
    st, b = chainfields._get("https://lite-api.jup.ag/tokens/v2/search?query=" + addr,
                             headers=UA, timeout=25)
    time.sleep(0.35)
    row = {}
    if isinstance(b, list):
        for t in b:
            if t.get("id") == addr:
                row = {"mcap": t.get("mcap"), "liquidity": t.get("liquidity"),
                       "holders": t.get("holderCount"), "symbol": t.get("symbol"),
                       "price": t.get("usdPrice")}
                break
    tmp = p + ".tmp"
    json.dump(row, io.open(tmp, "w", encoding="utf-8"), ensure_ascii=False)
    os.replace(tmp, p)
    return row


def outcome(row):
    """⭐ IDENTICAL to build.outcome. Any drift here invalidates the comparison."""
    if not row:
        return "unresolved"
    liq = row.get("liquidity")
    if liq is None:
        return "unresolved"
    if liq < 1000:
        return "rugged"
    if (row.get("mcap") or 0) >= 1_000_000:
        return "alive"
    return "faded"


def main():
    cohort = json.load(io.open(os.path.join(HERE, "our_1m_cohort.json"), encoding="utf-8"))
    first = {}
    for r in cohort:
        t = r["token"]
        if t not in first or r["date"] < first[t]["date"]:
            first[t] = r
    toks = sorted(first.values(), key=lambda r: r["date"])
    out, t0 = [], time.time()
    for i, r in enumerate(toks):
        try:
            st = state_of(r["token"])
        except Exception as e:
            st = {"error": f"{type(e).__name__}: {str(e)[:80]}"}
        out.append({**r, "now": st, "outcome": outcome(st)})
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(toks)} {el:.0f}s, {el/(i+1)*(len(toks)-i-1):.0f}s left",
                  flush=True)
            json.dump(out, io.open(os.path.join(HERE, "control_scored.json"), "w",
                                   encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(out, io.open(os.path.join(HERE, "control_scored.json"), "w",
                           encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("control n =", len(out), dict(Counter(r["outcome"] for r in out)))


if __name__ == "__main__":
    main()
