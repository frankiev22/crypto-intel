"""The tracked universe: every Solana token over $1M that can actually be sold, kept for good.

Frank, 2026-09-18: "I need all coins over $1M market cap tracked and the top
trending ones always visible which can lead to determining the narratives"

⭐ A LEDGER, NOT A DETECTOR. Everything else in this repo fires once on an event
- a launch, a crossing, a graduation - and forgets the token. Here a token that
qualifies is admitted once and never removed. A coin that crossed $1M three
weeks ago and is running today is on the page because it never left it.

⛔ EVERY MEMBER IS GATED ON A REAL ROUND TRIP. Measured 2026-09-19 on a seeded
random 80 of the 1,035 tokens the listings put over $1M: 65.0% [54.1, 74.5]
return more than 90% of $100 bought and sold straight back, and 13 of the 15
with no buy route at all carry Jupiter's own "verified" tag. A listing's $1M is
not a $1M anyone can exit. The rule is pre-committed in docs/UNIVERSE.md §3:

  candidate  reported mcap >= $1M from any discovery source, not yet quoted
  member     a $100 round trip came back TRADEABLE (< 10% lost) - admitted
  refused    the admission round trip said anything else; kept, retried later

A member whose re-check fails stays a member with gate.status "failing". A
member that falls under $1M stays a member with below_floor_since.

Quotes only: chainfields.round_trip() asks Jupiter what $100 buys and what that
sells back for. Nothing is executed and no wallet exists.

Run: python universe.py [--gate-seconds N]     (one pass, writes data/universe/)
"""
import datetime as dt
import json
import os
import sys
import time
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import liveness
import market

BASE = os.path.dirname(os.path.abspath(__file__))
OUT_DIR = os.path.join(BASE, "data", "universe")
EVENTS_DIR = os.path.join(OUT_DIR, "events")
HISTORY_DIR = os.path.join(OUT_DIR, "history")

UA = {"User-Agent": "Mozilla/5.0 (crypto-intel universe)", "Accept": "application/json"}
JUP_TOKENS = "https://lite-api.jup.ag/tokens/v2"
CG = "https://api.coingecko.com/api/v3"
DS = "https://api.dexscreener.com"

# ⛔ docs/UNIVERSE.md §3, pre-committed. Frank's number and chainfields' existing
# verdict boundary - neither was fitted to the sample.
MCAP_FLOOR = 1_000_000
GATE_PASS = "TRADEABLE"
RETRY_REFUSED_H = 48
RETRY_REFUSED_TRENDING_H = 6
# Scheduling, not measurement: how stale a member's last quote may get before it
# is due again. The budget, not this number, decides how often it really is.
REVERIFY_H = 24
REVERIFY_TRENDING_H = 6

GATE_SECONDS = float(os.environ.get("CRYPTO_UNIVERSE_GATE_S", "150"))
SEARCH_BATCH = 100
CG_EVERY_H = 6
CG_MAP_REFRESH_H = 24
CG_GAP_S = 8.0
MILESTONE_LOOKBACK_D = 30
GRAD_WATCH_H = 72
THEMES_N = 12
THEME_GAP_S = 1.1      # Dexscreener meta pages, one per ~second
MEMBERS_CAP = 40      # members listed per cluster/theme in narratives.json
TRENDING_FRESH_H = 6  # trending marks older than this are shown as stale

CALLS = {"n": 0}
SOURCES = {}


# --------------------------------------------------------------------------
# HTTP. Every source's outcome is recorded; an empty answer and a failed one
# are different facts (docs/MARKET_DATA.md, index.json `sources`).
# --------------------------------------------------------------------------
def _get(url, timeout=30):
    CALLS["n"] += 1
    try:
        with urllib.request.urlopen(urllib.request.Request(url, headers=UA),
                                    timeout=timeout) as r:
            return r.status, json.loads(r.read())
    except urllib.error.HTTPError as e:
        return e.code, None
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e)[:100]}"


def _fetch(label, url, jupiter=False, timeout=30):
    if jupiter:
        try:
            import chainfields
            chainfields._JUP.take()
        except Exception:
            pass
    s, d = _get(url, timeout)
    if s != 200 or d is None or isinstance(d, str):
        prev = SOURCES.get(label) or {}
        SOURCES[label] = {"status": "error", "http": s, "n": prev.get("n", 0),
                          "calls": prev.get("calls", 0) + 1,
                          "error": d if isinstance(d, str) else f"HTTP {s}"}
        return None
    prev = SOURCES.get(label) or {}
    n = prev.get("n", 0) + (len(d) if isinstance(d, (list, dict)) else 0)
    SOURCES[label] = {"status": "ok" if n else "empty", "http": s, "n": n,
                      "calls": prev.get("calls", 0) + 1,
                      "error": prev.get("error") if prev.get("status") == "error" else None}
    return d


_num, _r, _stat, volume = market._num, market._r, market._stat, market.volume


def _iso(ts):
    return (dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")
            if ts else None)


# --------------------------------------------------------------------------
# State. ⛔ An unreadable members.json is NEVER overwritten.
# --------------------------------------------------------------------------
def _path(name):
    return os.path.join(OUT_DIR, name)


def load():
    """(state, error). A missing file is an empty universe; a corrupt one is an
    error, and the caller must not write - a fresh file would drop everyone."""
    p = _path("members.json")
    if not os.path.exists(p):
        return {"tokens": {}, "cg_map": {}, "cg_map_ts": 0, "cg_ts": 0}, None
    try:
        with open(p, encoding="utf-8") as f:
            d = json.load(f)
        if not isinstance(d.get("tokens"), dict):
            return None, "members.json has no tokens object"
        d.setdefault("cg_map", {})
        d.setdefault("cg_map_ts", 0)
        d.setdefault("cg_ts", 0)
        return d, None
    except Exception as e:
        return None, f"members.json unreadable: {type(e).__name__}"


def _write(name, obj):
    os.makedirs(OUT_DIR, exist_ok=True)
    p = _path(name)
    tmp = p + ".tmp"
    with open(tmp, "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, p)
    return p


def _read(name):
    try:
        with open(_path(name), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def _append(dirpath, fname, rows):
    if not rows:
        return None
    os.makedirs(dirpath, exist_ok=True)
    p = os.path.join(dirpath, fname)
    with open(p, "a", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False, separators=(",", ":")) + "\n")
    return p


# --------------------------------------------------------------------------
# One token's latest snapshot, from a Jupiter token object.
# --------------------------------------------------------------------------
def snapshot(t, now):
    a = t.get("audit") or {}
    return {
        "ts": int(now),
        "price_usd": _num(t.get("usdPrice")),
        "mcap_usd": _r(_num(t.get("mcap")), 0),
        "fdv_usd": _r(_num(t.get("fdv")), 0),
        # Jupiter's number - NOT realizable depth. The gate is the round trip.
        "liquidity_usd_reported": _r(_num(t.get("liquidity")), 0),
        "holders": t.get("holderCount"),
        "change_pct": {h: _r(_stat(t, h, "priceChange"), 2) for h in ("5m", "1h", "6h", "24h")},
        "volume_usd": {h: _r(volume(t, h), 0) for h in ("1h", "24h")},
        "traders_24h": _stat(t, "24h", "numTraders"),
        "organic_score": _r(_num(t.get("organicScore")), 1),
        "top_holders_pct": _r(_num(a.get("topHoldersPercentage")), 2),
        "mint_authority_disabled": a.get("mintAuthorityDisabled"),
        "freeze_authority_disabled": a.get("freezeAuthorityDisabled"),
        "cap_backing_pct": cap_backing(_num(t.get("liquidity")), _num(t.get("mcap"))),
    }


def cap_backing(liq, mcap):
    """⛔ What the pool could pay out if EVERY holder sold, as a % of the cap.

    Found on the first seed (2026-09-19): 30 members from the graduation ledger,
    tickers reused across up to 6 contracts, ~2,000 holders each with the top 10
    holding a median 9.8% (other members: 34.8%), claimed $3.53B between them -
    $827M for one - on pools holding ~$640k of SOL. Supply spread over a wallet
    farm, a pool holding almost none of it: price x supply is fiction, and a $100
    round trip still passes at 0.6%. The quote half of Jupiter's reported
    liquidity over the cap. DESCRIPTIVE - it overlaps real coins (their p10 is
    0.087%), so it is shown on every row and gates nothing (docs/UNIVERSE.md 3a)."""
    if liq is None or not mcap:
        return None
    return round(liq / 2 / mcap * 100, 4)


def _mcap(e):
    last = e.get("last") or {}
    m = last.get("mcap_usd")
    return m if m is not None else e.get("cg_mcap_usd")


# --------------------------------------------------------------------------
# Discovery
# --------------------------------------------------------------------------
def jupiter_verified():
    d = _fetch("jupiter.verified", f"{JUP_TOKENS}/tag?query=verified", jupiter=True, timeout=60)
    return {t["id"]: t for t in d or [] if isinstance(t, dict) and t.get("id")}


def jupiter_search(mints):
    out = {}
    mints = list(mints)
    for i in range(0, len(mints), SEARCH_BATCH):
        d = _fetch("jupiter.search", f"{JUP_TOKENS}/search?query=" + ",".join(mints[i:i + SEARCH_BATCH]),
                   jupiter=True)
        for t in d or []:
            if isinstance(t, dict) and t.get("id"):
                out[t["id"]] = t
    return out


def market_lists():
    """The market stage's Jupiter lists: this process's if it ran, else fetched."""
    last = getattr(market, "LAST", None)
    if last and time.time() - last.get("ts", 0) < 1800:
        return last["universe"], last["lists"], last.get("verified") or {}, "market stage (same pass)"
    universe, lists = market.gather_universe()
    return universe, lists, {}, "fetched"


def trending_marks(now):
    """{mint: ["jup.1h#3", ...]} from the trending file the site reads, plus its age."""
    try:
        with open(os.path.join(market.OUT_DIR, "trending.json"), encoding="utf-8") as f:
            tr = json.load(f)
    except Exception:
        SOURCES["market.trending_file"] = {"status": "error", "n": 0, "error": "unreadable"}
        return {}, None, []
    marks, rows = {}, []

    def mark(m, label, rank, sym, extra=None):
        if not m:
            return
        marks.setdefault(m, []).append(f"{label}#{rank}")
        rows.append(dict({"source": label, "rank": rank, "token": m, "symbol": sym}, **(extra or {})))

    for h, L in (tr.get("jupiter") or {}).items():
        for x in L or []:
            mark(x.get("token"), f"jupiter.toptrending.{h}", x.get("rank"), x.get("symbol"))
    for h, L in (tr.get("geckoterminal") or {}).items():
        for i, x in enumerate(L or []):
            mark(x.get("token"), f"geckoterminal.trending.{h}", i + 1, None,
                 {"pool": x.get("pool"), "dex": x.get("dex")})
    for key in ("boosts_top",):
        for i, x in enumerate(tr.get(key) or []):
            mark(x.get("token"), f"dexscreener.{key}", i + 1, None,
                 {"paid": True, "boost_total": x.get("boost_total")})
    SOURCES["market.trending_file"] = {"status": "ok" if marks else "empty", "n": len(marks),
                                       "error": None}
    return marks, tr.get("built_ts"), rows


def our_crossings(now):
    import milestones
    out = {}
    lo = now - MILESTONE_LOOKBACK_D * 86400
    try:
        names = sorted(n for n in os.listdir(milestones.DIR) if n[:4].isdigit() and n.endswith(".jsonl"))
    except OSError:
        return out
    for n in names[-2:]:
        with open(os.path.join(milestones.DIR, n), encoding="utf-8") as f:
            for line in f:
                if '"mcap_1m"' not in line and '"mcap_5m"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("token") and (r.get("crossed_ts") or 0) > lo:
                    out.setdefault(r["token"], f"milestone.{r.get('milestone')}")
    return out


def recent_graduations(now):
    try:
        import graduations
        return graduations.recent_mints(now - GRAD_WATCH_H * 3600)
    except Exception as e:
        SOURCES["graduations"] = {"status": "error", "n": 0, "error": type(e).__name__}
        return set()


def coingecko(state, now):
    """{mint: mcap} for solana-ecosystem coins >= floor. Every CG_EVERY_H only."""
    if now - (state.get("cg_ts") or 0) < CG_EVERY_H * 3600:
        SOURCES["coingecko.markets"] = {"status": "skipped", "n": 0,
                                        "error": f"runs every {CG_EVERY_H}h; last "
                                                 f"{_iso(state.get('cg_ts'))}"}
        return None
    by_id, page = {}, 1
    while page <= 8:
        rows = _fetch("coingecko.markets",
                      f"{CG}/coins/markets?vs_currency=usd&category=solana-ecosystem"
                      f"&order=market_cap_desc&per_page=250&page={page}")
        if not isinstance(rows, list) or not rows:
            break
        keep = [r for r in rows if (_num(r.get("market_cap")) or 0) >= MCAP_FLOOR]
        for r in keep:
            by_id[r["id"]] = _num(r.get("market_cap"))
        if len(keep) < len(rows):
            break
        page += 1
        time.sleep(CG_GAP_S)
    if not by_id:
        return None
    cmap = state["cg_map"]
    unknown = [i for i in by_id if i not in cmap]
    if unknown and now - (state.get("cg_map_ts") or 0) >= CG_MAP_REFRESH_H * 3600:
        time.sleep(CG_GAP_S)
        cl = _fetch("coingecko.coins_list", f"{CG}/coins/list?include_platform=true", timeout=90)
        if isinstance(cl, list):
            state["cg_map_ts"] = int(now)
            for c in cl:
                if isinstance(c, dict) and c.get("id") in by_id:
                    cmap[c["id"]] = ((c.get("platforms") or {}).get("solana") or None)
    state["cg_ts"] = int(now)
    return {cmap[i]: m for i, m in by_id.items() if cmap.get(i)}


# --------------------------------------------------------------------------
# The gate
# --------------------------------------------------------------------------
def gate_queue(tokens, now, trending):
    q = []
    for m, e in tokens.items():
        g = e.get("gate") or {}
        last_ts = g.get("ts") or 0
        age = now - last_ts
        tr = m in trending
        liq = ((e.get("last") or {}).get("liquidity_usd_reported")) or 0
        above = (_mcap(e) or 0) >= MCAP_FLOOR
        st = e.get("status")
        if st == "candidate":
            # never-quoted first; a failed CHECK (not a verdict) goes behind them
            q.append(((0 if tr else 1), 1 if g.get("error") else 0, -liq, m))
        elif st == "member":
            if tr and age >= REVERIFY_TRENDING_H * 3600:
                q.append((2, 0, last_ts, m))
            elif age >= REVERIFY_H * 3600:
                q.append((4, 0, last_ts, m))
        elif st == "refused" and above:
            if tr and age >= RETRY_REFUSED_TRENDING_H * 3600:
                q.append((3, 0, last_ts, m))
            elif age >= RETRY_REFUSED_H * 3600:
                q.append((5, 0, last_ts, m))
    q.sort()
    return [x[-1] for x in q]


def apply_verdict(e, res, now, origin):
    """Move one token through the pre-committed state machine. Returns the event."""
    v = res.get("verdict")
    before = e.get("status")
    prev_gate = e.get("gate") or {}
    g = {"verdict": v, "rt_cost_pct": res.get("rt_cost_pct"), "usd_back": res.get("usd_back"),
         "probe_usd": res.get("probe_usd"), "ts": int(res.get("ts") or now),
         # ⭐ chain supply x the price the $100 buy actually got (A3). Not
         # Jupiter's mcap: nothing self-reported goes into it. None = unknown.
         "fdv_onchain_usd": res.get("fdv_onchain_usd"),
         "error": None if v else (res.get("error") or "no verdict"), "origin": origin}
    ev = {"ts": int(now), "token": e["token"], "event": "gate", "verdict": v,
          "rt_cost_pct": g["rt_cost_pct"], "status_before": before, "origin": origin}
    if not v:
        # ⛔ A check that could not run is not a verdict. State unchanged.
        g["status"] = prev_gate.get("status")
        g["verdict"] = prev_gate.get("verdict")
        g["failing_since"] = prev_gate.get("failing_since")
        g["last_error_ts"] = int(now)
        e["gate"] = g
        ev.update(event="gate_check_failed", error=g["error"], status_after=before)
        return ev
    if before in ("candidate", "refused"):
        if v == GATE_PASS:
            e["status"] = "member"
            e["admitted_ts"] = int(now)
            e["admitted_mcap_usd"] = _mcap(e)
            e["admitted_rt"] = {"verdict": v, "rt_cost_pct": g["rt_cost_pct"]}
            e["admitted_fdv_onchain_usd"] = g["fdv_onchain_usd"]
            g["status"] = "passing"
            ev["event"] = "admitted"
            if before == "refused":
                ev["previously_refused"] = True
        else:
            e["status"] = "refused"
            g["status"] = "refused"
            ev["event"] = "refused"
    else:  # member
        if v == GATE_PASS:
            g["status"] = "passing"
            if prev_gate.get("status") == "failing":
                ev["event"] = "gate_restored"
        else:
            g["status"] = "failing"
            g["failing_since"] = prev_gate.get("failing_since") or int(now)
            if prev_gate.get("status") != "failing":
                ev["event"] = "gate_failed"
    if g.get("status") != "failing":
        g.pop("failing_since", None)
    e["gate"] = g
    e["gate_checks"] = (e.get("gate_checks") or 0) + 1
    ev["status_after"] = e["status"]
    return ev


def _fdv_onchain(m, res):
    import chainfields
    v = chainfields.market_cap(m, rt=res)
    return None if v is None else round(v)


def gate(tokens, now, trending, budget_s, rt=None, reuse=None, origin=None, fdv=None):
    """Quote down the priority queue until the budget is spent. Returns
    (events, stats). `reuse` is {mint: round_trip dict} already quoted this pass."""
    if rt is None:
        import chainfields
        rt = chainfields.round_trip
    fdv = _fdv_onchain if fdv is None else fdv
    order = gate_queue(tokens, now, trending)
    events, t0, n_q, n_reused = [], time.time(), 0, 0
    for m in order:
        r0 = (reuse or {}).get(m)
        if r0 and r0.get("verdict") and now - (r0.get("ts") or 0) < 1800:
            res, n_reused = r0, n_reused + 1
        else:
            if time.time() - t0 >= budget_s:
                break
            try:
                res = rt(m) or {}
            except Exception as ex:
                res = {"error": type(ex).__name__}
            n_q += 1
            if res.get("verdict") == GATE_PASS and res.get("px_per_raw"):
                try:
                    res = dict(res, fdv_onchain_usd=fdv(m, res))
                except Exception:
                    res = dict(res, fdv_onchain_usd=None)
        events.append(apply_verdict(tokens[m], res, time.time(), origin))
    elapsed = time.time() - t0
    stats = {"queue": len(order), "quoted": n_q, "reused_from_market": n_reused,
             "deferred": max(0, len(order) - n_q - n_reused), "seconds": round(elapsed, 1),
             "budget_s": round(budget_s, 1)}
    stats["deferred_by_status"] = {}
    done = {ev["token"] for ev in events}
    for m in order:
        if m not in done:
            st = tokens[m].get("status")
            stats["deferred_by_status"][st] = stats["deferred_by_status"].get(st, 0) + 1
    return events, stats


# --------------------------------------------------------------------------
# Narratives: trending x the universe
# --------------------------------------------------------------------------
def _brief(m, e):
    last = e.get("last") or {}
    g = e.get("gate") or {}
    return {"token": m, "symbol": e.get("symbol"), "symbol_flags": e.get("symbol_flags"),
            "name": e.get("name"), "status": e.get("status"), "class": e.get("class"),
            "gate": g.get("status"), "gate_verdict": g.get("verdict"), "gate_ts": g.get("ts"),
            "mcap_usd": last.get("mcap_usd"), "cap_backing_pct": last.get("cap_backing_pct"),
            "liquidity_usd_reported": last.get("liquidity_usd_reported"),
            "ticker_contracts": e.get("ticker_contracts"),
            "top_holders_pct": last.get("top_holders_pct"),
            "from_graduation_ledger": "graduation" in (e.get("sources") or []),
            "change_pct": last.get("change_pct"),
            "volume_usd_24h": (last.get("volume_usd") or {}).get("24h"),
            "trending": e.get("trending") or []}


def _agg(members):
    mc = [(b["mcap_usd"], (b["change_pct"] or {}).get("24h")) for b in members]
    tot = sum(x for x, _ in mc if x)
    w = [(x, c) for x, c in mc if x and c is not None]
    wsum = sum(x for x, _ in w)
    liq = [b.get("liquidity_usd_reported") for b in members if b.get("liquidity_usd_reported") is not None]
    tops = sorted(b["top_holders_pct"] for b in members if b.get("top_holders_pct") is not None)
    return {"mcap_usd": round(tot) if tot else None,
            # ⛔ never the cap without what backs it: the quote half of reported liquidity
            "mcap_backed_usd": round(sum(liq) / 2) if liq else None,
            "shared_ticker_n": sum(1 for b in members if (b.get("ticker_contracts") or 0) > 1),
            "from_graduation_ledger_n": sum(1 for b in members if b.get("from_graduation_ledger")),
            "median_top_holders_pct": tops[len(tops) // 2] if tops else None,
            "volume_usd_24h": round(sum(b["volume_usd_24h"] or 0 for b in members)) or None,
            # mcap-weighted: what the narrative as a whole did, not its best coin
            "change_24h_pct_mcap_weighted": round(sum(x * c for x, c in w) / wsum, 2) if wsum else None,
            "trending_now_n": sum(1 for b in members if b["trending"])}


def name_clusters(tokens, now):
    import clusters
    rows = []
    for m, e in tokens.items():
        if e.get("status") != "member" or e.get("class") != "token":
            continue
        rows.append({"ts": e.get("admitted_ts") or e.get("first_seen_ts") or now, "token": m,
                     "symbol": f"{e.get('symbol') or ''} {e.get('name') or ''}".strip(),
                     "liq": (e.get("last") or {}).get("liquidity_usd_reported")})
    cs = clusters.find(rows, window_h=1e7, min_members=3, end=now + 1)
    out = []
    for c in cs:
        mem = [_brief(r["token"], tokens[r["token"]]) for r in c["members"]]
        mem.sort(key=lambda b: -(b["mcap_usd"] or 0))
        out.append(dict({"root": c["root"], "size": c["size"], "variants": c["variants"],
                         "swarm": c["swarm"]}, **_agg(mem),
                        members=mem[:MEMBERS_CAP], members_truncated=max(0, len(mem) - MEMBERS_CAP)))
    out.sort(key=lambda c: (-c["trending_now_n"], -(c["volume_usd_24h"] or 0)))
    return out


def themes(tokens):
    try:
        with open(os.path.join(market.OUT_DIR, "clusters.json"), encoding="utf-8") as f:
            metas = (json.load(f) or {}).get("dexscreener_metas") or []
    except Exception:
        metas = []
    if not metas:
        metas = market.dexscreener_metas()
    out = []
    for meta in metas[:THEMES_N]:
        slug = meta.get("slug")
        if not slug:
            continue
        d = _fetch("dexscreener.meta_detail", f"{DS}/metas/meta/v1/{slug}")
        time.sleep(THEME_GAP_S)
        pairs = (d or {}).get("pairs") if isinstance(d, dict) else None
        sol = {}
        for p in pairs or []:
            if p.get("chainId") == "solana":
                b = (p.get("baseToken") or {}).get("address")
                if b:
                    sol.setdefault(b, (p.get("baseToken") or {}).get("symbol"))
        inu = [_brief(m, tokens[m]) for m in sol if m in tokens]
        inu.sort(key=lambda b: -(b["mcap_usd"] or 0))
        mem = [b for b in inu if b["status"] == "member"]
        out.append(dict({"name": meta.get("name"), "slug": slug,
                         "dexscreener": {k: meta.get(k) for k in ("token_count", "mcap_usd",
                                                                  "mcap_change_pct", "volume_usd")},
                         "pairs_returned": len(pairs or []), "solana_tokens": len(sol),
                         "in_universe_n": len(inu), "members_n": len(mem)},
                        **_agg(mem), tokens=inu[:MEMBERS_CAP],
                        not_in_universe=[{"token": m, "symbol": s} for m, s in sol.items()
                                         if m not in tokens][:MEMBERS_CAP]))
    return out


# --------------------------------------------------------------------------
# The pass
# --------------------------------------------------------------------------
def build(verbose=True, now=None, rt=None, gate_s=None, discover=True, fdv=None):
    now = time.time() if now is None else now
    t0 = time.time()
    CALLS["n"] = 0
    SOURCES.clear()
    origin = os.environ.get("CRYPTO_ORIGIN") or liveness.origin()
    gate_s = GATE_SECONDS if gate_s is None else gate_s

    state, err = load()
    if state is None:
        # ⛔ Never overwrite what we cannot read. Liveness goes stale on its own.
        print(f"  universe: REFUSING TO WRITE - {err}")
        return {"error": err}
    tokens = state["tokens"]
    before_n = {s: sum(1 for e in tokens.values() if e.get("status") == s)
                for s in ("member", "candidate", "refused")}

    # ---- 1. discovery ---------------------------------------------------
    info, sources_of, cg_mcap = {}, {}, {}

    def found(m, src):
        sources_of.setdefault(m, set()).add(src)

    reuse = {}
    probe = set()
    if discover:
        for m, t in jupiter_verified().items():
            info[m] = t
            if (_num(t.get("mcap")) or 0) >= MCAP_FLOOR:
                found(m, "jupiter.verified")
        try:
            uni, lists, verified, how = market_lists()
            SOURCES["market.lists"] = {"status": "ok" if uni else "empty", "n": len(uni),
                                       "error": None, "via": how}
            for m, t in uni.items():
                info.setdefault(m, t)
                if (_num(t.get("mcap")) or 0) >= MCAP_FLOOR:
                    for lab in lists.get(m, ()):
                        found(m, lab)
            for m, v in (verified or {}).items():
                if (v.get("round_trip") or {}).get("verdict"):
                    reuse[m] = v["round_trip"]
        except Exception as e:
            SOURCES["market.lists"] = {"status": "error", "n": 0, "error": type(e).__name__}
        for m, lab in our_crossings(now).items():
            probe.add(m)
            sources_of.setdefault(m, set())
            sources_of[m].add(lab + "?")      # confirmed below if mcap >= floor
        for m in recent_graduations(now):
            probe.add(m)
            sources_of.setdefault(m, set()).add("graduation?")
        cg = coingecko(state, now)
        for m, mc in (cg or {}).items():
            cg_mcap[m] = mc
            found(m, "coingecko")
    marks, trending_ts, trending_rows = trending_marks(now)
    probe |= set(marks)

    # ---- 2. re-check everything known, plus what discovery wants priced ---
    want = (set(tokens) | probe | set(cg_mcap)) - set(info)
    info.update(jupiter_search(want))

    # ---- 3. fold into state ---------------------------------------------
    new_events = []
    for m in set(tokens) | set(info) | set(cg_mcap):
        t = info.get(m)
        srcs = sources_of.get(m, set())
        mc = _num((t or {}).get("mcap")) if t else None
        if mc is None:
            mc = cg_mcap.get(m)
        confirmed = {s.rstrip("?") for s in srcs if not s.endswith("?")}
        if mc is not None and mc >= MCAP_FLOOR:
            confirmed |= {s.rstrip("?") for s in srcs if s.endswith("?")}
            if m in marks:
                confirmed.add("trending")
        e = tokens.get(m)
        if e is None:
            if not confirmed or mc is None or mc < MCAP_FLOOR:
                continue          # not over $1M: not in the universe
            e = tokens[m] = {"token": m, "status": "candidate", "first_seen_ts": int(now),
                             "first_seen_mcap_usd": round(mc), "sources": []}
            new_events.append({"ts": int(now), "token": m, "event": "discovered",
                               "mcap_usd": round(mc), "sources": sorted(confirmed),
                               "origin": origin})
        e["sources"] = sorted(set(e.get("sources") or []) | confirmed)
        if m in cg_mcap:
            e["cg_mcap_usd"] = round(cg_mcap[m])
        if t:
            e["symbol"] = t.get("symbol")
            e["name"] = (t.get("name") or "")[:60] or None
            e["symbol_flags"] = market.symbol_flags(t.get("symbol"))
            e["class"] = market.token_class(t)
            e["launchpad"] = t.get("launchpad")
            e["tags"] = [x for x in (t.get("tags") or []) if isinstance(x, str)][:8]
            e["last"] = snapshot(t, now)
            e.pop("jupiter_missing_since", None)
        elif m in tokens and "jupiter_missing_since" not in e:
            e["jupiter_missing_since"] = int(now)
        cur = _mcap(e)
        if cur is not None and cur > (e.get("peak_mcap_usd") or 0):
            e["peak_mcap_usd"], e["peak_mcap_ts"] = round(cur), int(now)
        if e.get("status") == "member" and cur is not None:
            if cur < MCAP_FLOOR and not e.get("below_floor_since"):
                e["below_floor_since"] = int(now)
                new_events.append({"ts": int(now), "token": m, "event": "below_floor",
                                   "mcap_usd": round(cur), "origin": origin})
            elif cur >= MCAP_FLOOR and e.get("below_floor_since"):
                new_events.append({"ts": int(now), "token": m, "event": "back_above_floor",
                                   "mcap_usd": round(cur), "below_since": e["below_floor_since"],
                                   "origin": origin})
                e.pop("below_floor_since", None)
    # Standing rule 2 inside the universe: how many tracked contracts carry this
    # ticker. The farm above reuses one ticker across up to six.
    tick = {}
    for e in tokens.values():
        k = str(e.get("symbol") or "").strip().upper()
        if k:
            tick[k] = tick.get(k, 0) + 1
    for m, e in tokens.items():
        e["trending"] = marks.get(m, [])
        k = str(e.get("symbol") or "").strip().upper()
        e["ticker_contracts"] = tick.get(k) if k else None

    # ---- 4. the gate ------------------------------------------------------
    gate_events, gstats = gate(tokens, now, marks, gate_s, rt=rt, reuse=reuse, origin=origin,
                               fdv=fdv)

    # ---- 5. write, then read back ----------------------------------------
    counts = {s: sum(1 for e in tokens.values() if e.get("status") == s)
              for s in ("member", "candidate", "refused")}
    counts["members_gate_failing"] = sum(1 for e in tokens.values() if e.get("status") == "member"
                                         and (e.get("gate") or {}).get("status") == "failing")
    counts["members_below_floor"] = sum(1 for e in tokens.values() if e.get("status") == "member"
                                        and e.get("below_floor_since"))
    counts["members_trending_now"] = sum(1 for e in tokens.values() if e.get("status") == "member"
                                         and e.get("trending"))
    head = {"built_at": _iso(now), "built_ts": int(now), "origin": origin,
            "mcap_floor_usd": MCAP_FLOOR, "gate_rule": "$100 round trip TRADEABLE (<10% lost)",
            "rule_source": "docs/UNIVERSE.md section 3 (pre-committed)"}
    _write("members.json", dict(head, counts=counts, cg_map=state["cg_map"],
                                cg_map_ts=state.get("cg_map_ts", 0), cg_ts=state.get("cg_ts", 0),
                                tokens=tokens))
    month = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m")
    _append(EVENTS_DIR, f"{month}.jsonl", new_events + gate_events)
    day = dt.datetime.fromtimestamp(now, dt.timezone.utc).strftime("%Y-%m-%d")
    cols = ["token", "price_usd", "mcap_usd", "liquidity_usd_reported", "volume_usd_24h",
            "change_24h_pct", "gate"]
    hist = [[m, (e.get("last") or {}).get("price_usd"), (e.get("last") or {}).get("mcap_usd"),
             (e.get("last") or {}).get("liquidity_usd_reported"),
             ((e.get("last") or {}).get("volume_usd") or {}).get("24h"),
             ((e.get("last") or {}).get("change_pct") or {}).get("24h"),
             (e.get("gate") or {}).get("status")]
            for m, e in tokens.items() if e.get("status") == "member"]
    _append(HISTORY_DIR, f"{day}.jsonl", [{"ts": int(now), "cols": cols, "rows": hist}] if hist else [])

    stale_tr = (trending_ts is None) or (now - trending_ts > TRENDING_FRESH_H * 3600)
    tr_rows = []
    for r in trending_rows:
        e = tokens.get(r["token"])
        tr_rows.append(dict(r, universe_status=(e or {}).get("status") or "not tracked",
                            **({k: v for k, v in _brief(r["token"], e).items()
                                if k not in ("token", "trending")} if e else {"symbol": r.get("symbol")})))
    narr = dict(head, trending_built_at=_iso(trending_ts), trending_stale=stale_tr,
                caveats=["Descriptive only. Clusters are ordered by how many members are trending "
                         "now, then 24h volume - size and activity, never a quality ranking.",
                         "Market cap is price x supply and can be fiction. Never show or sum it without "
                         "cap_backing_pct / mcap_backed_usd beside it: 30 members of the first seed "
                         "claimed $3.53B on pools holding a fraction of a percent of that "
                         "(docs/UNIVERSE.md 3a).",
                         "Dexscreener boosts are PAID promotion.",
                         "Themes are Dexscreener's categories; it returns only the top pairs of each.",
                         "A trending token 'not tracked' is under $1M or was never priced by Jupiter."],
                trending_now=tr_rows, name_clusters=[], themes=[])
    try:
        narr["name_clusters"] = name_clusters(tokens, now)
    except Exception as e:
        SOURCES["narratives.name_clusters"] = {"status": "error", "n": 0, "error": type(e).__name__}
    if discover:
        try:
            narr["themes"] = themes(tokens)
        except Exception as e:
            SOURCES["narratives.themes"] = {"status": "error", "n": 0, "error": type(e).__name__}
    _write("narratives.json", narr)

    back = _read("members.json")
    on_disk = sum(1 for e in ((back or {}).get("tokens") or {}).values() if e.get("status") == "member")
    nback = _read("narratives.json") or {}
    manifest = dict(head, elapsed_s=round(time.time() - t0, 1), http_calls=CALLS["n"],
                    counts=counts, counts_before=before_n,
                    members_on_disk=on_disk, members_file_readable=back is not None,
                    narratives_on_disk={k: len(nback.get(k) or []) for k in
                                        ("trending_now", "name_clusters", "themes")},
                    discovered_this_pass=sum(1 for x in new_events if x["event"] == "discovered"),
                    gate=gstats, sources=dict(SOURCES), trending_stale=stale_tr)
    _write("index.json", manifest)
    liveness.beat("universe.members", on_disk,
                  detail=f"{on_disk} members, {counts['candidate']} candidates, "
                         f"{gstats['quoted']} quoted, {gstats['deferred']} deferred")
    if verbose:
        print(line(manifest))
    return manifest


def line(m):
    if m.get("error"):
        return f"  universe: ERROR {m['error']}"
    c, g = m["counts"], m["gate"]
    return (f"  universe: {c['member']} members ({c['members_gate_failing']} failing the gate, "
            f"{c['members_below_floor']} under $1M, {c['members_trending_now']} trending), "
            f"{c['candidate']} candidates, {c['refused']} refused | gate quoted {g['quoted']} "
            f"(+{g['reused_from_market']} reused) in {g['seconds']}s, {g['deferred']} deferred | "
            f"{m['http_calls']} calls, {m['elapsed_s']}s")


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    gs = None
    if "--gate-seconds" in sys.argv:
        gs = float(sys.argv[sys.argv.index("--gate-seconds") + 1])
    build(gate_s=gs)
