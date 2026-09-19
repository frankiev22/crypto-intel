"""market.py writes what it says, excludes what it says, and says what it skipped.
Run: python test_market.py      (offline - every source is a canned payload)

⛔ Every assertion here is on the FILES market.build() writes, read back from
disk, because that is what the site reads. A list that was computed correctly
and never landed is the failure this project keeps finding (standing rule 16).
"""
import io
import json
import os
import sys
import time
import types

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
ROOT = testsandbox.activate()

import chainfields
import journal
import liveness
import market
import paper

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


# No sleeping and no shared Jupiter bucket in an offline test.
market.time = types.SimpleNamespace(time=time.time, sleep=lambda s: None)
market.GT_GAP_S = 0
chainfields._JUP.take = lambda *a, **k: None

WSOL = market.WSOL
NOW = 1789900000.0


def stats(chg, vol=None, org=None, traders=None):
    s = {"priceChange": chg}
    if vol is not None:
        s.update(buyVolume=vol / 2, sellVolume=vol / 2)
    if org is not None:
        s.update(buyOrganicVolume=org / 2, sellOrganicVolume=org / 2)
    if traders is not None:
        s["numTraders"] = traders
    return s


def tok(mint, sym, c1, c6, c24, liq, vol24=None, org24=None, tags=None, **kw):
    t = {"id": mint, "symbol": sym, "name": sym, "liquidity": liq,
         "stats5m": stats(0.1), "stats1h": stats(c1, vol=(vol24 or 0) / 10),
         "stats6h": stats(c6), "stats24h": stats(c24, vol=vol24, org=org24, traders=500),
         "tags": tags or [], "holderCount": 900,
         "firstPool": {"createdAt": "2026-09-18T00:00:00Z"},
         "audit": {"mintAuthorityDisabled": True, "freezeAuthorityDisabled": True}}
    t.update(kw)
    return t


SOL = tok(WSOL, "SOL", -0.5, 1.0, 10.0, 9e8, vol24=5e9, org24=1e8, tags=["major", "strict"])
USDC = tok("USDCmint", "USDC", 0.0, 0.0, 0.0, 5e8, vol24=3e9, org24=1e8, tags=["stable"])
STOCK = tok("SPYxmint", "SPYx", 0.1, 0.2, 0.3, 2e6, vol24=4e7, tags=["xstocks", "stocks"])
BIG = tok("BIGmint", "BIG", 900.0, 5000.0, 20000.0, 50000.0, vol24=2e7, org24=1e6)
MID = tok("MIDmint", "MID", 50.0, 60.0, 70.0, 20000.0, vol24=1e6, org24=5e4)
POOR = tok("POORmint", "POOR", 99999.0, 99999.0, 99999.0, 50.0, vol24=9e9)     # under the floor
NOLIQ = tok("NOLIQmint", "NOLIQ", 88888.0, 88888.0, 88888.0, None)             # liquidity unknown
DOWN = tok("DOWNmint", "DOWN", -40.0, -60.0, -80.0, 30000.0, vol24=2e5)
NOSTAT = {"id": "NOSTATmint", "symbol": "NS", "liquidity": 1e6}                # no stats at all
BIDI = tok("BIDImint", "U" + chr(0x202E) + "CDS", 10.0, 10.0, 10.0, 40000.0, vol24=1e5)
ALL = [SOL, USDC, STOCK, BIG, MID, POOR, NOLIQ, DOWN, NOSTAT, BIDI]

GT_POOL = {"attributes": {"address": "poolX", "name": "BIG / SOL",
                          "price_change_percentage": {"h1": "12.5", "h24": "300"},
                          "volume_usd": {"h24": "123456.7"}, "reserve_in_usd": "40000",
                          "transactions": {"h24": {"buyers": 10, "sellers": 4}}},
           "relationships": {"base_token": {"data": {"id": "solana_BIGmint"}},
                             "dex": {"data": {"id": "pumpswap"}}}}
BOOST = [{"chainId": "solana", "tokenAddress": "BOOSTmint", "amount": 10, "totalAmount": 500,
          "url": "u", "description": "d", "links": [{"type": "twitter"}]},
         {"chainId": "base", "tokenAddress": "0xnotsolana", "amount": 1}]
META = [{"name": "Cat", "slug": "cat", "tokenCount": 97, "marketCap": 9e8,
         "marketCapChange": {"h24": 9.2}, "volume": 2e8, "liquidity": 6e7}]

FAIL = set()          # URL substrings that should fail this build


def fake_get(url, timeout=20):
    market.CALLS["n"] += 1
    for f in FAIL:
        if f in url:
            return 503, None
    if "lite-api.jup.ag/tokens/v2/search" in url:
        return 200, [SOL]
    if "lite-api.jup.ag/tokens/v2/" in url:
        return 200, [dict(t) for t in ALL]
    if "coingecko.com/api/v3/simple/price" in url:
        return 200, {"solana": {"usd": 113.0, "usd_24h_change": 10.0},
                     "bitcoin": {"usd": 81000.0}, "ethereum": {"usd": 2600.0}}
    if "coingecko.com/api/v3/global" in url:
        return 200, {"data": {"total_volume": {"usd": 1.2e11},
                              "total_market_cap": {"usd": 2.7e12},
                              "market_cap_change_percentage_24h_usd": 2.9}}
    if "llama.fi" in url:
        return 200, {"total24h": 2.5e9, "total48hto24h": 2.8e9, "total7d": 1.7e10,
                     "change_1d": -7.4}
    if "geckoterminal.com" in url:
        return 200, {"data": [GT_POOL]}
    if "token-boosts" in url:
        return 200, BOOST
    if "token-profiles" in url or "community-takeovers" in url:
        return 200, [dict(BOOST[0], claimDate="2026-09-18")]
    if "metas/trending" in url:
        return 200, META
    return 404, None


market._get = fake_get
RT_CALLS = []


def fake_rt(mint):
    RT_CALLS.append(mint)
    if mint == "MIDmint":
        raise RuntimeError("quote service down")
    return {"verdict": "TRADEABLE", "rt_cost_pct": 3.1, "usd_back": 96.9,
            "probe_usd": 100, "price_impact_pct": 0.4, "ts": int(NOW)}


# One of these tokens is in our journal - the in_journal field must say so.
os.makedirs(journal.OBS, exist_ok=True)
with io.open(os.path.join(journal.OBS, "2026-09-18.jsonl"), "w", encoding="utf-8") as f:
    # journal._read() keeps only rows carrying both `ts` and `pair`.
    f.write(json.dumps({"token": "MIDmint", "pair": "MIDpair", "symbol": "MID",
                        "ts": NOW - 3600}) + "\n")


def read(name):
    with io.open(os.path.join(market.OUT_DIR, name), encoding="utf-8") as f:
        return json.load(f)


print("=" * 70)
print("0. the liquidity floor is the project's existing one, not a new number")
print("=" * 70)
check("⛔ market.MIN_LIQ_USD == paper.MIN_EXIT_DEPTH", market.MIN_LIQ_USD == paper.MIN_EXIT_DEPTH,
      f"{market.MIN_LIQ_USD} vs {paper.MIN_EXIT_DEPTH}")

m = market.build(verbose=False, now=NOW, rt=fake_rt)

print()
print("=" * 70)
print("1. ⛔ every file lands, and the manifest counts what is ON DISK")
print("=" * 70)
for n in market.FILES + ("index.json",):
    check(f"{n} exists", os.path.exists(os.path.join(market.OUT_DIR, n)))
idx = read("index.json")
for n in market.FILES:
    on_disk = market.rows_on_disk(n, read(n))
    check(f"index says {n} has {idx['files'][n]['rows']} rows - the file has {on_disk}",
          idx["files"][n]["rows"] == on_disk and on_disk > 0)
check("rows_total is the sum of the files", idx["rows_total"] ==
      sum(market.rows_on_disk(n, read(n)) for n in market.FILES))
reg = json.load(io.open(liveness.REG, encoding="utf-8"))
beat = (reg.get("market.snapshot") or {})
check("⭐ liveness was beaten ONCE with the ROW COUNT read back, not a bare 1",
      beat.get("firings") == 1 and beat.get("rows_total") == idx["rows_total"] > 1,
      {k: beat.get(k) for k in ("firings", "rows_total", "empty_firings")})
check("the origin of a hand run is recorded as manual, not unattended",
      idx["origin"] == "manual", idx["origin"])
mv = read("movers.json")["lists"]
vol = read("volume.json")
vrows = (vol.get("leaders_24h") or []) + (vol.get("leaders_24h_tokens") or [])
mrows = [r for L in mv.values() for r in L] + vrows
check("the volume rows are actually in that check (not an empty list passing vacuously)", len(vrows) > 0, len(vrows))
check("⛔ every mover and volume row carries cap_backing_pct beside its cap (the site shows no cap without it)",
      mrows and all("cap_backing_pct" in r for r in mrows), len(mrows))
check("...computed as the quote half of reported liquidity over the cap, None when unknown",
      all(r["cap_backing_pct"] == market.cap_backing(r["liquidity_usd_reported"], r["mcap_usd"]) for r in mrows)
      and market.cap_backing(None, 5e6) is None and market.cap_backing(1e3, 0) is None)

print()
print("=" * 70)
print("2. ⛔ ranking: by the move, with every exclusion COUNTED")
print("=" * 70)
mv = read("movers.json")
g24 = [r["token"] for r in mv["lists"]["gainers_24h"]]
check("gainers are ordered by the 24h move, largest first",
      g24[:2] == ["BIGmint", "MIDmint"], g24)
check("⛔ a +99,999% token on $50 of liquidity is NOT a gainer", "POORmint" not in g24)
check("...and it is counted as under the floor, not silently dropped",
      mv["exclusions"]["gainers_24h"]["under_liquidity_floor"] == 1, mv["exclusions"]["gainers_24h"])
check("⛔ unknown liquidity is excluded and counted separately",
      "NOLIQmint" not in g24 and mv["exclusions"]["gainers_24h"]["liquidity_unknown"] == 1)
check("a token with no stats is unknown, not zero, and counted",
      "NOSTATmint" not in g24 and mv["exclusions"]["gainers_24h"]["unknown_value"] == 1)
check("losers hold only negative moves, worst first",
      [r["token"] for r in mv["lists"]["losers_24h"]] == ["DOWNmint"],
      [r["token"] for r in mv["lists"]["losers_24h"]])
big = next(r for r in mv["lists"]["gainers_24h"] if r["token"] == "BIGmint")
check("vs_sol_pp is the move minus SOL's own move, per horizon",
      big["vs_sol_pp"] == {"1h": 900.5, "6h": 4999.0, "24h": 19990.0}, big["vs_sol_pp"])
check("⭐ in_journal says whether our scanner EVER saw it",
      big["in_journal"] is False and
      next(r for r in mv["lists"]["gainers_24h"] if r["token"] == "MIDmint")["in_journal"] is True)
check("the universe size is published", mv["universe_n"] == len(ALL), mv["universe_n"])

print()
print("=" * 70)
print("3. ⛔ round trips: quotes only, and 'not checked' is said out loud")
print("=" * 70)
check("the top gainer was checked and carries a verdict",
      big["round_trip_status"] == "checked" and big["round_trip"]["verdict"] == "TRADEABLE")
mid = next(r for r in mv["lists"]["gainers_24h"] if r["token"] == "MIDmint")
check("a quote that raised says 'check failed', never a fake verdict",
      mid["round_trip_status"].startswith("check failed") and mid["round_trip"]["verdict"] is None,
      mid["round_trip_status"])
check("each token is quoted at most once per snapshot", len(RT_CALLS) == len(set(RT_CALLS)), RT_CALLS)
market.build(verbose=False, now=NOW, rt=fake_rt, verify_s=0)
mv0 = read("movers.json")
check("⛔ with no time left, rows say 'not checked: time budget spent'",
      all(r["round_trip_status"] == "not checked: time budget spent"
          for r in mv0["lists"]["gainers_24h"][:market.VERIFY_PER_LIST]),
      {r["round_trip_status"] for r in mv0["lists"]["gainers_24h"]})

print()
print("=" * 70)
print("4. volume: SOL and stablecoins do not bury the tokens, and no fake wash flag")
print("=" * 70)
vo = read("volume.json")
allv = [r["token"] for r in vo["leaders_24h"]]
tokv = [r["token"] for r in vo["leaders_24h_tokens"]]
check("the full list is by 24h volume and includes SOL", allv[0] == WSOL, allv)
check("⭐ the token list drops base (major/stable) and stock tags - Jupiter's tags",
      WSOL not in tokv and "USDCmint" not in tokv and "SPYxmint" not in tokv and tokv[0] == "BIGmint",
      tokv)
check("SOL's own organic share is published as the baseline",
      vo["organic_share_baseline_sol"]["24h"] == 0.02, vo["organic_share_baseline_sol"])
check("⛔ and the caveat says organic share is NOT a wash signal",
      any("NOT a wash signal" in c for c in vo["caveats"]))
b = next(r for r in vo["leaders_24h_tokens"] if r["token"] == "BIGmint")
check("turnover is volume over reported liquidity", b["turnover_24h"] == 400.0, b["turnover_24h"])
check("no row carries a wash verdict field", all("wash" not in k for r in vo["leaders_24h"] for k in r))

print()
print("=" * 70)
print("5. trending, clusters, majors")
print("=" * 70)
tr = read("trending.json")
check("⛔ boosts are labelled PAID promotion", any("PAID" in c for c in tr["caveats"]))
check("non-Solana boosts are dropped", [r["token"] for r in tr["boosts_top"]] == ["BOOSTmint"])
check("a GeckoTerminal pool resolves to its base token CA",
      tr["geckoterminal"]["1h"][0]["token"] == "BIGmint" and
      tr["geckoterminal"]["1h"][0]["change_pct"]["h24"] == 300.0)
cl = read("clusters.json")
check("Dexscreener metas are published", cl["dexscreener_metas"][0]["slug"] == "cat")
check("⚠️ our cluster 'funded' count is named for what it measures",
      all("funded_by_reported_liq" in c for c in cl["ours"]) or not cl["ours"])
mj = read("majors.json")
check("SOL has price, 24h move from CoinGecko and 1h/6h from Jupiter",
      mj["sol"]["price_usd"] == 113.0 and mj["sol"]["change_pct"]["1h"] == -0.5,
      mj["sol"])
check("Solana DEX volume and its day-on-day change",
      mj["solana_dex"]["volume_24h_usd"] == 2.5e9 and mj["solana_dex"]["change_1d_pct"] == -7.4)
bid = next(r for r in mv["lists"]["gainers_24h"] if r["token"] == "BIDImint")
check("⛔ a bidi-override symbol is flagged as data", bid["symbol_flags"]["bidi"] is True)

print()
print("=" * 70)
print("6. ⛔ a failing source is REPORTED, and the rest still lands")
print("=" * 70)
FAIL.update({"geckoterminal.com", "coingecko.com"})
m2 = market.build(verbose=False, now=NOW, rt=fake_rt, verify_s=0)
FAIL.clear()
bad = {k for k, v in m2["sources"].items() if v["status"] == "error"}
check("the failed sources are named in the manifest",
      {"coingecko.simple_price", "coingecko.global",
       "geckoterminal.trending_pools.1h"} <= bad, sorted(bad))
check("movers still landed from Jupiter", m2["files"]["movers.json"]["rows"] > 0)
check("⛔ the unknown BTC price is None, not 0", read("majors.json")["btc"]["price_usd"] is None)
FAIL.update({"lite-api.jup.ag", "geckoterminal.com", "coingecko.com", "llama.fi",
             "dexscreener.com"})
m3 = market.build(verbose=False, now=NOW, rt=fake_rt, verify_s=0)
FAIL.clear()
check("⛔ every source down -> movers and volume write ZERO rows, and say so",
      m3["files"]["movers.json"]["rows"] == 0 and m3["files"]["volume.json"]["status"] == "empty",
      m3["files"])

print()
print("=" * 70)
print("7. history is append-only, one line per list per snapshot")
print("=" * 70)
hist = [os.path.join(market.HISTORY_DIR, f) for f in os.listdir(market.HISTORY_DIR)]
lines = [json.loads(l) for h in hist for l in io.open(h, encoding="utf-8") if l.strip()]
per = 2 * len(market.HORIZONS) + 2
check(f"4 snapshots x {per} lists = {4 * per} lines", len(lines) == 4 * per, len(lines))
check("every history row names its columns", all(l["cols"][0] == "token" for l in lines))

print()
print("=" * 70)
print("8. ⛔ wired into the collector, and it cannot push a pass past the timeout")
print("=" * 70)
import inspect
import collect
check("market is a stage and fires market.snapshot",
      "market" in collect.STAGES and collect.STAGE_FIRES["market"] == {"market.snapshot"})
src = inspect.getsource(collect.one_pass)
check("one_pass runs it BEFORE outcome scoring",
      0 < src.index("market_stage(") < src.index("track.score_all("))
seen_budget = []
real_build = market.build
market.build = lambda verbose=True, verify_s=None, **k: seen_budget.append(verify_s)
collect._PASS_T0 = time.time() - 30
collect.market_stage(verbose=False)
collect._PASS_T0 = time.time() - (collect.MARKET_SOFT_LIMIT_S + 60)
collect.market_stage(verbose=False)
market.build = real_build
check("early in a pass it gets the full verification budget",
      seen_budget[0] == market.VERIFY_SECONDS, seen_budget)
check("⛔ past the soft limit it gets ZERO seconds of quotes", seen_budget[1] == 0.0, seen_budget)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
