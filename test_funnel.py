"""The funnel row, its alarms, and the batched pair lookups behind them.

⛔ Every check here reads the OUTPUT back: the row on disk, the alarm text, the
object the cache serves. A test that only proves the function ran is the exact
failure standing rule 16 exists for.

No network. The batch tests stub sources._get and assert on what the cache then
hands to callers.
"""
import io
import json
import os
import sys
import time

import testsandbox
testsandbox.activate()          # this suite beats liveness; data/ must not move

import funnel
import sources

R = []


def check(name, cond, detail=None):
    R.append((name, bool(cond), detail))
    print(f"  {'PASS' if cond else 'FAIL':4}  {name}" + (f"  [{detail}]" if detail and not cond else ""))


def section(t):
    print(f"\n{t}\n" + "=" * 70)


# --------------------------------------------------------------------------
section("1. the row is written, and it is the row we asked for")
TMP = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "_test_funnel")
_orig_dir, _orig_latest = funnel.DIR, funnel.LATEST
funnel.DIR = TMP
funnel.LATEST = os.path.join(TMP, "latest.json")
try:
    class _LS(dict):
        pass
    import scanner
    import track
    _save_scan, _save_cov = scanner.LAST_SCAN, track.LAST_COVERAGE
    _save_hh = dict(track.HORIZON_HEALTH)
    # the real 2026-09-21 shape: the 24h primary source at 37/189, its floor 20%
    track.HORIZON_HEALTH.clear()
    track.HORIZON_HEALTH.update({1: {"primary_ok": 300, "primary_miss": 117},
                                 6: {"primary_ok": 37, "primary_miss": 152}})
    scanner.LAST_SCAN = {"pools": 200, "reached": 70, "enriched": 68, "failed": 2,
                         "budget_hit": True, "truncate_reason": "stage deadline",
                         "carried_forward": 130, "pools_carried": 110, "skipped": ["a", "b"]}
    # the real shape of 2026-09-20 06:30Z: two horizons, 1,073 rows standing
    track.LAST_COVERAGE = {1: {"due": 417, "scored_this_pass": 120, "not_reached": 297,
                               "expiring_before_next_pass": 30, "coverage": 120 / 417,
                               "slice_limit": 120},
                           6: {"due": 656, "scored_this_pass": 120, "not_reached": 536,
                               "expiring_before_next_pass": 121, "coverage": 120 / 656,
                               "slice_limit": 120}}
    seen = []
    row = funnel.record(stage="scan", origin="scheduled", verbose=False,
                        record_finding=lambda *a, **k: seen.append((a, k)))
    check("record() returned a row", isinstance(row, dict))
    path = funnel._rows_path(row["ts"])
    back = [json.loads(l) for l in open(path, encoding="utf-8")][-1]
    check("⭐ the row is ON DISK and identical to what was returned", back == row)
    check("...with the scan coverage this pass actually achieved",
          back["scan"]["coverage"] == 0.35, back["scan"]["coverage"])
    check("...the pools it carried forward", back["scan"]["carried_forward"] == 130)
    check("...and the queue it did not reach", back["outcomes"]["6h"]["not_reached"] == 536)
    check("latest.json is written for the site", os.path.exists(funnel.LATEST))

    # ⭐ the primary price source, per horizon. Only the TEXT of a lookup-outage
    # finding recorded this before, and that is written only once the rate is
    # already under the floor - so the trend was unmeasurable by construction.
    check("⭐ the row carries the primary source's rate per horizon",
          back["outcomes"]["6h"]["primary_rate"] == round(37 / 189, 4),
          back["outcomes"]["6h"].get("primary_rate"))
    check("...with the numerator and denominator beside it, not just the ratio",
          (back["outcomes"]["6h"]["primary_ok"], back["outcomes"]["6h"]["primary_seen"])
          == (37, 189))
    check("...and the pre-committed floor it is judged against",
          back["outcomes"]["6h"]["primary_floor"] is not None,
          back["outcomes"]["6h"].get("primary_floor"))
    # ⛔ A horizon the health dict knows nothing about must read unknown. Tested
    # by removing it from HORIZON_HEALTH while it stays in LAST_COVERAGE, which
    # is exactly what a horizon skipped for want of budget looks like.
    _hh6 = track.HORIZON_HEALTH.pop(6)
    _o = funnel._outcomes()
    track.HORIZON_HEALTH[6] = _hh6
    check("⛔ a horizon nobody looked at reads unknown, not 0%",
          _o["6h"]["primary_rate"] is None and _o["6h"]["primary_seen"] is None
          and _o["1h"]["primary_rate"] is not None, _o["6h"])
    check("...and the pass line omits it rather than printing 0%",
          "0% of" not in funnel.line({"outcomes": _o}), funnel.line({"outcomes": _o}))
    check("the pass line names the rate and says when it is under the floor",
          "primary source" in funnel.line(back) and "UNDER FLOOR" in funnel.line(back),
          funnel.line(back))
    check("⛔ a narrowing funnel raises a finding", len(seen) == 1, seen)
    check("...naming the loss that cannot be recovered",
          "age out UNSCORED" in json.dumps(seen[0]) if seen else False)

    section("2. the alarms fire on the conditions that lost us data on 09-19")
    check("scan coverage below the floor alarms",
          any("scan coverage" in a for a in row["alarms"]), row["alarms"])
    check("⛔ ANY row about to age out unscored alarms",
          any("age out UNSCORED" in a for a in row["alarms"]))
    check("a 1,073-deep queue across horizons alarms",
          any("outcome queue" in a for a in row["alarms"]), row["alarms"])
    check("...and one horizon alone, under the total, does not",
          not any("outcome queue" in a for a in funnel.alarms(
              {"outcomes": {"6h": {"due": 400, "expiring_before_next_pass": 0}}})))
    healthy = {"scan": {"coverage": 0.97, "pools_seen": 200, "pools_reached": 194,
                        "carried_forward": 6},
               "outcomes": {"6h": {"due": 40, "expiring_before_next_pass": 0}},
               "graduations": {"backlog": 12, "lag_h": 0.2}}
    check("⭐ a healthy pass raises NOTHING", funnel.alarms(healthy) == [], funnel.alarms(healthy))
    check("graduation lag alarms on its own",
          any("behind" in a for a in funnel.alarms(
              {"graduations": {"backlog": 880, "lag_h": 12.0}})))
    check("...and so does a backlog under the lag limit",
          any("backlog" in a for a in funnel.alarms(
              {"graduations": {"backlog": 300, "lag_h": 0.5}})))

    section("3. unknown is 'unknown', never 0 (standing rule 5)")
    ln = funnel.line({"scan": {"coverage": None, "pools_seen": None, "pools_reached": None,
                               "carried_forward": None},
                      "graduations": {"backlog": 5, "lag_h": None}})
    check("an unmeasured coverage renders as unknown", "scan unknown" in ln, ln)
    check("an unmeasured lag renders as unknown", "lag unknown" in ln, ln)
    check("⛔ and neither renders as 0%", "0%" not in ln and "0h" not in ln, ln)

    section("4. a pass with nothing to report writes no row")
    scanner.LAST_SCAN = {}
    track.LAST_COVERAGE = {}
    sources.PREFETCH_STATS.update({"calls": 0, "asked": 0, "found": 0, "served": 0, "stale": 0})
    _g = funnel._graduations
    funnel._graduations = lambda: None
    n_before = len(open(path, encoding="utf-8").readlines())
    check("record() returns None when nothing was measured",
          funnel.record(stage="idle", verbose=False) is None)
    check("...and appends nothing", len(open(path, encoding="utf-8").readlines()) == n_before)
    funnel._graduations = _g

    section("5. summary() reads the rows back")
    s = funnel.summary(hours=24)
    check("summary counts the pass we wrote", s["passes"] >= 1, s)
    check("...and carries the rows that were about to be lost",
          s["rows_expiring_unscored"] == 151, s)
finally:
    scanner.LAST_SCAN, track.LAST_COVERAGE = _save_scan, _save_cov
    track.HORIZON_HEALTH.clear()
    track.HORIZON_HEALTH.update(_save_hh)
    funnel.DIR, funnel.LATEST = _orig_dir, _orig_latest
    import shutil
    shutil.rmtree(TMP, ignore_errors=True)

# --------------------------------------------------------------------------
section("6. batched pair lookups: 30 per call, and identity is preserved")
CALLS = []
A = [f"pair{i:02d}" for i in range(35)]


def fake_get(url, *a, **k):
    CALLS.append(url)
    asked = url.rsplit("/", 1)[-1].split(",")
    # the real endpoint omits pools it does not have; pair07 is one of those
    return {"pairs": [{"pairAddress": p, "priceUsd": "1.5",
                       "baseToken": {"address": "t" + p}} for p in asked if p != "pair07"]}


_real_get = sources._get
sources._get = fake_get
sources._PAIR_PRE.clear()
sources.PREFETCH_STATS.update({"calls": 0, "asked": 0, "found": 0, "served": 0, "stale": 0})
try:
    calls = sources.prefetch_pairs("solana", A)
    check("35 addresses cost 2 calls, not 35", calls == 2 and len(CALLS) == 2, (calls, len(CALLS)))
    check("⛔ no call asks for more than the measured limit of 30",
          all(len(u.rsplit("/", 1)[-1].split(",")) <= 30 for u in CALLS),
          [len(u.rsplit("/", 1)[-1].split(",")) for u in CALLS])
    hit, p = sources.prefetched_pair("solana", "pair03")
    check("a prefetched pool is served from the cache", hit and p["pairAddress"] == "pair03")
    n_before = len(CALLS)
    got = sources.dexscreener_pair("solana", "pair03")
    check("⭐ dexscreener_pair serves it WITHOUT another call",
          got["pairAddress"] == "pair03" and len(CALLS) == n_before)
    check("...and it is the pool that was asked for, not whichever sorted first",
          got["baseToken"]["address"] == "tpair03")
    miss_hit, miss = sources.prefetched_pair("solana", "pair07")
    check("⛔ a pool the source does not have is cached as ABSENT, not as another pool",
          miss_hit and miss is None)
    check("...and dexscreener_pair returns None for it without a live call",
          sources.dexscreener_pair("solana", "pair07") is None and len(CALLS) == n_before)
    check("absence is not recorded as a pair-identity mismatch",
          not any(m.get("asked") == "pair07" for m in sources.LAST_PAIR_MISMATCH))

    section("7. a stale entry is never served")
    sources._PAIR_PRE[("solana", "pair03")] = (time.time() - sources.PREFETCH_TTL_S - 1,
                                               {"pairAddress": "pair03"})
    hit, _ = sources.prefetched_pair("solana", "pair03")
    check("past the TTL the cache reports a miss", not hit)
    n_before = len(CALLS)
    sources.dexscreener_pair("solana", "pair03")
    check("...so the caller makes a live call instead of reading a stale price",
          len(CALLS) == n_before + 1)
    check("the stale read is counted", sources.PREFETCH_STATS["stale"] >= 1)

    section("8. require_match=False still goes to the live endpoint")
    n_before = len(CALLS)
    sources.prefetch_pairs("solana", ["freshpair"])   # not in the batch above
    sources.dexscreener_pair("solana", "freshpair", require_match=False)
    check("⛔ the unverified path is never served from the matched cache",
          len(CALLS) == n_before + 2, (n_before, len(CALLS)))
finally:
    sources._get = _real_get
    sources._PAIR_PRE.clear()

ok = sum(1 for _, c, _ in R if c)
print(f"\n{ok}/{len(R)} passed")
sys.exit(0 if ok == len(R) else 1)
