"""
Free data sources, no API key required. Every endpoint here was probed live
2026-08-20 and returned 200 from a US IP.

Deliberately excluded:
  Binance   - HTTP 451 from US infrastructure
  Jupiter   - DNS blocked in the sandbox. CONFIRMED WORKING from Frank's
              machine 2026-09-17 (lite-api.jup.ag, HTTP 200, p50 181ms) and
              now the trusted liquidity source. See chainfields.py.
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
# now takes ~10 minutes instead of 2.
#
# CORRECTED 2026-09-07: "EVERY STAGE FITS" IS NO LONGER TRUE.
#
# Those per-stage timings (scan 105s, watchlist 60s, paper 21s, each horizon
# ~140s) were measured at PACE_S=0.05. Pacing then went to 1.0s - a 20x change -
# and the runbook line was never re-derived. At 1.0s of sleep plus a measured
# 0.116s request, every call costs ~1.116s, so a stage's duration is very
# nearly its call count in seconds:
#
#   stage             calls   ~seconds   vs the sandbox's 178s command cap
#   scan                105       117    fits, ~34% headroom
#   watchlist            60        67    fits
#   paper                21        23    fits
#   --stage 1           200       223    DOES NOT FIT (HORIZON_LIMIT[1] is 200)
#   --stage 6/24/168    120       134    fits bare, before any fallback lookups
#   --stage outcomes    421       470    DOES NOT FIT, and never could at 1.0s
#
# Call counts are the measured 2026-09-07 pass (421 outcomes, 105 enrichment,
# 60 watchlist, 21 paper) against HORIZON_LIMIT/HORIZON_SLICE.
#
# RESOLVED 2026-09-09: staged invocations now carry a call budget
# (CRYPTO_STAGE_CALLS, default 150 ~ 170s) and stop cleanly when it is spent,
# resuming on the next invocation. The table below is why the budget exists.
#
# THIS MOSTLY DOES NOT MATTER, because the 178s cap is the Claude dispatch
# sandbox's, not production's. Production is .github/workflows/collect.yml,
# which runs `collect.py solana` UNSTAGED on an hourly cron with a 15-minute
# job timeout, and an ~11 minute pass fits that with room. --stage is the
# sandbox path only: run scan, then watchlist, then paper, then ONE horizon at
# a time. ⚠️ The "lower CRYPTO_LIMIT_1H below ~150 or it is killed mid-pass"
# advice that stood here was written when every row cost a paced call; since
# the 2026-09-20 batching it is 400, and the time budget - not the row count -
# is what stops the stage.
PACE_S = float(os.environ.get("CRYPTO_HTTP_PACE_S", "1.0"))

def pace():
    """Sleep the shared inter-request gap. Call between paged fetches."""
    time.sleep(PACE_S)


def pace_since(calls_before):
    """Pace only if a live request was actually made since `calls_before`.

    ⛔ The gap exists to rate-limit REQUESTS. Once pair lookups were batched
    (30 per call), most rows made none and the sleep became pure latency:
    measured 2026-09-20, the 6h stage spent 108.4s on 77 rows while making
    5 HTTP calls in total, so ~1.4s of every row was a sleep owed to nobody.
    A row that hit the cache is not traffic and must not be paced for.
    """
    if CALLS > calls_before:
        pace()

# Permanent HTTP failures. A delisted pair is gone forever, so retrying it is
# pure latency. Measured 2026-08-30: _get retried 3x at timeout=20s with
# backoff, so ONE dead pool cost ~63s against the sandbox's 178s command cap.
# Three consecutive passes journalled zero observations because of it.
PERMANENT_STATUS = (400, 401, 403, 404, 410, 422)


# ---------------------------------------------------------------------------
# CALL BUDGET. Make the work fit the window instead of making the calls faster.
#
# Pacing to the only published rate limit (60/min) is a deliberate choice and it
# stands. The consequence is arithmetic: at ~1.116s per call - 1.0s of pacing
# plus a measured 0.116s request - a full pass of ~607 calls takes about ten
# minutes. That fits the GitHub runner's 15-minute job timeout with room, and
# blows the Claude dispatch sandbox's 178s command cap by 3.4x.
#
# So Claude-side passes were being SIGKILLed part-way through, which is exactly
# what the data showed: runtime per pass climbing 8.4s -> 70s -> 97s -> 110s
# while pools returned per pass fell 79 -> 33, and observations per day fell
# 2,881 -> 678 over three days before anyone noticed.
#
# A budget is counted here rather than estimated by the caller, because this is
# the only place that knows what a call is. Callers check `over_budget()` at
# their own loop boundaries and stop CLEANLY, so a short pass is a recorded
# fact rather than a corpse the next pass has to infer.
# ---------------------------------------------------------------------------
# A CALL COUNT WAS THE WRONG UNIT, AND IT DRIFTED WITHIN A DAY.
#
# The first version budgeted 150 calls on an assumed 1.116s/call. That number
# came from a runbook correction and was never re-measured. Measured fresh
# 2026-09-10 against live queue rows: a bare Dexscreener request is 0.33s
# median (p95 0.72s), so an effective 1.33s with PACE_S=1.0 - but a single ROW
# can spend several calls (primary, GeckoTerminal fallback, an on-chain reserve
# read) plus retries, and observed per-row cost reached 2.77s. 150 x 2.77s is
# 415s against a 178s cap, so every staged command died and filed a spurious
# aborted-pass marker.
#
# Any hardcoded call count is a guess about latency that goes stale the moment
# anything changes - the network, the fallback rate, the retry mix. So the
# budget is a DEADLINE, and cost per call is measured continuously rather than
# assumed. The stop rule asks "is there time for another one of whatever these
# have been costing", which needs no constant at all.
CALLS = 0                  # calls made since the last budget reset
CALL_BUDGET = None         # legacy call cap; None unless explicitly set
DEADLINE = None            # monotonic time after which we must stop
_T0 = None
_RECENT = []               # rolling per-call durations, newest last
_RECENT_MAX = 40


def set_time_budget(seconds, call_cap=None):
    """Start a budgeted window of `seconds`. None disables it."""
    global CALLS, DEADLINE, _T0, _RECENT, CALL_BUDGET
    CALLS = 0
    _RECENT = []
    _T0 = time.monotonic()
    DEADLINE = (_T0 + float(seconds)) if seconds else None
    CALL_BUDGET = int(call_cap) if call_cap else None
    return DEADLINE


# Kept so existing callers and tests keep working; expressed in time.
def set_call_budget(n):
    return set_time_budget(None if not n else n * per_call_estimate(),
                           call_cap=n)


def per_call_estimate():
    """Measured cost of a call, biased pessimistic. 1.5s until we know."""
    # PACE_S is part of the cost: every call in the scoring loops is followed
    # by pace(). Leaving it out is how a budget looks affordable and is not.
    if not _RECENT:
        return 1.5 + PACE_S
    v = sorted(_RECENT)
    p75 = v[min(len(v) - 1, int(0.75 * len(v)))]
    # Never trust an optimistic estimate near a hard kill: overrunning costs a
    # SIGKILL mid-write, stopping early costs one deferred row that the next
    # invocation picks up.
    return max(p75, 0.25) + PACE_S


def seconds_left():
    return None if DEADLINE is None else (DEADLINE - time.monotonic())


def over_budget(headroom=1):
    """True when there is not time for `headroom` more calls of recent cost."""
    if CALL_BUDGET is not None and (CALLS + headroom) >= CALL_BUDGET:
        return True
    if DEADLINE is None:
        return False
    return seconds_left() <= headroom * per_call_estimate()


def calls_made():
    return CALLS


def budget_report():
    el = None if _T0 is None else (time.monotonic() - _T0)
    return {"calls": CALLS, "elapsed_s": None if el is None else round(el, 1),
            "seconds_left": None if DEADLINE is None else round(seconds_left(), 1),
            "per_call_s": round(per_call_estimate(), 3),
            "measured_n": len(_RECENT)}


def _get(url, timeout=20, tries=3, backoff=1.6, headers=None):
    global CALLS
    CALLS += 1
    _t0 = time.monotonic()
    try:
        return _get_inner(url, timeout, tries, backoff, headers)
    finally:
        _RECENT.append(time.monotonic() - _t0)
        if len(_RECENT) > _RECENT_MAX:
            del _RECENT[:-_RECENT_MAX]


def _get_inner(url, timeout=20, tries=3, backoff=1.6, headers=None):
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
#
# BATCHED PAIR LOOKUPS, 2026-09-20.
#
# /latest/dex/pairs takes up to 30 comma-separated addresses in ONE call
# (measured: 30 -> 200 with all 30 returned, 31 -> 400). Every loop here used
# to spend one paced call per pair, so the outcome queue cost ~1.25s a row and
# could not be drained: on 2026-09-19 the funnel ran at 33-40% scan coverage
# with 1,129 rows due and 121 about to age out UNSCORED.
#
# Staleness is bounded by construction: the cache is filled a chunk at a time,
# just before the rows in that chunk are read, so a price is never older than
# the time it takes to process 30 rows. PREFETCH_TTL_S is the hard ceiling and
# a stale entry falls back to a single live call rather than being served.
PAIR_BATCH_MAX = 30
PREFETCH_TTL_S = float(os.environ.get("CRYPTO_PAIR_PREFETCH_TTL_S", "300"))
_PAIR_PRE = {}
PREFETCH_STATS = {"calls": 0, "asked": 0, "found": 0, "served": 0, "stale": 0}


def prefetch_pairs(chain, addresses, ttl_s=None):
    """Fill the pair cache for `addresses`, PAIR_BATCH_MAX per call.

    Absence is cached as None: Dexscreener returning 200 without our pool is
    the same answer the single-pair path gets, and the caller's fallback runs.
    Returns the number of HTTP calls made.
    """
    ttl = PREFETCH_TTL_S if ttl_s is None else ttl_s
    now = time.time()
    want = []
    for a in addresses:
        if not a:
            continue
        hit = _PAIR_PRE.get((chain, a))
        if hit and now - hit[0] < ttl:
            continue
        if a not in want:
            want.append(a)
    calls = 0
    for i in range(0, len(want), PAIR_BATCH_MAX):
        chunk = want[i:i + PAIR_BATCH_MAX]
        try:
            d = _get(f"https://api.dexscreener.com/latest/dex/pairs/{chain}/{','.join(chunk)}")
        except Exception:
            continue          # leave them uncached; the single path will try
        calls += 1
        pairs = d.get("pairs") or d.get("pair") or []
        if isinstance(pairs, dict):
            pairs = [pairs]
        by = {(p or {}).get("pairAddress"): p for p in pairs}
        t = time.time()
        for a in chunk:
            _PAIR_PRE[(chain, a)] = (t, by.get(a))
        PREFETCH_STATS["found"] += sum(1 for a in chunk if by.get(a))
        PREFETCH_STATS["asked"] += len(chunk)
    PREFETCH_STATS["calls"] += calls
    return calls


def prefetched_pair(chain, pair_address):
    """(hit, pair) - hit is False when nothing fresh is cached."""
    e = _PAIR_PRE.get((chain, pair_address))
    if not e:
        return False, None
    if time.time() - e[0] >= PREFETCH_TTL_S:
        PREFETCH_STATS["stale"] += 1
        return False, None
    return True, e[1]


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
    if require_match:
        hit, cached = prefetched_pair(chain, pair_address)
        if hit:
            PREFETCH_STATS["served"] += 1
            return cached
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
# SOLANA RPC. Routed through Helius when HELIUS_API_KEY is set, and the key HAS
# been set since 2026-08-23.
#
# THIS LINE WAS A HARDCODED PUBLIC ENDPOINT UNTIL 2026-09-07, and that mistake
# cost two weeks of a blocked feature. config.helius_rpc() already existed and
# already did the right thing; nothing called it. On 2026-09-06 I then wrote
# ONCHAIN_COST.md concluding holder concentration was "blocked by not having an
# API key" - measured against the public endpoint, without ever checking .env,
# where the key was sitting the whole time. It was blocked on not looking.
#
# The difference is not marginal. getTokenLargestAccounts, the method
# concentration needs, returns HTTP 429 from the public endpoint at ANY spacing
# (0 of 5 succeeded at 0/5/15/30/45s) and returns in ~100-200ms through Helius.
#
# Falls back to the public endpoint when no key is present, so this stays
# correct for anyone running without one.
try:
    import config as _config
    SOL_RPC = _config.helius_rpc()
except Exception:
    SOL_RPC = "https://api.mainnet-beta.solana.com"
PUMP_FUN_PROGRAM = "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P"

def sol_slot():
    return _post(SOL_RPC, {"jsonrpc":"2.0","id":1,"method":"getSlot"})["result"]

def sol_signatures(address, limit=25):
    """Recent transactions for any address. Works for wallets AND programs,
    which is how launches get spotted before the aggregators index them."""
    return _post(SOL_RPC, {"jsonrpc":"2.0","id":1,"method":"getSignaturesForAddress",
                           "params":[address, {"limit": limit}]}).get("result", [])
