"""RULE_V2: v1 with the score band deleted, and nothing else altered.

Runs in PARALLEL with v1 over the same observation stream - same market, same
hours, two filters. Sequential would have confounded the filter change with the
market change, since a fortnight of this market is not comparable to the next.

v1 stays pinned. This module never writes to v1's ledger, never reads its
constants for its own decisions, and shares only the hash-chain primitives.

THE COMPARISON, and it is easy to get wrong: v1's entry set is a SUBSET of v2's,
because v2 is v1 minus a filter. So v1-vs-v2 compares a set to its own superset
and the overlap drags the two together. The question is whether the tokens the
score was REJECTING are worse than the ones it was accepting, so every entry
records `also_qualifies_v1` and the arms are:

    A = qualifies under BOTH    (the score accepted these)
    B = qualifies under v2 ONLY (the score rejected these)

Read at n >= 30 distinct tokens per arm, Wilson intervals, per
PRECOMMIT_rule_v2.md.

Run: python paperv2.py            (status)
     python paperv2.py --verify   (chain)
"""
import datetime as dt
import json
import os
import sys

import paper

EPOCH = "2026-09-10"
LOG_DIR = paper.LOG_DIR
LEDGER = os.path.join(LOG_DIR, "ledger_v2.jsonl")

# Every fraud constant is v1's, by value, so a v1 change cannot silently drag
# v2 with it - and PINNED_GATE_V2 below catches it if one tries.
MIN_EXIT_DEPTH = 1000.0
TARGET_MULT = 2.0
MAX_HOLD_H = 24.0
NOTIONAL_USD = 100.0
MIN_N = 30

PINNED_GATE_V2 = {"MIN_EXIT_DEPTH": 1000.0, "TARGET_MULT": 2.0,
                  "MAX_HOLD_H": 24.0, "NOTIONAL_USD": 100.0, "MIN_N": 30,
                  "SCORE_LO": None, "SCORE_HI": None}


def gate_drift():
    """Any movement in the pinned constants refuses every entry, as in v1."""
    live = {"MIN_EXIT_DEPTH": MIN_EXIT_DEPTH, "TARGET_MULT": TARGET_MULT,
            "MAX_HOLD_H": MAX_HOLD_H, "NOTIONAL_USD": NOTIONAL_USD,
            "MIN_N": MIN_N, "SCORE_LO": None, "SCORE_HI": None}
    return [(k, PINNED_GATE_V2[k], live[k]) for k in PINNED_GATE_V2
            if live[k] != PINNED_GATE_V2[k]]


def qualifies(row):
    """RULE_V2. Identical to v1 except that no score is consulted, ever.

    Reads only fields captured at observation time. Nothing here may consult a
    later price, liquidity, or outcome.
    """
    drift = gate_drift()
    if drift:
        return False, ("RULE_V2 GATE HAS DRIFTED - refusing to enter: "
                       + "; ".join(f"{k} pinned {p} but is {a}" for k, p, a in drift))
    if (row.get("venue_type") or "") != "amm":
        return False, f"venue={row.get('venue_type') or 'unknown'}, not amm"
    depth = row.get("exit_depth_usd")
    if depth is None:
        return False, "no exit depth measured"
    if float(depth) < MIN_EXIT_DEPTH:
        return False, f"exit depth ${float(depth):,.0f} < ${MIN_EXIT_DEPTH:,.0f}"
    # Unknown authority fails closed, exactly as in v1. Removing the score does
    # not remove the requirement to have LOOKED - it removes the thing that was
    # preventing the look.
    if row.get("can_mint") is None or row.get("can_freeze") is None:
        why = "mint/freeze authority unknown"
        if row.get("authorities_error"):
            why += " (" + str(row.get("authorities_error")) + ")"
        if row.get("authorities_skipped"):
            why += " [never attempted: " + str(row.get("authorities_skipped")) + "]"
        return False, why + " - not entering on an unverified contract"
    if row.get("can_mint"):
        return False, "mint authority live - deployer can print supply"
    if row.get("can_freeze"):
        return False, "freeze authority live - deployer can stop you selling"
    sells, buys = row.get("sells_h1"), row.get("buys_h1")
    if sells is not None and buys is not None and sells == 0 and buys >= 10:
        return False, f"no sell side: {buys} buys, 0 sells - price never tested"
    return True, "qualifies under RULE_V2"


LABELS = {
    "A": "qualified under BOTH - the score accepted these (70-99)",
    "B_high": "v2 only - v1 rejected for scoring 100, ABOVE its band",
    "B_low": "v2 only - v1 rejected for scoring BELOW 70",
}


def _sub_arm(entry):
    """B_high / B_low, derived from the row if it predates the field.

    The 90 entries written on 2026-09-10/11 carry `score_at_entry` but not
    `sub_arm`, so the split is recoverable without re-entering anything and
    without rewriting an append-only ledger.
    """
    sa = entry.get("sub_arm")
    if sa:
        return sa
    if entry.get("arm") != "B":
        return None
    return "B_high" if (entry.get("score_at_entry") or 0) > 99 else "B_low"


def _read():
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                try:
                    out.append(json.loads(line))
                except ValueError:
                    continue
    return out


# --------------------------------------------------------------------------
# ⛔ QUARANTINED 2026-09-17 — see PRECOMMIT_paper_v3.md section 2.
#
# RULE_V2 changed the FILTER, not the pricing. Its fills come from the same
# Dexscreener mid as v1, so the A/B it was built to answer sits on top of
# fictional exits and cannot be read. Frozen, not deleted, not merged into v3.
# --------------------------------------------------------------------------
QUARANTINED = True
QUARANTINE_REASON = ("RULE_V2 fills are priced on the same mid as v1; the "
                     "filter A/B is unreadable on fictional exits. Use paperv3.")


QUARANTINED_PATHS = {os.path.abspath(LEDGER)}


def frozen():
    """True when this ledger refuses writes. Callers skip; they do not crash.

    The quarantine must not turn the collector's paper stage into a stack trace
    on every row. It did exactly that on the first scheduled pass - one
    RuntimeError per candidate, caught and printed, which is noise pretending to
    be a failure. A frozen ledger is a STATE, and the honest response to it is to
    skip with a reason, once.
    """
    if os.environ.get("CRYPTO_PAPER_UNFREEZE") == "1":
        return False
    return bool(QUARANTINED) and os.path.abspath(LEDGER) in QUARANTINED_PATHS


def _refuse_if_quarantined():
    """Freeze the FILE, not the module - see paper._refuse_if_quarantined."""
    if os.environ.get("CRYPTO_PAPER_UNFREEZE") == "1":
        return
    if QUARANTINED and os.path.abspath(LEDGER) in QUARANTINED_PATHS:
        raise RuntimeError("%s is QUARANTINED and refuses appends: %s"
                           % (LEDGER, QUARANTINE_REASON))



def _append(rec):
    """Append one record to the V2 chain. The only writer in this module."""
    _refuse_if_quarantined()
    os.makedirs(LOG_DIR, exist_ok=True)
    rows = _read()
    rec["prev"] = rows[-1].get("hash") if rows else None
    rec["seq"] = len(rows)
    rec["hash"] = paper._hash(rec)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def open_positions():
    rows = _read()
    closed = {r.get("entry_id") for r in rows if r.get("type") == "exit"}
    return [r for r in rows if r.get("type") == "entry" and r.get("hash") not in closed]


def has_open(contract):
    return any(r.get("contract") == contract for r in open_positions())


def open_entry(row):
    """Enter one observation into the v2 ledger, recording which arm it is in."""
    if frozen():
        return (None, "frozen")
    ok, why = qualifies(row)
    if not ok:
        return None, why
    contract = row.get("token") or row.get("addr")
    if not contract:
        return None, "no contract address"
    if has_open(contract):
        return None, "already open"
    v1_ok, v1_why = paper.qualifies(row)
    rec = {
        "type": "entry", "rule": "v2", "epoch": EPOCH,
        "contract": contract, "symbol": row.get("symbol") or row.get("name"),
        "entry_price_usd": row.get("price_usd"),
        "exit_depth_usd": row.get("exit_depth_usd"),
        "liq": row.get("liq"), "fdv": row.get("fdv"),
        "venue_type": row.get("venue_type"), "dex_id": row.get("dex_id"),
        "pair": row.get("pair"),
        # Recorded at ENTRY so the two arms stay separable forever without
        # re-deriving v1's rule against a row we may later reshape.
        "also_qualifies_v1": bool(v1_ok),
        "v1_reason": None if v1_ok else v1_why,
        "arm": "A" if v1_ok else "B",
        # ARM B IS HETEROGENEOUS AND MUST BE SPLIT. v1 rejects a token either
        # for scoring BELOW the 70-99 band or for scoring exactly 100, which is
        # ABOVE it - and post-epoch those are opposite ends of the outcome
        # distribution, not one population:
        #     0-44   0.09% [0.03, 0.28]  lift 0.40x
        #     45-69  0.17% [0.07, 0.43]  lift 0.71x
        #     70-99  1.37% [0.24, 7.36]  lift 5.82x
        #     100    1.95% [0.90, 4.20]  lift 8.31x   <- the best bucket
        # Pooling them would average the best band with the worst and report a
        # number describing neither. Recorded at entry, from the score only.
        "sub_arm": (None if v1_ok else
                    "B_high" if (row.get("score") or 0) > 99 else "B_low"),
        # Kept as an observed FACT, never as an input to the decision.
        "score_at_entry": row.get("score"),
        "target_mult": TARGET_MULT, "max_hold_h": MAX_HOLD_H,
        "notional_usd": NOTIONAL_USD,
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    return _append(rec), "entered"


def close_entry(entry, price, depth, code, detail, elapsed_h):
    """Append a v2 exit. Mirrors v1's record shape so the two are comparable."""
    if frozen():
        return None
    ep = entry.get("entry_price_usd")
    mult = (price / ep) if (price and ep) else None
    return _append({
        "type": "exit", "rule": "v2", "entry_id": entry["hash"],
        "contract": entry.get("contract"), "symbol": entry.get("symbol"),
        "arm": entry.get("arm"),
        "exit_price_usd": price, "exit_depth_usd": depth,
        "mult": mult, "reason": code, "detail": detail,
        "elapsed_h": round(elapsed_h, 4),
        "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    })


def sweep(fetch_pair, verbose=True, should_stop=None):
    """Close every open v2 position, on EXACTLY v1's decision logic.

    `should_stop` has the same contract as in paper.sweep: a position not
    reached before the stage budget stays open and is counted as deferred.

    Calls paper.close_decision so the two ledgers cannot diverge in how they
    close. If they diverged, the comparison would be measuring the closer
    rather than the filter, and the divergence would be invisible - two
    plausible numbers that were never computed the same way.
    """
    if frozen():
        return (0, 0)
    now = dt.datetime.now(dt.timezone.utc)
    stats = {"checked": 0, "closed": 0, "target": 0, "expiry": 0,
             "unpriceable": 0, "still_open": 0, "deferred": 0}
    for e in open_positions():
        if should_stop is not None and should_stop():
            stats["deferred"] += 1
            continue
        stats["checked"] += 1
        try:
            t0 = dt.datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
            elapsed_h = (now - t0).total_seconds() / 3600.0
        except Exception:
            elapsed_h = 0.0
        pa = e.get("pair")
        if not pa:
            # We do not know the pool, so we know nothing. Never spend an
            # irreversible close on a failure to read our own ledger.
            stats["still_open"] += 1
            continue
        try:
            pair = fetch_pair("solana", pa)
        except Exception as err:
            # A fetch that RAISED is a failed lookup, not a delisted pool.
            # Only a lookup that SUCCEEDED and returned nothing is evidence
            # of absence.
            if verbose:
                print(f"  [v2] {e.get('symbol')} left open - fetch failed: "
                      f"{type(err).__name__}")
            stats["still_open"] += 1
            continue
        action, px, depth, code, detail = paper.close_decision(
            e, pair, elapsed_h, target_mult=TARGET_MULT,
            min_depth=MIN_EXIT_DEPTH, max_hold_h=MAX_HOLD_H)
        if action == "hold":
            stats["still_open"] += 1
            continue
        close_entry(e, px, depth, code, detail, elapsed_h)
        stats["closed"] += 1
        stats["unpriceable" if action == "unpriceable" else action] += 1
        if verbose:
            print(f"  [v2/{e.get('arm')}] CLOSED {e.get('symbol')} {action} "
                  f"after {elapsed_h:.1f}h - {detail[:60]}")
    if verbose and stats["checked"]:
        print(f"  [v2] {stats['checked']} open checked, {stats['closed']} closed "
              f"({stats['target']} target, {stats['expiry']} expiry, "
              f"{stats['unpriceable']} unpriceable), {stats['still_open']} still open")
    if stats["deferred"]:
        print(f"  [v2] {stats['deferred']} open positions NOT checked - stage budget "
              f"reached; they stay open and the next sweep reaches them")
    return stats


def verify():
    rows = _read()
    if not rows:
        return True, 0, "empty"
    forks = 0
    for i, r in enumerate(rows):
        body = {k: v for k, v in r.items() if k != "hash"}
        if paper._hash(body) != r.get("hash"):
            return False, i, f"row {i} hash does not match its content - edited in place"
        if i and r.get("prev") != rows[i - 1].get("hash"):
            forks += 1
    return True, len(rows), (f"{len(rows)} rows, {forks} concurrent-writer FORKED"
                             if forks else f"{len(rows)} rows, chain intact")


def summary():
    """Both arms, separately. Never a pooled number - the pool is meaningless."""
    rows = _read()
    entries = [r for r in rows if r.get("type") == "entry"]
    exits = {r.get("entry_id"): r for r in rows if r.get("type") == "exit"}
    out = {"rule": "v2", "epoch": EPOCH, "entries": len(entries),
           "closed": len(exits), "open": len(entries) - len(exits), "arms": {}}
    for arm in ("A", "B_high", "B_low"):
        if arm == "A":
            ents = [e for e in entries if e.get("arm") == "A"]
        else:
            ents = [e for e in entries
                    if e.get("arm") == "B" and _sub_arm(e) == arm]
        mults = sorted(exits[e["hash"]]["mult"] for e in ents
                       if e["hash"] in exits and exits[e["hash"]].get("mult") is not None)
        tokens = {e.get("contract") for e in ents}
        # CLOSED distinct tokens, which is what the rate is actually computed
        # over. Gating on ENTERED tokens printed "100.00%" on two closes out of
        # 75 entries - the hit-rate leak this project has had twice before, and
        # PRECOMMIT_rule_v2.md says "n >= 30 CLOSED distinct tokens per arm".
        # An entry is not an outcome.
        closed_tokens = {e.get("contract") for e in ents
                         if e["hash"] in exits
                         and exits[e["hash"]].get("mult") is not None}
        n = len(mults)
        # THE GATE, as v1 applies it. A multiple on a pool with no exit depth is
        # a price on a corpse - the Grogu shape - and v1's summary has refused
        # to count one since 2026-09-08. This summary did not: GAY and MARIO
        # (arm A) and SOL GRND, POLLY and a CJK token (B_high) printed >=2x at
        # expiry on $0 of depth and were counted, turning B_high's 4 gated wins
        # into "7 wins, 14.89%". Price-only is kept, beside it, never instead.
        def _gated(x):
            d = x.get("exit_depth_usd")
            return d is not None and d >= MIN_EXIT_DEPTH
        closed_rows = [exits[e["hash"]] for e in ents
                       if e["hash"] in exits and exits[e["hash"]].get("mult") is not None]
        wins = [x["mult"] for x in closed_rows if x["mult"] >= TARGET_MULT and _gated(x)]
        wins_price_only = [m for m in mults if m >= TARGET_MULT]
        a = {"label": LABELS[arm],
             "entries": len(ents), "distinct_tokens": len(tokens),
             "closed_priceable": n, "wins": len(wins), "min_n": MIN_N,
             "wins_price_only": len(wins_price_only),
             "wins_unexitable": len(wins_price_only) - len(wins),
             "closed_tokens": len(closed_tokens),
             "conclusive": len(closed_tokens) >= MIN_N}
        if n:
            a["median_mult"] = mults[n // 2] if n % 2 else (mults[n // 2 - 1] + mults[n // 2]) / 2
            a["max_mult"] = mults[-1]
        a["rate"] = (f"{100.0 * len(wins) / n:.2f}%" if a["conclusive"] and n
                     else f"WITHHELD - {len(closed_tokens)} CLOSED tokens "
                          f"({len(tokens)} entered), need {MIN_N}")
        out["arms"][arm] = a
    return out


if __name__ == "__main__":
    if "--verify" in sys.argv:
        ok, n, msg = verify()
        print(f"  {'OK' if ok else 'FAIL'}  {msg}")
        sys.exit(0 if ok else 1)
    s = summary()
    print(f"RULE_V2  epoch {s['epoch']}  ledger {LEDGER}")
    print(f"  drift: {gate_drift() or 'none - pinned'}")
    print(f"  {s['entries']} entries, {s['closed']} closed, {s['open']} open")
    for arm, a in s["arms"].items():
        print(f"\n  ARM {arm}: {a['label']}")
        print(f"    {a['entries']} entries, {a['distinct_tokens']} distinct tokens, "
              f"{a['closed_priceable']} priceable closes")
        print(f"    >={TARGET_MULT}x: {a['wins']}   {a['rate']}")
