"""Volume integrity: the two methods that separated, under their pre-committed rule.

BACKLOG B5. docs/VOLUME_INTEGRITY.md §2 measured five methods on n=4 tokens and
§3 PRE-COMMITTED this rule on 2026-09-17, before any validation run:

    VOLUME_SUSPECT if  dup_amount_share >= 0.50  or  multi_tx_slots >= 4 per 60 txns
    VOLUME_CLEAN   if  dup_amount_share <  0.25  and multi_tx_slots <= 1
    otherwise      VOLUME_UNKNOWN

  M1 dup_amount_share  share of the mint's balance deltas whose exact size (to 4
                       dp) was seen before in the sample. Bots loop a fixed size.
  M2 multi_tx_slots    slots holding more than one of the sampled transactions.

⛔ THIS IS THE 09-17 COMPUTATION, reproduced from the session that measured it,
so the thresholds mean what they meant: the mint's most recent signatures, the
first 60 parsed as jsonParsed, deltas from pre/post token balances. Two
corrections, both in the direction of saying less:
  1. transactions are requested at version 1. ~5% of the stream is v1 now
     (measured 2026-09-19) and the original dropped them silently;
  2. ⛔ NO OBSERVED TRADE IS UNKNOWN, NOT CLEAN. The original returned
     dup_amount_share = 0 when it saw no balance delta, and 0 < 0.25 reads
     CLEAN - a dead token with no trades would have been certified clean volume.
     Standing rule 5. Here it is None and the verdict is VOLUME_UNKNOWN.

⛔ NOT QUOTABLE UNTIL VALIDATED: n >= 30 tokens per arm, labelled independently
by chainfields.round_trip(), Wilson intervals, both ways (§3). validate() does
exactly that against the universe's own gate labels.

Cost: 1 + up to 60 RPC calls per token. A decision-point tool, never the scan
path. ⛔ The RPC URL carries the Helius key when one is set; it is never printed.

Run: python volintegrity.py <MINT> [<MINT> ...]
     python volintegrity.py --validate [per_arm]
"""
import collections
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

SAMPLE = 60           # §2: "measured on 60 parsed transactions per token"
SIG_LIMIT = 250
SUSPECT_DUP, CLEAN_DUP = 0.50, 0.25          # §3, pre-committed
SUSPECT_SLOTS, CLEAN_SLOTS = 4, 1            # §3, pre-committed
SEED = 20260919
CALLS = {"n": 0}


def rpc(method, params, tries=3):
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    for i in range(tries):
        CALLS["n"] += 1
        try:
            req = urllib.request.Request(config.helius_rpc(), data=body, headers={
                "Content-Type": "application/json", "User-Agent": "crypto-intel/1.0"})
            with urllib.request.urlopen(req, timeout=45) as f:
                d = json.loads(f.read())
        except Exception:
            time.sleep(1.2 * (i + 1))
            continue
        return None if "error" in d else d.get("result")
    return None


def verdict(dup, slots):
    """§3 exactly. None inputs can only ever make the answer less certain."""
    if (dup is not None and dup >= SUSPECT_DUP) or (slots is not None and slots >= SUSPECT_SLOTS):
        return "VOLUME_SUSPECT"
    if dup is not None and slots is not None and dup < CLEAN_DUP and slots <= CLEAN_SLOTS:
        return "VOLUME_CLEAN"
    return "VOLUME_UNKNOWN"


def profile_from(mint, txs):
    """M1/M2 from already-fetched jsonParsed transactions. Pure - tested offline."""
    slots, amounts, parsed = collections.Counter(), collections.Counter(), 0
    amounts_tx = collections.Counter()      # M1', §3b: one size per transfer
    for tx in txs:
        if not tx:
            continue
        parsed += 1
        slots[tx.get("slot")] += 1
        meta = tx.get("meta") or {}
        pre = {b.get("accountIndex"): b for b in (meta.get("preTokenBalances") or [])}
        in_tx = set()
        for b in meta.get("postTokenBalances") or []:
            if b.get("mint") != mint:
                continue
            p = pre.get(b.get("accountIndex")) or {}
            try:
                d = abs(float((b.get("uiTokenAmount") or {}).get("uiAmount") or 0)
                        - float((p.get("uiTokenAmount") or {}).get("uiAmount") or 0))
            except (TypeError, ValueError):
                d = 0
            if d > 0:
                amounts[round(d, 4)] += 1
                in_tx.add(round(d, 4))
        for d in in_tx:
            amounts_tx[d] += 1
    n_amt = sum(amounts.values())
    dup = (sum(c for c in amounts.values() if c > 1) / n_amt) if n_amt else None
    n_tx = sum(amounts_tx.values())
    dup_tx = (sum(c for c in amounts_tx.values() if c > 1) / n_tx) if n_tx else None
    multi = sum(1 for v in slots.values() if v > 1) if parsed else None
    return {"mint": mint, "parsed": parsed, "deltas": n_amt, "distinct_amounts": len(amounts),
            "dup_amount_share": None if dup is None else round(dup, 4),
            "multi_tx_slots": multi, "verdict": verdict(dup, multi),
            # §3b, pre-committed 2026-09-19: the two legs of one transfer collapsed
            "dup_amount_share_tx": None if dup_tx is None else round(dup_tx, 4),
            "verdict_v2": verdict(dup_tx, multi)}


def measure(mint, gap=0.11):
    sigs = rpc("getSignaturesForAddress", [mint, {"limit": SIG_LIMIT}])
    if sigs is None:
        return {"mint": mint, "error": "signatures unreadable", "verdict": "VOLUME_UNKNOWN",
                "verdict_v2": "VOLUME_UNKNOWN"}
    txs = []
    for s in sigs[:SAMPLE]:
        txs.append(rpc("getTransaction", [s["signature"], {"maxSupportedTransactionVersion": 1,
                                                          "encoding": "jsonParsed"}]))
        time.sleep(gap)
    out = profile_from(mint, txs)
    out.update(n_sigs=len(sigs), fetch_failed=sum(1 for t in txs if not t), ts=int(time.time()))
    ts = [s["blockTime"] for s in sigs[:SAMPLE] if s.get("blockTime")]
    out["sample_span_h"] = round((max(ts) - min(ts)) / 3600, 2) if len(ts) > 1 else None
    return out


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return (round((c - a) / d, 4), round((c + a) / d, 4))


def validate(per_arm=30, members_path=None, out_path=None):
    """§3's validation, labelled by the universe gate's own round-trip verdicts:
    TRADEABLE members vs tokens refused at the gate. Seeded, both ways."""
    members_path = members_path or os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                                "data", "universe", "members.json")
    with open(members_path, encoding="utf-8") as f:
        T = json.load(f)["tokens"]
    arms = {
        "TRADEABLE": sorted(m for m, e in T.items() if e.get("status") == "member"
                            and (e.get("gate") or {}).get("verdict") == "TRADEABLE"
                            and e.get("class") == "token"),
        "NOT_TRADEABLE": sorted(m for m, e in T.items() if e.get("status") == "refused"),
    }
    rng = random.Random(SEED)
    rows = []
    for arm, pool in arms.items():
        for m in rng.sample(pool, min(per_arm, len(pool))):
            r = measure(m)
            r["arm"] = arm
            r["gate_verdict"] = (T[m].get("gate") or {}).get("verdict")
            rows.append(r)
            print(f"  {arm:14} {m[:8]}… parsed {r.get('parsed')!s:>3} dup {r.get('dup_amount_share')!s:>6} "
                  f"dup_tx {r.get('dup_amount_share_tx')!s:>6} slots {r.get('multi_tx_slots')!s:>3} "
                  f"-> {r['verdict']} / v2 {r['verdict_v2']}", flush=True)
    rep = {"per_arm": per_arm, "arms": {}, "rows": rows,
           "rule": "docs/VOLUME_INTEGRITY.md section 3 (2026-09-17) and 3b (2026-09-19), both pre-committed"}
    for arm in arms:
        for key in ("verdict", "verdict_v2"):
            rs = [r for r in rows if r["arm"] == arm]
            n = len(rs)
            c = collections.Counter(r[key] for r in rs)
            known = [r for r in rs if r[key] != "VOLUME_UNKNOWN"]
            rep["arms"][f"{arm}.{key}"] = {
                "n": n, "verdicts": dict(c),
                # both ways: over everything sampled, and over the ones with a verdict
                "suspect_rate_all": (round(c["VOLUME_SUSPECT"] / n, 4) if n else None),
                "suspect_wilson_all": wilson(c["VOLUME_SUSPECT"], n),
                "suspect_rate_known": (round(c["VOLUME_SUSPECT"] / len(known), 4) if known else None),
                "suspect_wilson_known": wilson(c["VOLUME_SUSPECT"], len(known)),
                "n_known": len(known)}
    if out_path:
        with open(out_path, "w", encoding="utf-8") as f:
            json.dump(rep, f, indent=1)
    return rep


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    if "--validate" in sys.argv:
        i = sys.argv.index("--validate")
        n = int(sys.argv[i + 1]) if len(sys.argv) > i + 1 else 30
        rep = validate(n)
        print(json.dumps(rep["arms"], indent=1))
    else:
        for m in sys.argv[1:]:
            print(json.dumps(measure(m), indent=1))
