"""Headline numbers derived from chain state, not from a pair's self-report.

READ `docs/LIQUIDITY.md` AND `docs/TRUSTED_FIELDS.md` FIRST.

WHY THIS MODULE EXISTS. Every number this project has ever led with came from
Dexscreener's `liquidity.usd` or `fdv`, and that field overstates exitable size
by a median 781x. Conclusions built on it - the 2.10% base rate, the lift
figures, the detectors' precision - inherit the error. This module is the
replacement source, and its contract is different in one specific way:

    ⛔ AN UNKNOWN IS RETURNED AS None, NEVER AS 0.

That is not a style preference. `exit_depth_usd` is 0.0 on 76% of stored rows,
and a 0 that means "not measured" is indistinguishable from a 0 that means
"empty pool" once it is written to disk. Five separate failures in this repo
came from an absent measurement rendering as a real value. Every function here
fails closed and says why.

WHAT EACH FIELD COSTS, measured 2026-09-17 on Frank's machine:

    round_trip()   ~370ms   two Jupiter quotes, free, no key, ~60 quotes/min
    supply()       ~200ms   one Helius getTokenSupply
    holder_count() ~850ms   Helius DAS, 3 pages for a ~1,400-holder token

⚠️ THE RATE LIMIT IS THE DESIGN CONSTRAINT. Jupiter's free endpoint serves
about 97 calls and then returns 429 on everything with no partial service. So
these are DECISION-POINT calls - watchlist entry, paper entry/exit, a
graduation - and must never be put on the per-row scan path. The bucket below
enforces that rather than trusting callers to remember.
"""
import json
import os
import sys
import threading
import time
import urllib.error
import urllib.request

import config

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
JUP_QUOTE = "https://lite-api.jup.ag/swap/v1/quote"

# Measured wall: ~97 calls then hard 429. 55/min leaves headroom for the burst
# allowance to refill and keeps a round trip (2 calls) affordable.
JUP_PER_MIN = 55
DEFAULT_PROBE_USD = 100

# Round-trip cost bands. Pre-committed here so they cannot be tuned per result.
TRADEABLE_MAX_PCT = 10.0
COSTLY_MAX_PCT = 50.0


class _Bucket:
    """Token bucket. Shared by every Jupiter caller in the process.

    A per-callsite limiter would not work: the limit is per-IP, so two loops
    each politely pacing themselves still add up to a 429. One bucket at module
    scope is the only version that is actually correct.
    """

    def __init__(self, per_min):
        self.cap = float(per_min)
        self.tokens = float(per_min)
        self.rate = per_min / 60.0
        self.t = time.time()
        self.lock = threading.Lock()

    def take(self, n=1):
        with self.lock:
            while True:
                now = time.time()
                self.tokens = min(self.cap, self.tokens + (now - self.t) * self.rate)
                self.t = now
                if self.tokens >= n:
                    self.tokens -= n
                    return
                time.sleep(max(0.05, (n - self.tokens) / self.rate))


_JUP = _Bucket(JUP_PER_MIN)


def _get(url, headers=None, timeout=15):
    """GET returning (status, parsed_json_or_error_text). Never raises."""
    try:
        r = urllib.request.urlopen(
            urllib.request.Request(url, headers=headers or UA), timeout=timeout)
        return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        try:
            return e.code, json.loads(e.read())
        except Exception:
            return e.code, None
    except Exception as e:
        return None, str(e)[:120]


def _rpc(method, params, timeout=40, tries=3):
    """Helius JSON-RPC. Returns (result, error_string)."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1,
                       "method": method, "params": params}).encode()
    last = "no attempt"
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                config.helius_rpc(), data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": UA["User-Agent"]}), timeout=timeout)
            d = json.loads(r.read())
            if "error" in d:
                return None, str(d["error"])[:120]
            return d.get("result"), None
        except Exception as e:
            last = str(e)[:120]
            time.sleep(1.0 + i)
    return None, last


def _quote(in_mint, out_mint, amount, slippage_bps=5000, tries=4):
    """One Jupiter quote. Returns (body, error). Backs off on 429."""
    url = ("%s?inputMint=%s&outputMint=%s&amount=%d&slippageBps=%d"
           % (JUP_QUOTE, in_mint, out_mint, int(amount), slippage_bps))
    for i in range(tries):
        _JUP.take()
        st, b = _get(url)
        if st == 200 and isinstance(b, dict) and b.get("outAmount"):
            return b, None
        if st == 429:
            time.sleep(6 + i * 6)
            continue
        if isinstance(b, dict) and b.get("errorCode"):
            return None, b["errorCode"]
        return None, "HTTP %s" % st
    return None, "rate limited"


def round_trip(mint, usd=DEFAULT_PROBE_USD):
    """⭐ What you actually get back if you buy $usd and sell it again, now.

    This is the only liquidity measure in the project that is realizable rather
    than nominal. It needs no price, no supply and no pool layout: buy a fixed
    dollar amount, then sell exactly what that returned. Both legs are quotes -
    NOTHING IS EXECUTED and no wallet is involved.

    Returns a dict. `verdict` is one of:

        TRADEABLE      round trip costs < 10%
        COSTLY         10-50%
        TOTAL_LOSS     > 50% - the pool takes essentially everything
        NO_SELL_ROUTE  can be bought, cannot be sold. The one-sided shape.
        NO_BUY_ROUTE   not routable at all

    ⚠️ NO_SELL_ROUTE and NO_BUY_ROUTE are ANSWERS, not errors, and callers must
    not coerce them to 0. On the 141 recorded "wins" this separated 8 tradeable
    contracts from 126 that cannot be exited (docs/LIQUIDITY.md section 5).
    """
    out = {"mint": mint, "probe_usd": usd, "ts": int(time.time()),
           "usd_back": None, "rt_cost_pct": None, "verdict": None,
           "venues": None, "px_per_raw": None, "error": None}
    buy, err = _quote(USDC, mint, usd * 1_000_000)
    if not buy:
        out["verdict"] = "NO_BUY_ROUTE"
        out["error"] = err
        return out
    out["venues"] = [((h.get("swapInfo") or {}).get("label") or "?")
                     for h in (buy.get("routePlan") or [])]
    # Price implied by the BUY leg, in USD per raw token unit. Kept here so
    # market_cap() never has to spend a third quote to recover it.
    out["px_per_raw"] = usd / float(buy["outAmount"])
    sell, err = _quote(mint, USDC, int(buy["outAmount"]))
    if not sell:
        out["verdict"] = "NO_SELL_ROUTE"
        out["error"] = err
        return out
    back = int(sell["outAmount"]) / 1e6
    cost = (usd - back) / usd * 100.0
    out["usd_back"] = round(back, 4)
    out["rt_cost_pct"] = round(cost, 4)
    out["verdict"] = ("TRADEABLE" if cost < TRADEABLE_MAX_PCT
                      else "COSTLY" if cost < COSTLY_MAX_PCT
                      else "TOTAL_LOSS")
    return out


def supply(mint):
    """(ui_supply, decimals) from chain, or (None, None)."""
    res, err = _rpc("getTokenSupply", [mint])
    v = (res or {}).get("value") or {}
    if not v:
        return None, None
    try:
        return float(v.get("uiAmount")), int(v.get("decimals"))
    except (TypeError, ValueError):
        return None, None


def market_cap(mint, usd=DEFAULT_PROBE_USD, rt=None):
    """Supply from chain x the price a buyer would actually pay.

    ⚠️ On pump.fun-shaped launches supply is fixed and fully circulating, so
    this is both FDV and market cap. That stops being true anywhere supply is
    locked or vesting; this returns FDV and says so in the key name rather than
    guessing at a circulating figure it cannot see.

    Returns None when either input is missing. It does NOT fall back to a
    reported price - substituting a self-reported number into a field whose
    whole purpose is to avoid self-reports is the bug this module replaces.
    """
    sup, dec = supply(mint)
    if sup is None:
        return None
    rt = rt if rt is not None else round_trip(mint, usd)
    px = rt.get("px_per_raw")
    if not px:
        return None
    return sup * (10 ** dec) * px


def holder_count(mint, max_pages=25):
    """⭐ Distinct wallets holding a non-zero balance. None if unreadable.

    Frank: "A coin can bond with 2 holders. Not something we want to deal with."
    He is right, and it is the sharpest separator measured in this project:
    median holders is 1,350 for contracts that can actually be sold and 3 for
    contracts that return nothing (docs/TRUSTED_FIELDS.md section 1).

    ⚠️ A token account is NOT a holder. Helius already omits zero-balance
    accounts and the sampled tokens had no wallet holding two accounts for the
    same mint - but that is a property of that sample, not a guarantee, so this
    deduplicates by owner and filters on balance anyway.

    `truncated` is True when the mint has more holders than max_pages covers.
    A truncated count is a FLOOR, not a count, and callers must not compare it
    against a threshold as if it were exact.
    """
    owners = {}
    cursor = None
    pages = 0
    while True:
        p = {"mint": mint, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        res, err = _rpc("getTokenAccounts", p)
        if err:
            return {"holders": None, "truncated": False, "error": err}
        accts = (res or {}).get("token_accounts") or []
        for a in accts:
            try:
                amt = float(a.get("amount") or 0)
            except (TypeError, ValueError):
                continue
            if amt > 0:
                o = a.get("owner")
                owners[o] = owners.get(o, 0.0) + amt
        pages += 1
        cursor = (res or {}).get("cursor")
        if not cursor or not accts or pages >= max_pages:
            break
    if not owners:
        return {"holders": 0, "truncated": pages >= max_pages, "error": None}
    total = sum(owners.values())
    ranked = sorted(owners.values(), reverse=True)
    out = {"holders": len(owners), "truncated": pages >= max_pages,
           "error": None, "top1_pct": ranked[0] / total * 100.0}
    # ⚠️ Top-N is only meaningful when there are materially more than N holders.
    # Computed unconditionally it returns 100% for everything, which is what my
    # first version did - see docs/TRUSTED_FIELDS.md section 3.
    if len(owners) > 20:
        out["top10_pct"] = sum(ranked[:10]) / total * 100.0
    else:
        out["top10_pct"] = None
    return out


def trusted(mint, usd=DEFAULT_PROBE_USD, want_holders=True):
    """Every trusted field for one contract address. ~1.2s, or ~2s with holders.

    ⛔ DECISION-POINT ONLY. At ~60 Jupiter quotes/min this cannot run on the
    per-row scan path, and holder enumeration adds a second per token. Call it
    on a graduation, a crossing, a watchlist entry or a paste into check.py.
    """
    rt = round_trip(mint, usd)
    sup, dec = supply(mint)
    out = {"mint": mint, "ts": int(time.time()),
           "exit_verdict": rt["verdict"],
           "exit_realizable_usd": rt["usd_back"],
           "exit_rt_cost_pct": rt["rt_cost_pct"],
           "exit_venues": rt["venues"],
           "supply": sup, "decimals": dec,
           "fdv_onchain_usd": None,
           "holders": None, "holders_truncated": None, "top10_pct": None}
    if sup is not None and rt.get("usd_back"):
        out["fdv_onchain_usd"] = market_cap(mint, usd, rt=rt)
    if want_holders:
        h = holder_count(mint)
        out["holders"] = h.get("holders")
        out["holders_truncated"] = h.get("truncated")
        out["top10_pct"] = h.get("top10_pct")
    return out


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for m in sys.argv[1:]:
        print(json.dumps(trusted(m), indent=1))
