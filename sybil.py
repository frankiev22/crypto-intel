"""⭐⭐ THE STACKED-SIGNAL COORDINATION DETECTOR. Four weak signals, one
confidence level, and the signals that produced it always named.

Frank, 2026-09-23: sophisticated bundlers *"fund 20-plus wallets through paths
that defeat naive funding-graph clustering."*

⛔ **So the funding graph cannot be the detector.** It is kept and DEMOTED, for
hub identification only. The rule, every threshold and the two results that would
make v1 wrong are pre-committed in `PRECOMMIT_sybil_v1.md`, written before a
single wallet was scored.

## Why stacked, in one line each

- ⛔ **S1 same-slot co-buying is DEAD, weight 0, killed by its own control on
  the day it was written.** It fired on **9 of 9** ordinary graduations, co-buy
  share 0.625 to 0.933. A Solana slot is ~400ms and a launch is a frenzy, so
  independent buyers share a slot because the slot is wide. It is still measured
  and recorded, and it contributes nothing. See the RESULT section of the
  pre-commit.
- **S2 wallet age** is hard to defeat because ageing twenty wallets costs time
  and rent and cannot be bought after the fact.
- **S3 exit correlation** is hard to disguise because the reason to bundle is to
  sell into the crowd, and that has to happen.
- **S4 shared funder** is already defeated. Weight 1, and it can never carry a
  level on its own.

## ⛔ It must be able to report a NEGATIVE, and that is not a formality

Measured 2026-09-23 over 60 consecutive graduations: the top holders of fresh
pump.fun graduates are **not** fresh wallets, every one carried **3,000+
signatures**, and **0 of the top 10 of two tested graduates was fresh**.
Collapsing those by shared funder would have manufactured clusters out of
ordinary market participants. **"All of these are established traders" is a real
finding** and this module says it out loud.

## ⛔ What it never outputs

No score, no grade, no rank, no expected return, and no binary "bundled or not".
A level is a description of coordination that has **already happened**, which is
the narrow exception Marino allows. It says nothing about what the price does
next, and `test_sybil.py` fails at the AST level if a ranking term appears.
"""
import json
import os
import time
import urllib.request

import config

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel research; contact via github)"}

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "data", "sybil")

# ⛔ EVERY NUMBER BELOW IS PRE-COMMITTED IN PRECOMMIT_sybil_v1.md.
N_BUYERS = 30                 # first N distinct wallets to receive the mint
MIN_BUYERS_TO_JUDGE = 8       # under this the answer is INSUFFICIENT DATA
EXIT_WINDOW_S = 600           # S3's co-selling window
FRESH_SHARE_FIRES = 0.30      # S2
EXIT_SHARE_FIRES = 0.30       # S3
S1_MIN_GROUP = 3              # one group of this many fires S1
S1_MIN_GROUPS = 2             # or this many groups of >= 2
S4_MIN_SHARED = 3             # buyers sharing one funder

# ⛔⛔ S1's WEIGHT IS 0, AND THAT IS A RESULT, NOT A CONFIGURATION CHOICE.
# It was pre-committed at 3 as the hardest signal to defeat. The control
# PRECOMMIT_sybil_v1.md section 7 demanded, run the same day on 9 consecutive
# graduations chosen by recency alone, fired S1 on **9 of 9**, co-buy share 0.625
# to 0.933. A Solana slot is ~400ms and a launch is a frenzy, so independent
# buyers share a slot because the slot is wide. Sharing a slot is the BASE RATE.
#
# The pre-commit said the weight must move to 0 rather than be re-tuned, so it is
# 0. The measurement is still taken and still recorded on every row, because that
# is how a baseline-relative version gets its baseline - but a baseline-relative
# signal needs its OWN pre-commit written before it is measured, because choosing
# a threshold after seeing the data is the bug this repo has the most scars from.
WEIGHTS = {"S1_same_slot": 0, "S2_wallet_age": 2,
           "S3_exit_correlation": 2, "S4_shared_funder": 1}

# The cluster-buy lane.
CLUSTER_MIN_WALLETS = 3
CLUSTER_WINDOW_S = 900

NONE = "NONE OBSERVED"
WEAK = "WEAK"
MODERATE = "MODERATE"
STRONG = "STRONG"
INSUFFICIENT = "INSUFFICIENT DATA"


# --------------------------------------------------------------------------
# chain reads
# --------------------------------------------------------------------------
def _rpc(method, params, timeout=45):
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


def _enrich(signatures):
    """Helius /v0/transactions, up to 100 signatures a call."""
    u = "https://api.helius.xyz/v0/transactions?api-key=%s" % config.key("helius")
    body = json.dumps({"transactions": list(signatures)}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            u, data=body, headers={"Content-Type": "application/json",
                                   "User-Agent": UA["User-Agent"]}), timeout=60)
        d = json.loads(r.read())
        return d if isinstance(d, list) else []
    except Exception:
        return []


def flows(mint, n=N_BUYERS, max_pages=8, exclude=(), enrich=None, rpc=None):
    """⭐ Every early transfer of this mint, WITH ITS SLOT.

    ⛔ The slot is the whole point and is why this does not just call
    `devwallet.first_buyers()`, which drops it. S1 is a same-SLOT test, and a
    timestamp is a second-resolution rounding of a slot: two buys 400ms apart in
    the same slot and two buys 900ms apart in different slots can both carry the
    same `ts`. Testing coordination on the rounded field would be rule 13 again.

    Returns buys, sells, `truncated`, and why.
    """
    rpc = rpc or _rpc
    enrich = enrich or _enrich
    sigs, before = [], None
    reached_start = False
    for _ in range(max_pages):
        res, err = rpc("getSignaturesForAddress",
                       [mint, {"limit": 1000, "before": before}])
        if err or res is None:
            return {"ok": False, "why": str(err)[:140], "truncated": None}
        if not res:
            reached_start = True
            break
        sigs += res
        before = res[-1]["signature"]
        if len(res) < 1000:
            reached_start = True
            break

    if not sigs:
        return {"ok": False, "why": "no signatures on this mint",
                "truncated": False}

    sigs.sort(key=lambda x: (x.get("slot") or 0))
    batch = [s["signature"] for s in sigs[:300]]
    txs = []
    for i in range(0, len(batch), 100):
        txs += enrich(batch[i:i + 100]) or []
    txs.sort(key=lambda t: (t.get("slot") or 0))

    skip = set(exclude) | {mint}
    buys, sells, seen = [], [], set()
    for t in txs:
        slot = t.get("slot")
        ts = t.get("timestamp")
        sig = t.get("signature")
        for tt in (t.get("tokenTransfers") or []):
            if tt.get("mint") != mint:
                continue
            to_ = tt.get("toUserAccount")
            from_ = tt.get("fromUserAccount")
            amt = tt.get("tokenAmount")
            # ⛔ The pool is not a buyer. The first token transfer on any mint
            # goes into the pool account; counting it produced a "buyer" that
            # was the pair address itself on the first live run of first_buyers.
            if to_ and to_ not in skip:
                if to_ not in seen and len(seen) < n:
                    seen.add(to_)
                    buys.append({"wallet": to_, "slot": slot, "ts": ts,
                                 "amount": amt, "signature": sig})
            if from_ and from_ not in skip and from_ in seen:
                sells.append({"wallet": from_, "slot": slot, "ts": ts,
                              "amount": amt, "signature": sig})
    return {"ok": True, "buys": buys, "sells": sells,
            # ⚠️ A truncated walk did not reach the mint's first transaction, so
            # these are EARLY buyers, not FIRST buyers, and every conclusion from
            # them is a floor.
            "truncated": not reached_start,
            "n_signatures_seen": len(sigs), "why": None}


# --------------------------------------------------------------------------
# the four signals. Each returns its own measurement whether or not it fired.
# --------------------------------------------------------------------------
def s1_same_slot(buys, migration_slots=()):
    """Buyers arriving in the SAME SLOT. The hardest signal to defeat.

    ⛔ A pump.fun graduation migrates in ONE transaction, so the migration slot
    is not a co-buy. It is excluded by slot, not explained away afterwards
    (PRECOMMIT section 7).
    """
    groups = {}
    skip = set(migration_slots)
    for b in buys:
        s = b.get("slot")
        if s is None or s in skip:
            continue
        groups.setdefault(s, set()).add(b["wallet"])
    multi = {s: sorted(w) for s, w in groups.items() if len(w) >= 2}
    sizes = sorted((len(w) for w in multi.values()), reverse=True)
    in_group = len({w for ws in multi.values() for w in ws})
    examined = len({b["wallet"] for b in buys if b.get("slot") not in skip})
    fired = bool(sizes) and (sizes[0] >= S1_MIN_GROUP or len(sizes) >= S1_MIN_GROUPS)
    return {
        "signal": "S1_same_slot", "fired": fired, "weight": WEIGHTS["S1_same_slot"],
        "max_group": sizes[0] if sizes else 0,
        "n_groups": len(sizes),
        "wallets_in_a_group": in_group,
        "buyers_examined": examined,
        "co_buy_share": round(in_group / examined, 4) if examined else None,
        "groups": {str(s): w for s, w in sorted(multi.items())[:10]},
        "migration_slots_excluded": sorted(skip),
        "why": ("splitting one buy across wallets is what makes them arrive in "
                "the same slot; staggering costs the launch price"),
    }


def s2_wallet_age(buys, age_fn=None, budget=12):
    """How many of these wallets had NO history before this launch.

    ⛔ Never dates a wallet by walking its history to now - that gave WOFI an age
    of MINUS 0.1 hours. It asks whether there was activity BEFORE the wallet's
    own first signature on this mint.

    ⚠️ A wallet whose age could not be established is counted in NEITHER the
    numerator nor the denominator, and the count of those is reported. Unknown is
    not "established" and it is not "fresh".
    """
    if age_fn is None:
        import devwallet
        age_fn = devwallet.activity_before
    fresh, established, unknown = [], [], []
    for b in buys[:budget]:
        try:
            prior = age_fn(b["wallet"], b.get("signature"))
        except Exception:
            unknown.append(b["wallet"])
            continue
        # ⛔ `activity_before` answers {"had_prior": True/False/None}. None
        # means the QUERY FAILED and must never be read as False: "we could not
        # check" and "this wallet is brand new" are different answers and only
        # one of them is damning.
        had = (prior or {}).get("had_prior") if isinstance(prior, dict) else None
        if had is None:
            unknown.append(b["wallet"])
        elif had is False:
            fresh.append(b["wallet"])
        else:
            established.append(b["wallet"])
    denom = len(fresh) + len(established)
    share = (len(fresh) / denom) if denom else None
    return {
        "signal": "S2_wallet_age", "fired": bool(share is not None
                                                 and share >= FRESH_SHARE_FIRES),
        "weight": WEIGHTS["S2_wallet_age"],
        "fresh": fresh, "n_fresh": len(fresh),
        "n_established": len(established),
        "n_age_unknown": len(unknown),
        "fresh_share": round(share, 4) if share is not None else None,
        "checked": min(len(buys), budget),
        "why": ("ageing twenty wallets costs time and rent and cannot be bought "
                "after the fact"),
        # ⭐ The real negative, stated rather than left as a zero.
        "note": (None if share else
                 "no fresh wallets among those datable. On pump.fun graduates "
                 "that is the NORM, not a clean bill of health: every top holder "
                 "measured on 2026-09-23 carried 3,000+ signatures."),
    }


def s3_exit_correlation(buys, sells, window_s=EXIT_WINDOW_S):
    """Do the same wallets LEAVE together. Harder to disguise than the entry.

    ⛔⛔ UNEVALUABLE ON A SAMPLE NARROWER THAN THE WINDOW, and the first
    version did not check that. Its control fired on 5 of 9 launches with an
    `exit_share` of **1.000 on all nine, including mints with ONE seller**,
    because `flows()` reads the mint's first ~300 signatures, which all land
    within minutes of launch. Every sell in that sample is inside a 600s window
    BY CONSTRUCTION.

    That is standing rule 13 exactly: never measure a duration with a sampler
    narrower than the thing measured. So the span of the observed sells is now a
    PRECONDITION. When it does not exceed the window, this returns
    `fired=None` and `unevaluable`, which is not the same as a clean negative.
    """
    buyers = {b["wallet"] for b in buys}
    exits = {}
    for s in sells:
        if s["wallet"] in buyers and s.get("ts"):
            exits.setdefault(s["wallet"], s["ts"])
            exits[s["wallet"]] = min(exits[s["wallet"]], s["ts"])
    times = sorted(exits.items(), key=lambda kv: kv[1])
    best, best_members = 0, []
    for i, (_w, t0) in enumerate(times):
        members = [w for w, t in times[i:] if t - t0 <= window_s]
        if len(members) > best:
            best, best_members = len(members), members
    n_sellers = len(times)
    share = (best / n_sellers) if n_sellers else None
    span = (times[-1][1] - times[0][1]) if n_sellers >= 2 else 0
    # ⛔ THE PRECONDITION. If every sell we can see fits inside one window,
    # "they sold together" is a property of the SAMPLE, not of the wallets.
    unevaluable = n_sellers < 2 or span <= window_s
    out = {
        "signal": "S3_exit_correlation",
        "fired": (None if unevaluable
                  else bool(best >= 3 and share >= EXIT_SHARE_FIRES)),
        "weight": WEIGHTS["S3_exit_correlation"],
        "n_sellers": n_sellers,
        "largest_exit_cluster": best,
        "cluster_wallets": best_members[:10],
        "exit_share": round(share, 4) if share is not None else None,
        "window_s": window_s,
        "observed_sell_span_s": span,
        "unevaluable": unevaluable,
        "why": ("the reason to bundle is to sell into the crowd, and that has "
                "to happen"),
    }
    if unevaluable:
        out["unevaluable_why"] = (
            "the sells we can see span %ds, which does not exceed the %ds "
            "window, so every sell is inside one window BY CONSTRUCTION. "
            "Standing rule 13: a sampler narrower than the thing measured "
            "cannot measure it. This is NOT a clean negative - it is not "
            "checked. Evaluating S3 needs the mint's LATER transactions, "
            "which flows() does not read." % (span, window_s))
    return out


def s4_shared_funder(buys, funder_fn=None, budget=10):
    """⛔ DEMOTED ON PURPOSE. Hub identification only, weight 1.

    Frank: sophisticated bundlers already *"fund 20-plus wallets through paths
    that defeat naive funding-graph clustering"*. A signal an adversary has
    already beaten may inform, and may never decide.
    """
    if funder_fn is None:
        import concentration
        funder_fn = concentration.funder
    by_funder, unknown = {}, 0
    for b in buys[:budget]:
        try:
            f = funder_fn(b["wallet"])
        except Exception:
            f = None
        if isinstance(f, dict):
            f = f.get("funder")
        if not f:
            unknown += 1
            continue
        by_funder.setdefault(f, []).append(b["wallet"])
    hubs = {f: ws for f, ws in by_funder.items() if len(ws) >= 2}
    biggest = max((len(ws) for ws in by_funder.values()), default=0)
    return {
        "signal": "S4_shared_funder",
        "fired": biggest >= S4_MIN_SHARED,
        "weight": WEIGHTS["S4_shared_funder"],
        "largest_shared_funder_group": biggest,
        "hubs": {f: ws for f, ws in sorted(hubs.items(),
                                           key=lambda kv: -len(kv[1]))[:5]},
        "n_funder_unknown": unknown,
        "checked": min(len(buys), budget),
        "why": ("already defeated by anyone competent, so it identifies hubs "
                "and can never carry a level on its own"),
    }


# --------------------------------------------------------------------------
def level_from(signals, n_buyers, truncated):
    """(level, points, why). The caps bind BEFORE the points table."""
    fired = [s for s in signals if s.get("fired")]
    points = sum(s.get("weight", 0) for s in fired)

    if n_buyers < MIN_BUYERS_TO_JUDGE:
        return (INSUFFICIENT, points,
                "only %d buyers could be examined, under the pre-committed "
                "minimum of %d. A thin sample is not a clean token."
                % (n_buyers, MIN_BUYERS_TO_JUDGE))

    names = [s["signal"] for s in fired]
    if names == ["S4_shared_funder"]:
        return (WEAK, points,
                "only the funding graph fired, and that signal is already "
                "defeated by anyone competent, so it is capped at WEAK")

    if points == 0:
        lvl = NONE
    elif points <= 2:
        lvl = WEAK
    elif points <= 4:
        lvl = MODERATE
    else:
        lvl = STRONG
    why = ("%d points from %s" % (points, ", ".join(names))) if names else \
        "no signal fired on the buyers examined"
    if truncated:
        why += (". ⚠ The buyer walk was TRUNCATED, so this is a FLOOR: it "
                "proves presence, never absence.")
    return lvl, points, why


def analyse(mint, exclude=(), flows_fn=None, age_fn=None, funder_fn=None,
            migration_slots=(), deep=True):
    """⭐ One mint in, one confidence level out, with every signal's measurement.

    ⛔ Records what did NOT fire as well as what did. A detector that records only
    its flags cannot be audited, and PRECOMMIT section 7 names two results that
    would make v1 wrong - both readable only from the non-firing measurements.
    """
    t0 = time.time()
    f = (flows_fn or flows)(mint, exclude=exclude)
    out = {"mint": mint, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rule": "PRECOMMIT_sybil_v1.md", "ok": bool(f.get("ok"))}
    if not f.get("ok"):
        out["level"] = INSUFFICIENT
        out["why"] = f.get("why") or "could not read this mint's transfers"
        out["signals"] = []
        return out

    buys, sells = f["buys"], f["sells"]
    signals = [s1_same_slot(buys, migration_slots=migration_slots)]
    if deep:
        signals.append(s2_wallet_age(buys, age_fn=age_fn))
        signals.append(s3_exit_correlation(buys, sells))
        signals.append(s4_shared_funder(buys, funder_fn=funder_fn))
    else:
        # ⛔ A skipped signal is recorded as SKIPPED with its reason, never as
        # not-fired. Not checked must not read as checked and clean.
        for name in ("S2_wallet_age", "S3_exit_correlation", "S4_shared_funder"):
            signals.append({"signal": name, "fired": None,
                            "weight": WEIGHTS[name], "skipped": True,
                            "why": "deep=False: this signal costs chain walks "
                                   "and was not run. Not checked, not clean."})

    lvl, points, why = level_from(signals, len(buys), f.get("truncated"))
    out.update({
        "level": lvl, "points": points, "why": why,
        "signals": signals,
        "n_buyers_examined": len(buys),
        "n_sells_seen": len(sells),
        "truncated": f.get("truncated"),
        "elapsed_s": round(time.time() - t0, 2),
        "not_checked": [
            "intent: coordination is not fraud. Market makers, launch partners "
            "and index bots all coordinate legitimately.",
            "completeness: only the first %d distinct receivers are examined, "
            "and a truncated walk makes every count a FLOOR." % N_BUYERS,
        ],
        "never_claims": ("this describes coordination that has ALREADY "
                         "happened. It is not a prediction, not a ranking and "
                         "not advice about whether to buy."),
    })
    return out


# --------------------------------------------------------------------------
# the cluster-buy lane, sharing the machinery above
# --------------------------------------------------------------------------
def cluster_buys(mint, known=None, window_s=CLUSTER_WINDOW_S,
                 min_wallets=CLUSTER_MIN_WALLETS, flows_fn=None, exclude=()):
    """⭐ Are wallets we have SEEN BEFORE showing up together on a new mint.

    Frank: *"I also want to find a way to see if coins are popping up from
    multiple big wallets."*

    ⛔⛔ THIS IS NOT A BUY SIGNAL AND MUST NEVER BE PRESENTED AS ONE. The
    most-copied wallet is the worst to copy: our own re-derivation of degentape's
    tape put **6.0% [5.8, 6.3]** of 45,853 closed positions at 2x or better,
    median position 0.925x. Following these wallets is a measured way to lose
    money. What this notices is that a launch is being worked.

    ⚠️ `known` is the recurrence registry, which is a FLOOR by construction: it
    holds the wallets we happen to have seen top-holding a mint before. A wallet
    absent from it is UNSEEN, not new.
    """
    if known is None:
        import concentration
        # ⚠️ `_index()` returns (wallet -> set of mints, n_mints). The
        # registry is a FLOOR: >= 2 means we have SEEN it top-hold two mints.
        idx, _n_mints = concentration._index()
        known = {w for w, mints in (idx or {}).items() if len(mints) >= 2}
    f = (flows_fn or flows)(mint, exclude=exclude)
    if not f.get("ok"):
        return {"mint": mint, "ok": False, "why": f.get("why"), "fired": None}

    hits = [b for b in f["buys"] if b["wallet"] in known and b.get("ts")]
    hits.sort(key=lambda b: b["ts"])
    best, members = 0, []
    for i, h in enumerate(hits):
        grp = [g for g in hits[i:] if g["ts"] - h["ts"] <= window_s]
        if len(grp) > best:
            best, members = len(grp), grp
    return {
        "mint": mint, "ok": True,
        "fired": best >= min_wallets,
        "n_known_buyers": len({h["wallet"] for h in hits}),
        "largest_window_cluster": best,
        "window_s": window_s,
        "wallets": [m["wallet"] for m in members][:12],
        "registry_size": len(known),
        "truncated": f.get("truncated"),
        "not_checked": [
            "size: combined USD is not priced here. The amounts are token "
            "units and pricing them needs a quote per mint.",
        ],
        "never_claims": ("a coordination observation, NEVER a buy signal. "
                         "6.0% [5.8, 6.3] of 45,853 copied positions reached 2x."),
    }


def write(rows, day=None):
    """Append runs to data/sybil/<day>.jsonl. Append only (standing rule 8)."""
    os.makedirs(OUT_DIR, exist_ok=True)
    day = day or time.strftime("%Y-%m-%d", time.gmtime())
    path = os.path.join(OUT_DIR, day + ".jsonl")
    n = 0
    with open(path, "a", encoding="utf-8") as fh:
        for r in (rows if isinstance(rows, list) else [rows]):
            fh.write(json.dumps(r, sort_keys=True) + "\n")
            n += 1
    try:
        import liveness
        liveness.beat("sybil.analysed", n=n,
                      detail="rule=PRECOMMIT_sybil_v1.md")
    except Exception:
        pass
    return path, n


if __name__ == "__main__":
    import sys
    args = [a for a in sys.argv[1:] if not a.startswith("-")]
    if not args:
        print(__doc__)
        raise SystemExit(0)
    deep = "--shallow" not in sys.argv
    r = analyse(args[0], deep=deep)
    print(json.dumps(r, indent=1))
