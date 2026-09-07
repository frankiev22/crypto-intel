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
    return _append({
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


def summary():
    """Counts only. Refuses to quote a rate below MIN_N."""
    rows = _read()
    entries = [r for r in rows if r.get("type") == "entry"]
    exits = [r for r in rows if r.get("type") == "exit" and not r.get("void")]
    voids = [r for r in rows if r.get("type") == "exit" and r.get("void")]
    mults = sorted(r["mult"] for r in exits if r.get("mult") is not None)
    wins = [m for m in mults if m >= TARGET_MULT]
    out = {"entries": len(entries), "closed": len(exits), "void": len(voids),
           "open": len(entries) - len(exits) - len(voids),
           "wins": len(wins), "min_n": MIN_N,
           "conclusive": len(exits) >= MIN_N}
    if mults:
        n = len(mults)
        out["median_mult"] = mults[n // 2] if n % 2 else (mults[n // 2 - 1] + mults[n // 2]) / 2
        out["p25_mult"] = mults[int(0.25 * (n - 1))]
        out["p75_mult"] = mults[int(0.75 * (n - 1))]
        out["max_mult"] = mults[-1]
    out["hit_rate"] = (f"{100.0 * len(wins) / len(exits):.2f}%" if out["conclusive"]
                       else f"WITHHELD - {len(exits)} closed, need {MIN_N}")
    return out


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
    try:
        import journal
        best = None
        for o in journal.observations():
            if o.get("token") != entry.get("contract"):
                continue
            if best is None or o.get("ts", 0) < best.get("ts", 0):
                best = o
        return (best or {}).get("pair")
    except Exception:
        return None


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
            pair = fetch_pair("solana", _pa) if _pa else None
        except Exception:
            pair = None

        if not pair:
            if expired:
                _close(e, None, None, CLOSE_UNPRICEABLE,
                       "source dropped the pair before the hold expired; "
                       "no exit price is knowable and none is invented")
                stats["closed"] += 1; stats["unpriceable"] += 1
                if verbose:
                    print(f"  [paper] CLOSED {e.get('symbol')} unpriceable "
                          f"after {elapsed_h:.1f}h")
            else:
                stats["still_open"] += 1
            continue

        try:
            px = float(pair.get("priceUsd")) if pair.get("priceUsd") else None
        except (TypeError, ValueError):
            px = None
        depth = _exit_depth(pair)
        ep = e.get("entry_price_usd")
        mult = (px / ep) if (px and ep) else None
        target = float(e.get("target_mult") or TARGET_MULT)

        hit = (mult is not None and mult >= target
               and depth is not None and depth >= MIN_EXIT_DEPTH)
        if hit:
            _close(e, px, depth, CLOSE_TARGET,
                   f"reached {mult:.3f}x with ${depth:,.0f} of quote-side depth")
            stats["closed"] += 1; stats["target"] += 1
            if verbose:
                print(f"  [paper] CLOSED {e.get('symbol')} TARGET {mult:.2f}x "
                      f"depth ${depth:,.0f} after {elapsed_h:.1f}h")
        elif expired:
            _close(e, px, depth, CLOSE_EXPIRY,
                   f"max hold {elapsed_h:.1f}h elapsed at "
                   f"{('%.3fx' % mult) if mult is not None else 'no price'}")
            stats["closed"] += 1; stats["expiry"] += 1
            if verbose:
                m = f"{mult:.3f}x" if mult is not None else "unpriced"
                print(f"  [paper] CLOSED {e.get('symbol')} expiry {m} "
                      f"depth ${(depth or 0):,.0f} after {elapsed_h:.1f}h")
        else:
            stats["still_open"] += 1
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
