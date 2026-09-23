"""Re-score the control the honest way: a live round trip on every address.

⛔ CORRECTION TO MY OWN METHOD, 2026-09-22. `control_cohort.py` classified a
token as gone when the listings stopped returning it. A 6-token sample said that
was safe. **A 44-token sample said it is not: 86.4% [73.3, 93.6] dead, so about
one in seven "missing" tokens is alive** - including ZEC, a bridged major that
simply is not in that search index. Absence from a third-party index is not
death, and treating it as death would have overstated the base rate by roughly
14 points.

That is standing rule 15 in its usual clothes: the small sample was the exposed
one, and I nearly published from it.

So this file asks the only question that settles it, the same one we trust for
everything else Frank would act on: **can $100 actually round trip today?**
`chainfields.round_trip` gives a verdict from Jupiter's own error codes, so a
network failure reads as unknown rather than as death (`chainfields.answered`).

Outcome, pre-committed:
  NO_BUY_ROUTE / NO_SELL_ROUTE / TOTAL_LOSS, or under $1 back   -> dead
  a verdict with >= $1 back                                     -> alive_tradeable
  no verdict at all (outage, rate limit)                        -> unknown, EXCLUDED
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.abspath(os.path.join(HERE, "..", "..")))
import chainfields  # noqa: E402

OUT = os.path.join(HERE, "control_roundtrip.json")


def classify(rt):
    v = rt.get("verdict")
    back = rt.get("usd_back")
    if v is None:
        return "unknown"
    if v in ("NO_BUY_ROUTE", "NO_SELL_ROUTE", "TOTAL_LOSS"):
        return "dead"
    if isinstance(back, (int, float)) and back < 1:
        return "dead"
    return "alive_tradeable"


def main():
    cohort = json.load(io.open(os.path.join(HERE, "our_1m_cohort.json"), encoding="utf-8"))
    first = {}
    for r in cohort:
        t = r["token"]
        if t not in first or r["date"] < first[t]["date"]:
            first[t] = r
    toks = sorted(first.values(), key=lambda r: r["date"])

    done = {}
    if os.path.exists(OUT):
        try:
            done = {r["token"]: r for r in json.load(io.open(OUT, encoding="utf-8"))}
        except Exception:
            done = {}

    out, t0 = [], time.time()
    for i, r in enumerate(toks):
        if r["token"] in done:
            out.append(done[r["token"]])
            continue
        try:
            rt = chainfields.round_trip(r["token"], 100)
        except Exception as e:
            rt = {"verdict": None, "error": f"{type(e).__name__}: {str(e)[:80]}"}
        out.append({**r, "verdict": rt.get("verdict"), "usd_back": rt.get("usd_back"),
                    "state": classify(rt)})
        time.sleep(0.2)
        if (i + 1) % 50 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(toks)} {el:.0f}s, {el/(i+1)*(len(toks)-i-1):.0f}s left",
                  flush=True)
            json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1, ensure_ascii=False)
    from collections import Counter
    print("control by round trip:", dict(Counter(r["state"] for r in out)))


if __name__ == "__main__":
    main()
