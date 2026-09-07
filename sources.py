"""
Free data sources, no API key required. Every endpoint here was probed live
2026-08-20 and returned 200 from a US IP.

Deliberately excluded:
  Binance   - HTTP 451 from US infrastructure
  Jupiter   - DNS blocked in the sandbox, may work from Frank's machine
  Reservoir - same
"""
import json, os, time, datetime as dt, urllib.request, urllib.error

UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}

# --------------------------------------------------------------------------
# Pacing.
#
# Every caller that loops over pairs sleeps between requests. The value lives
# here rather than being retyped as a bare number in scanner and track, because
# those are the same rate budget and drifting them apart is how a 429 storm
# starts.
#
# CRYPTO_HTTP_PACE_S overrides it, and the override is the thing to watch: the
# GitHub workflow set it to 0.05 - about 360 req/min once the ~0.116s request
# is counted - while its own comment claimed 240 against a 300 limit. Both
# numbers were wrong and neither was ever sourced. Corrected 2026-09-07.
#
# GeckoTerminal is a SEPARATE, stricter budget (~30/min unauthenticated) and
# keeps its own fixed sleep below. It must not be sped up.
# --------------------------------------------------------------------------
#
# RESOLVED 2026-09-07, and the old comment above was resting on an unsourced
# number. What was actually checked:
#
#   * Dexscreener's current API reference documents **60 requests per minute**,
#     but ONLY for /token-profiles, /community-takeovers, /ads and /metas -
#     endpoints this project does not use.
#   * The endpoints we DO use - /latest/dex/pairs and /latest/dex/tokens - have
#     **no rate limit stated anywhere in the current documentation.** They are
#     linked as OpenAPI specs with no limit shown.
#   * **No rate-limit headers are published on any endpoint.** Checked live on
#     all three: no x-ratelimit-*, no retry-after, nothing. The server gives no
#     runtime signal, so there is no way to discover the limit by observation
#     short of being banned.
#   * We have never recorded a 429 from Dexscreener.
#
# AN UNSTATED LIMIT IS NOT PERMISSION. The only published number that could
# apply is 60/min, so that is what we pace to. Running at 300 because nothing
# has stopped us is exactly the reasoning that gets an API key revoked, and
# this source is a single point of failure twice over: it supplies collection
# AND the reserve split that is ground truth for the fraud detector. Losing it
# would not just stop the data, it would make the detector unfalsifiable.
#
# WHAT IT COSTS: nothing. Measured 2026-09-07 - 607 Dexscreener calls per pass
# (421 outcomes, 105 enrichment, 60 watchlist, 21 paper) against an hourly
# budget of 3,600 at 60/min. That is 83% headroom. A single-command full pass
# now takes ~10 minutes instead of 2, which exceeds the 178s runner cap, but
# `collect.py --stage` already splits it and EVERY STAGE FITS: scan 105s,
# watchlist 60s, paper 21s, each horizon ~140s.
PACE_S = float(os.environ.get("CRYPTO_HTTP_PACE_S", "1.0"))

def pace():
    """Sleep the shared inter-request gap. Call between paged fetches."""
    time.sleep(PACE_S)

# Permanent HTTP failures. A delisted pair is gone forever, so retrying it is
# pure latency. Measured 2026-08-30: _get retried 3x at timeout=20s with
# backoff, so ONE dead pool cost ~63s against the sandbox's 178s command cap.
# Three consecutive passes journalled zero observations because of it.
PERMANENT_STATUS = (400, 401, 403, 404, 410, 422)


def _get(url, timeout=20, tries=3, backoff=1.6, headers=None):
    last = None
    h = {**UA, **(headers or {})}
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            return json.loads(r.read().decode("utf-8", "ignore"))
        except urllib.error.HTTPError as e:
            # 429 IS worth retrying - it is a rate limit, not a dead resource.
            if e.code in PERMANENT_STATUS:
                raise
            last = e
            if i < tries - 1:
                time.sleep(backoff ** i)
        except Exception as e:
            last = e
            if i < tries - 1:
                time.sleep(backoff ** i)
    raise last


def _post(url, payload, timeout=20):
    req = urllib.request.Request(url, headers={**UA, "Content-Type": "application/json"},
                                 data=json.dumps(payload).encode(), method="POST")
    return json.loads(urllib.request.urlopen(req, timeout=timeout).read().decode())


# --------------------------------------------------------------------------
# Discovery coverage.
#
# new_pools is a WINDOW, not a feed. Measured 2026-08-28: 40 pools spanned 37
# seconds of Solana launches, and pagination dies at page 10 (page 11 returns
# 429), so one pass reaches ~5 minutes back at absolute best. Run hourly, that
# observes roughly 1% of the stream at pages=2 and ~9% at pages=10.
#
# That is why real CYBERLEEK (pool created 2026-08-27 23:47:09Z) never entered
# the journal. It was ~18 minutes deep by the next pass. Not a scoring failure
# and not a DEX gap - the feed does return pumpswap pools. The funnel is simply
# 1% wide.
#
# LAST_WINDOW records what each pass actually saw so coverage stops being a
# one-off finding and becomes a number that accumulates.
# --------------------------------------------------------------------------
LAST_WINDOW = {"pools": 0, "oldest": None, "newest": None, "span_s": None}


def _window(pools):
    ts = []
    for p in pools:
        c = (p.get("attributes") or {}).get("pool_created_at")
        if c:
            try:
                ts.append(dt.datetime.fromisoformat(c.replace("Z", "+00:00")))
            except ValueError:
                pass
    if not ts:
        LAST_WINDOW.update(pools=len(pools), oldest=None, newest=None, span_s=None)
        return LAST_WINDOW
    lo, hi = min(ts), max(ts)
    LAST_WINDOW.update(pools=len(pools), oldest=lo.isoformat(), newest=hi.isoformat(),
                       span_s=round((hi - lo).total_seconds(), 1))
    return LAST_WINDOW

# ---------- new-pair discovery ----------
PAGES = int(os.environ.get("CRYPTO_NEW_POOL_PAGES", "5"))


def new_pools(network="solana", pages=None):
    """Newest pools on a chain. This is the front line for catching launches.

    pages is the coverage dial. Each page is 20 pools and roughly 20 seconds of
    stream, and page 10 is the hard ceiling - page 11 returns 429. Default 5 is
    a deliberate middle: it quadruples the window over the old pages=2 without
    sitting on the rate limit, which matters because a 429 costs a whole page
    and the pass has no way to get those launches back.

    A failed page is SKIPPED, not fatal. Losing one page of a five-page sweep
    costs 20 pools; raising would cost all 100 and the outcome scoring behind
    it. That trade only got worse as pages went up.
    """
    pages = PAGES if pages is None else pages
    out, lost, seen = [], 0, set()
    for p in range(1, pages + 1):
        try:
            d = _get(f"https://api.geckoterminal.com/api/v2/networks/{network}/new_pools?page={p}")
            # Pagination is NOT stable. Measured 2026-08-28: five pages returned
            # 100 rows containing 67 distinct pools, and page 5 was a complete
            # duplicate of page 1. New pools keep arriving during the ~15s a
            # sweep takes, so the feed re-sorts underneath it. Dedupe here or a
            # third of the enrichment budget is spent re-fetching known pools.
            for r in d.get("data", []):
                a = (r.get("attributes") or {}).get("address")
                if a and a not in seen:
                    seen.add(a)
                    out.append(r)
        except Exception as e:
            lost += 1
            print(f"  [new_pools] page {p} lost: {type(e).__name__} {str(e)[:60]}")
        # Measured 2026-08-28: 429s appear at 20 calls/min from a residential
        # IP, so the "~30/min" in the old comment was optimistic. Keep the gap
        # wide.
        time.sleep(2.2)
    _window(out)
    LAST_WINDOW["pages_lost"] = lost
    return out

def trending_pools(network="solana"):
    return _get(f"https://api.geckoterminal.com/api/v2/networks/{network}/trending_pools").get("data", [])

# ---------- enrichment ----------
def dexscreener_pair(chain, pair_address, require_match=True):
    """One pair, and BY DEFAULT it is the pair you asked for.

    P0 FIX 2026-09-07. This used to `return pairs[0]` with no check that the
    returned pairAddress was the one requested. Nothing in the primary outcome
    path then guaranteed that the pool we priced was the pool we held, and 85 of
    165 realizable 3x+ wins (51.5%) sit in a single $1.2M-$1.35M liquidity band
    across 53 different symbols - the signature of many tokens being priced off
    one shared reference pool. Every one of those rows came through THIS
    function with no reasons recorded; the existing `cross_pair_fallback` guard
    only ever covered the fallback branch.

    The list is SEARCHED for the requested address rather than rejected
    outright, because a multi-pair response containing ours is fine - we just
    have to pick ours instead of whichever happened to sort first.
    """
    d = _get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}")
    pairs = d.get("pairs") or d.get("pair")
    if isinstance(pairs, dict):
        pairs = [pairs]
    if not pairs:
        return None
    if not require_match:
        return pairs[0]
    for p in pairs:
        if (p or {}).get("pairAddress") == pair_address:
            return p
    # Asked for one pool, given another. That is not our series and must never
    # be divided into our entry price.
    LAST_PAIR_MISMATCH.append({"asked": pair_address,
                               "got": [(p or {}).get("pairAddress") for p in pairs]})
    return None


# Pair-identity misses seen this process. Read by track.py so a mismatch is
# reported rather than silently indistinguishable from a delisting.
LAST_PAIR_MISMATCH = []

def dexscreener_token(token_address):
    d = _get(f"https://api.dexscreener.com/latest/dex/tokens/{token_address}")
    return d.get("pairs") or []

def boosted_tokens():
    """Paid promotion. Useful as a CONTRARIAN signal - someone paying for
    attention on a token with no organic volume is a warning, not a buy."""
    return _get("https://api.dexscreener.com/token-boosts/latest/v1")

# ---------- macro ----------
def fear_greed():
    d = _get("https://api.alternative.me/fng/?limit=1")["data"][0]
    return int(d["value"]), d["value_classification"]

def global_market():
    d = _get("https://api.coingecko.com/api/v3/global")["data"]
    return {"btc_dominance": d["market_cap_percentage"]["btc"],
            "eth_dominance": d["market_cap_percentage"]["eth"],
            "mcap_change_24h": d["market_cap_change_percentage_24h_usd"],
            "total_mcap_usd": d["total_market_cap"]["usd"]}

def prices(ids=("bitcoin", "ethereum", "solana")):
    return _get("https://api.coingecko.com/api/v3/simple/price?ids="
                + ",".join(ids) + "&vs_currencies=usd&include_24hr_change=true")

def chain_tvl():
    return {c["name"]: c["tvl"] for c in _get("https://api.llama.fi/v2/chains")}

def btc_fees():
    return _get("https://mempool.space/api/v1/fees/recommended")

# ---------- solana chain ----------
SOL_RPC = "https://api.mainnet-beta.solana.com"
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

def sol_slot():
    return _post(SOL_RPC, {"jsonrpc":"2.0","id":1,"method":"getSlot"})["result"]

def sol_signatures(address, limit=25):
    """Recent transactions for any address. Works for wallets AND programs,
    which is how launches get spotted before the aggregators index them."""
    return _post(SOL_RPC, {"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress",
                           "params":[address, {"limit": limit}]}).get("result", [])
