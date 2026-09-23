"""Redo the `gone` verification by DERIVING pools from the MINT, on chain.

Rule: ../../PRECOMMIT_pool_discovery.md, written before this script read a single
sample contract. Instrument validated first on mints OUTSIDE the sample.

Frank: "I think the 1.7% testing result is inaccurate. We need to use the
contract address to find the real pool so we can see it after bonding."

⛔ Both earlier attempts answered the wrong question:
  - the all-pairs recheck asked the SAME INDEXER in both arms (118/120 NO_PAIRS
    on both), so it measured "does Dexscreener list this";
  - my own on-chain probe read `getAccountInfo` on the pool address OUR ROW
    recorded, and all 54 were pump.fun CURVE accounts, which are never closed
    when a token bonds. That result was guaranteed before the first RPC.

This one starts from the contract address and finds the pool itself.

Run: python analysis/gone_pools/run.py
"""
import glob
import io
import json
import math
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import pooldiscovery as pd  # noqa: E402

# ⛔ PRE-COMMITTED in PRECOMMIT_pool_discovery.md before any sample read.
N_SAMPLE = 120
WINDOW_H = 72
UNREADABLE_SHARE_KILLS_RATE = 1.0 / 3.0


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(100 * (c - m) / d, 2), round(100 * (c + m) / d, 2))


def sample():
    """Newest-first distinct contracts labelled `gone` inside the window.

    ⛔ The row's recorded `pair` is carried for COMPARISON ONLY. It is never used
    to find the pool. That is the bug being corrected.
    """
    cutoff = time.time() - WINDOW_H * 3600
    rows = []
    for path in sorted(glob.glob(os.path.join(ROOT, "data", "outcomes",
                                              "*.jsonl")))[-4:]:
        for ln in io.open(path, encoding="utf-8"):
            if '"gone"' not in ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            if r.get("status") != "gone" or not r.get("token"):
                continue
            ts = r.get("checked_ts") or r.get("observed_ts") or 0
            if ts < cutoff:
                continue
            rows.append(r)
    rows.sort(key=lambda r: -(r.get("checked_ts") or 0))
    seen = {}
    for r in rows:
        t = r["token"]
        if t in seen:
            continue
        seen[t] = {
            "token": t,
            "symbol": r.get("symbol"),
            "recorded_pair": r.get("pair"),
            "checked_ts": r.get("checked_ts"),
            "horizon_h": r.get("horizon_h"),
            "reasons": r.get("reasons"),
        }
        if len(seen) >= N_SAMPLE:
            break
    return list(seen.values()), len(rows)


def main():
    samp, total_rows = sample()
    px, src, ts = pd.sol_price()
    print("sample %d distinct contracts from %d `gone` rows in %dh"
          % (len(samp), total_rows, WINDOW_H))
    print("SOL $%s from %s at %d\n" % (px, src, ts))

    out = {
        "rule": "PRECOMMIT_pool_discovery.md",
        "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "window_h": WINDOW_H,
        "n_sample": len(samp),
        "gone_rows_in_window": total_rows,
        "sol_usd": px,
        "sol_usd_source": src,
        "sol_usd_read_at": ts,
        "rows": [],
    }
    budget = pd.Budget()
    t0 = time.time()
    for i, s in enumerate(samp, 1):
        d = pd.discover(s["token"], sol_usd=px, budget=budget)
        row = dict(s)
        row.update({
            "verdict": d["verdict"],
            "rung": d["rung"],
            "pool_count": d["pool_count"],
            "quote_usd_max": round(d["quote_usd_max"], 4),
            "quote_usd_total": round(d["quote_usd_total"], 4),
            "unvalued_vaults": d["unvalued_vaults"],
            "holders_reached": d["holders_reached"],
            "holders_total_known": d.get("holders_total_known"),
            "truncated_holders": d.get("truncated_holders"),
            "venues": sorted({p["venue"] for p in d["pools"]}),
            "pools": [{"pool": p["pool"], "venue": p["venue"],
                       "quote_usd": p["quote_usd"], "lamports": p["lamports"],
                       "base_amount": p["base_amount"]} for p in d["pools"]],
            "errors": d["errors"][:4],
            # ⛔ Rule 15: record WHAT was missed, not only how much. This is
            # the field that diagnosed both threshold misses, so it is persisted.
            "unknown_programs": d.get("unknown_programs") or [],
            "excluded_owners": [
                {"owner": e["owner"], "program": e["program"],
                 "known_non_pool": e["known_non_pool"],
                 "base_amount": e["base_amount"]}
                for e in (d.get("excluded_owners") or [])[:8]],
            # ⛔ Did our own recorded pair even appear among the real pools?
            "recorded_pair_is_a_discovered_pool":
                s["recorded_pair"] in {p["pool"] for p in d["pools"]},
            "absence_is_a_floor": True,
        })
        out["rows"].append(row)
        print("%3d/%d %-12s %-22s rung %s pools %d quote $%.2f  %s" % (
            i, len(samp), (s["symbol"] or "")[:12], d["verdict"], d["rung"],
            d["pool_count"], d["quote_usd_max"], s["token"][:10]))
        sys.stdout.flush()

    # -------------------------------------------------- tally
    tally = {}
    for r in out["rows"]:
        tally[r["verdict"]] = tally.get(r["verdict"], 0) + 1
    unreadable = tally.get("UNREADABLE", 0)
    usable = len(out["rows"]) - unreadable
    k100 = tally.get("POOL_QUOTE_100", 0)
    k10 = tally.get("POOL_QUOTE_10", 0)
    out["tally"] = tally
    out["usable_n"] = usable
    out["unreadable_n"] = unreadable
    out["headline"] = {
        "definition": ("share of `gone` contracts with a pool holding >= $100 of "
                       "VALUED quote-side reserves on chain"),
        "k": k100, "n": usable,
        "pct": round(100.0 * k100 / usable, 2) if usable else None,
        "wilson95": wilson(k100, usable),
        "is_a_lower_bound": True,
        "why_lower_bound": ("discovery reaches the largest holders only, so a "
                            "NO_POOL_FOUND is not proof that no pool exists"),
    }
    out["band_10_plus"] = {
        "k": k100 + k10, "n": usable,
        "pct": round(100.0 * (k100 + k10) / usable, 2) if usable else None,
        "wilson95": wilson(k100 + k10, usable),
    }
    out["any_pool_at_all"] = {
        "k": usable - tally.get("NO_POOL_FOUND", 0), "n": usable,
        "pct": (round(100.0 * (usable - tally.get("NO_POOL_FOUND", 0)) / usable, 2)
                if usable else None),
        "wilson95": wilson(usable - tally.get("NO_POOL_FOUND", 0), usable),
    }
    out["rate_published"] = (
        usable > 0 and unreadable / float(len(out["rows"]))
        <= UNREADABLE_SHARE_KILLS_RATE)
    if not out["rate_published"]:
        out["rate_suppressed_why"] = (
            "UNREADABLE %d of %d exceeds the pre-committed one-third kill "
            "threshold, so this is a finding about our RPC budget, not the "
            "market" % (unreadable, len(out["rows"])))
    out["recorded_pair_was_a_real_pool"] = sum(
        1 for r in out["rows"] if r["recorded_pair_is_a_discovered_pool"])
    out["unknown_program_rows"] = sum(
        1 for r in out["rows"] if r["unknown_programs"])
    out["unknown_programs_seen"] = sorted(
        {p for r in out["rows"] for p in r["unknown_programs"]})
    # ⛔ The honest bound on the FLOOR: a NO_POOL_FOUND row that saw an
    # EXECUTABLE program we do not know may well have a pool we cannot name.
    out["no_pool_found_with_unknown_program"] = sum(
        1 for r in out["rows"]
        if r["verdict"] == "NO_POOL_FOUND" and r["unknown_programs"])
    out["venue_counts"] = {}
    for r in out["rows"]:
        for v in r["venues"]:
            out["venue_counts"][v] = out["venue_counts"].get(v, 0) + 1
    out["rpc"] = {"calls": budget.calls, "errors": budget.errors,
                  "rate_limited": budget.rate_limited,
                  "wall_s": round(time.time() - t0, 1)}

    path = os.path.join(HERE, "result.json")
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(out, indent=1, sort_keys=True))
    print("\n" + json.dumps({k: v for k, v in out.items() if k != "rows"},
                            indent=1, sort_keys=True))
    print("\nwrote", path)
    return 0


if __name__ == "__main__":
    sys.exit(main())
