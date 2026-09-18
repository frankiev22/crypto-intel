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

# Keyed endpoint when a key exists, keyless otherwise. Both return identical
# quotes - verified 2026-09-17, same outAmount to the unit on the same token.
JUP_QUOTE_KEYED = "https://api.jup.ag/swap/v1/quote"
JUP_QUOTE_FREE = "https://lite-api.jup.ag/swap/v1/quote"

# ⚠️ MEASURED 2026-09-17, AND THE KEY DOES NOT BUY SPEED.
#
#   keyless : ~97 calls, then a hard 429 on everything. No partial service.
#   keyed   : 45/45 at 1.0 req/s. At 2 req/s, 30/45. At 3 req/s, 23/45.
#             Effective ceiling ~1.1 req/s however hard it is pushed.
#
# So the key buys RELIABILITY and a refilling bucket, not throughput. The
# decision-point-only rule below still stands; this must not go on the scan path.
JUP_PER_MIN = 55

# Free tier is 25,000,000 credits/month. At 1 credit per quote and two quotes
# per round trip, that is ~12.5M round trips - about 17,000/hour sustained,
# which we cannot reach anyway at 1 req/s. Tracked so the claim stays checkable.
USAGE_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "_jupiter_usage.json")
JUP_FREE_CREDITS_MONTH = 25_000_000
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


def _bump_usage(n=1):
    """Count quotes against the monthly free allowance. Never fails a call."""
    try:
        month = time.strftime("%Y-%m")
        d = {}
        if os.path.exists(USAGE_PATH):
            with open(USAGE_PATH, encoding="utf-8") as fh:
                d = json.load(fh)
        if d.get("month") != month:
            d = {"month": month, "quotes": 0}
        d["quotes"] = d.get("quotes", 0) + n
        os.makedirs(os.path.dirname(USAGE_PATH), exist_ok=True)
        with open(USAGE_PATH, "w", encoding="utf-8") as fh:
            json.dump(d, fh)
        return d
    except Exception:
        return None


def usage():
    """Quotes used this calendar month, and the share of the free allowance."""
    try:
        with open(USAGE_PATH, encoding="utf-8") as fh:
            d = json.load(fh)
    except Exception:
        return {"month": time.strftime("%Y-%m"), "quotes": 0, "pct_of_free": 0.0}
    q = d.get("quotes", 0)
    return {"month": d.get("month"), "quotes": q,
            "pct_of_free": q / JUP_FREE_CREDITS_MONTH * 100.0}


def _quote(in_mint, out_mint, amount, slippage_bps=5000, tries=4):
    """One Jupiter quote. Returns (body, error). Backs off on 429."""
    k = config.key("jupiter")
    base = JUP_QUOTE_KEYED if k else JUP_QUOTE_FREE
    hdr = dict(UA, **({"x-api-key": k} if k else {}))
    url = ("%s?inputMint=%s&outputMint=%s&amount=%d&slippageBps=%d"
           % (base, in_mint, out_mint, int(amount), slippage_bps))
    for i in range(tries):
        _JUP.take()
        _bump_usage()
        st, b = _get(url, headers=hdr)
        if st == 200 and isinstance(b, dict) and b.get("outAmount"):
            return b, None
        if st == 429:
            time.sleep(6 + i * 6)
            continue
        if isinstance(b, dict) and b.get("errorCode"):
            return None, b["errorCode"]
        return None, "HTTP %s" % st
    return None, "rate limited"


# ---------------------------------------------------------------------------
# ⛔ JUPITER'S priceImpactPct IS A SENTINEL FOR LONGTAIL TOKENS, NOT A NUMBER.
#
# Measured 2026-09-18. For tokens it can reference-price it returns a small
# decimal fraction:
#     SOL   $100    '0.0000425409323578214859860615'   = 0.004%
#     SOL   $50,000 '0.0001166599206688746226102528'   = 0.012%
#     BONK  $100    '0.0014902943073434322217160682'   = 0.149%
#
# For memecoins it returns the string '1' - EXACTLY 1, meaning 100% impact -
# even when our own round trip on the same pool in the same second costs 0.76%.
# OpenClaw: verdict TRADEABLE, rt_cost_pct 0.7643, priceImpactPct '1'. Those
# cannot both be true. '1' means "no reference price", not "you lose everything".
#
# ⭐ So exactly 1.0 is UNKNOWN and is recorded as None (standing rule 5: unknown
# never renders as a value). A token that genuinely had 100% impact would return
# the same 1 and be indistinguishable, which is precisely why it cannot be
# trusted as a measurement either way.
#
# ⚠️ THE TRUSTWORTHY IMPACT NUMBER IS OUR OWN `rt_cost_pct`, computed from the
# two quoted legs: buy $100, sell back what it returned, compare. It needs no
# reference price and cannot be a sentinel. paperv3 records both and its
# pre-committed failure condition is written against the round-trip cost.
# ---------------------------------------------------------------------------
def _impact_pct(q):
    """Jupiter's price impact as a percent, or None when it did not compute one."""
    try:
        v = float(q.get("priceImpactPct"))
    except (TypeError, ValueError):
        return None
    if v >= 1.0:
        return None                      # sentinel, not a measurement
    return round(v * 100.0, 6)


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
           "venues": None, "px_per_raw": None, "error": None,
           # ⭐ Added 2026-09-18 for paperv3, which needs the FILL, not just the
           # verdict: the exact raw token quantity $usd bought, so the exit can
           # be quoted for that same quantity, and Jupiter's own price-impact
           # number for the buy leg. PRECOMMIT_paper_v3.md section 4 requires
           # both on every recorded fill - impact is "the number that was
           # invisible and killed the edge".
           "token_qty_raw": None, "price_impact_pct": None}
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
    out["token_qty_raw"] = int(buy["outAmount"])
    out["price_impact_pct"] = _impact_pct(buy)
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


def sell_quote(mint, raw_qty):
    """⭐ USD returned for selling exactly `raw_qty` raw token units, right now.

    The exit half of a paperv3 fill. round_trip() sells back exactly what its
    own buy leg returned; this sells a quantity bought EARLIER, which is the
    only way to price an exit against the position actually held.

    Returns a dict. ⛔ `usd_out` is None when no route exists - that is an
    ANSWER, not an error, and paperv3 records it as a total loss rather than
    skipping the close. Never coerce it to 0 at the call site; the distinction
    between "no route" and "zero recovered" is preserved in `verdict`.
    """
    out = {"mint": mint, "raw_qty": int(raw_qty), "ts": int(time.time()),
           "usd_out": None, "venues": None, "price_impact_pct": None,
           "verdict": None, "error": None}
    if int(raw_qty) <= 0:
        out["verdict"] = "NO_POSITION"
        out["error"] = "raw_qty must be positive"
        return out
    sell, err = _quote(mint, USDC, int(raw_qty))
    if not sell:
        out["verdict"] = "NO_SELL_ROUTE"
        out["error"] = err
        return out
    out["usd_out"] = round(int(sell["outAmount"]) / 1e6, 6)
    out["venues"] = [((h.get("swapInfo") or {}).get("label") or "?")
                     for h in (sell.get("routePlan") or [])]
    out["price_impact_pct"] = _impact_pct(sell)
    out["verdict"] = "QUOTED"
    return out


def depth_curve(mint, sizes=(10, 100, 500, 1000)):
    """⭐ Round-trip cost at several notionals. The shape IS the depth.

    A single number cannot express depth: a pool that costs 0.1% on $10 and 60%
    on $1,000 is a different asset from one that costs 3% at both. Frank trades
    $100 clips, so $100 is the number that matters - but the curve either side
    of it says whether that price survives him sizing up.

    Returns a list of dicts, one per size, each carrying the same verdict
    vocabulary as round_trip(). Costs 2 quotes per size.
    """
    out = []
    for usd in sizes:
        r = round_trip(mint, usd)
        out.append({"usd": usd, "verdict": r["verdict"],
                    "usd_back": r["usd_back"], "rt_cost_pct": r["rt_cost_pct"]})
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


# Which spelling this process has found to work. A list so the swap below is a
# mutation, not a global rebind - and it is deliberately process-wide: paying
# the wrong-name round trip once per pass, not once per token.
_HOLDER_MINT_KEY = ["mint"]


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
        # ⛔ THE PARAMETER NAME DIFFERS BY ENDPOINT, AND THE RUNNER HAS NO KEY.
        #
        # config.helius_rpc() falls back to api.mainnet-beta.solana.com when
        # HELIUS_API_KEY is absent, which is the case on GitHub Actions - .env is
        # gitignored and stays that way. That endpoint DOES serve
        # getTokenAccounts, and returns the same token_accounts/amount/owner/
        # cursor shape, but it wants `mintAddress` where Helius wants `mint` and
        # rejects the other outright:
        #
        #   Helius: unknown field `mintAddress`, expected one of `owner`, `mint`...
        #   public: unknown field `mint`, expected one of `ownerAddress`,
        #           `mintAddress`...
        #
        # ⚠️ Without this, holder counts return None on every scheduled run, and
        # paperv3 - whose gate refuses an unknown float - would enter NOTHING on
        # the runner while entering normally by hand. A capability that works
        # only when a human runs it is the failure this project keeps paying for.
        # Probed live 2026-09-18, both endpoints, both spellings.
        p = {_HOLDER_MINT_KEY[0]: mint, "limit": 1000}
        if cursor:
            p["cursor"] = cursor
        res, err = _rpc("getTokenAccounts", p)
        if err and "unknown field" in err and _HOLDER_MINT_KEY[0] in err:
            # Wrong endpoint for this spelling. Switch once, for the process,
            # and retry this page - never silently return None.
            _HOLDER_MINT_KEY[0] = ("mintAddress" if _HOLDER_MINT_KEY[0] == "mint"
                                   else "mint")
            p.pop("mint", None)
            p.pop("mintAddress", None)
            p[_HOLDER_MINT_KEY[0]] = mint
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
