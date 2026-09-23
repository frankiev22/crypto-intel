"""Replace the `gone` label with the state we can actually measure.

Rule: ../../PRECOMMIT_pool_state.md sections 3 and 4.

Frank: *"Replace the `gone` label. It is wrong about mechanism in 7 of 8 cases."*

⛔⛔ NOTHING IS OVERWRITTEN AND NOTHING IS DELETED (standing rule 8, and the
pre-commit says so explicitly). `status` stays `gone` on every outcome row as the
historical label. The measured state is written to a SIDECAR,
`data/pools/state.jsonl`, keyed on the contract address, append-only. Anything
reading outcomes joins on `token` and prefers `pool_state` when present.

⚠️ A backfill measures the pool TODAY, not at the moment the row was scored. A
pool drained after we scored it backfills identically to one drained before, and
we cannot tell those apart. Every row carries `backfilled: true` and its
measurement time, and ⛔ no rate computed over these rows may be described as a
rate at the time of scoring.

Run: python analysis/pool_offsets/backfill.py [--limit N]
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
import poolstate  # noqa: E402

OUT = os.path.join(ROOT, "data", "pools", "state.jsonl")
WINDOW_H = 72


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / float(n)
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round(100 * (c - m) / d, 2), round(100 * (c + m) / d, 2))


def already_done():
    """Contracts already in the sidecar. ⛔ Append-only, so never re-measured."""
    seen = {}
    if os.path.exists(OUT):
        for ln in io.open(OUT, encoding="utf-8"):
            ln = ln.strip()
            if not ln:
                continue
            try:
                r = json.loads(ln)
            except ValueError:
                continue
            seen[r.get("token")] = r
    return seen



def _is_deepest(pair, pools):
    """Was the pair we priced the pool holding the MOST quote side?

    ⛔ None when nothing is priced at all, because "no pool has money" is not
    an answer to "did we look at the right pool".
    """
    vals = [(p.get("quote_usd") or 0.0) for p in pools
            if p.get("quote_usd") is not None]
    if not vals or max(vals) <= 0:
        return None
    top = max(vals)
    mine = next((p.get("quote_usd") for p in pools if p["pool"] == pair), None)
    if mine is None:
        return False
    return abs(mine - top) <= max(1e-9, top * 1e-9)


def sample(limit):
    """The same population as the gone_pools run, so the two are comparable."""
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
        if r["token"] in seen:
            continue
        seen[r["token"]] = {"token": r["token"], "symbol": r.get("symbol"),
                            "recorded_pair": r.get("pair"),
                            "checked_ts": r.get("checked_ts")}
        if len(seen) >= limit:
            break
    return list(seen.values()), len(rows)


def main(argv):
    limit = 120
    if "--limit" in argv:
        limit = int(argv[argv.index("--limit") + 1])
    samp, total = sample(limit)
    done = already_done()
    # ⛔ --remeasure-stale re-measures rows written under an EARLIER rule version
    # and APPENDS the new answer (standing rule 8: the old row stays). The tally
    # keys on `token` and takes the LAST row, so the newest measurement wins
    # without anything being edited or removed.
    stale_before = None
    if "--remeasure-stale" in argv:
        stale_before = int(argv[argv.index("--remeasure-stale") + 1])
    # ⛔ --only re-measures exactly these contracts and APPENDS (rule 8: the old
    # row stays, the tally takes the last row per token). Used when a reader fix
    # lands mid-run and only some rows are affected.
    only = None
    if "--only" in argv:
        only = set(argv[argv.index("--only") + 1].split(","))
    if only:
        todo = [s for s in samp if s["token"] in only]
    elif stale_before:
        todo = [s for s in samp
                if s["token"] not in done
                or (done[s["token"]].get("pool_state_measured_at") or 0)
                < stale_before]
    else:
        todo = [s for s in samp if s["token"] not in done]
    px, src, ts = pd.sol_price()
    print("sample %d distinct `gone` contracts from %d rows in %dh"
          % (len(samp), total, WINDOW_H))
    print("already measured: %d, to do: %d" % (len(samp) - len(todo), len(todo)))
    print("SOL $%s from %s at %d" % (px, src, ts))
    print("queryable venues (MEASURED offsets): %s"
          % [v for v, _p, _o in poolstate.queryable_venues()])
    print("⛔ NOT queryable, never asked: %s\n"
          % [v for v, _p in poolstate.unqueryable_venues()])

    budget = pd.Budget()
    t0 = time.time()
    fh = io.open(OUT, "a", encoding="utf-8")
    written = 0
    for i, s in enumerate(todo, 1):
        try:
            # ⛔ `known_pair` is what makes `pool_closed` claimable at all
            # (PRECOMMIT_pool_state.md §3a). It is the pool THIS ROW priced, so
            # its absence on chain is evidence a pool once existed and is gone.
            # Without it the row can only reach `not_found`.
            d = poolstate.state(s["token"], sol_usd=px, budget=budget,
                                known_pair=s["recorded_pair"])
        except Exception as e:
            d = {"pool_state": "unreadable",
                 "errors": ["%s: %s" % (type(e).__name__, str(e)[:100])],
                 "pool_count": 0, "pools": [], "quote_usd_max": 0.0,
                 "pools_existing": 0, "pools_absent": 0, "venues": [],
                 "how_found": [], "rejected_non_pairs": [],
                 "known_pair_absent": None,
                 "pool_state_measured_at": int(time.time())}
        row = {
            "token": s["token"],
            "symbol": s["symbol"],
            "historical_status": "gone",
            "recorded_pair": s["recorded_pair"],
            # ⛔ Did the pair we priced even belong to this mint?
            "recorded_pair_is_a_real_pool":
                s["recorded_pair"] in {p["pool"] for p in d.get("pools") or []},
            # ⭐⭐ AND THE QUESTION THAT ACTUALLY MATTERS: was it the pool holding
            # the money? A bonding curve IS a real pool of the mint and it is
            # usually the address we recorded, so "is it a real pool" was the
            # wrong test - all three sellable tokens had a recorded pair that was
            # a real, existing, EMPTY curve while a PumpSwap pool held $360-440.
            "recorded_pair_quote_usd": next(
                (p.get("quote_usd") for p in d.get("pools") or []
                 if p["pool"] == s["recorded_pair"]), None),
            # ⚠️ Compared against the pools' OWN full-precision values, not against
            # `quote_usd_max`, which is rounded to 6 dp on the way out. A first
            # version compared a full-precision float to the rounded one and
            # reported the recorded pair as the wrong pool 61 of 61 times - a
            # rounding artifact, caught before it was published.
            "recorded_pair_is_the_deepest_pool":
                _is_deepest(s["recorded_pair"], d.get("pools") or []),
            "pool_state": d["pool_state"],
            "known_pair_absent": d.get("known_pair_absent"),
            "state_rule_version": "PRECOMMIT_pool_state.md v2 (§3a amendment)",
            "pool_state_measured_at": d["pool_state_measured_at"],
            "backfilled": True,
            "supersedes_earlier_row": bool((stale_before or only)
                                           and s["token"] in done),
            "backfill_note": ("measured TODAY, not at scoring time; a pool "
                              "drained after we scored it is indistinguishable "
                              "from one drained before"),
            "quote_usd_max": d["quote_usd_max"],
            "quote_unreadable_pools": d.get("quote_unreadable_pools"),
            "venues_one_sided": d.get("venues_one_sided"),
            "pool_count": d["pool_count"],
            "pools_existing": d.get("pools_existing"),
            "pools_absent": d.get("pools_absent"),
            "venues": d.get("venues"),
            "how_found": d.get("how_found"),
            # ⛔ compute and persist are two separate steps, and this repo has
            # lost five fields to exactly that gap. Everything the reader decided
            # with is written down: HOW the vaults were read, whose authority
            # they sit under, and what the authority guard threw away.
            "pools": [{"pool": p["pool"], "venue": p["venue"],
                       "how": p["how"], "exists": p.get("exists"),
                       "quote_usd": p.get("quote_usd"),
                       "quote_source": p.get("quote_source"),
                       "quote_unreadable_why": p.get("quote_unreadable_why"),
                       "vaults_via": p.get("vaults_via"),
                       "vault_authority": p.get("vault_authority"),
                       "struct_vaults_dropped": p.get("struct_vaults_dropped"),
                       "lamports_above_rent": p.get("lamports_above_rent"),
                       "pair_verified": p.get("pair_verified")}
                      for p in (d.get("pools") or [])],
            "rejected_non_pairs": d.get("rejected_non_pairs"),
            "pairs_unverifiable": d.get("pairs_unverifiable"),
            "venues_NOT_queryable": d.get("venues_NOT_queryable"),
            "sellable": None,
            "sellable_note": ("NOT measured here. The exit is "
                              "chainfields.round_trip() and only that."),
            "rule": "PRECOMMIT_pool_state.md",
            "sol_usd": px,
        }
        fh.write(json.dumps(row, sort_keys=True) + "\n")
        fh.flush()
        written += 1
        print("%3d/%d %-12s %-13s quote $%8.2f pools %2d(%2d live) %s"
              % (i, len(todo), (s["symbol"] or "")[:12], d["pool_state"],
                 d["quote_usd_max"], d["pool_count"],
                 d.get("pools_existing") or 0, d.get("how_found")))
        sys.stdout.flush()
    fh.close()

    # ---- tally over the WHOLE sidecar, LATEST ROW PER TOKEN
    # ⛔ The file is append-only, so a token re-measured under a corrected rule
    # has more than one row. `already_done()` keys on `token` and the later row
    # overwrites, so the tally is the newest measurement per contract and the
    # superseded rows stay on disk. Both counts are printed.
    seen_rows = 0
    for _ln in io.open(OUT, encoding="utf-8"):
        if _ln.strip():
            seen_rows += 1
    all_rows = list(already_done().values())
    print("\nsidecar holds %d rows for %d distinct contracts (%d superseded by a "

          "later measurement, kept on disk)"
          % (seen_rows, len(all_rows), seen_rows - len(all_rows)))
    tally = {}
    for r in all_rows:
        tally[r["pool_state"]] = tally.get(r["pool_state"], 0) + 1
    n = len(all_rows)
    usable = n - tally.get("unreadable", 0)
    print("\n==== pool_state over %d backfilled contracts ====" % n)
    for st in poolstate.STATES:
        k = tally.get(st, 0)
        if not k:
            continue
        lo, hi = wilson(k, usable) if st != "unreadable" else (None, None)
        print("  %-13s %4d  %5.1f%%  %s"
              % (st, k, 100.0 * k / usable if usable else 0,
                 "[%s, %s]" % (lo, hi) if lo is not None else ""))
    # ⭐ the defect, measured two ways: the pair was not a pool of this mint at
    # all, versus the pair was a real pool that is not the one holding the money.
    # ⛔ recomputed from each row's OWN pool list, so the tally does not depend
    # on a stored boolean, and a row written by older code is still counted right.
    withm = [r for r in all_rows
             if _is_deepest(r.get("recorded_pair"), r.get("pools") or [])
             is not None]
    wrongpool = [r for r in withm
                 if not _is_deepest(r.get("recorded_pair"),
                                    r.get("pools") or [])]
    print("\n⭐⭐ of %d contracts with ANY quote side on chain, the pair we "
          "recorded was NOT the pool holding the most: %d (%.1f%%) %s"
          % (len(withm), len(wrongpool),
             100.0 * len(wrongpool) / len(withm) if withm else 0,
             wilson(len(wrongpool), len(withm))))
    bad_pair = sum(1 for r in all_rows if not r["recorded_pair_is_a_real_pool"])
    print("\n⛔ recorded pair was NOT one of the real pools: %d of %d (%.1f%%)"
          % (bad_pair, n, 100.0 * bad_pair / n if n else 0))
    print("   ⛔ `gone` claimed the pool was gone. pool_closed is the only "
          "state that means that: %d of %d." % (tally.get("pool_closed", 0), n))
    kp = sum(1 for r in all_rows if r.get("known_pair_absent") is not None)
    print("   ⚠️ rows where pool_closed was REACHABLE (a known pair to check): "
          "%d of %d. The rest could only reach not_found (§3a)." % (kp, n))
    # ⛔ rule 15: say WHAT the answer could not see, not only how much.
    one_sided = sorted({v for r in all_rows
                        for v in (r.get("venues_one_sided") or [])})
    never_asked = sorted({v for r in all_rows
                          for v in (r.get("venues_NOT_queryable") or [])})
    unread = sum(1 for r in all_rows if r.get("quote_unreadable_pools"))
    print("\n⚠️ venues NEVER ASKED (no measured offset): %s"
          % never_asked)
    print("⚠️ venues ONE-SIDED (a pool with our mint on the other side is "
          "invisible): %s" % one_sided)
    print("⚠️ contracts with at least one pool whose quote side could NOT be "
          "read: %d of %d" % (unread, len(all_rows)))
    viar = {}
    for r in all_rows:
        for p in r.get("pools") or []:
            if p.get("quote_usd") is not None:
                key = (p.get("vaults_via") or p.get("quote_source") or "?")
                viar[key] = viar.get(key, 0) + 1
    print("⭐ how each priced pool's quote side was read: %s" % viar)
    print("rpc: %d calls, %d errors, %d rate-limited, %.1fs"
          % (budget.calls, budget.errors, budget.rate_limited,
             time.time() - t0))
    print("wrote %d rows to %s" % (written, OUT))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
