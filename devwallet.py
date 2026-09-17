"""Who launched this, what else have they launched, and who paid for it.

READ `docs/DEV_WALLET.md` FIRST.

WHY. Every other signal in this project can be bought. Liquidity can be seeded,
volume can be washed, holders can be farmed, socials can be purchased. A
deployer's history cannot be bought, because it already happened. That makes it
the only signal here that an attacker cannot fake with money - they can only
evade it, and the evasion has its own signature.

THE EVASION, AND WHY THE FUNDING GRAPH IS NOT OPTIONAL. The obvious counter to
"check the deployer's record" is a fresh wallet per launch. A per-launch wallet
has no history by construction, so a naive deployer check sees a clean sheet and
passes it.

HOW TO ASK THAT CHEAPLY, AND A MISTAKE NOT TO REPEAT. The first version tried to
date the wallet by walking its history to the beginning. That does not work: a
deployer with over 1,200 transactions never reaches the start within any sane
page budget, and the oldest transaction seen then post-dates the launch, which
produced an age of MINUS six minutes. The right question is not "how old is this
wallet" but "did this wallet exist before the launch", and there is a one-call
answer - getSignaturesForAddress(addr, before=<create signature>, limit=1). If
it comes back empty the wallet had no life before the token. See
activity_before().

    ⭐ So the question is never "what has this wallet done" - it is
       "what has whoever FUNDED this wallet done".

A brand-new wallet funded by a wallet with twelve dead launches is the same dev.
funding_chain() walks that edge.

⛔ AN UNKNOWN IS None, NEVER 0 OR False. Same contract as chainfields. A
deployer we could not resolve is not a clean deployer. `truncated` and
`resolved` flags say when an answer is a bound rather than a count, and a bound
must never be compared against a threshold as if it were exact.

COSTS, measured 2026-09-17:
    deployer()        ~600ms   one RugCheck call, free, no key
    launches()        ~500ms   one Helius v0 call, type=CREATE
    funding_chain()   ~1-4s    one v0 page-walk per hop
    wallet_age()      ~500ms   or several pages for a busy wallet
"""
import json
import sys
import time
import urllib.error
import urllib.request

import config

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
V0 = "https://api.helius.xyz/v0/addresses/%s/transactions"
RUGCHECK = "https://api.rugcheck.xyz/v1/tokens/%s/report"

# ⚠️ ROUTERS AND AGGREGATORS ARE NOT BUNDLERS. Trading terminals fund and route
# for thousands of unrelated users, so "these ten buyers share a funder" is
# meaningless when the funder is Axiom or a Jupiter aggregator authority. Found
# on the token `beer`, whose six first buyers shared one funder that turned out
# to be AxiomRXZ... - a terminal, not a dev. Prefix matching is deliberately
# crude and is only used to DOWNGRADE a bundle claim, never to raise one.
ROUTER_PREFIXES = ("Axiom", "JUP", "Jupiter", "BullX", "Photon", "Trojan",
                   "BSC", "GMGN", "Pump")

# A wallet younger than this when it launched is a per-launch wallet, not a dev
# with a record. Pre-committed here before any validation run.
FRESH_WALLET_SECONDS = 24 * 3600
MAX_PAGES = 12          # 1,200 txns. Beyond this we report a bound, not a count.


def _get(url, timeout=35):
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=UA), timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception:
        return None, None


def _v0(addr, limit=100, before=None, typ=None, source=None):
    u = "%s?api-key=%s&limit=%d" % (V0 % addr, config.key("helius"), limit)
    if before:
        u += "&before=" + before
    if typ:
        u += "&type=" + typ
    if source:
        u += "&source=" + source
    st, b = _get(u)
    return b if isinstance(b, list) else None


def _walk(addr, max_pages=MAX_PAGES):
    """Newest-first history. Returns (txns, reached_beginning)."""
    out = []
    before = None
    for _ in range(max_pages):
        b = _v0(addr, limit=100, before=before)
        if not b:
            return out, (len(out) > 0 or b is not None)
        out += b
        before = b[-1]["signature"]
        if len(b) < 100:
            return out, True
    return out, False


def deployer(mint):
    """Who created this token. None if unresolved - NOT a clean result.

    Uses RugCheck's `creator`, which is free, keyless and ~600ms. The chain
    alternative - paginate the mint's signatures to the oldest - is not viable:
    WOFI alone has over 12,000 signatures, and stopping early returns a
    transaction that merely looks oldest. Getting that wrong silently attributes
    a token to the wrong wallet, which is worse than returning None.
    """
    st, b = _get(RUGCHECK % mint)
    if st != 200 or not b:
        return {"deployer": None, "resolved": False,
                "why": "rugcheck HTTP %s" % st}
    return {"deployer": b.get("creator"),
            "resolved": bool(b.get("creator")),
            "launchpad": b.get("launchpad"),
            "rugged_flag": b.get("rugged"),
            "why": None}


def launches(addr):
    """Every token this address has created. The back catalogue.

    `type=CREATE` on the enriched v0 endpoint is the launch event: verified on
    WOFI's deployer, which returns exactly one CREATE carrying the WOFI mint.
    """
    # type=CREATE catches pump.fun-shaped launches. Tokens deployed straight
    # to an AMM never emit it, which is why ROCK came back unresolved on the
    # first run - a real coverage gap, not a transient failure.
    txns = _v0(addr, limit=100, typ="CREATE")
    if txns is None:
        return {"launches": None, "resolved": False, "n": None,
                "why": "v0 request failed"}
    if not txns:
        return {"launches": [], "resolved": True, "n": 0, "truncated": False,
                "why": "no type=CREATE events - deployer may launch off-curve"}
    out = []
    for t in txns:
        mints = [tt.get("mint") for tt in (t.get("tokenTransfers") or [])
                 if tt.get("mint") and not tt["mint"].startswith("So111111")]
        for m in dict.fromkeys(mints):
            out.append({"mint": m, "ts": t.get("timestamp"),
                        "source": t.get("source"),
                        "signature": t.get("signature")})
    return {"launches": out, "resolved": True,
            "n": len(out),
            "truncated": len(txns) >= 100,
            "why": None}


def activity_before(addr, signature, limit=3):
    """⭐ Did this wallet do ANYTHING before `signature`? One RPC call.

    Returns {"had_prior": True/False/None, "n_seen": int}. None means the query
    failed and MUST NOT be read as False - "we could not check" and "this wallet
    is brand new" are different answers and only one of them is damning.

    This replaces dating the wallet. Age is expensive and often unknowable;
    existence-before-launch is one call and is the thing actually being asked.
    """
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": "getSignaturesForAddress",
                       "params": [addr, {"before": signature, "limit": limit}]}).encode()
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            config.helius_rpc(), data=body,
            headers={"Content-Type": "application/json",
                     "User-Agent": UA["User-Agent"]}), timeout=30)
        d = json.loads(r.read())
        if "error" in d:
            return {"had_prior": None, "n_seen": None, "why": str(d["error"])[:90]}
        res = d.get("result") or []
        return {"had_prior": len(res) > 0, "n_seen": len(res), "why": None}
    except Exception as e:
        return {"had_prior": None, "n_seen": None, "why": str(e)[:90]}


def wallet_age(addr, at_ts=None):
    """(first_seen_ts, age_seconds_at `at_ts`, exact). exact=False means a bound.

    ⚠️ For a busy wallet the walk stops at MAX_PAGES and first_seen is then the
    oldest transaction WE SAW, so the real wallet is at least that old. Returned
    with exact=False so a caller cannot mistake a floor for a measurement.
    """
    txns, reached = _walk(addr)
    if not txns:
        return {"first_seen": None, "age_s": None, "exact": False,
                "why": "no history"}
    first = min(t["timestamp"] for t in txns if t.get("timestamp"))
    ref = at_ts or int(time.time())
    age = ref - first
    # ⛔ A NEGATIVE AGE IS NOT AN AGE. It means the walk stopped before reaching
    # this wallet's first transaction, so the oldest thing we saw is NEWER than
    # the moment we are measuring against. Returning -0.1h there would be a
    # nonsense number wearing the costume of a measurement, which is the exact
    # failure this codebase keeps repeating. Found on WOFI, whose deployer has
    # over 1,200 transactions after a launch we were trying to date.
    if age < 0:
        return {"first_seen": first, "age_s": None, "exact": False,
                "n_txns_seen": len(txns),
                "why": "history walk did not reach wallet creation; "
                       "oldest transaction seen is newer than the launch"}
    return {"first_seen": first, "age_s": age, "exact": reached,
            "n_txns_seen": len(txns), "why": None}


def is_router(addr):
    """Crude, and only ever used to weaken a conclusion - see ROUTER_PREFIXES."""
    return bool(addr) and any(addr.startswith(p) for p in ROUTER_PREFIXES)


def funding_chain(addr, hops=3, max_pages=MAX_PAGES):
    """⭐ Walk back through whoever funded this wallet, up to `hops`.

    This is the answer to the fresh-wallet-per-launch evasion. Each hop takes
    the EARLIEST inbound native SOL transfer and follows it. Exchange hot
    wallets terminate the useful part of the chain - they fund everyone, so
    they carry no signal - and are not flagged here, only reported, because
    labelling them needs a list this module does not have.
    """
    chain = []
    seen = {addr}
    cur = addr
    for _ in range(hops):
        txns, _r = _walk(cur, max_pages=max_pages)
        if not txns:
            break
        inbound = []
        for t in txns:
            for nt in (t.get("nativeTransfers") or []):
                if nt.get("toUserAccount") == cur and (nt.get("amount") or 0) > 0:
                    inbound.append((t.get("timestamp"), nt.get("fromUserAccount"),
                                    nt["amount"] / 1e9))
        inbound = [x for x in inbound if x[1] and x[1] not in seen]
        if not inbound:
            break
        inbound.sort()
        ts, funder, amt = inbound[0]
        # `exact` is False when the walk hit MAX_PAGES: the earliest inbound WE
        # SAW is then not necessarily the transfer that funded the wallet.
        chain.append({"funder": funder, "ts": ts, "sol": round(amt, 6),
                      "exact": _r})
        seen.add(funder)
        cur = funder
    return chain


def track_record(mint, follow_funding=True):
    """⭐ Full deployer profile for one token. ~3-8s. Decision-point only.

    Returns the deployer, their back catalogue, how old their wallet was when
    they launched this, and - when the wallet is fresh - the funding chain and
    the back catalogue of whoever paid for it.
    """
    out = {"mint": mint, "ts": int(time.time()),
           "deployer": None, "deployer_resolved": False,
           "prior_launches": None, "launch_list": None,
           "wallet_age_s_at_launch": None, "wallet_age_exact": None,
           "had_prior_activity": None,
           "fresh_wallet": None, "funding_chain": None,
           "funder_launches": None, "verdict": None}
    d = deployer(mint)
    out["deployer"] = d.get("deployer")
    out["deployer_resolved"] = d.get("resolved")
    if not d.get("resolved"):
        out["verdict"] = "UNRESOLVED"
        return out
    addr = d["deployer"]
    L = launches(addr)
    this = None
    at = None
    if L.get("resolved"):
        lst = L["launches"]
        out["launch_list"] = lst
        out["prior_launches"] = max(0, len(lst) - 1)   # exclude this one
        this = next((x for x in lst if x["mint"] == mint), None)
        at = this["ts"] if this else None
    # Cheap, exact, and the question actually being asked.
    this_sig = this.get("signature") if this else None
    if this_sig:
        ab = activity_before(addr, this_sig)
        out["had_prior_activity"] = ab.get("had_prior")
        if ab.get("had_prior") is not None:
            out["fresh_wallet"] = not ab["had_prior"]
    a = wallet_age(addr, at_ts=at)
    out["wallet_age_s_at_launch"] = a.get("age_s")
    out["wallet_age_exact"] = a.get("exact")
    if out["fresh_wallet"] is None and a.get("age_s") is not None:
        out["fresh_wallet"] = a["age_s"] < FRESH_WALLET_SECONDS
    if follow_funding and out["fresh_wallet"]:
        ch = funding_chain(addr)
        out["funding_chain"] = ch
        if ch:
            fl = launches(ch[0]["funder"])
            out["funder_launches"] = fl.get("n") if fl.get("resolved") else None
    n = out["prior_launches"]
    fn = out["funder_launches"]
    if n is None or out["fresh_wallet"] is None:
        out["verdict"] = "UNKNOWN_HISTORY"
    elif n == 0 and not out["fresh_wallet"]:
        out["verdict"] = "FIRST_LAUNCH_AGED_WALLET"
    elif out["fresh_wallet"] and (fn or 0) > 1:
        out["verdict"] = "FRESH_WALLET_FUNDED_BY_SERIAL_LAUNCHER"
    elif out["fresh_wallet"]:
        out["verdict"] = "FRESH_WALLET"
    elif n >= 3:
        out["verdict"] = "SERIAL_LAUNCHER"
    else:
        out["verdict"] = "SOME_HISTORY"
    return out


def first_buyers(mint, n=20, max_pages=8, exclude=()):
    """⭐ The first `n` wallets to receive this token, and who funded them.

    Frank: "Ten wallets funded from one wallet is a bundle wearing a costume."
    That is the same edge funding_chain() walks for the deployer, so it is the
    same traversal reused rather than a second implementation.

    ⚠️ Requires paging to the OLDEST transactions on the mint. Feasible on a
    young token, which is the case that matters - we check at graduation, not
    years later. `truncated` is True when the walk did not reach the beginning,
    and a truncated list is NOT the first buyers, it is merely early ones.
    """
    sigs = []
    before = None
    for _ in range(max_pages):
        body = json.dumps({"jsonrpc": "2.0", "id": 1,
                           "method": "getSignaturesForAddress",
                           "params": [mint, {"limit": 1000, "before": before}]}).encode()
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                config.helius_rpc(), data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": UA["User-Agent"]}), timeout=45)
            res = json.loads(r.read()).get("result") or []
        except Exception as e:
            return {"buyers": None, "truncated": None, "why": str(e)[:90]}
        if not res:
            break
        sigs += res
        before = res[-1]["signature"]
        if len(res) < 1000:
            break
    else:
        return {"buyers": None, "truncated": True,
                "why": "mint too busy to reach its first transactions"}
    if not sigs:
        return {"buyers": None, "truncated": False, "why": "no signatures"}
    sigs.sort(key=lambda x: (x.get("slot") or 0))
    seen, buyers = set(), []
    # /v0/transactions takes up to 100 signatures per call. Doing this one at a
    # time cost 72 seconds on a single young token; batching makes it two calls.
    batch = [sg["signature"] for sg in sigs[:200]]
    enriched = []
    for i in range(0, len(batch), 100):
        enriched += _v0_txs(batch[i:i + 100]) or []
    enriched.sort(key=lambda t: (t.get("slot") or 0))
    for b in enriched:
        for tt in (b.get("tokenTransfers") or []):
            if tt.get("mint") != mint:
                continue
            who = tt.get("toUserAccount")
            # ⛔ The pool is not a buyer. The first token transfer on any mint
            # goes into the pool account, and counting it produced a "buyer"
            # that was the pair address itself on the first live run.
            if who in exclude or who == mint:
                continue
            if who and who not in seen:
                seen.add(who)
                buyers.append({"wallet": who, "ts": b.get("timestamp"),
                               "amount": tt.get("tokenAmount")})
        if len(buyers) >= n:
            break
    return {"buyers": buyers[:n], "truncated": False, "why": None}


def _v0_txs(signatures):
    """Enrich up to 100 signatures in one call."""
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


def buyer_funding_overlap(mint, n=20, exclude=()):
    """⭐ Do the first buyers share a funder? That is a bundle, not a crowd.

    ⚠️ Unless the shared funder is a router, in which case it is a queue at the
    same till. `router_funder` says which, and a True there means this result
    carries NO bundle evidence either way.
    """
    fb = first_buyers(mint, n=n, exclude=exclude)
    if not fb.get("buyers"):
        return {"shared_funder": None, "why": fb.get("why") or "no buyers found"}
    funders = {}
    for b in fb["buyers"]:
        ch = funding_chain(b["wallet"], hops=1, max_pages=3)
        f = ch[0]["funder"] if ch else None
        if f:
            funders.setdefault(f, []).append(b["wallet"])
    if not funders:
        return {"shared_funder": None, "why": "no funding edges resolved"}
    top, wallets = max(funders.items(), key=lambda kv: len(kv[1]))
    router = is_router(top)
    return {"n_buyers": len(fb["buyers"]), "distinct_funders": len(funders),
            "top_funder": top, "top_funder_count": len(wallets),
            "router_funder": router,
            "shared_funder": (len(wallets) > 1) and not router,
            "concentration": len(wallets) / max(1, len(fb["buyers"])),
            "why": "top funder looks like a router; no bundle evidence"
                   if router else None}


def lp_detail(mint):
    """LP settings: burned vs locked vs neither, and how much supply is pooled.

    Sourced from RugCheck, which already exposes lockers, LP providers and
    market data - see docs/EXISTING_TOOLS.md. ⛔ Unknown stays None: "we could
    not read the lock state" is not "unlocked".
    """
    st, b = _get(RUGCHECK % mint)
    if st != 200 or not b:
        return {"resolved": False, "why": "rugcheck HTTP %s" % st}
    lockers = b.get("lockers") or {}
    markets = b.get("markets") or []
    lp_locked_pct = None
    for m in markets:
        lp = m.get("lp") or {}
        if lp.get("lpLockedPct") is not None:
            lp_locked_pct = lp.get("lpLockedPct")
            break
    return {"resolved": True,
            "n_lockers": len(lockers) if isinstance(lockers, dict) else None,
            "locker_scan": b.get("lockerScanStatus"),
            "lp_locked_pct": lp_locked_pct,
            "total_lp_providers": b.get("totalLPProviders"),
            "total_market_liquidity": b.get("totalMarketLiquidity"),
            "mint_authority": b.get("mintAuthority"),
            "freeze_authority": b.get("freezeAuthority"),
            "why": None}


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for m in sys.argv[1:]:
        print(json.dumps(track_record(m), indent=1))
