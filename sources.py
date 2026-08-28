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
# Every caller that loops over pairs sleeps between requests so we stay well
# inside Dexscreener's published 300 req/min on the pairs endpoint. The value
# lives here rather than being retyped as a bare 0.25 in scanner and track,
# because those two are the same rate budget and drifting them apart is how a
# 429 storm starts.
#
# CRYPTO_HTTP_PACE_S overrides it. The hosted runner sets a smaller value: the
# request itself already costs ~0.2s, so 0.05 still leaves us near 240 req/min,
# and it is what keeps a scheduled run inside one billable minute.
#
# GeckoTerminal is a SEPARATE, stricter budget (~30/min unauthenticated) and
# keeps its own fixed sleep below. It must not be sped up.
# --------------------------------------------------------------------------
PACE_S = float(os.environ.get("CRYPTO_HTTP_PACE_S", "0.25"))

def pace():
    """Sleep the shared inter-request gap. Call between paged fetches."""
    time.sleep(PACE_S)

def _get(url, timeout=20, tries=3, backoff=1.6, headers=None):
    last = None
    h = {**UA, **(headers or {})}
    for i in range(tries):
        try:
            r = urllib.request.urlopen(urllib.request.Request(url, headers=h), timeout=timeout)
            return json.loads(r.read().decode("utf-8", "ignore"))
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
def dexscreener_pair(chain, pair_address):
    d = _get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{pair_address}")
    pairs = d.get("pairs") or d.get("pair")
    if isinstance(pairs, list): return pairs[0] if pairs else None
    return pairs

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
