"""The safety verdict on every tracked token. The rule is PRECOMMIT_safety_v1.md.

Frank, 2026-09-19: "those top coins need to also pass safety tests. We can't
have honeypots and fake volume." Every token the universe tracks - member,
refused or candidate - carries one of DANGER / WARN / NO FLAGS / UNKNOWN, the
checks behind it, and the list of what was NOT checked.

⛔ A token that fails is FLAGGED, never dropped. "Running and dangerous" is the
information. ⛔ NO FLAGS is never "safe": it always travels with `not_checked`,
and fake volume is ALWAYS in that list because no test for it survived
validation (docs/VOLUME_INTEGRITY.md 3c, 3e).

Inputs, cheapest first, each cached on the entry with its own timestamp:
    gate      the universe's $100 round trip (S1)             - already there
    chain     mint account, jsonParsed, 100 per call (S2-S4)  - every 24h
    dex       Dexscreener most-liquid pair, 30 per call (S5-S6) - every refresh
    rugcheck  keyless report, <= 1/s, optional (S9, S11)      - every 24h
Jupiter's holders and top-holder share (S8) and cap backing (S7) come from the
universe snapshot. Unknown is None and is listed; it never passes.
"""
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel safety; +https://crypto-intel-one-eta.vercel.app)",
      "Accept": "application/json", "Content-Type": "application/json"}
DEX_BATCH = 30            # Dexscreener tokens/v1 takes 30 addresses
CHAIN_BATCH = 100         # getMultipleAccounts caps at 100
CHAIN_EVERY_S = 24 * 3600
RUGCHECK_EVERY_S = 24 * 3600
RUGCHECK_GAP_S = float(os.environ.get("CRYPTO_RUGCHECK_GAP_S", "1.0"))   # their free tier is 3/s
GATE_STALE_S = 48 * 3600

# PRECOMMIT_safety_v1.md, table row by row. Changing one of these is a new
# version of the rule, not an edit.
FEE_DANGER_BPS = 1000                 # S4: transfer fee >= 10%
CAP_BACKING_WARN_PCT = 1.0            # S7
TOP_HOLDERS_WARN_PCT = 50.0           # S8
MIN_HOLDERS_WARN = 100                # S8
INSIDER_WARN_PCT = 10.0               # S9 - v1.1: not evaluable, see NOT_CHECKED_ALWAYS
LP_LOCKED_WARN_PCT = 50.0             # S11
# v1.1 (declared amendment, PRECOMMIT_safety_v1.md "Amendment v1.1"): issuer
# control is by design for these universe classes, so S2/S3 and the
# issuer-control extensions in S4 are shown as info, not DANGER/WARN.
ISSUER_CLASSES = ("base", "stock")
RULE_VERSION = "v1.1"
SELL_DANGER = ("TOTAL_LOSS", "NO_SELL_ROUTE")
SELL_WARN = ("COSTLY",)
NOT_CHECKED_ALWAYS = ("fake volume: no validated test (docs/VOLUME_INTEGRITY.md 3c, 3e)",
                      # v1.1: RugCheck's insider-network amount is not a share of
                      # supply (BONK 98%, one token 175%), so S9's insider clause
                      # cannot be evaluated and no other bundle source is validated.
                      "bundles / insiders: no valid source (PRECOMMIT_safety_v1.md amendment v1.1)")

CALLS = {"chain": 0, "dex": 0, "rugcheck": 0}
SOURCES = {}


def _http(url, body=None, timeout=20):
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(url, data=data, headers=UA, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=timeout) as r:
            return r.status, json.loads(r.read().decode("utf-8", "replace"))
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, type(e).__name__


def _note(label, ok, n=0, err=None):
    prev = SOURCES.get(label) or {"calls": 0, "n": 0, "errors": 0}
    SOURCES[label] = {"calls": prev["calls"] + 1, "n": prev["n"] + n,
                      "errors": prev["errors"] + (0 if ok else 1),
                      "last_error": err if not ok else prev.get("last_error")}


# --------------------------------------------------------------------------
# S2-S4: the mint account, from chain
# --------------------------------------------------------------------------
def parse_mint(acct):
    """One getMultipleAccounts jsonParsed value -> the facts S2-S4 need, or None."""
    if not isinstance(acct, dict):
        return None
    data = acct.get("data")
    if not isinstance(data, dict) or not isinstance(data.get("parsed"), dict):
        return None
    info = data["parsed"].get("info") or {}
    exts = {}
    for x in info.get("extensions") or []:
        if isinstance(x, dict) and x.get("extension"):
            exts[x["extension"]] = x.get("state") if isinstance(x.get("state"), dict) else {}
    fee = None
    if "transferFeeConfig" in exts:
        st = exts["transferFeeConfig"]
        bps = [((st.get(k) or {}).get("transferFeeBasisPoints")) for k in ("olderTransferFee", "newerTransferFee")]
        bps = [b for b in bps if isinstance(b, (int, float))]
        fee = max(bps) if bps else None
    delegate = (exts.get("permanentDelegate") or {}).get("delegate")
    hook = (exts.get("transferHook") or {}).get("programId")
    return {"program": data.get("program"),
            "mint_authority": info.get("mintAuthority"),
            "freeze_authority": info.get("freezeAuthority"),
            "extensions": sorted(exts),
            "transfer_fee_bps": fee,
            # an extension with no authority set cannot be used: record which are LIVE
            "permanent_delegate": delegate,
            "transfer_hook_program": hook,
            "default_state_frozen": (exts.get("defaultAccountState") or {}).get("accountState") == "frozen",
            "non_transferable": "nonTransferable" in exts,
            "pausable": "pausableConfig" in exts,
            "paused": bool((exts.get("pausableConfig") or {}).get("paused"))}


def chain_mints(mints, url=None):
    """{mint: facts | None}. None means the read failed - unknown, never clean."""
    out = {}
    mints = list(mints)
    for i in range(0, len(mints), CHAIN_BATCH):
        chunk = mints[i:i + CHAIN_BATCH]
        CALLS["chain"] += 1
        st, d = _http(url or config.helius_rpc(),
                      {"jsonrpc": "2.0", "id": 1, "method": "getMultipleAccounts",
                       "params": [chunk, {"encoding": "jsonParsed"}]}, timeout=30)
        vals = ((d or {}).get("result") or {}).get("value") if isinstance(d, dict) else None
        ok = isinstance(vals, list) and len(vals) == len(chunk)
        _note("chain.getMultipleAccounts", ok, len(chunk) if ok else 0,
              None if ok else (f"HTTP {st}" if not isinstance(d, str) else d))
        for j, m in enumerate(chunk):
            out[m] = parse_mint(vals[j]) if ok else None
    return out


# --------------------------------------------------------------------------
# S5-S6: the most liquid pair, from Dexscreener
# --------------------------------------------------------------------------
def pair_facts(p):
    liq = ((p.get("liquidity") or {}).get("usd"))
    tx = (p.get("txns") or {}).get("h1") or {}
    b, s = tx.get("buys"), tx.get("sells")
    return {"pair": p.get("pairAddress"), "dex": p.get("dexId"), "liq": liq,
            "fdv": p.get("fdv"), "mcap": p.get("marketCap"),
            "buys_h1": b, "sells_h1": s,
            "txns_h1": (b + s) if isinstance(b, int) and isinstance(s, int) else None}


def dex_pairs(mints):
    """{mint: facts of its most liquid Solana pair | None}. Absent from the reply = None."""
    out = {m: None for m in mints}
    mints = list(mints)
    for i in range(0, len(mints), DEX_BATCH):
        chunk = mints[i:i + DEX_BATCH]
        CALLS["dex"] += 1
        st, d = _http("https://api.dexscreener.com/tokens/v1/solana/" + ",".join(chunk))
        ok = isinstance(d, list)
        _note("dexscreener.tokens", ok, len(d) if ok else 0, None if ok else f"HTTP {st}")
        if not ok:
            continue
        best = {}
        for p in d:
            m = ((p.get("baseToken") or {}).get("address"))
            if m not in out or p.get("chainId") != "solana":
                continue
            liq = ((p.get("liquidity") or {}).get("usd")) or 0
            if m not in best or liq > (((best[m].get("liquidity") or {}).get("usd")) or 0):
                best[m] = p
        for m, p in best.items():
            out[m] = pair_facts(p)
    return out


def d1(f):
    """detector.d1 on pair facts. Same conjunction, same fields - see detector.py."""
    import detector
    return detector.d1({"liq": f.get("liq"), "fdv": f.get("fdv"),
                        "sells_h1": f.get("sells_h1"), "buys_h1": f.get("buys_h1")})


def d2(f):
    import detector
    return detector.d2({"liq": f.get("liq"), "txns_h1": f.get("txns_h1")})


# --------------------------------------------------------------------------
# S9, S11: RugCheck, attributed, optional
# --------------------------------------------------------------------------
def rugcheck(mint):
    CALLS["rugcheck"] += 1
    st, r = _http(f"https://api.rugcheck.xyz/v1/tokens/{mint}/report", timeout=20)
    ok = isinstance(r, dict)
    _note("rugcheck.report", ok, 1 if ok else 0, None if ok else f"HTTP {st}")
    if not ok:
        return None
    tok = r.get("token") or {}
    supply, dec = tok.get("supply"), tok.get("decimals")
    ins = []
    for n in r.get("insiderNetworks") or []:
        amt = n.get("tokenAmount")
        pct = (100.0 * amt / supply) if isinstance(amt, (int, float)) and supply else None
        ins.append({"size": n.get("size"), "type": n.get("type"),
                    "pct_supply": round(pct, 2) if pct is not None else None})
    mk = sorted(r.get("markets") or [], key=lambda x: -((x.get("lp") or {}).get("lpLockedUSD") or 0)
                - ((x.get("lp") or {}).get("quoteUSD") or 0))
    lp = (mk[0].get("lp") or {}) if mk else {}
    return {"rugged": r.get("rugged"),
            "score_normalised": r.get("score_normalised"),
            "risks": [{"name": x.get("name"), "level": x.get("level")} for x in r.get("risks") or []],
            "insider_networks": ins,
            "graph_insiders": r.get("graphInsidersDetected"),
            "lp_locked_pct": lp.get("lpLockedPct") if mk else None,
            "market_type": mk[0].get("marketType") if mk else None,
            "decimals": dec}


# --------------------------------------------------------------------------
# The verdict. Pure: every input is an argument, so it is tested offline.
# --------------------------------------------------------------------------
def _c(level, detail, source):
    return {"level": level, "detail": detail, "source": source}


def verdict(e, now):
    """The PRECOMMIT_safety_v1 verdict for one universe entry, from what is cached on it."""
    checks, not_checked = {}, list(NOT_CHECKED_ALWAYS)
    cls = e.get("class") or "token"
    g = e.get("gate") or {}
    last = e.get("last") or {}

    # S1 sellable
    v = g.get("verdict")
    if v is None:
        checks["S1"] = _c("unknown", "never quoted", "jupiter $100 round trip")
        not_checked.append("sellable: no round trip yet")
    elif v in SELL_DANGER:
        checks["S1"] = _c("danger", f"$100 round trip: {v}", "jupiter $100 round trip")
    elif v in SELL_WARN:
        checks["S1"] = _c("warn", f"$100 round trip loses {g.get('rt_cost_pct')}%", "jupiter $100 round trip")
    elif v == "TRADEABLE":
        checks["S1"] = _c("ok", f"$100 round trip loses {g.get('rt_cost_pct')}%", "jupiter $100 round trip")
    else:
        checks["S1"] = _c("unknown", f"$100 round trip: {v}", "jupiter $100 round trip")
    if v is not None and g.get("ts") and now - g["ts"] > GATE_STALE_S and checks["S1"]["level"] == "ok":
        checks["S1"] = _c("warn", checks["S1"]["detail"] + f"; checked {round((now - g['ts']) / 3600)}h ago",
                          "jupiter $100 round trip")

    # S2-S4 from the mint account
    ch = (e.get("chain") or {}).get("facts")
    if ch is None:
        not_checked.append("mint account (authorities, extensions): not read")
    else:
        issuer = cls in ISSUER_CLASSES
        if ch.get("freeze_authority"):
            checks["S2"] = _c("info" if issuer else "danger",
                              "freeze authority active: the issuer can freeze holders"
                              + (f" (a {cls}: issuer-controlled by design)" if issuer else ""), "chain")
        else:
            checks["S2"] = _c("ok", "no freeze authority", "chain")
        if ch.get("mint_authority"):
            checks["S3"] = _c("info" if issuer else "warn", "mint authority active: supply can grow", "chain")
        else:
            checks["S3"] = _c("ok", "no mint authority", "chain")
        bad, warn, info = [], [], []
        ctl = []
        if ch.get("permanent_delegate"):
            ctl.append("permanent delegate (can move anyone's tokens)")
        if ch.get("pausable"):
            ctl.append("pausable" + (" and PAUSED" if ch.get("paused") else ""))
        if ch.get("default_state_frozen"):
            ctl.append("new accounts start frozen")
        (info if issuer else bad).extend(ctl)
        if ch.get("non_transferable"):
            bad.append("non-transferable")
        fee = ch.get("transfer_fee_bps")
        if isinstance(fee, (int, float)) and fee >= FEE_DANGER_BPS:
            bad.append(f"transfer fee {fee / 100:g}%")
        elif isinstance(fee, (int, float)) and fee > 0:
            warn.append(f"transfer fee {fee / 100:g}%")
        if ch.get("transfer_hook_program"):
            warn.append("transfer hook (custom code runs on every transfer)")
        checks["S4"] = (_c("danger", "; ".join(bad + warn), "chain") if bad
                        else _c("warn", "; ".join(warn), "chain") if warn
                        else _c("info", "; ".join(info) + f" (a {cls}: issuer-controlled by design)", "chain") if info
                        else _c("ok", "no risky Token-2022 extension" if ch.get("extensions") else "classic SPL token",
                                "chain"))

    # S5-S6 from the most liquid pair
    dx = (e.get("dex") or {}).get("facts")
    if dx is None:
        not_checked.append("D1 fake-pool: no pair data")
    else:
        checks["S5"] = (_c("danger", "D1: pool ~ entire supply, 10+ buys and no sell in the last hour", "dexscreener + detector.d1")
                        if d1(dx) else _c("ok", "D1 does not fire", "dexscreener + detector.d1"))
        if d2(dx):
            checks["S6"] = _c("info", "D2 fires (unvalidated hypothesis; affects nothing)", "dexscreener + detector.d2")

    # S7 the farm signature
    cb = last.get("cap_backing_pct")
    farm = ("graduation" in (e.get("sources") or []) and (e.get("ticker_contracts") or 0) > 1)
    if cb is None:
        not_checked.append("cap backing: no liquidity or cap reading")
    elif cb < CAP_BACKING_WARN_PCT and farm:
        checks["S7"] = _c("warn", f"cap {cb}% backed, graduated recently, ticker shared by "
                                  f"{e.get('ticker_contracts')} contracts: the cap is likely fiction", "universe")
    else:
        checks["S7"] = _c("info" if cb < CAP_BACKING_WARN_PCT else "ok", f"cap {cb}% backed", "universe")

    # S8 holders
    top, n = last.get("top_holders_pct"), last.get("holders")
    if top is None and n is None:
        not_checked.append("holders: no reading")
    else:
        w = []
        if isinstance(top, (int, float)) and top > TOP_HOLDERS_WARN_PCT:
            w.append(f"top holders own {top}%")
        if isinstance(n, int) and n < MIN_HOLDERS_WARN:
            w.append(f"only {n} holders")
        checks["S8"] = (_c("warn", "; ".join(w), "jupiter") if w
                        else _c("ok", f"{n} holders, top holders {top}%", "jupiter"))

    # S9, S11 RugCheck
    rc = (e.get("rugcheck") or {}).get("facts")
    if rc is None:
        not_checked.append("RugCheck: not fetched")
    else:
        dangers = [x["name"] for x in rc.get("risks") or [] if x.get("level") == "danger"]
        if rc.get("rugged"):
            checks["S9"] = _c("danger", "RugCheck marks it RUGGED", "rugcheck")
        elif dangers:
            checks["S9"] = _c("warn", "; ".join(f"RugCheck: {d}" for d in dangers), "rugcheck")
        else:
            checks["S9"] = _c("ok", "RugCheck: no danger-level risk", "rugcheck")
        lp = rc.get("lp_locked_pct")
        if lp is None:
            checks["S11"] = _c("info", "LP lock: not reported for this market type", "rugcheck")
        else:
            checks["S11"] = _c("warn" if lp < LP_LOCKED_WARN_PCT else "ok", f"LP {round(lp)}% locked", "rugcheck")

    levels = [c["level"] for c in checks.values()]
    if "danger" in levels:
        level = "DANGER"
    elif (checks.get("S1") or {}).get("level") == "unknown":
        level = "UNKNOWN"
    elif "warn" in levels:
        level = "WARN"
    else:
        level = "NO FLAGS"
    return {"level": level, "rule": "PRECOMMIT_safety_v1.md " + RULE_VERSION, "computed_ts": int(now),
            "reasons": [f"{k}: {c['detail']}" for k, c in sorted(checks.items()) if c["level"] in ("danger", "warn")],
            "checks": checks, "not_checked": not_checked}


# --------------------------------------------------------------------------
# Refresh: fetch what is due, cache it on the entry, recompute every verdict
# --------------------------------------------------------------------------
def refresh(tokens, now, budget_s=120, rugcheck_budget_s=None, dex=True, rc=True, chain_url=None):
    """Recompute `safety` on every entry. Fetches only what is due, inside budget_s.

    Returns stats. What did not fit is counted by input, never silent (rule 15)."""
    t0 = time.time()
    tracked = [m for m, e in tokens.items() if e.get("status") in ("member", "refused", "candidate")]
    due_chain = [m for m in tracked if now - ((tokens[m].get("chain") or {}).get("ts") or 0) > CHAIN_EVERY_S]
    stats = {"tracked": len(tracked), "chain_due": len(due_chain), "chain_read": 0,
             "dex_read": 0, "rugcheck_due": 0, "rugcheck_read": 0}
    if due_chain:
        got = chain_mints(due_chain, url=chain_url)
        for m, f in got.items():
            if f is not None or not tokens[m].get("chain"):
                tokens[m]["chain"] = {"facts": f, "ts": int(now) if f is not None else 0}
            stats["chain_read"] += f is not None
    if dex and time.time() - t0 < budget_s:
        got = dex_pairs(tracked)
        for m, f in got.items():
            tokens[m]["dex"] = {"facts": f, "ts": int(now)}
            stats["dex_read"] += f is not None
    if rc:
        due = sorted((m for m in tracked
                      if now - ((tokens[m].get("rugcheck") or {}).get("ts") or 0) > RUGCHECK_EVERY_S),
                     key=lambda m: ((tokens[m].get("rugcheck") or {}).get("ts") or 0,
                                    0 if tokens[m].get("trending") else 1))
        stats["rugcheck_due"] = len(due)
        rb = budget_s if rugcheck_budget_s is None else rugcheck_budget_s
        for m in due:
            if time.time() - t0 > rb:
                break
            f = rugcheck(m)
            if f is not None:
                tokens[m]["rugcheck"] = {"facts": f, "ts": int(now)}
                stats["rugcheck_read"] += 1
            time.sleep(RUGCHECK_GAP_S)
    lv = {}
    for m in tracked:
        tokens[m]["safety"] = verdict(tokens[m], now)
        lv[tokens[m]["safety"]["level"]] = lv.get(tokens[m]["safety"]["level"], 0) + 1
    stats["levels"] = lv
    stats["rugcheck_deferred"] = stats["rugcheck_due"] - stats["rugcheck_read"]
    stats["seconds"] = round(time.time() - t0, 1)
    stats["sources"] = dict(SOURCES)
    return stats
