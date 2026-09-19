"""Market intelligence: what is running on Solana NOW, not only what launched.

⛔ THE SCOPE ERROR THIS FIXES (named 2026-09-18). Everything this pipeline
collected was about tokens AT BIRTH - new pairs, curve position, graduation
odds. None of it answered "what is running right now", which is the question
Frank opens a dashboard to ask. A coin that launched three weeks ago and is up
300% today was invisible to us. Frank: "the dashboard kinda sucks. you also
need to track the top coins and trends." The empty dashboard was the symptom;
the data model was the disease.

Every pass this writes data/market/:

    movers.json     biggest % gainers and losers over 1h / 6h / 24h,
                    market-wide, each also shown against SOL's own move
    volume.json     what is actually being traded, with the wash caveat ON the row
    trending.json   what the aggregators call trending, per source, labelled
    clusters.json   our narrative clusters (clusters.py) + Dexscreener's metas
    majors.json     the tape: SOL/BTC/ETH, market-wide volume, Solana DEX volume
    index.json      manifest - every file, its n, each source's status, caveats
    history/YYYY-MM.jsonl   compact append-only copy of every list, every pass

⚠️ WHAT "MARKET-WIDE" MEANS, EXACTLY. The universe is the union of Jupiter's
ranked lists (top trending 1h/6h/24h, top traded 1h/24h, top organic 1h - 600
slots). It is the most active slice of Solana, not a census. A coin nobody is
trading will not appear, which is correct for "what is running", and
`universe_n` is published so nobody mistakes it for every token.

⛔ VOLUME IS THE EASIEST NUMBER TO FAKE, AND WE HAVE NO WASH DETECTOR HERE.
Jupiter splits every volume figure into total and "organic", and my first read
of that split was wrong: the top 1h token did $5.97M of which Jupiter called
$334k (5.6%) organic, which I took as a wash signal. Then the first full run put
SOL ITSELF at 1.8% organic and USDC at 4.2%. Jupiter's "organic" excludes bots
and arbitrage, not just wash, so a low share is the NORM, not a warning.
`organic_share` is published with SOL's own share beside it as the baseline, and
is NOT used to flag or filter anything. Our pre-committed wash tests
(docs/VOLUME_INTEGRITY.md M1/M2) need per-transaction data and are not applied
here. What each volume row does carry is descriptive: traders, turnover.

⛔ A % MOVE IS NOT A WIN (standing rule 3). Rows under the existing exit-depth
floor are excluded and COUNTED, and the top of each list is checked with
chainfields.round_trip() at Frank's $100 clip - two quotes, nothing executed,
no wallet. A row that was not checked says so. Unknown is None, never 0.

THIS DOES NOT RANK BY QUALITY. Every list is ordered by the size of a move or
of volume that has ALREADY happened - description, not prediction (CLAUDE.md,
"What this is NOT"). Nothing here says a mover will keep moving.
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

import liveness

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "data", "market")
HISTORY_DIR = os.path.join(BASE, "data", "market", "history")

# Standing rule 12: every one of these hosts is Cloudflare-fronted or picky.
UA = {"User-Agent": "Mozilla/5.0 (crypto-intel market)", "Accept": "application/json"}
WSOL = "So11111111111111111111111111111111111111112"
JUP_TOKENS = "https://lite-api.jup.ag/tokens/v2"
GT = "https://api.geckoterminal.com/api/v2/networks/solana"
DS = "https://api.dexscreener.com"
CG = "https://api.coingecko.com/api/v3"
LLAMA = "https://api.llama.fi/overview/dexs/solana"

HORIZONS = ("1h", "6h", "24h")
STATS = {"5m": "stats5m", "1h": "stats1h", "6h": "stats6h", "24h": "stats24h"}
JUP_LISTS = (("toptrending", "1h"), ("toptrending", "6h"), ("toptrending", "24h"),
             ("toptraded", "1h"), ("toptraded", "24h"), ("toporganicscore", "1h"))
GT_TRENDING = ("1h", "6h", "24h")

TOP_N = int(os.environ.get("CRYPTO_MARKET_TOP_N", "25"))
LOSERS_N = int(os.environ.get("CRYPTO_MARKET_LOSERS_N", "10"))
VERIFY_PER_LIST = int(os.environ.get("CRYPTO_MARKET_VERIFY", "6"))
# 45s of quotes. The first live run spent 75s here and 94s overall; the runner's
# job timeout is 15 minutes and the longest pass on record is 13.6. collect.py
# also shrinks this when the pass is already running long - see market_stage().
VERIFY_SECONDS = float(os.environ.get("CRYPTO_MARKET_VERIFY_S", "45"))
MEMBERS_CAP = 30

# ⛔ NOT A NEW THRESHOLD. Same env var and default as paper.MIN_EXIT_DEPTH: the
# floor under which this project already refuses to treat a pool as exitable.
# Inventing a second floor here is how two numbers drift apart silently, so
# test_market.py asserts the two are equal instead of importing paper (which
# drags in the whole journal) at collector time.
MIN_LIQ_USD = float(os.environ.get("CRYPTO_PAPER_MIN_DEPTH", "1000"))

# GeckoTerminal 429'd the SIXTH call of a burst spaced 2.2s apart, measured
# 2026-09-18 - and the scanner's new_pools already spends that budget earlier in
# the same pass. Coverage of launches is the scarcer thing, so this waits.
GT_GAP_S = float(os.environ.get("CRYPTO_MARKET_GT_GAP_S", "6.5"))

CAVEATS = {
    "universe": ("Market-wide means the union of Jupiter's ranked lists - the most "
                 "active slice of Solana, not every token. See universe_n."),
    "volume": ("Volume is the easiest number to fake and nothing here detects wash "
               "trading. organic_share is Jupiter's split and is NOT a wash signal: "
               "SOL itself runs ~2% organic (see organic_share_baseline_sol). Our own "
               "wash tests (docs/VOLUME_INTEGRITY.md) need per-transaction data and "
               "are not applied here."),
    "classes": ("class comes from Jupiter's own tags: base = major/stable/lst/yield, "
                "stock = stocks/xstocks/rwa/equities; everything else is token. "
                "Bridged majors Jupiter does not tag (cbBTC, ZEC) stay in token."),
    "liquidity": ("liquidity_usd_reported is Jupiter's figure, not realizable depth. "
                  "Only round_trip (a $100 buy+sell quote, nothing executed) is "
                  "realizable. Rows under $%d reported liquidity are excluded and "
                  "counted." % MIN_LIQ_USD),
    "ranking": ("Ordered by the size of a move or of volume that already happened. "
                "Description, not prediction."),
    "boosts": ("Dexscreener boosts are PAID promotion. Someone paid for attention; "
               "that is not organic trending and is often a warning."),
    "clusters": ("Our clusters are built from our own journal, which sees ~1.3% of "
                 "launches (docs/COVERAGE.md) - a cluster here is a floor on the "
                 "wave, not its size. Dexscreener metas are theirs and span every "
                 "chain."),
    "symbols": ("symbol is raw and display-only. Key on `token`. symbol_flags marks "
                "bidi overrides and mixed alphabets (docs/SYMBOL_ATTACKS.md)."),
}

# Jupiter's own tags, not ours. Checked on the first live run: SOL carries
# `major`, USDC/USDT/PYUSD `stable`, JitoSOL `lst`, jlUSDC `yield`, SPYx `stocks`.
BASE_TAGS = {"major", "stable", "lst", "yield", "jup-lend-earn"}
STOCK_TAGS = {"stocks", "xstocks", "rwa", "equities", "prestocks", "pre-ipo"}

CALLS = {"n": 0}
SOURCES = {}
# This process's last snapshot, so universe.py reuses the lists and the round
# trips instead of fetching and quoting them twice in one pass.
LAST = {}


# --------------------------------------------------------------------------
# HTTP. Never raises; every failure is recorded against its source label so the
# manifest can say which panel is empty because the SOURCE failed, rather than
# because nothing happened. Those are different facts.
# --------------------------------------------------------------------------
def _get(url, timeout=20):
    CALLS["n"] += 1
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def _fetch(label, url, extract=None, timeout=20, jupiter=False):
    if jupiter:
        # One process-wide Jupiter budget. chainfields owns the bucket; the
        # round-trip checks below draw from it too.
        try:
            import chainfields
            chainfields._JUP.take()
        except Exception:
            pass
    s, d = _get(url, timeout)
    if s != 200 or d is None or isinstance(d, str):
        SOURCES[label] = {"status": "error", "http": s, "n": 0,
                          "error": d if isinstance(d, str) else f"HTTP {s}"}
        return None
    try:
        out = extract(d) if extract else d
    except Exception as e:
        SOURCES[label] = {"status": "error", "http": s, "n": 0,
                          "error": f"unexpected shape: {type(e).__name__}"}
        return None
    n = len(out) if isinstance(out, (list, dict)) else None
    SOURCES[label] = {"status": "empty" if n == 0 else "ok", "http": s, "n": n,
                      "error": None}
    return out


# --------------------------------------------------------------------------
# Values. Unknown is None. NaN and infinity are unknown too.
# --------------------------------------------------------------------------
def _num(x):
    if isinstance(x, bool):
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    if v != v or v in (float("inf"), float("-inf")):
        return None
    return v


def _r(x, nd=2):
    return None if x is None else round(x, nd)


def _stat(tok, h, k):
    return _num(((tok or {}).get(STATS[h]) or {}).get(k))


def volume(tok, h):
    b, s = _stat(tok, h, "buyVolume"), _stat(tok, h, "sellVolume")
    return None if b is None or s is None else b + s


def organic_share(tok, h):
    """Jupiter's organic volume over total volume. None when either is unknown
    or total is zero - a share of nothing is not zero, it is undefined."""
    v = volume(tok, h)
    ob, osl = _stat(tok, h, "buyOrganicVolume"), _stat(tok, h, "sellOrganicVolume")
    if not v or ob is None or osl is None:
        return None
    return round((ob + osl) / v, 4)


def _parse_ts(s):
    if not s:
        return None
    try:
        return dt.datetime.fromisoformat(str(s).replace("Z", "+00:00")).timestamp()
    except ValueError:
        return None


def age_h(tok, now):
    t = _parse_ts((tok.get("firstPool") or {}).get("createdAt")) or _parse_ts(tok.get("createdAt"))
    return None if t is None else round((now - t) / 3600.0, 2)


def symbol_flags(sym):
    """What dashboard.safe_sym() warns about, as data. The site renders; the
    pipeline only says what it found."""
    try:
        from dashboard import _BIDI, _script
    except Exception:
        return {"bidi": None, "mixed_script": None}
    raw = str(sym or "")
    stripped = "".join(c for c in raw if ord(c) not in _BIDI)
    scripts = {s for s in (_script(c) for c in stripped) if s}
    return {"bidi": len(stripped) != len(raw), "mixed_script": len(scripts) > 1}


def token_class(tok):
    tags = set((tok or {}).get("tags") or [])
    if tags & BASE_TAGS:
        return "base"
    if tags & STOCK_TAGS:
        return "stock"
    return "token"


def token_row(tok, sol, now, seen, lists):
    mint = tok.get("id")
    ch = {h: _stat(tok, h, "priceChange") for h in ("5m", "1h", "6h", "24h")}
    a = tok.get("audit") or {}
    return {
        "token": mint,
        "symbol": tok.get("symbol"),
        "symbol_flags": symbol_flags(tok.get("symbol")),
        "name": tok.get("name"),
        "price_usd": _num(tok.get("usdPrice")),
        "change_pct": {h: _r(v, 3) for h, v in ch.items()},
        # A coin up 40% on a day SOL is up 15% is a different story from one up
        # 40% on a flat day. Simple difference, in percentage points.
        "vs_sol_pp": {h: (None if ch.get(h) is None or sol.get(h) is None
                          else round(ch[h] - sol[h], 3)) for h in HORIZONS},
        "volume_usd": {h: _r(volume(tok, h)) for h in ("1h", "24h")},
        "organic_share": {h: organic_share(tok, h) for h in ("1h", "24h")},
        "traders": {h: _stat(tok, h, "numTraders") for h in ("1h", "24h")},
        "liquidity_usd_reported": _r(_num(tok.get("liquidity"))),
        "mcap_usd": _r(_num(tok.get("mcap"))),
        "fdv_usd": _r(_num(tok.get("fdv"))),
        "holders": tok.get("holderCount"),
        "age_h": age_h(tok, now),
        "launchpad": tok.get("launchpad"),
        "class": token_class(tok),
        "tags": tok.get("tags") or [],
        "audit": {"mint_authority_disabled": a.get("mintAuthorityDisabled"),
                  "freeze_authority_disabled": a.get("freezeAuthorityDisabled"),
                  "top_holders_pct": _r(_num(a.get("topHoldersPercentage"))),
                  "dev_balance_pct": _r(_num(a.get("devBalancePercentage")))},
        "organic_score": _r(_num(tok.get("organicScore"))),
        "organic_label": tok.get("organicScoreLabel"),
        "lists": sorted(lists.get(mint, ())),
        # ⭐ THE SCOPE ERROR, MEASURED ON EVERY ROW: has our launch scanner ever
        # seen this token? None means the journal could not be read.
        "in_journal": (None if seen is None else mint in seen),
        "round_trip": None,
        "round_trip_status": "not checked",
    }


# --------------------------------------------------------------------------
# Ranking. Exclusions are COUNTED, never silent (standing rule 15).
# --------------------------------------------------------------------------
def rank(universe, key, n, descending=True, sign=None):
    """Tokens ordered by key(tok). Returns (tokens, exclusion counts)."""
    counts = {"unknown_value": 0, "under_liquidity_floor": 0,
              "liquidity_unknown": 0, "wrong_sign": 0, "eligible": 0}
    elig = []
    for tok in universe.values():
        v = key(tok)
        if v is None:
            counts["unknown_value"] += 1
            continue
        if (sign == "+" and v <= 0) or (sign == "-" and v >= 0):
            counts["wrong_sign"] += 1
            continue
        liq = _num(tok.get("liquidity"))
        if liq is None:
            counts["liquidity_unknown"] += 1
            continue
        if liq < MIN_LIQ_USD:
            counts["under_liquidity_floor"] += 1
            continue
        elig.append((v, tok))
    counts["eligible"] = len(elig)
    elig.sort(key=lambda x: x[0], reverse=descending)
    return [t for _, t in elig[:n]], counts


def verify(lists_in_priority, budget_s=None, rt=None, per_list=None):
    """Realizable check on the top of each list, until the time budget is spent.

    ⛔ Quotes only. chainfields.round_trip() asks Jupiter what $100 buys and what
    that sells back for; nothing is executed and no wallet exists.
    """
    budget_s = VERIFY_SECONDS if budget_s is None else budget_s
    per_list = VERIFY_PER_LIST if per_list is None else per_list
    if rt is None:
        import chainfields
        rt = chainfields.round_trip
    t0, done = time.time(), {}
    for rows in lists_in_priority:
        for r in rows[:per_list]:
            m = r["token"]
            if m in done:
                continue
            if time.time() - t0 > budget_s:
                r["round_trip_status"] = "not checked: time budget spent"
                continue
            try:
                res = rt(m) or {}
            except Exception as e:
                res = {"error": f"{type(e).__name__}"}
            v = res.get("verdict")
            done[m] = {
                "round_trip": {"verdict": v,
                               "rt_cost_pct": res.get("rt_cost_pct"),
                               "usd_back": res.get("usd_back"),
                               "probe_usd": res.get("probe_usd"),
                               "price_impact_pct": res.get("price_impact_pct"),
                               "ts": res.get("ts")},
                "round_trip_status": ("checked" if v else
                                      f"check failed: {res.get('error') or 'no verdict'}")}
    # A token checked for one list carries the result into every list it is in.
    for rows in lists_in_priority:
        for r in rows:
            if r["token"] in done:
                r.update(done[r["token"]])
    return done


# --------------------------------------------------------------------------
# Sources
# --------------------------------------------------------------------------
def gather_universe():
    universe, lists = {}, {}
    for kind, interval in JUP_LISTS:
        label = f"jupiter.{kind}.{interval}"
        got = _fetch(label, f"{JUP_TOKENS}/{kind}/{interval}?limit=100", jupiter=True)
        for tok in got or []:
            m = tok.get("id") if isinstance(tok, dict) else None
            if not m:
                continue
            universe.setdefault(m, tok)
            lists.setdefault(m, set()).add(label)
    return universe, lists


def sol_tape(universe, cg_prices):
    """SOL's own move per horizon - the baseline every row is read against."""
    tok = universe.get(WSOL)
    if tok is None:
        got = _fetch("jupiter.search.SOL", f"{JUP_TOKENS}/search?query={WSOL}",
                     jupiter=True)
        tok = next((t for t in (got or []) if isinstance(t, dict) and t.get("id") == WSOL), None)
    out = {h: (_stat(tok, h, "priceChange") if tok else None) for h in ("5m", "1h", "6h", "24h")}
    out["source"] = "jupiter" if tok else None
    if out.get("24h") is None and cg_prices:
        out["24h"] = _num((cg_prices.get("solana") or {}).get("usd_24h_change"))
        out["source"] = "coingecko (24h only)" if out["24h"] is not None else None
    return out


def gt_row(p, seen):
    a = p.get("attributes") or {}
    rel = p.get("relationships") or {}
    base = ((rel.get("base_token") or {}).get("data") or {}).get("id") or ""
    tok = base.split("_", 1)[1] if base.startswith("solana_") else None
    pc = a.get("price_change_percentage") or {}
    tx = (a.get("transactions") or {}).get("h24") or {}
    return {"token": tok, "pool": a.get("address"), "name": a.get("name"),
            "dex": ((rel.get("dex") or {}).get("data") or {}).get("id"),
            "change_pct": {k: _num(pc.get(k)) for k in ("m5", "h1", "h6", "h24")},
            "volume_usd_24h": _r(_num((a.get("volume_usd") or {}).get("h24"))),
            "reserve_usd_reported": _r(_num(a.get("reserve_in_usd"))),
            "fdv_usd": _r(_num(a.get("fdv_usd"))),
            "mcap_usd": _r(_num(a.get("market_cap_usd"))),
            "buyers_24h": tx.get("buyers"), "sellers_24h": tx.get("sellers"),
            "pool_created_at": a.get("pool_created_at"),
            "in_journal": (None if seen is None or not tok else tok in seen)}


def _sol_only(rows):
    return [r for r in rows or [] if isinstance(r, dict) and r.get("chainId") == "solana"]


def dexscreener(seen):
    def links(r):
        return [l.get("type") or l.get("label") for l in (r.get("links") or [])
                if isinstance(l, dict)]

    def base(r):
        t = r.get("tokenAddress")
        return {"token": t, "url": r.get("url"),
                "description": (r.get("description") or "")[:160] or None,
                "links": links(r),
                "in_journal": (None if seen is None or not t else t in seen)}

    out = {}
    for key, path in (("boosts_top", "/token-boosts/top/v1"),
                      ("boosts_latest", "/token-boosts/latest/v1")):
        rows = _fetch(f"dexscreener.{key}", DS + path, extract=_sol_only)
        out[key] = [dict(base(r), boost_amount=r.get("amount"),
                         boost_total=r.get("totalAmount")) for r in rows or []]
        time.sleep(1.0)
    rows = _fetch("dexscreener.profiles_latest", DS + "/token-profiles/latest/v1",
                  extract=_sol_only)
    out["profiles_latest"] = [base(r) for r in rows or []]
    time.sleep(1.0)
    rows = _fetch("dexscreener.community_takeovers", DS + "/community-takeovers/latest/v1",
                  extract=_sol_only)
    out["community_takeovers"] = [dict(base(r), claim_date=r.get("claimDate"))
                                  for r in rows or []]
    time.sleep(1.0)
    return out


def dexscreener_metas():
    rows = _fetch("dexscreener.metas_trending", DS + "/metas/trending/v1")
    out = []
    for m in rows or []:
        if not isinstance(m, dict):
            continue
        c = m.get("marketCapChange") or {}
        out.append({"name": m.get("name"), "slug": m.get("slug"),
                    "token_count": m.get("tokenCount"),
                    "mcap_usd": _r(_num(m.get("marketCap"))),
                    "mcap_change_pct": {k: _r(_num(c.get(k)), 3) for k in ("m5", "h1", "h6", "h24")},
                    "volume_usd": _r(_num(m.get("volume"))),
                    "liquidity_usd_reported": _r(_num(m.get("liquidity")))})
    return out


def our_clusters(obs, now):
    import clusters
    cs = clusters.find(obs, window_h=24, min_members=3, end=now)
    out = []
    for c in cs[:40]:
        out.append({
            "root": c["root"], "size": c["size"], "variants": c["variants"],
            # ⚠️ clusters.py counts `liq > 0` - REPORTED liquidity, which
            # overstates by a median 781x. Named for what it is.
            "funded_by_reported_liq": c["funded"],
            "first_seen": c["first_seen"], "last_seen": c["last_seen"],
            "span_h": c["span_h"], "swarm": c["swarm"],
            "members": [{"token": m.get("token"), "symbol": m.get("symbol"),
                         "symbol_flags": symbol_flags(m.get("symbol")),
                         "first_seen": m.get("ts"), "pair": m.get("pair")}
                        for m in c["members"][:MEMBERS_CAP]],
            "members_truncated": max(0, c["size"] - MEMBERS_CAP)})
    return out


def majors(universe):
    cg = _fetch("coingecko.simple_price",
                f"{CG}/simple/price?ids=solana,bitcoin,ethereum&vs_currencies=usd"
                "&include_24hr_change=true&include_24hr_vol=true&include_market_cap=true")
    time.sleep(1.5)
    glob = _fetch("coingecko.global", f"{CG}/global", extract=lambda d: d["data"])
    time.sleep(1.0)
    llama = _fetch("defillama.solana_dex_volume",
                   LLAMA + "?excludeTotalDataChart=true&excludeTotalDataChartBreakdown=true",
                   extract=lambda d: {k: d.get(k) for k in
                                      ("total24h", "total48hto24h", "total7d", "change_1d")})
    sol = sol_tape(universe, cg)

    def coin(k):
        c = (cg or {}).get(k) or {}
        return {"price_usd": _num(c.get("usd")),
                "change_24h_pct": _r(_num(c.get("usd_24h_change")), 3),
                "volume_24h_usd": _r(_num(c.get("usd_24h_vol"))),
                "mcap_usd": _r(_num(c.get("usd_market_cap")))}

    g, ll = glob or {}, llama or {}
    return {
        "sol": dict(coin("solana"),
                    change_pct={h: _r(sol.get(h), 3) for h in ("5m", "1h", "6h", "24h")},
                    change_source=sol.get("source")),
        "btc": coin("bitcoin"),
        "eth": coin("ethereum"),
        "crypto_market": {
            "total_volume_24h_usd": _r(_num((g.get("total_volume") or {}).get("usd"))),
            "total_mcap_usd": _r(_num((g.get("total_market_cap") or {}).get("usd"))),
            "mcap_change_24h_pct": _r(_num(g.get("market_cap_change_percentage_24h_usd")), 3)},
        "solana_dex": {
            "volume_24h_usd": _r(_num(ll.get("total24h"))),
            "volume_prev_24h_usd": _r(_num(ll.get("total48hto24h"))),
            "volume_7d_usd": _r(_num(ll.get("total7d"))),
            "change_1d_pct": _r(_num(ll.get("change_1d")), 3)},
    }, sol


# --------------------------------------------------------------------------
# Output. Written atomically, then READ BACK - the manifest and the liveness row
# count come from what is on disk, not from what we meant to write (rule 16).
# --------------------------------------------------------------------------
FILES = ("movers.json", "volume.json", "trending.json", "clusters.json", "majors.json")


def _write(name, obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    path = os.path.join(OUT_DIR, name)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)
    return path


def _read(name):
    try:
        with open(os.path.join(OUT_DIR, name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def rows_on_disk(name, d):
    """How many real rows a written file holds. Counted from the file."""
    if d is None:
        return 0
    if name == "movers.json":
        return sum(len(v) for v in (d.get("lists") or {}).values())
    if name == "volume.json":
        return len(d.get("leaders_24h") or []) + len(d.get("leaders_24h_tokens") or [])
    if name == "trending.json":
        return (sum(len(v) for v in (d.get("jupiter") or {}).values())
                + sum(len(v) for v in (d.get("geckoterminal") or {}).values())
                + sum(len(d.get(k) or []) for k in ("boosts_top", "boosts_latest",
                                                    "profiles_latest", "community_takeovers")))
    if name == "clusters.json":
        return len(d.get("ours") or []) + len(d.get("dexscreener_metas") or [])
    if name == "majors.json":
        return sum(1 for k in ("sol", "btc", "eth")
                   if (d.get(k) or {}).get("price_usd") is not None)
    return 0


def _history(ts, named_lists):
    os.makedirs(HISTORY_DIR, exist_ok=True)
    path = os.path.join(HISTORY_DIR, dt.datetime.fromtimestamp(ts, dt.timezone.utc)
                        .strftime("%Y-%m") + ".jsonl")
    cols = ["token", "chg_1h", "chg_6h", "chg_24h", "vol_24h", "liq_reported",
            "organic_share_24h", "rt_verdict", "in_journal"]
    with open(path, "a", encoding="utf-8", newline="\n") as f:
        for kind, rows in named_lists.items():
            f.write(json.dumps({"ts": ts, "kind": kind, "cols": cols, "rows": [
                [r.get("token"), r["change_pct"].get("1h"), r["change_pct"].get("6h"),
                 r["change_pct"].get("24h"), r["volume_usd"].get("24h"),
                 r.get("liquidity_usd_reported"), r["organic_share"].get("24h"),
                 (r.get("round_trip") or {}).get("verdict"), r.get("in_journal")]
                for r in rows]}, ensure_ascii=False, separators=(",", ":")) + "\n")
    return path


def _seen_and_obs():
    try:
        import journal
        obs = journal.observations()
        return {o.get("token") for o in obs if o.get("token")}, obs
    except Exception as e:
        SOURCES["journal"] = {"status": "error", "n": 0, "error": f"{type(e).__name__}"}
        return None, []


def build(verbose=True, now=None, rt=None, verify_s=None):
    """One snapshot. Returns the manifest. Never raises for a source failure."""
    now = time.time() if now is None else now
    t0 = time.time()
    CALLS["n"] = 0
    SOURCES.clear()
    built = dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec="seconds")
    origin = os.environ.get("CRYPTO_ORIGIN") or liveness.origin()
    seen, obs = _seen_and_obs()

    universe, lists = gather_universe()
    tape, sol = majors(universe)

    def row(t):
        return token_row(t, sol, now, seen, lists)

    movers, counts = {}, {}
    for h in HORIZONS:
        g, cg_ = rank(universe, lambda t, h=h: _stat(t, h, "priceChange"), TOP_N, True, "+")
        lo, cl_ = rank(universe, lambda t, h=h: _stat(t, h, "priceChange"), LOSERS_N, False, "-")
        movers[f"gainers_{h}"] = [row(t) for t in g]
        movers[f"losers_{h}"] = [row(t) for t in lo]
        counts[f"gainers_{h}"], counts[f"losers_{h}"] = cg_, cl_
    vol_toks, vcounts = rank(universe, lambda t: volume(t, "24h"), TOP_N, True)
    vol_rows = [row(t) for t in vol_toks]
    # The same ranking with SOL, stablecoins, LSTs and tokenized stocks removed -
    # otherwise the "what is being traded" list is SOL, USDC, USDT, every pass.
    tok_only = {m: t for m, t in universe.items() if token_class(t) == "token"}
    tok_toks, _ = rank(tok_only, lambda t: volume(t, "24h"), TOP_N, True)
    tok_rows = [row(t) for t in tok_toks]
    for r in vol_rows + tok_rows:
        v, liq = r["volume_usd"].get("24h"), r.get("liquidity_usd_reported")
        # Turnover: 24h volume over reported liquidity. Descriptive, no threshold.
        r["turnover_24h"] = (round(v / liq, 2) if v is not None and liq else None)

    # The realizable check, gainers first - the headline Frank reads.
    verified = verify([movers["gainers_1h"], movers["gainers_6h"],
                       movers["gainers_24h"], tok_rows, vol_rows], rt=rt, budget_s=verify_s)
    for rows in list(movers.values()) + [vol_rows, tok_rows]:
        for r in rows:
            if r["token"] in verified:
                r.update(verified[r["token"]])

    trending = {"jupiter": {}, "geckoterminal": {}}
    for interval in ("1h", "6h", "24h"):
        label = f"jupiter.toptrending.{interval}"
        ms = [m for m, ls in lists.items() if label in ls][:TOP_N]
        trending["jupiter"][interval] = [
            {"rank": i + 1, "token": m, "symbol": universe[m].get("symbol"),
             "change_pct": _r(_stat(universe[m], interval, "priceChange"), 3),
             "in_journal": (None if seen is None else m in seen)}
            for i, m in enumerate(ms)]
    for d in GT_TRENDING:
        time.sleep(GT_GAP_S)
        pools = _fetch(f"geckoterminal.trending_pools.{d}",
                       f"{GT}/trending_pools?duration={d}", extract=lambda x: x["data"])
        trending["geckoterminal"][d] = [gt_row(p, seen) for p in pools or []]
    trending.update(dexscreener(seen))

    ours = []
    try:
        ours = our_clusters(obs, now) if obs else []
        SOURCES["clusters.ours"] = {"status": "ok" if ours else "empty", "n": len(ours),
                                    "error": None if obs else "journal unavailable"}
    except Exception as e:
        SOURCES["clusters.ours"] = {"status": "error", "n": 0, "error": type(e).__name__}
    metas = dexscreener_metas()
    LAST.clear()
    LAST.update(ts=now, universe=universe, lists=lists, verified=verified)

    head = {"built_at": built, "built_ts": int(now), "origin": origin}
    _write("movers.json", dict(head, universe_n=len(universe), sol_change_pct=sol,
                              min_liquidity_usd=MIN_LIQ_USD, exclusions=counts,
                              caveats=[CAVEATS[k] for k in ("universe", "liquidity",
                                                            "ranking", "symbols")],
                              lists=movers))
    sol_tok = universe.get(WSOL)
    _write("volume.json", dict(head, universe_n=len(universe), min_liquidity_usd=MIN_LIQ_USD,
                              exclusions=vcounts,
                              organic_share_baseline_sol={
                                  h: organic_share(sol_tok, h) if sol_tok else None
                                  for h in ("1h", "24h")},
                              caveats=[CAVEATS[k] for k in ("volume", "classes", "liquidity",
                                                            "ranking", "symbols")],
                              leaders_24h=vol_rows, leaders_24h_tokens=tok_rows))
    _write("trending.json", dict(head, caveats=[CAVEATS["boosts"], CAVEATS["symbols"]],
                                 **trending))
    _write("clusters.json", dict(head, window_h=24, caveats=[CAVEATS["clusters"]],
                                 ours=ours, dexscreener_metas=metas))
    _write("majors.json", dict(head, **tape))

    # ⛔ READ BACK. What the site will see is what is on disk.
    files = {}
    for n in FILES:
        d = _read(n)
        rows = rows_on_disk(n, d)
        files[n] = {"status": "unreadable" if d is None else ("ok" if rows else "empty"),
                    "rows": rows}
    total = sum(f["rows"] for f in files.values())
    checked = sum(1 for v in verified.values() if v["round_trip_status"] == "checked")
    in_j = [r.get("in_journal") for r in movers["gainers_24h"]]
    manifest = dict(head, elapsed_s=round(time.time() - t0, 1), http_calls=CALLS["n"],
                    universe_n=len(universe), rows_total=total, files=files,
                    sources=dict(SOURCES), round_trips_checked=checked,
                    top_gainers_24h_in_journal=(None if seen is None else
                                                f"{sum(1 for x in in_j if x)}/{len(in_j)}"),
                    caveats=CAVEATS)
    try:
        _history(int(now), dict(movers, volume_24h=vol_rows, volume_24h_tokens=tok_rows))
    except Exception as e:
        manifest["history_error"] = type(e).__name__
    _write("index.json", manifest)
    liveness.beat("market.snapshot", total,
                  detail=f"{total} rows, universe {len(universe)}, {checked} round trips")
    if verbose:
        print(line(manifest))
    return manifest


def line(m):
    bad = {k: v for k, v in (m.get("sources") or {}).items() if v.get("status") != "ok"}
    s = (f"  market: {m['rows_total']} rows, universe {m['universe_n']}, "
         f"{m['round_trips_checked']} round trips, {m['http_calls']} calls, "
         f"{m['elapsed_s']}s; top 24h gainers ever in our journal: "
         f"{m['top_gainers_24h_in_journal']}")
    if bad:
        s += "\n  ⚠️ sources not ok: " + ", ".join(
            f"{k} ({v.get('status')}: {v.get('error')})" for k, v in sorted(bad.items()))
    return s


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    build(verbose=True)
