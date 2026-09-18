"""PAPER v3 - a ledger where every fill is a quote somebody could have taken.

⛔ THE RULES ARE FROZEN IN `PRECOMMIT_paper_v3.md`, WHICH WAS COMMITTED BEFORE
THIS FILE EXISTED. Nothing here may loosen them. Changing one means v4 and a new
ledger; `gate_drift()` refuses every entry if a constant has moved.

WHY v1 AND v2 ARE WORTHLESS, in one line of their own code:

    "notional_usd": NOTIONAL_USD,             # recorded on every entry
    mult = price / entry["entry_price_usd"]   # and never used

The multiple was a mid-to-mid price ratio with ZERO price impact. Size was
recorded and ignored. ⭐ So a "win" was a price nobody could have obtained at any
size - the exits were fictional, not merely optimistic, which is why 0 of the
all-time wins survive an exit-integrity check. Measured scale of the gap: across
18 random contracts, stored liquidity claimed $7,467,996,005 against $1.68
actually recoverable at a $100 probe (docs/LIQUIDITY.md section 12).

WHAT CHANGES HERE, and it is only one thing that matters:

    ENTRY   chainfields.round_trip(mint, 100) -> the raw token quantity $100
            actually buys, at impact. That quantity IS the position.
    EXIT    chainfields.sell_quote(mint, that_exact_quantity) -> USD back.
            realizable_multiple = usd_out / usd_in

⛔ NO MID PRICE APPEARS ANYWHERE IN THE P&L. A fill that cannot be quoted is not
a fill: if no route exists at exit the position closes at $0 recovered and is
recorded as a TOTAL LOSS, never skipped and never voided.

⭐ THE THIRD EXIT CONDITION IS THE WHOLE POINT. v1 had no way to notice that an
exit had stopped existing. v3 closes the moment round_trip returns TOTAL_LOSS,
NO_SELL_ROUTE or NO_BUY_ROUTE, and records the loss.

⚠️ THIS IS A SIMULATION. It sizes nothing, sends nothing and signs nothing. No
wallet is involved, no key with write scope is used, and both legs of every fill
are QUOTES. Frank has no realized P&L and this file does not create one.

⛔ IT ONLY COUNTS IF IT RUNS FORWARD FROM A FIXED EPOCH. Backfilling is
impossible by construction - round_trip() measures NOW and cannot reconstruct a
past exit. That is exactly why the record is credible and exactly why every hour
the collector is down is an hour that cannot be bought back.
"""
import datetime as dt
import json
import os

import chainfields
import liveness
import paper                      # for _hash only: one chain implementation

LOG_DIR = os.path.join("data", "paper")
LEDGER = os.path.join(LOG_DIR, "ledger_v3.jsonl")

EPOCH = "2026-09-17"

# ---------------------------------------------------------------------------
# PINNED_GATE_V3. Every value below is also read from the environment, so a
# workflow could otherwise widen the rule without touching Python. Drift refuses
# every entry - see gate_drift(). PRECOMMIT_paper_v3.md section 6.
# ---------------------------------------------------------------------------
NOTIONAL_USD = float(os.environ.get("CRYPTO_V3_NOTIONAL", "100"))
TARGET_MULT = float(os.environ.get("CRYPTO_V3_TARGET", "2.0"))
MAX_HOLD_H = float(os.environ.get("CRYPTO_V3_MAX_HOLD_H", "24"))
MIN_HOLDERS = int(os.environ.get("CRYPTO_V3_MIN_HOLDERS", "100"))
ENTRY_VERDICT = "TRADEABLE"
MIN_N = int(os.environ.get("CRYPTO_V3_MIN_N", "30"))

# $100 is traded. $250 and $500 are QUOTED AND RECORDED, never traded, so the
# depth cliff is captured as it was at the moment of the trade rather than
# remembered. The reason, measured (docs/LIQUIDITY.md section 10):
#     sym        $10      $100         $500
#     ROCK     8.28%     8.51%        9.51%
#     WOFI     3.46%    11.63%  NO_SELL_ROUTE
# ⭐ At $10 WOFI looks like the better token. At $500 it cannot be sold. A ledger
# recording one size cannot tell those apart, and the difference is the risk.
SIZES_RECORDED = (100, 250, 500)
SIZE_TRADED = 100

RULE_V3 = ("amm+TRADEABLE@100+no_mint+no_freeze+has_sell_side+holders>=100"
           "+holders_not_truncated")
EXIT_RULE_V3 = ("first of: realizable 2.0x on a live sell quote, 24h elapsed, "
                "or exit route degraded (TOTAL_LOSS/NO_SELL_ROUTE/NO_BUY_ROUTE)")

PINNED_GATE_V3 = {"NOTIONAL_USD": 100.0, "TARGET_MULT": 2.0, "MAX_HOLD_H": 24.0,
                  "MIN_HOLDERS": 100, "MIN_N": 30}

DEGRADED = ("TOTAL_LOSS", "NO_SELL_ROUTE", "NO_BUY_ROUTE")

# ⭐ THE TWO REFUSALS THAT MEAN "EVERYTHING CHEAPER PASSED, GO AND MEASURE".
#
# A caller escalates: run qualifies() for free, and only when it comes back with
# one of these spend the call it names. That keeps the gate in ONE place - the
# caller never re-implements a condition and so cannot drift from it - and stops
# us buying a holder count or a quote for a row that fails on something free.
#
# ⛔ They are exact strings, so test_paperv3.py asserts qualifies() actually
# returns them. A silently reworded reason would turn the escalation into a
# permanent no-op that enters nothing and looks like a quiet market.
NEEDS_HOLDERS = "holder count unknown - not entering on an unknown float"
NEEDS_QUOTE = "no round_trip measurement supplied"


def gate_drift():
    """[(name, pinned, actual)] for every constant that has moved. Empty = ok."""
    live = {"NOTIONAL_USD": NOTIONAL_USD, "TARGET_MULT": TARGET_MULT,
            "MAX_HOLD_H": MAX_HOLD_H, "MIN_HOLDERS": MIN_HOLDERS,
            "MIN_N": MIN_N}
    return [(k, v, live[k]) for k, v in PINNED_GATE_V3.items()
            if float(live[k]) != float(v)]


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _read():
    if not os.path.exists(LEDGER):
        return []
    out = []
    with open(LEDGER, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except ValueError:
                # Kept by position so chain indices still line up with the file.
                out.append({"_unparseable": line[:200]})
    return out


def _append(rec):
    """Append one record to the V3 chain. The ONLY writer in this module."""
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
    return [r for r in rows if r.get("type") == "entry"
            and r.get("hash") not in closed]


def has_open(contract):
    return any(r.get("contract") == contract for r in open_positions())


# ---------------------------------------------------------------------------
# THE ENTRY GATE. PRECOMMIT_paper_v3.md section 3, clause for clause.
#
# ⛔ NO SCORE APPEARS HERE AND NONE MAY EVER BE ADDED. The 70-99 band in v1
# rejected a token graded 100 on two intervals that overlap, measured on a
# population its own gate had hollowed out. `test_scoreband.py` walks this
# function at the AST level and fails if a score term reaches a branch.
# ---------------------------------------------------------------------------
def qualifies(row, rt=None):
    """Does this observation meet RULE_V3? Returns (bool, reason).

    `rt` lets a caller pass a round_trip() result it already has, so the
    decision costs no extra quotes. When it is None nothing is fetched here -
    the caller must supply it. ⭐ That keeps this function pure and testable, and
    keeps Jupiter off the per-row scan path (chainfields caps at 55/min).
    """
    drift = gate_drift()
    if drift:
        return False, ("V3 GATE HAS DRIFTED - refusing to enter: "
                       + "; ".join(f"{k} pinned {p} but is {a}"
                                   for k, p, a in drift))
    if (row.get("venue_type") or "") != "amm":
        return False, f"venue={row.get('venue_type') or 'unknown'}, not amm"

    # FAIL CLOSED ON UNKNOWN AUTHORITY. Until 2026-09-07 an absent lookup read
    # as None and PASSED - absence of evidence rendering as evidence of absence,
    # on the single most destructive fact about a token. A pool whose deployer
    # might freeze your sale is not one you enter because an RPC call timed out.
    if row.get("can_mint") is None or row.get("can_freeze") is None:
        return False, "mint/freeze authority unknown - not entering unverified"
    if row.get("can_mint"):
        return False, "mint authority live - deployer can print supply"
    if row.get("can_freeze"):
        return False, "freeze authority live - deployer can stop you selling"

    # A pool with buys and no sells has never had a counterparty. Ask whether
    # one has ever existed BEFORE asking how big any number is.
    sells, buys = row.get("sells_h1"), row.get("buys_h1")
    if sells is not None and buys is not None and sells == 0 and buys >= 10:
        return False, f"no sell side: {buys} buys, 0 sells - price never tested"

    # HOLDERS BEFORE THE QUOTE. ⚠️ The decision is identical either way - every
    # condition is required - but the ORDER decides what we pay for a refusal.
    # A round trip is two Jupiter quotes; a holder count is one Helius page. Ask
    # the cheaper question first, and never buy a quote for a row that fails on
    # the float. ⛔ This changes no threshold: PINNED_GATE_V3 is about values.
    #
    # The rule itself is an unvalidated candidate, pre-committed precisely so it
    # gets TESTED rather than tuned. If it is wrong, v3 fails and that is a
    # result. Median holders on our own past "winners" was 9; on
    # Jupiter-TRADEABLE contracts it is 1,350.
    h = row.get("holders")
    if h is None:
        return False, NEEDS_HOLDERS
    if row.get("holders_truncated"):
        return False, f"holder count truncated at {h} - a bound is not a count"
    if int(h) < MIN_HOLDERS:
        return False, f"{h} holders < {MIN_HOLDERS}"

    # ⭐ THE REALIZABLE CHECK. Not reported liquidity, which overstates by a
    # median 781x, and not a mid price. Can $100 round-trip for under 10% now?
    if not rt:
        return False, NEEDS_QUOTE
    if rt.get("verdict") != ENTRY_VERDICT:
        return False, (f"exit verdict {rt.get('verdict')}, need {ENTRY_VERDICT}"
                       + (f" ({rt.get('error')})" if rt.get("error") else ""))
    if not rt.get("token_qty_raw"):
        return False, "round_trip returned no token quantity - cannot size a fill"
    return True, "qualifies under RULE_V3"


def _shadow_quotes(mint, skip=SIZE_TRADED):
    """Round-trip cost at the sizes we record but never trade.

    ⚠️ Costs one round trip (two quotes) per size. Recorded so the depth cliff
    is measured AT THE MOMENT OF THE TRADE instead of remembered.
    """
    out = {}
    for usd in SIZES_RECORDED:
        if usd == skip:
            continue
        try:
            r = chainfields.round_trip(mint, usd)
            out[str(usd)] = {"verdict": r.get("verdict"),
                             "rt_cost_pct": r.get("rt_cost_pct"),
                             "usd_back": r.get("usd_back")}
        except Exception as e:
            # Unknown stays unknown. A failed shadow quote must never look like
            # a measured one, and must never block the real entry.
            out[str(usd)] = {"verdict": None, "rt_cost_pct": None,
                             "usd_back": None, "error": f"{type(e).__name__}"}
    return out


def open_entry(row, rt=None, shadows=True):
    """Enter one observation into the v3 ledger at a REAL quoted fill.

    Returns (record, reason). The record is None when nothing was entered, and
    the reason always says why - a refusal is information, not silence.
    """
    contract = row.get("token") or row.get("addr") or row.get("contract")
    if not contract:
        return None, "no contract address - never key on ticker"
    if has_open(contract):
        return None, "already open"
    if rt is None:
        rt = chainfields.round_trip(contract, NOTIONAL_USD)
    ok, why = qualifies(row, rt=rt)
    if not ok:
        return None, why

    qty = int(rt["token_qty_raw"])
    rec = _append({
        "type": "entry",
        "rule": RULE_V3,
        "exit_rule": EXIT_RULE_V3,        # DECLARED AT ENTRY, never at exit
        "epoch": EPOCH,
        "ts": _now(),
        "contract": contract,
        "pair": row.get("pair"),
        "symbol": row.get("symbol") or row.get("name"),
        # ⭐ THE FILL. Not a price - the money and the quantity.
        "usd_in": NOTIONAL_USD,
        "token_qty_raw": qty,
        "entry_price_impact_pct": rt.get("price_impact_pct"),
        "entry_rt_cost_pct": rt.get("rt_cost_pct"),
        "entry_verdict": rt.get("verdict"),
        "route_venues": rt.get("venues"),
        "quote_ts": rt.get("ts"),
        # Recorded as observed FACTS, never as inputs to the decision.
        "holders_at_entry": row.get("holders"),
        "venue_type": row.get("venue_type"),
        "dex_id": row.get("dex_id"),
        "shadow_quotes": _shadow_quotes(contract) if shadows else None,
        "target_mult": TARGET_MULT,
        "max_hold_h": MAX_HOLD_H,
        "sizes_recorded": list(SIZES_RECORDED),
        "size_traded": SIZE_TRADED,
    })
    liveness.beat("paperv3.open", detail=str(rec["contract"])[:24])
    return rec, "entered"


def _elapsed_h(entry, now=None):
    t0 = dt.datetime.strptime(entry["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc)
    now = now or dt.datetime.now(dt.timezone.utc)
    return (now - t0).total_seconds() / 3600.0


def close_entry(entry, sq=None, shadows=True, now=None, reason=None):
    """Close one open position against a live sell quote for the exact holding.

    ⛔ A position whose exit route has vanished closes at $0 RECOVERED and is
    recorded as a total loss. It is never skipped and never voided. The only
    `void` permitted anywhere in v3 is a RECORDING failure, which close_void()
    writes with its reason so it can be reported separately.
    """
    qty = int(entry["token_qty_raw"])
    if sq is None:
        sq = chainfields.sell_quote(entry["contract"], qty)

    usd_out = sq.get("usd_out")
    if usd_out is None:
        # ⭐ The condition v1 could not express. No route is an ANSWER.
        usd_out = 0.0
        exit_reason = "NO_SELL_ROUTE"
    else:
        exit_reason = None

    usd_in = float(entry["usd_in"])
    mult = usd_out / usd_in if usd_in else None
    elapsed = _elapsed_h(entry, now=now)

    if exit_reason is None:
        # ⛔ THE CALLER SAYS WHY, and only the two conditions this module can see
        # for itself are inferred. The first version labelled every other close
        # "DEGRADED", which is a claim about the pool - so a position closed for
        # any other reason carried a fabricated cause. A recorded reason that
        # was never observed is the same class of error as a fabricated fill.
        if mult is not None and mult >= TARGET_MULT:
            exit_reason = "TARGET"
        elif elapsed >= MAX_HOLD_H:
            exit_reason = "MAX_HOLD"
        elif reason:
            exit_reason = str(reason)
        else:
            exit_reason = "FORCED"      # closed by a caller that gave no cause

    rec = _append({
        "type": "exit",
        "entry_id": entry["hash"],
        "epoch": EPOCH,
        "ts": _now(),
        "contract": entry["contract"],
        "symbol": entry.get("symbol"),
        "usd_in": usd_in,
        "usd_out": round(usd_out, 6),
        # ⭐ THE ONLY P&L NUMBER IN THIS FILE, and it is a ratio of two real
        # quoted dollar amounts at a stated size. No mid price touches it.
        "realizable_multiple": round(mult, 6) if mult is not None else None,
        "token_qty_raw": qty,
        "exit_price_impact_pct": sq.get("price_impact_pct"),
        "exit_route_venues": sq.get("venues"),
        "exit_quote_ts": sq.get("ts"),
        "exit_quote_verdict": sq.get("verdict"),
        "exit_quote_error": sq.get("error"),
        "exit_reason": exit_reason,
        "elapsed_h": round(elapsed, 4),
        "on_time": elapsed <= MAX_HOLD_H + 1.0,
        "shadow_quotes": (_shadow_quotes(entry["contract"]) if shadows else None),
    })
    liveness.beat("paperv3.close", detail=f"{entry.get('symbol')} {exit_reason}")
    return rec


def close_void(entry, reason):
    """Record a RECORDING failure - the quote API was down at exit.

    ⛔ This is NOT a loss and NOT a win, and it is the only void v3 permits. It
    must be reported separately and never silently dropped from a denominator.
    A position whose exit route vanished is a LOSS, not a void - see
    close_entry().
    """
    return _append({
        "type": "exit", "void": True, "entry_id": entry["hash"],
        "epoch": EPOCH, "ts": _now(), "contract": entry["contract"],
        "symbol": entry.get("symbol"), "usd_in": float(entry["usd_in"]),
        "usd_out": None, "realizable_multiple": None,
        "exit_reason": "VOID_RECORDING_FAILURE", "void_reason": str(reason)[:300],
        "elapsed_h": round(_elapsed_h(entry), 4),
    })


def should_close(entry, rt=None):
    """(bool, reason) - is this position due to close, without quoting an exit?

    Cheap pre-check for the sweep: elapsed time needs no call. The degraded and
    target conditions do need a quote, so `rt` is passed in when one is in hand.
    """
    if _elapsed_h(entry) >= MAX_HOLD_H:
        return True, "MAX_HOLD"
    if rt and rt.get("verdict") in DEGRADED:
        return True, "DEGRADED"
    return False, "open"


def sweep(verbose=True, should_stop=None, sell_quote=None):
    """Close every position that is due, against a live quote for the holding.

    ⛔ NOTHING SCHEDULED THIS MODULE UNTIL 2026-09-18. paperv3 had 71 passing
    tests, a pre-committed rule and a live hand-run entry, and `collect.py` did
    not call it - so the ledger recorded nothing automatically and the one asset
    with a route to being worth money was a thing you could run by hand. Passing
    tests are not evidence that something is in the system.

    ⭐ ONE QUOTE PER OPEN POSITION, and the same quote is reused for the close.
    `should_close()` answers MAX_HOLD for free; the target and the degraded route
    both need a live sell quote of the EXACT holding - not a $100 round trip,
    which says nothing about what this position is worth.

    `sell_quote` is an injection point so the offline suite can exercise this
    without touching the network. Returns a dict of counts; never raises.
    """
    sq_fn = sell_quote or chainfields.sell_quote
    out = {"checked": 0, "closed": 0, "deferred": 0, "errors": 0, "reasons": {}}
    # ⭐ Beat FIRST and with the count, so "the sweep ran" is recorded even on a
    # pass with nothing open - that is the difference between `stale` and a
    # quiet market, and n is the row count so an empty sweep cannot read as
    # health. See docs/ENGINEERING_DISCIPLINE.md rule B.
    liveness.beat("paperv3.sweep", len(open_positions()))
    for entry in open_positions():
        if should_stop and should_stop():
            # ⛔ Recorded, not silent - the caller reports it as a stage stop.
            out["deferred"] += 1
            continue
        out["checked"] += 1
        try:
            due, why = should_close(entry)
            sq = None
            if due:
                # ⛔ FETCH IT HERE, NOT IN close_entry. A MAX_HOLD close still
                # has to be priced, and close_entry would reach for
                # chainfields.sell_quote itself - straight past the injection
                # point this function advertises. An offline suite that silently
                # hits the network is a bug this project already paid for once
                # today; a parameter that only isolates SOME paths is the same
                # thing with a promise attached.
                sq = sq_fn(entry["contract"], int(entry["token_qty_raw"]))
            if not due:
                # The only way to know whether the target is hit or the route is
                # gone is to ask what the holding sells for, right now.
                sq = sq_fn(entry["contract"], int(entry["token_qty_raw"]))
                usd_out = sq.get("usd_out")
                if usd_out is None:
                    due, why = True, "NO_SELL_ROUTE"
                else:
                    usd_in = float(entry["usd_in"])
                    if usd_in and (usd_out / usd_in) >= TARGET_MULT:
                        due, why = True, "TARGET"
            if not due:
                continue
            rec = close_entry(entry, sq=sq, reason=why)
            out["closed"] += 1
            r = (rec or {}).get("exit_reason") or why
            out["reasons"][r] = out["reasons"].get(r, 0) + 1
            if verbose:
                print(f"  [v3] closed {entry.get('symbol')} "
                      f"{str(entry.get('contract'))[:12]} {r} at "
                      f"{rec.get('realizable_multiple')}x")
        except Exception as e:
            # ⛔ A recording failure is a VOID with a reason, never a skip that
            # leaves the position silently open for ever.
            out["errors"] += 1
            try:
                close_void(entry, f"sweep failed: {type(e).__name__}")
            except Exception:
                pass
            if verbose:
                print(f"  [v3] sweep error on {entry.get('symbol')}: "
                      f"{type(e).__name__}: {str(e)[:80]}")
    return out


def verify():
    """(ok, index, message) for the hash chain. Mirrors paper.verify()."""
    rows = _read()
    forked = 0
    for i, r in enumerate(rows):
        if "_unparseable" in r:
            return False, i, f"row {i} is not JSON"
        expect = rows[i - 1].get("hash") if i else None
        if r.get("prev") != expect:
            # A concurrent writer re-parenting is a FORK, not tampering. The
            # hosted runner and a local pass can both append; neither edited
            # anything. Tampering is a row whose own hash does not match.
            forked += 1
        if paper._hash(r) != r.get("hash"):
            return False, i, f"row {i} hash mismatch - EDITED IN PLACE"
    msg = f"{len(rows)} rows intact"
    if forked:
        msg += f" ({forked} FORKED - concurrent writers, nothing edited)"
    return True, None, msg


def summary():
    """Counts and, ONLY at n >= MIN_N distinct contracts, the headline number.

    ⛔ Below MIN_N this returns the counts and says "not enough data". That is
    pre-committed in PRECOMMIT_paper_v3.md section 7 and standing rule 7, and it
    is the whole reason this ledger is worth anything: the threshold was fixed
    before a single row existed, so it cannot be moved to meet a result.
    """
    rows = _read()
    entries = [r for r in rows if r.get("type") == "entry"]
    exits = [r for r in rows if r.get("type") == "exit" and not r.get("void")]
    voids = [r for r in rows if r.get("type") == "exit" and r.get("void")]
    mults = [r["realizable_multiple"] for r in exits
             if r.get("realizable_multiple") is not None]
    contracts = {r["contract"] for r in exits}
    out = {"epoch": EPOCH, "ledger": LEDGER, "rule": RULE_V3,
           "entries": len(entries), "closes": len(exits),
           "distinct_contracts_closed": len(contracts),
           "open": len(open_positions()), "voids": len(voids),
           "min_n": MIN_N, "gate_drift": gate_drift(),
           "total_losses": sum(1 for m in mults if m == 0.0),
           "no_route_exits": sum(1 for r in exits
                                 if r.get("exit_reason") == "NO_SELL_ROUTE")}
    if len(contracts) < MIN_N:
        out["verdict"] = (f"not enough data: {len(contracts)} distinct contracts "
                          f"closed, need {MIN_N}")
        out["median_realizable_multiple"] = None
        return out
    s = sorted(mults)
    n = len(s)
    out["median_realizable_multiple"] = (
        s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0)
    out["wins"] = sum(1 for m in mults if m >= TARGET_MULT)
    out["verdict"] = "reportable"
    return out


if __name__ == "__main__":
    import pprint
    pprint.pprint(summary())
    print(verify())
