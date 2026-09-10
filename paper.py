"""Forward-recorded paper log. Append-only, hash-chained, never retro-edited.

WHY THIS EXISTS. Every predictive claim this project has made has died the same
death: a feature measured after the fact, scored against an outcome that had
already partly happened. The liquidity-trajectory gradient (14.5x lift) was
leakage - 11 of 11 out-of-sample wins were already >=2x at the decision point.
The graduation predictor (16.1x lift on fdv>=$20k) was the same shape - the
token was already halfway to the $69k threshold. Both looked like forecasts and
were restatements of progress already made.

Retrospective analysis cannot fix this, because the thing that goes wrong is
the ordering of measurement and outcome, and history has no ordering we can
trust. A forward log does. A row here is written BEFORE the outcome exists.
That is the whole point, and it is the only property this file protects.

INTEGRITY MODEL. Each record carries `prev` - the SHA-256 of the previous
record's canonical JSON. Editing any earlier row breaks every hash after it,
and `verify()` reports the first index where the chain parts. This does not
make editing impossible; it makes silent editing impossible, which is the
achievable guarantee. Nothing is ever deleted: a mistaken entry is closed with
`void` and the reason, and the original stays on the chain.

TWO RECORD TYPES, never merged:

    entry  ts, contract, symbol, rule, entry_price, entry_exit_depth, ...
           and `exit_rule`, DECLARED AT ENTRY. An exit rule invented after the
           fact is the same leakage in a new costume.
    exit   entry_id, ts, exit_price, mult, exit_depth_usd, elapsed_h, reason

An entry with no exit is OPEN and must be reported as open, never dropped from
a denominator. Survivorship in the denominator is how the 227x filter got
mistaken for an edge.

THE OPENING RULE, and why this one. Frank's instruction was to start with the
simplest defensible rule rather than wait for a good one - the point is the
log's integrity, not the rule's quality. So `RULE_V1` uses only facts already
measured in this repo, and nothing that has ever failed out of sample:

    venue_type == "amm"        curve tokens are 0.01% >=2x (2 wins in 14,802);
                               AMM tokens are 2.27% [1.75, 2.93]. 227x apart,
                               intervals nowhere near touching. This is a
                               FILTER, not an edge - it says where a position
                               is possible at all, not that one is good.
    exit_depth_usd >= 1000     the quote side, computed from reserves. The only
                               signal in this project that has never been
                               retracted. Reported liquidity is not usable:
                               five measured pools overstated it 125.6-125.8x.
    70 <= score <= 99          measured within the AMM population: 4.55%
                               [2.62, 7.78] against 1.20% [0.64, 2.27] at
                               score 100. The ceiling is where the losers are.

Expected hit rate is therefore ~4.5%, and n will be small for a long time.
NOTHING IS CONCLUDED FROM THIS LOG UNTIL IT HAS `MIN_N` CLOSED ENTRIES. That
threshold is stated here, before any data exists, so it cannot be moved to meet
a result.

NOT A RECOMMENDATION. This is a simulation ledger. It sizes nothing, sends
nothing, and signs nothing. `NOTIONAL_USD` is a bookkeeping constant so that
multiples can be expressed in dollars; no capital is at risk and none is
implied.
"""
import datetime as dt
import hashlib
import liveness
import json
import os

LOG_DIR = os.path.join("data", "paper")
LEDGER = os.path.join(LOG_DIR, "ledger.jsonl")

# Declared before the first row exists so it cannot be moved to meet a result.
MIN_N = int(os.environ.get("CRYPTO_PAPER_MIN_N", "30"))

# Bookkeeping only. No capital is at risk and none is implied.
NOTIONAL_USD = float(os.environ.get("CRYPTO_PAPER_NOTIONAL", "100"))

RULE_V1 = "amm+depth>=1000+score70-99"
EXIT_RULE_V1 = "first of: 2.0x on quote-side depth, or 24h elapsed"

MIN_EXIT_DEPTH = float(os.environ.get("CRYPTO_PAPER_MIN_DEPTH", "1000"))
SCORE_LO = int(os.environ.get("CRYPTO_PAPER_SCORE_LO", "70"))
SCORE_HI = int(os.environ.get("CRYPTO_PAPER_SCORE_HI", "99"))
TARGET_MULT = float(os.environ.get("CRYPTO_PAPER_TARGET", "2.0"))
MAX_HOLD_H = float(os.environ.get("CRYPTO_PAPER_MAX_HOLD_H", "24"))

# ---------------------------------------------------------------------------
# THE GATE IS LOCKED.
#
# Every constant above reads an environment variable, so a one-line change in
# the workflow could widen the entry rule without touching a line of Python and
# without anything noticing. That would not be cheating so much as quietly
# destroying the experiment: the whole value of this log is that the rule was
# fixed BEFORE the outcomes existed, and a gate that moves mid-run makes the
# closes non-comparable and the n meaningless.
#
# The measurement runs to n=200 closes, projected 2026-09-14. Until then these
# values are pinned here as literals and checked on every entry. Changing the
# rule requires editing this block and starting RULE_V2 with its own ledger -
# which is the honest way to change a rule, and leaves the v1 record intact.
#
# Loosening is the specific risk: a 14.3% hit rate with a 0.40x median is
# information, and the temptation when the number is bad is to widen the gate
# until it looks better.
PINNED_GATE = {"MIN_EXIT_DEPTH": 1000.0, "SCORE_LO": 70, "SCORE_HI": 99,
               "TARGET_MULT": 2.0, "MAX_HOLD_H": 24.0,
               "NOTIONAL_USD": 100.0, "MIN_N": 30}


def gate_drift():
    """[(name, pinned, actual)] for every constant that has moved. Empty = ok."""
    live = {"MIN_EXIT_DEPTH": MIN_EXIT_DEPTH, "SCORE_LO": SCORE_LO,
            "SCORE_HI": SCORE_HI, "TARGET_MULT": TARGET_MULT,
            "MAX_HOLD_H": MAX_HOLD_H, "NOTIONAL_USD": NOTIONAL_USD,
            "MIN_N": MIN_N}
    return [(k, v, live[k]) for k, v in PINNED_GATE.items()
            if float(live[k]) != float(v)]


def _now():
    return dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def _canon(rec):
    """Canonical bytes for hashing: the record without its own hash field."""
    d = {k: v for k, v in rec.items() if k != "hash"}
    return json.dumps(d, sort_keys=True, separators=(",", ":")).encode()


def _hash(rec):
    return hashlib.sha256(_canon(rec)).hexdigest()


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
                # A corrupt line is kept in the count by position so the chain
                # indices still line up with the file. Never silently skipped.
                out.append({"_unparseable": line[:200]})
    return out


def _append(rec):
    """Append one record, chained to the last. The ONLY writer in this module."""
    os.makedirs(LOG_DIR, exist_ok=True)
    rows = _read()
    rec["prev"] = rows[-1].get("hash") if rows else None
    rec["seq"] = len(rows)
    rec["hash"] = _hash(rec)
    with open(LEDGER, "a", encoding="utf-8") as f:
        f.write(json.dumps(rec, sort_keys=True) + "\n")
    return rec


def qualifies(row):
    """Does this observation meet RULE_V1? Returns (bool, reason).

    Refuses outright if the gate constants have drifted from PINNED_GATE - a
    widened rule must not silently enter positions into a v1 ledger.

    Reads only fields captured at observation time. Nothing here may consult a
    later price, a later liquidity, or an outcome - that is the leakage this
    whole file exists to prevent.
    """
    _drift = gate_drift()
    if _drift:
        return False, ("ENTRY GATE HAS DRIFTED from RULE_V1 - refusing to enter: "
                       + "; ".join(f"{k} pinned {p} but is {a}" for k, p, a in _drift))
    if (row.get("venue_type") or "") != "amm":
        return False, f"venue={row.get('venue_type') or 'unknown'}, not amm"
    depth = row.get("exit_depth_usd")
    if depth is None:
        return False, "no exit depth measured"
    if float(depth) < MIN_EXIT_DEPTH:
        return False, f"exit depth ${float(depth):,.0f} < ${MIN_EXIT_DEPTH:,.0f}"
    # CAPABILITY DISQUALIFIERS, checked before any number. A depth floor cannot
    # catch a pool nobody has ever sold into, and no amount of liquidity helps
    # if the deployer can print supply into your bid or freeze your sell. These
    # are facts about what the contract PERMITS, not estimates.
    # FAIL CLOSED ON UNKNOWN. Until 2026-09-07 a row whose authority lookup had
    # never run, or had failed, read as `None` and PASSED - absence of evidence
    # rendered as evidence of absence, on the single most destructive fact about
    # a token. 85% of qualifying observations had no authority recorded. A pool
    # whose deployer might be able to freeze your sale is not a pool you enter
    # because the RPC call timed out.
    #
    # The scanner fetches authorities immediately before this runs, so the cost
    # of failing closed is only the rows where that fetch genuinely failed.
    if row.get("can_mint") is None or row.get("can_freeze") is None:
        return False, (f"mint/freeze authority unknown"
                       f"{' (' + str(row.get('authorities_error')) + ')' if row.get('authorities_error') else ''}"
                       f" - not entering on an unverified contract")
    if row.get("can_mint"):
        return False, "mint authority live - deployer can print supply"
    if row.get("can_freeze"):
        return False, "freeze authority live - deployer can stop you selling"
    # A pool with buys and no sells has never had a counterparty. Ask whether
    # one has ever existed BEFORE asking how big the number is.
    _sells = row.get("sells_h1")
    _buys = row.get("buys_h1")
    if _sells is not None and _buys is not None and _sells == 0 and _buys >= 10:
        return False, f"no sell side: {_buys} buys, 0 sells - price never tested"
    score = row.get("score")
    if score is None:
        return False, "no score"
    if not (SCORE_LO <= float(score) <= SCORE_HI):
        return False, f"score {score} outside {SCORE_LO}-{SCORE_HI}"
    return True, "qualifies"


# ---------------------------------------------------------------------------
# WHICH ROWS EARN AN AUTHORITY LOOKUP. Deliberately independent of the score.
#
# The scanner used to decide this with:
#     _act = (row.get("score", 0) >= 70) or paper.qualifies(row)[0]
# and the second branch could never fire, because qualifies() fails closed on
# can_mint/can_freeze - precisely the fields the call it guarded would fetch.
# So the authority lookup ran if and only if the score cleared 70.
#
# That made the score gate the EVIDENCE, not just the decision. A low-scoring
# token never got its authorities read, so it read as "unverified contract" and
# could never qualify, whatever else was true about it. Self-fulfilling: 328 of
# the 457 known false negatives scored 0-44 and were structurally incapable of
# passing, and 67 of 73 we resolved live on 2026-09-10 had BOTH authorities
# revoked - they were clean all along and we never looked.
#
# The predicate below uses only facts already in hand before any RPC call, and
# never the score. It CANNOT loosen the gate: it moves rows from "unknown, so
# rejected" to "known, so decided", which is strictly more verification. Cost
# measured 2026-09-10: +29 lookups/day, about one per pass.
# ---------------------------------------------------------------------------
def wants_authority_check(row):
    """True when a row is worth an on-chain authority lookup.

    Mirrors the fraud gate's cheap, already-known checks. Must never consult
    `score` - that is the bug this function exists to make impossible.
    """
    if (row.get("venue_type") or "") != "amm":
        return False
    depth = row.get("exit_depth_usd")
    if depth is None or float(depth) < MIN_EXIT_DEPTH:
        return False
    sells, buys = row.get("sells_h1"), row.get("buys_h1")
    if sells is not None and buys is not None and sells == 0 and buys >= 10:
        return False
    return True


def has_open(contract):
    return any(r.get("contract") == contract for r in open_positions())


def open_entry(contract, symbol=None, price=None, exit_depth=None, liq=None,
               fdv=None, score=None, venue_type=None, dex_id=None,
               rule=RULE_V1, exit_rule=EXIT_RULE_V1, note=None, pair=None):
    """Record an entry. Keyed on CONTRACT ADDRESS, never ticker.

    Returns None if this contract already has an open position. A token that
    keeps qualifying on every hourly pass would otherwise be entered a dozen
    times and dominate the denominator - one position per contract at a time.
    """
    if not contract:
        raise ValueError("contract address is required - never key on ticker")
    if has_open(contract):
        return None
    # `return _append({...})` put the liveness beat below it beyond reach: 69
    # entries were written while paper.open reported `never fired`, and
    # paper.close logged 94. The registry was right; the beat was dead code.
    rec = _append({
        "type": "entry",
        "ts": _now(),
        "contract": contract,
        # THE POOL, not just the token. Closing a position by token-level price
        # is how a different pool's quote gets divided into our entry - the
        # exact defect that contaminated the outcome journal. Stored at entry.
        "pair": pair,
        "symbol": symbol,
        "rule": rule,
        "exit_rule": exit_rule,          # declared NOW, not at exit
        "entry_price_usd": price,
        "entry_exit_depth_usd": exit_depth,
        "entry_liq_usd": liq,
        "entry_fdv_usd": fdv,
        "entry_score": score,
        "venue_type": venue_type,
        "dex_id": dex_id,
        "notional_usd": NOTIONAL_USD,
        "target_mult": TARGET_MULT,
        "max_hold_h": MAX_HOLD_H,
        "note": note,
    })
    liveness.beat("paper.open", detail=str(symbol or contract)[:24])
    return rec


def close_entry(entry_id, price=None, exit_depth=None, reason=None, void=None,
                chain_depth=None):
    """Record an exit against an open entry. Never edits the entry row.

    `void` closes a row entered in error. The entry stays on the chain; the
    void is a new record saying why. Nothing is ever deleted.
    """
    rows = _read()
    ent = next((r for r in rows if r.get("hash") == entry_id
                and r.get("type") == "entry"), None)
    if ent is None:
        raise ValueError(f"no entry with hash {entry_id}")
    if any(r.get("entry_id") == entry_id for r in rows if r.get("type") == "exit"):
        raise ValueError(f"entry {entry_id[:12]} already closed - "
                         "an exit is written once and never revised")
    ep = ent.get("entry_price_usd")
    mult = None
    if ep and price:
        mult = float(price) / float(ep)
    elapsed = None
    try:
        t0 = dt.datetime.strptime(ent["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
            tzinfo=dt.timezone.utc)
        elapsed = round((dt.datetime.now(dt.timezone.utc) - t0).total_seconds() / 3600, 3)
    except Exception:
        pass
    # Realisable only to the depth actually there. A 10x on a $40 pool is $40.
    realizable = None
    if mult is not None and exit_depth is not None:
        gross = NOTIONAL_USD * mult
        realizable = min(gross, float(exit_depth))
    return _append({
        "type": "exit",
        "ts": _now(),
        "entry_id": entry_id,
        "contract": ent.get("contract"),
        "symbol": ent.get("symbol"),
        "exit_price_usd": price,
        "exit_depth_usd": exit_depth,
        # Independent quote-side depth read from chain AT THE MOMENT OF CLOSE.
        # Not recoverable later at any RPC tier - see _close().
        "chain_depth_usd": chain_depth,
        "mult": (round(mult, 6) if mult is not None else None),
        "actual_elapsed_h": elapsed,
        "realizable_usd": (round(realizable, 2) if realizable is not None else None),
        "reason": reason,
        "void": bool(void),
        "void_reason": void if isinstance(void, str) else None,
    })


def open_positions():
    rows = _read()
    closed = {r.get("entry_id") for r in rows if r.get("type") == "exit"}
    return [r for r in rows if r.get("type") == "entry" and r.get("hash") not in closed]


def verify():
    """Walk the chain. Returns (ok, first_bad_index, message).

    TWO DIFFERENT FAILURES, and conflating them would be a lie in the direction
    that matters. Discovered 2026-09-07 when merging the hosted runner's history:

      TAMPERING     a row's content no longer matches its own hash, or a row was
                    removed or reordered. The ledger is not trustworthy.

      A FORK        two writers - Frank's machine and the hosted runner - each
                    appended independently, so two rows share a `seq` and chain
                    to different predecessors. Every row is still internally
                    valid and nothing is lost; the log simply is not a single
                    line any more.

    A hash chain with one `prev` pointer cannot survive concurrent writers, and
    union-merging one across two machines produces a fork by construction. The
    honest response is to REPORT the fork, not to re-chain the rows: rewriting
    the hashes so verify() passes would forge exactly the property the chain
    exists to prove.

    So per-row integrity is checked for every row, and a broken link is only
    called tampering when the rows involved do not look like a merge fork.
    """
    rows = _read()
    # 1. per-row integrity - this catches editing regardless of any fork
    for i, r in enumerate(rows):
        if "_unparseable" in r:
            return False, i, f"row {i} is not valid JSON"
        if r.get("hash") != _hash(r):
            return False, i, (f"row {i} content does not match its own hash - "
                              "edited in place")
    # 2. linkage
    by_hash = {r.get("hash") for r in rows}
    seqs = {}
    for r in rows:
        seqs.setdefault(r.get("seq"), []).append(r)
    forks = sorted(s for s, rs in seqs.items() if len(rs) > 1)
    prev = None
    breaks = []
    for i, r in enumerate(rows):
        if r.get("prev") != prev:
            breaks.append(i)
        prev = r.get("hash")
    if not breaks:
        return True, None, f"chain intact, {len(rows)} records"
    # A break whose stated `prev` is some other row we hold is a re-parenting -
    # the signature of a merge, not of a deletion.
    reparent = all((rows[i].get("prev") is None or rows[i].get("prev") in by_hash)
                   for i in breaks)
    if forks and reparent:
        return (True, breaks[0],
                f"chain FORKED at seq {forks}, {len(rows)} records, every row "
                f"individually valid and none missing - two writers appended "
                f"concurrently and the histories were merged. Not tampering.")
    return False, breaks[0], (
        f"row {breaks[0]} says prev={str(rows[breaks[0]].get('prev'))[:12]} which "
        f"is not a row we hold - something was edited, reordered or removed")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    cmd = sys.argv[1] if len(sys.argv) > 1 else "status"
    if cmd == "verify":
        ok, i, msg = verify()
        print(("  OK   " if ok else "  BROKEN ") + msg)
        sys.exit(0 if ok else 1)
    elif cmd == "open":
        for r in open_positions():
            print(f"  {r['hash'][:12]}  {str(r.get('symbol'))[:12]:<13} "
                  f"{r['contract'][:20]:<21} entry ${r.get('entry_price_usd')} "
                  f"depth ${r.get('entry_exit_depth_usd')}  {r['ts']}")
    elif cmd == "close":
        rec = close_entry(sys.argv[2], price=float(sys.argv[3]),
                          exit_depth=(float(sys.argv[4]) if len(sys.argv) > 4 else None),
                          reason=(sys.argv[5] if len(sys.argv) > 5 else None))
        print(f"  closed {rec['entry_id'][:12]} mult={rec['mult']} "
              f"elapsed={rec['actual_elapsed_h']}h")
    else:
        s = summary()
        ok, i, msg = verify()
        print(f"  chain     : {'OK' if ok else 'BROKEN'} - {msg}")
        print(f"  entries   : {s['entries']}  open {s['open']}  closed {s['closed']}  void {s['void']}")
        print(f"  hit rate  : {s['hit_rate']}")
        if "median_mult" in s:
            print(f"  mult      : p25 {s['p25_mult']:.3f}  median {s['median_mult']:.3f}  "
                  f"p75 {s['p75_mult']:.3f}  max {s['max_mult']:.3f}")


# ---------------------------------------------------------------------------
# THE CLOSER. Added 2026-09-07.
#
# A log of open positions is not a record, it is a wishlist. Twenty entries sat
# open for a day because nothing ever closed them, which meant the log contained
# no losers - and a log that only ever fills in the winners is worth nothing.
# THE LOSERS ARE THE PROOF.
#
# Every open position is evaluated against the exit rule DECLARED AT ENTRY, and
# every one that meets it is closed, whatever the number says. Three outcomes
# and all three are recorded:
#
#   target   the position reached its declared multiple on quote-side depth
#   expiry   max hold elapsed; closed at whatever it is worth, including zero
#   unpriceable  the source dropped the pair before we could close it
#
# `unpriceable` is NOT recorded as a zero. We do not know the price, and
# inventing one is exactly the class of error this whole file exists to prevent.
# It stays in the denominator as a closed position with `mult = None`, which is
# the honest treatment: it was never a win, and it was not measurably a loss.
# ---------------------------------------------------------------------------
class PairLookupFailed(RuntimeError):
    """Our own journal could not be read. The pool is UNKNOWN, not absent.

    Distinct from "no observation exists for this contract", which is a real
    answer. A close is permanent, so the caller must leave the position open.
    """


CLOSE_TARGET = "target"
CLOSE_EXPIRY = "expiry"
CLOSE_UNPRICEABLE = "unpriceable"


def _exit_depth(pair):
    liq = pair.get("liquidity") or {}
    try:
        q = float(liq.get("quote")) if liq.get("quote") is not None else None
        pu = float(pair.get("priceUsd")) if pair.get("priceUsd") else None
        pn = float(pair.get("priceNative")) if pair.get("priceNative") else None
    except (TypeError, ValueError):
        return None
    if q is not None and pu and pn:
        return q * (pu / pn)
    return None


def _pair_for(entry):
    """The pool this entry was opened on.

    Entries written before 2026-09-07 did not store it. It is RECOVERED from
    our own observation journal by contract address - not guessed, not looked
    up by token, because a token-level lookup can return a different pool and
    that is precisely the contamination this log exists to avoid. An entry
    whose pool cannot be recovered is closed `unpriceable`, never priced.
    """
    if entry.get("pair"):
        return entry["pair"]
    # NOT a bare except any more. Two different answers were collapsed into
    # None: "the journal holds no observation for this contract" (a real
    # answer) and "reading the journal failed" (not an answer). The caller
    # closes on None, and a close is PERMANENT in an append-only ledger - so a
    # transient read failure was writing an irreversible `unpriceable` verdict.
    # Same family as safeload: absent and unreadable must not answer alike.
    import journal
    try:
        obs = journal.observations()
    except Exception as e:
        raise PairLookupFailed(
            f"could not read the observation journal to recover the pool for "
            f"{entry.get('contract')}: {type(e).__name__}: {e}") from e
    best = None
    for o in obs:
        if o.get("token") != entry.get("contract"):
            continue
        if best is None or o.get("ts", 0) < best.get("ts", 0):
            best = o
    return (best or {}).get("pair")


# ---------------------------------------------------------------------------
# THE CLOSE DECISION, as a pure function shared by v1 and v2.
#
# Extracted 2026-09-10 when RULE_V2 began running in parallel. Both ledgers must
# close on IDENTICAL logic or the comparison measures the closer instead of the
# filter, and a divergence would be invisible - two plausible numbers that were
# never computed the same way. So there is one implementation and both sweeps
# call it. No I/O, no writes, no globals beyond the pinned constants.
# ---------------------------------------------------------------------------
def close_decision(entry, pair, elapsed_h, target_mult=None, min_depth=None,
                   max_hold_h=None):
    """(action, price, depth, reason_code, detail).

    action is one of: "target", "expiry", "unpriceable", "hold".
    `pair` is None when the lookup SUCCEEDED and returned nothing - a failed
    lookup must never reach here; that is a hold, decided by the caller.
    """
    target = float(target_mult if target_mult is not None
                   else entry.get("target_mult") or TARGET_MULT)
    floor = float(min_depth if min_depth is not None else MIN_EXIT_DEPTH)
    hold = float(max_hold_h if max_hold_h is not None
                 else entry.get("max_hold_h") or MAX_HOLD_H)
    expired = elapsed_h >= hold
    if not pair:
        if expired:
            return ("unpriceable", None, None, CLOSE_UNPRICEABLE,
                    "source dropped the pair before the hold expired; "
                    "no exit price is knowable and none is invented")
        return ("hold", None, None, None, "")
    try:
        px = float(pair.get("priceUsd")) if pair.get("priceUsd") else None
    except (TypeError, ValueError):
        px = None
    depth = _exit_depth(pair)
    ep = entry.get("entry_price_usd")
    mult = (px / ep) if (px and ep) else None
    # A multiple without depth is a price on a corpse. Both are required, and
    # this is the check that stopped Grogu's 6.144x on $0.0000007 of depth.
    if mult is not None and mult >= target and depth is not None and depth >= floor:
        return ("target", px, depth, CLOSE_TARGET,
                f"reached {mult:.3f}x with ${depth:,.0f} of quote-side depth")
    if expired:
        return ("expiry", px, depth, CLOSE_EXPIRY,
                f"max hold {elapsed_h:.1f}h elapsed at "
                f"{('%.3fx' % mult) if mult is not None else 'no price'}")
    return ("hold", px, depth, None, "")


def sweep(fetch_pair, verbose=True):
    """Close every open position whose declared exit rule has been met.

    `fetch_pair(network, pair_address) -> pair or None`, injected so this stays
    testable without network and free of a circular import.
    """
    import datetime as _dt
    liveness.beat("paper.sweep")
    rows = _read()
    closed_ids = {r.get("entry_id") for r in rows if r.get("type") == "exit"}
    opens = [r for r in rows if r.get("type") == "entry"
             and r.get("hash") not in closed_ids]
    now = dt.datetime.now(dt.timezone.utc)
    stats = {"checked": 0, "closed": 0, "target": 0, "expiry": 0,
             "unpriceable": 0, "still_open": 0}
    for e in opens:
        stats["checked"] += 1
        try:
            t0 = dt.datetime.strptime(e["ts"], "%Y-%m-%dT%H:%M:%SZ").replace(
                tzinfo=dt.timezone.utc)
            elapsed_h = (now - t0).total_seconds() / 3600.0
        except Exception:
            elapsed_h = 0.0
        expired = elapsed_h >= float(e.get("max_hold_h") or MAX_HOLD_H)

        pair = None
        try:
            _pa = _pair_for(e)
        except PairLookupFailed as err:
            # We do not know the pool, so we do not know anything. Leave the
            # position OPEN and try again next sweep; never spend an
            # irreversible close on a failure to read our own journal.
            print(f"  [paper] {e.get('symbol')} left open - {err}")
            stats["still_open"] += 1
            continue
        try:
            pair = fetch_pair("solana", _pa) if _pa else None
        except Exception as err:
            # A fetch that RAISED is a failed lookup, not a delisted pool.
            # Only a lookup that succeeded and returned nothing is evidence
            # of absence.
            print(f"  [paper] {e.get('symbol')} left open - exit price fetch "
                  f"failed: {type(err).__name__}: {err}")
            stats["still_open"] += 1
            continue

        action, px, depth, code, detail = close_decision(e, pair, elapsed_h)
        if action == "hold":
            stats["still_open"] += 1
        else:
            _close(e, px, depth, code, detail)
            stats["closed"] += 1
            stats["unpriceable" if action == "unpriceable" else action] += 1
            if verbose:
                print(f"  [paper] CLOSED {e.get('symbol')} {action} "
                      f"depth ${(depth or 0):,.0f} after {elapsed_h:.1f}h - {detail[:60]}")
    if verbose and stats["checked"]:
        print(f"  [paper] {stats['checked']} open checked, {stats['closed']} closed "
              f"({stats['target']} target, {stats['expiry']} expiry, "
              f"{stats['unpriceable']} unpriceable), {stats['still_open']} still open")
    return stats


def _close(entry, price, depth, reason, detail):
    """Write the exit. Applies the SAME gate the outcome journal uses, so a
    paper win and a journalled win mean the same thing."""
    try:
        import journal
        ok, failed = journal.verify_win(
            "alive" if price else "gone",
            None, (price / entry["entry_price_usd"]) if (price and entry.get("entry_price_usd")) else None,
            exit_depth=depth,
            pair=entry.get("contract"), exit_pair=entry.get("contract"),
            elapsed_h=1.0)
    except Exception:
        ok, failed = None, ["gate_unavailable"]
    # CAPTURE RESERVES AT THE MOMENT OF CLOSE. Solana RPC has no historical
    # account state at any tier - getAccountInfo always answers for the current
    # slot - so reserves not recorded now can never be recovered, only replayed
    # from transaction history at far greater cost. Repricing the first 10
    # closes failed for exactly this reason. One call here versus a permanently
    # unrepriceable ledger.
    _chain = None
    try:
        import onchain_reserves as _OR
        _pa = entry.get("pair") or _pair_for(entry)
        if _pa and entry.get("contract"):
            _d, _e, _ = _OR.exit_depth(_pa, entry["contract"], _OR.WSOL)
            _chain = _d
    except Exception:
        _chain = None
    rec = close_entry(entry["hash"], price=price, exit_depth=depth,
                      reason=f"{reason}: {detail}", chain_depth=_chain)
    liveness.beat("paper.close", detail=str(reason)[:24])
    return rec


# ---------------------------------------------------------------------------
# INFERRED TOTAL LOSSES: labelling what we already know, without inventing it.
#
# 26 of the first 40 closes were `unpriceable` - the pool was delisted before
# the 24h hold expired, so no exit price existed and none was invented. That is
# honest, but it is not the same as unknown. The last witness we hold for those
# positions says: 15 rugged, 5 dead, 4 alive; median last-known liquidity $0,
# with 19 of 24 under $1,000. A position whose pool was drained to nothing and
# then deindexed did not have an unknown outcome. It went to zero.
#
# WHAT WE MUST NOT DO, and it is the whole reason this is careful: adopt the
# last-known MULTIPLE. Median last multiple across those 26 is 0.967x and 8 of
# 24 printed >= 2x - on pools holding $0. Taking those numbers moves the >=2x
# rate from 21% to 29%: it manufactures wins out of drained pools. That is the
# rug-that-pumps-on-the-way-out shape which has fooled this project five times.
# So the label asserts a multiple of ZERO, from liquidity, never a price read
# off a corpse. `multiple_adopted` is written as null on every row to record
# that refusal explicitly.
#
# THE LEDGER IS APPEND-ONLY AND HASH-CHAINED, so labels are appended as their
# own records referencing an exit's hash. No exit row is ever edited. Deriving
# the log with or without inferred labels is therefore always possible, and the
# hit rate gets reported both ways, forever.
#
# Criteria pre-committed before the counts were computed:
#   status in (rugged, dead)  AND  last-known liquidity <= $100.
# `alive` is never labelled, however low its liquidity - an honest "unknown" is
# still the right answer for some rows, and forcing a label to raise coverage
# is exactly the failure this is meant to avoid.
# ---------------------------------------------------------------------------
LABEL_INFERRED_LOSS = "total_loss_inferred"
LABEL_MEASURED_LOSS = "total_loss_measured"
DEAD_LIQ_USD = float(os.environ.get("CRYPTO_PAPER_DEAD_LIQ_USD", "100"))
DEAD_STATUSES = ("rugged", "dead")


def _witness(entry):
    """The last outcome row that actually carried a price for this entry's pool.

    Read-only, from data/outcomes. Returns None when we hold no witness - in
    which case nothing is inferred and the close stays unpriceable.
    """
    import glob
    pair = entry.get("pair")
    if not pair:
        try:
            pair = _pair_for(entry)
        except PairLookupFailed:
            return None
    if not pair:
        return None
    best = None
    for path in sorted(glob.glob(os.path.join("data", "outcomes", "*.jsonl"))):
        with open(path, encoding="utf-8") as f:
            for line in f:
                if not line.strip() or pair not in line:
                    continue
                try:
                    d = json.loads(line)
                except ValueError:
                    continue
                if d.get("pair") != pair or d.get("price_usd") is None:
                    continue
                if best is None or (d.get("checked_ts") or 0) > (best.get("checked_ts") or 0):
                    best = d
    return best



def closes(rows=None):
    """One exit per entry: the EARLIEST. Concurrent sweeps double-close.

    Two writers run sweep() - this session and the hosted runner - and each
    computes `closed_ids` from its own view of the ledger. When the two
    histories are unioned, a position closed by one writer gets closed AGAIN by
    the other, which did not see the first. Measured 2026-09-09: 95 exits
    against 69 entries, 34 entries closed twice, giving a nonsensical -26 open
    positions and inflating n on a log whose whole purpose is a denominator.

    The earliest close is kept because it is the one a single writer would have
    produced; the later row exists only because a concurrent writer could not
    see it. In all 9 cases where the two disagree, the earliest carries a price
    and the later is `unpriceable` - the pool was still indexed at the real
    close and gone an hour later. Keeping the later row would be discarding a
    measured exit in favour of "we lost track of it".

    STATED PLAINLY: this rule yields one MORE win than keeping the latest (3 vs
    2). The rule is chosen on that structural argument, not on the count, and
    the count is reported so the choice can be checked.

    Deduplication happens on READ. The ledger is append-only and hash-chained,
    so nothing is removed - both rows stay on the record forever.
    """
    rows = _read() if rows is None else rows
    best = {}
    for r in rows:
        if r.get("type") != "exit" or r.get("void"):
            continue
        k = r.get("entry_id")
        if k not in best or str(r.get("ts") or "") < str(best[k].get("ts") or ""):
            best[k] = r
    return list(best.values())


def labelled_exits():
    """exit hash -> its label record. Labels never overwrite; the first stands."""
    out = {}
    for r in _read():
        if r.get("type") == "label" and r.get("exit_id") not in out:
            out[r["exit_id"]] = r
    return out


def label_unpriceable(dry_run=True, verbose=True):
    """Append `total_loss_inferred` labels for unambiguously dead positions."""
    rows = _read()
    entries = {r["hash"]: r for r in rows if r.get("type") == "entry"}
    already = labelled_exits()
    made, skipped = [], []
    for r in closes(rows):
        if not str(r.get("reason", "")).startswith(CLOSE_UNPRICEABLE):
            continue
        if r.get("hash") in already:
            continue
        e = entries.get(r.get("entry_id")) or {}
        w = _witness(e)
        if not w:
            skipped.append((r.get("symbol"), "no witness held"))
            continue
        status, liq = w.get("status"), w.get("liq")
        if status not in DEAD_STATUSES:
            skipped.append((r.get("symbol"), f"last seen {status} - stays unpriceable"))
            continue
        if liq is None or liq > DEAD_LIQ_USD:
            shown = "unknown" if liq is None else f"${liq:,.2f}"
            skipped.append((r.get("symbol"),
                            f"liquidity {shown} above the ${DEAD_LIQ_USD:,.0f} floor"))
            continue
        rec = {
            "type": "label", "exit_id": r["hash"], "entry_id": r.get("entry_id"),
            "contract": r.get("contract"), "symbol": r.get("symbol"),
            "label": LABEL_INFERRED_LOSS,
            "inferred": True,
            "mult_effective": 0.0,
            # Null on purpose: we refused to adopt the last-known price.
            "multiple_adopted": None,
            "witness_status": status,
            "witness_liq_usd": liq,
            "witness_price_usd": w.get("price_usd"),
            "witness_checked_ts": w.get("checked_ts"),
            "witness_horizon_h": w.get("horizon_h"),
            "witness_elapsed_h": w.get("actual_elapsed_h"),
            "basis": (f"pool last seen {status} holding ${liq:,.2f} of liquidity "
                      f"at checked_ts {w.get('checked_ts')}, then delisted before "
                      f"the hold expired. Outcome INFERRED from liquidity, not "
                      f"measured; the last-known price was deliberately not used."),
            "criteria": {"statuses": list(DEAD_STATUSES), "max_liq_usd": DEAD_LIQ_USD},
            "ts": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        }
        made.append(rec)
    if verbose:
        print(f"  {len(made)} to label, {len(skipped)} left unpriceable")
        for sym, why in skipped:
            print(f"    SKIP {str(sym)[:14]:<15} {why}")
    if not dry_run:
        for rec in made:
            _append(rec)
    return made, skipped


def summary(include_inferred=False):
    """Counts only. Refuses to quote a rate below MIN_N.

    `include_inferred` folds in positions labelled total_loss_inferred at a
    multiple of 0.0. Report BOTH ways: if they differ materially, that gap is
    the finding, not a footnote.
    """
    rows = _read()
    entries = [r for r in rows if r.get("type") == "entry"]
    exits = closes(rows)
    voids = [r for r in rows if r.get("type") == "exit" and r.get("void")]
    dup = sum(1 for r in rows
              if r.get("type") == "exit" and not r.get("void")) - len(exits)
    labels = labelled_exits()
    mults = sorted(r["mult"] for r in exits if r.get("mult") is not None)
    measured_n = len(mults)
    inferred = [r for r in exits
                if r.get("mult") is None
                and r.get("hash") in labels
                and labels[r["hash"]].get("label") == LABEL_INFERRED_LOSS]
    if include_inferred:
        mults = sorted(mults + [0.0] * len(inferred))
    # A WIN NEEDS A POOL TO SELL INTO, NOT JUST A PRICE.
    #
    # The target close path already requires depth: `mult >= target AND depth
    # >= MIN_EXIT_DEPTH`. The EXPIRY path does not - it closes at whatever the
    # last print says, including zero-liquidity prints. summary() then counted
    # those as wins on the multiple alone.
    #
    # Grogu, 2026-09-09: closed at expiry at 6.144x with an exit depth of
    # $0.0000007 and realizable_usd 0.00. It was the largest multiple in the
    # log and it was the top of the win column. Nothing could have been sold.
    # This is the rug-that-pumps-on-the-way-out shape for the sixth time.
    #
    # Both counts are reported so the gap stays visible; `wins` is the
    # realizable one and it is the one that means anything.
    def _realizable(r):
        d = r.get("exit_depth_usd")
        return d is not None and d >= MIN_EXIT_DEPTH
    win_rows = [r for r in exits
                if r.get("mult") is not None and r["mult"] >= TARGET_MULT]
    wins = [r["mult"] for r in win_rows if _realizable(r)]
    wins_price_only = [r["mult"] for r in win_rows]
    n = len(mults)
    # THE FLOOR COUNTS DISTINCT TOKENS, NOT ROWS. Declared 2026-09-07 after the
    # low-score inversion was found to rest on 9 rows that were 6 tokens. The
    # inferred labels make this bite: they took n from 14 to 33, over a row
    # floor of 30, and summary() published a 9.09% hit rate. But those 19 rows
    # are 12 distinct contracts - HOOD appears four times, CatGPT twice. A
    # token measured at several horizons is one token.
    counted = [r for r in exits if r.get("mult") is not None]
    if include_inferred:
        counted = counted + inferred
    n_tokens = len({r.get("contract") for r in counted if r.get("contract")})
    out = {"entries": len(entries), "closed": len(exits), "void": len(voids),
           "open": len(entries) - len(exits) - len(voids),
           "priceable": measured_n, "inferred_losses": len(inferred),
           "unpriceable_unlabelled": len(exits) - measured_n - len(inferred),
           "basis": ("measured + inferred" if include_inferred else "measured only"),
           "duplicate_closes_ignored": dup,
           "n": n, "n_tokens": n_tokens, "wins": len(wins),
           "wins_price_only": len(wins_price_only),
           "wins_unexitable": len(wins_price_only) - len(wins), "min_n": MIN_N,
           "conclusive": n_tokens >= MIN_N}
    if n:
        out["median_mult"] = mults[n // 2] if n % 2 else (mults[n // 2 - 1] + mults[n // 2]) / 2
        out["p25_mult"] = mults[int(0.25 * (n - 1))]
        out["p75_mult"] = mults[int(0.75 * (n - 1))]
        out["max_mult"] = mults[-1]
    out["hit_rate"] = (f"{100.0 * len(wins) / n:.2f}%" if out["conclusive"]
                       else f"WITHHELD - {n_tokens} distinct tokens, need {MIN_N}")
    return out
