"""Is a contract we called `gone` actually dead? Read the POOL ACCOUNT from chain.

Rule: ../../PRECOMMIT_gone_onchain.md, written before a single account was read.

⛔ WHY. `record_outcome` writes `gone` when TWO INDEXER LOOKUPS FAIL
(`journal.py:974`), which collapses four states into one word: the pool closed,
the pool is near zero, the indexer dropped it, or we read the wrong pool. The
all-pairs recheck could not separate them because **both arms asked the same
indexer**: 118 of 120 returned NO_PAIRS on both, so it measured "does Dexscreener
list this" and not "is this token dead". Frank caught it.

This asks the chain instead. Run: python analysis/gone_onchain/probe.py
"""
import glob
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import config  # noqa: E402

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}

# ⛔ PRE-COMMITTED in PRECOMMIT_gone_onchain.md before any read.
N_SAMPLE = 60
WINDOW_H = 72
UNUSABLE_SHARE_KILLS_RATE = 1.0 / 3.0

# Known AMM / launchpad program owners of a pool account. An account owned by
# something else was never a pool, which is a row-quality defect rather than a
# market event.
AMM_OWNERS = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium_v4",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "raydium_cpmm",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "raydium_clmm",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "meteora_dlmm",
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": "meteora_dynamic",
    "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN": "meteora_dbc",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "orca_whirlpool",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pumpfun_curve",
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": "openbook",
    "SoLFiHG9TfgtdUXUjWAxi3LtvYuFyDLVhBWxdMZxyCe": "solfi",
    "obriQD1zbpyLz95G5n7nJe6a4DPjpFwa5XYPoNm113y": "obric",
}


def rpc(method, params, timeout=40):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            config.helius_rpc(), data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": UA["User-Agent"]}), timeout=timeout)
        d = json.loads(r.read())
        return d.get("result"), d.get("error")
    except Exception as e:
        return None, "%s: %s" % (type(e).__name__, str(e)[:120])


def sample():
    """Newest-first distinct `gone` contracts in the window, with their pool."""
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
            if r.get("status") != "gone":
                continue
            ts = r.get("checked_ts") or r.get("ts") or 0
            if ts < cutoff:
                continue
            rows.append(r)
    rows.sort(key=lambda r: -(r.get("checked_ts") or r.get("ts") or 0))
    seen, out = set(), []
    for r in rows:
        tok = r.get("token")
        if not tok or tok in seen:
            continue
        seen.add(tok)
        out.append({"token": tok, "pool": r.get("pair"),
                    "symbol": r.get("symbol"),
                    "checked_ts": r.get("checked_ts") or r.get("ts"),
                    "mult": r.get("mult")})
        if len(out) >= N_SAMPLE:
            break
    return out, len(rows)


def verdict_for(pool):
    """POOL_ABSENT / POOL_EXISTS / NOT_A_POOL / UNREADABLE, per the pre-commit."""
    res, err = rpc("getAccountInfo", [pool, {"encoding": "base64"}])
    if err:
        return "UNREADABLE", {"why": str(err)[:140]}
    if res is None:
        return "UNREADABLE", {"why": "no result field in the RPC reply"}
    val = res.get("value")
    if val is None:
        return "POOL_ABSENT", {"why": "getAccountInfo returned null"}
    owner = val.get("owner")
    data = (val.get("data") or [None])[0] or ""
    info = {"owner": owner, "program": AMM_OWNERS.get(owner),
            "data_len_b64": len(data), "lamports": val.get("lamports")}
    if owner in AMM_OWNERS and data:
        return "POOL_EXISTS", info
    return "NOT_A_POOL", info


def wilson(k, n, z=1.96):
    if not n:
        return None, None
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return round((c - m) / d * 100, 1), round((c + m) / d * 100, 1)


def main():
    rows, n_rows = sample()
    print("PRECOMMIT_gone_onchain.md")
    print("window %dh, %d `gone` rows seen, %d distinct contracts sampled "
          "(cap %d)" % (WINDOW_H, n_rows, len(rows), N_SAMPLE))
    print()
    tally, results = {}, []
    no_pool = 0
    for i, r in enumerate(rows, 1):
        if not r["pool"]:
            # ⚠️ Counted and reported, never silently skipped: if we do not know
            # which pool we priced, that is a finding about the row.
            no_pool += 1
            v, info = "NO_POOL_RECORDED", {}
        else:
            v, info = verdict_for(r["pool"])
        tally[v] = tally.get(v, 0) + 1
        results.append(dict(r, verdict=v, **info))
        print("  %2d/%d %-12s %-44s %-16s %s"
              % (i, len(rows), str(r.get("symbol"))[:12], r["token"], v,
                 info.get("program") or info.get("why", "")[:40]))

    absent = tally.get("POOL_ABSENT", 0)
    exists = tally.get("POOL_EXISTS", 0)
    unusable = tally.get("UNREADABLE", 0) + tally.get("NOT_A_POOL", 0) + no_pool
    denom = absent + exists
    print()
    print("TALLY:", json.dumps(tally, sort_keys=True))
    share = (unusable / len(rows)) if rows else 0
    print("unusable (UNREADABLE + NOT_A_POOL + NO_POOL_RECORDED): %d of %d = %.1f%%"
          % (unusable, len(rows), share * 100))
    out = {"rule": "PRECOMMIT_gone_onchain.md",
           "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "window_h": WINDOW_H, "n_rows_seen": n_rows,
           "n_sampled": len(rows), "tally": tally,
           "unusable_share": round(share, 4), "results": results}
    if share > UNUSABLE_SHARE_KILLS_RATE:
        # ⛔ Pre-committed: past a third unusable, NO rate is published and the
        # finding is about our rows rather than about the market.
        out["headline"] = None
        out["headline_refused_why"] = (
            "%.1f%% of the sample was unusable, over the pre-committed one-third "
            "ceiling, so no rate is published. The finding is about our ROWS, "
            "not about the market." % (share * 100))
        print()
        print("⛔ NO RATE PUBLISHED:", out["headline_refused_why"])
    elif denom:
        lo, hi = wilson(absent, denom)
        out["headline"] = {"pool_absent": absent, "pool_exists": exists,
                           "n": denom, "pct": round(absent / denom * 100, 1),
                           "wilson": [lo, hi]}
        print()
        print("⭐ POOL ACTUALLY ABSENT: %d/%d = %.1f%% [%s, %s]"
              % (absent, denom, absent / denom * 100, lo, hi))
        print("⛔ POOL STILL ON CHAIN:  %d/%d = %.1f%%"
              % (exists, denom, exists / denom * 100))
    else:
        out["headline"] = None
        out["headline_refused_why"] = "no readable pool accounts in the sample"
        print()
        print("⛔ NO RATE: nothing readable")

    dest = os.path.join(HERE, "result.json")
    io.open(dest, "w", encoding="utf-8").write(json.dumps(out, indent=1))
    print("wrote", dest)


if __name__ == "__main__":
    main()
