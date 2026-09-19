"""The tracked universe admits only what sells, never forgets, and never overwrites
what it cannot read. Run: python test_universe.py      (offline, canned payloads)

⛔ Every assertion is on the FILES universe.build() writes, read back from disk -
members.json, events, history, narratives, index - because that is what the site
reads (standing rule 16). The membership rule under test is docs/UNIVERSE.md §3,
pre-committed before the first seed run.
"""
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
import graduations
import liveness
import market
import milestones
import universe as U

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# No sleeping and no shared Jupiter bucket in an offline test.
chainfields._JUP.take = lambda n=1: None
U.CG_GAP_S = 0
U.THEME_GAP_S = 0

NOW = time.time()


def mint(tag):
    return (tag + "1" * 44)[:44]


def jtok(m, sym, mcap, liq=50_000.0, name=None, chg24=5.0, tags=None):
    return {"id": m, "symbol": sym, "name": name or sym, "usdPrice": 0.01, "mcap": mcap,
            "fdv": mcap, "liquidity": liq, "holderCount": 1234,
            "stats24h": {"priceChange": chg24, "buyVolume": 1000.0, "sellVolume": 900.0,
                         "numTraders": 50},
            "stats1h": {"priceChange": 1.0, "buyVolume": 10.0, "sellVolume": 9.0},
            "tags": tags or [], "audit": {"mintAuthorityDisabled": True}}


# The world, keyed by contract. Symbols are display only.
BIG = mint("BIGverified")              # Jupiter verified, $5M
SMALL = mint("SMALLverified")          # Jupiter verified, $400k - NOT in the universe
TREND = mint("TRENDrunner")            # not verified, trending, $2M
NOMCAP = mint("NOMCAP")                # trending, mcap unknown
CROSS = mint("CROSSmilestone")         # our own $1M crossing, still $1.5M
CROSSDEAD = mint("CROSSdead")          # our own $1M crossing, now $80k
GRAD = mint("GRADrunner")              # graduated yesterday, now $3M
CGONLY = mint("CGONLYcoin")            # CoinGecko only, Jupiter does not know it
CGDISAGREE = mint("CGDISAGREE")        # CoinGecko $2M, Jupiter $600k -> Jupiter wins
REFUSE = mint("REFUSEme")              # $1.2M on the listing, cannot be sold
CATS = [mint(f"CAT{i}popcat") for i in range(3)]   # a name cluster of three
GHOST = mint("GHOSTboost")             # a paid boost Jupiter has never heard of

WORLD = {
    BIG: jtok(BIG, "BIG", 5e6, liq=900_000.0),
    SMALL: jtok(SMALL, "SMALL", 4e5),
    TREND: jtok(TREND, "TRND", 2e6, liq=80_000.0),
    NOMCAP: dict(jtok(NOMCAP, "NOM", None), mcap=None),
    CROSS: jtok(CROSS, "CRS", 1.5e6),
    CROSSDEAD: jtok(CROSSDEAD, "DEAD", 8e4),
    GRAD: jtok(GRAD, "GRD", 3e6),
    CGDISAGREE: jtok(CGDISAGREE, "DIS", 6e5),
    REFUSE: jtok(REFUSE, "RFS", 1.2e6, liq=12.0),
}
for i, m in enumerate(CATS):
    WORLD[m] = jtok(m, f"POPCAT{i}", 2e6 + i, name=f"Popcat {'Moon Riot Zzz'.split()[i]}")
VERIFIED = [WORLD[BIG], WORLD[SMALL], WORLD[REFUSE]] + [WORLD[m] for m in CATS]
HIDDEN = set()                         # contracts Jupiter pretends not to know
CG_ROWS = [{"id": "cgonly", "market_cap": 3e6}, {"id": "cgdis", "market_cap": 2e6},
           {"id": "cgsmall", "market_cap": 5e5}]
CG_LIST = [{"id": "cgonly", "platforms": {"solana": CGONLY}},
           {"id": "cgdis", "platforms": {"solana": CGDISAGREE}},
           {"id": "cgsmall", "platforms": {"solana": mint("CGSMALL")}}]
URLS = []


def fake_get(url, timeout=30):
    URLS.append(url)
    U.CALLS["n"] += 1
    if "/tag?query=verified" in url:
        return 200, [t for t in VERIFIED if t["id"] not in HIDDEN]
    if "/search?query=" in url:
        q = url.split("query=", 1)[1].split(",")
        return 200, [WORLD[m] for m in q if m in WORLD and m not in HIDDEN]
    if "coins/markets" in url:
        return 200, (CG_ROWS if "page=1&" in url or url.endswith("page=1") else [])
    if "coins/list" in url:
        return 200, CG_LIST
    if "/metas/meta/v1/" in url:
        return 200, {"pairs": [{"chainId": "solana", "baseToken": {"address": m, "symbol": "C"}}
                               for m in CATS] + [{"chainId": "base", "baseToken": {"address": "0xabc"}}]}
    return 404, None


U._get = fake_get

# The market stage ran this pass: its lists and one round trip it already quoted.
market.LAST.clear()
market.LAST.update(ts=NOW, universe={TREND: WORLD[TREND]},
                   lists={TREND: {"jupiter.toptrending.1h"}},
                   verified={CROSS: {"round_trip": {"verdict": "TRADEABLE", "rt_cost_pct": 0.4,
                                                    "ts": int(NOW)},
                                     "round_trip_status": "checked"}})
os.makedirs(market.OUT_DIR, exist_ok=True)
with open(os.path.join(market.OUT_DIR, "trending.json"), "w", encoding="utf-8") as f:
    json.dump({"built_ts": int(NOW), "jupiter": {"1h": [{"rank": 1, "token": TREND, "symbol": "TRND"},
                                                        {"rank": 2, "token": NOMCAP, "symbol": "NOM"}]},
               "geckoterminal": {"1h": [{"token": GRAD, "pool": "p", "dex": "pumpswap"}]},
               "boosts_top": [{"token": CATS[0], "boost_total": 500},
                              # untracked paid rows arrive with no symbol (the site
                              # showed 13 of 13 as "unknown", 2026-09-19)
                              {"token": SMALL, "boost_total": 100},
                              {"token": GHOST, "boost_total": 50}]}, f)
with open(os.path.join(market.OUT_DIR, "clusters.json"), "w", encoding="utf-8") as f:
    json.dump({"dexscreener_metas": [{"name": "Cats", "slug": "cat", "token_count": 90}]}, f)
os.makedirs(milestones.DIR, exist_ok=True)
with open(os.path.join(milestones.DIR, time.strftime("%Y-%m", time.gmtime(NOW)) + ".jsonl"),
          "w", encoding="utf-8") as f:
    for m in (CROSS, CROSSDEAD):
        f.write(json.dumps({"token": m, "milestone": "mcap_1m", "kind": "mcap",
                            "crossed_ts": NOW - 5 * 86400}) + "\n")
os.makedirs(graduations.DIR, exist_ok=True)
with open(os.path.join(graduations.DIR, time.strftime("%Y-%m", time.gmtime(NOW)) + ".jsonl"),
          "w", encoding="utf-8") as f:
    f.write(json.dumps({"kind": "graduation", "mint": GRAD, "block_time": NOW - 86400}) + "\n")

QUOTED = []
VERDICT = {REFUSE: "NO_BUY_ROUTE"}

# ⛔ The safety refresh must never reach the network from a test: the real
# refresh runs against a faked _http, so the verdict code itself is exercised.
import safety as SAFE


def _safe_http(url, body=None, timeout=20):
    if body is not None:
        vals = []
        for m in body["params"][0]:
            fz = "FreezeAuth" if m == TREND else None
            vals.append({"data": {"program": "spl-token", "parsed": {"info": {
                "mintAuthority": None, "freezeAuthority": fz, "extensions": []}}}})
        return 200, {"result": {"value": vals}}
    if "dexscreener" in url:
        return 200, []
    return 404, None


SAFE._http = _safe_http
SAFE.RUGCHECK_GAP_S = 0


def fake_rt(m):
    QUOTED.append(m)
    v = VERDICT.get(m, "TRADEABLE")
    return {"mint": m, "verdict": v, "rt_cost_pct": 0.8 if v == "TRADEABLE" else None,
            "usd_back": 99.2 if v == "TRADEABLE" else None, "probe_usd": 100, "ts": int(time.time()),
            "px_per_raw": 1e-9 if v == "TRADEABLE" else None}


FDV_CALLS = []


def fake_fdv(m, res):
    FDV_CALLS.append(m)
    return None if m == GRAD else 4_200_000


def read(name):
    with open(os.path.join(U.OUT_DIR, name), encoding="utf-8") as f:
        return json.load(f)


def events():
    out = []
    for n in sorted(os.listdir(U.EVENTS_DIR)):
        with open(os.path.join(U.EVENTS_DIR, n), encoding="utf-8") as f:
            out += [json.loads(l) for l in f if l.strip()]
    return out


section("1. the state machine, one verdict at a time (docs/UNIVERSE.md §3)")
e = {"token": "X", "status": "candidate", "last": {"mcap_usd": 2e6}}
ev = U.apply_verdict(e, {"verdict": "TRADEABLE", "rt_cost_pct": 0.5, "ts": NOW}, NOW, "manual")
check("candidate + TRADEABLE -> member, admitted with its mcap and its quote",
      e["status"] == "member" and e["admitted_mcap_usd"] == 2e6 and ev["event"] == "admitted"
      and e["gate"]["status"] == "passing", e)
e2 = {"token": "Y", "status": "candidate", "last": {"mcap_usd": 2e6}}
ev = U.apply_verdict(e2, {"verdict": "COSTLY", "rt_cost_pct": 22.0, "ts": NOW}, NOW, "manual")
check("⛔ candidate + COSTLY -> refused. Only TRADEABLE admits",
      e2["status"] == "refused" and ev["event"] == "refused")
ev = U.apply_verdict(e2, {"verdict": "TRADEABLE", "rt_cost_pct": 3.0, "ts": NOW}, NOW, "manual")
check("refused + TRADEABLE later -> member, marked previously refused",
      e2["status"] == "member" and ev.get("previously_refused") is True)
ev = U.apply_verdict(e, {"verdict": "TOTAL_LOSS", "ts": NOW}, NOW + 10, "manual")
check("⛔ member + TOTAL_LOSS -> STILL A MEMBER, gate failing, since recorded",
      e["status"] == "member" and e["gate"]["status"] == "failing"
      and e["gate"]["failing_since"] == int(NOW + 10) and ev["event"] == "gate_failed", e["gate"])
ev = U.apply_verdict(e, {"verdict": "NO_SELL_ROUTE", "ts": NOW}, NOW + 20, "manual")
check("a second failure keeps the FIRST failing_since", e["gate"]["failing_since"] == int(NOW + 10))
ev = U.apply_verdict(e, {"verdict": None, "error": "URLError"}, NOW + 30, "manual")
check("⛔ a check that could not run is NOT a verdict - state and gate unchanged",
      e["status"] == "member" and e["gate"]["status"] == "failing"
      and e["gate"]["verdict"] == "NO_SELL_ROUTE" and ev["event"] == "gate_check_failed", e["gate"])
ev = U.apply_verdict(e, {"verdict": "TRADEABLE", "ts": NOW}, NOW + 40, "manual")
check("member failing + TRADEABLE -> restored, failing_since cleared",
      e["gate"]["status"] == "passing" and "failing_since" not in e["gate"]
      and ev["event"] == "gate_restored")

section("2. one pass: discovery, the $1M floor, the gate - read back from disk")
m1 = U.build(verbose=False, now=NOW, rt=fake_rt, gate_s=60, fdv=fake_fdv)
doc = read("members.json")
T = doc["tokens"]
check("a Jupiter-verified $5M token is in", BIG in T)
check("a verified $400k token is NOT - the floor is the floor", SMALL not in T)
check("⭐ a trending runner the listings miss is in", TREND in T and "trending" in T[TREND]["sources"],
      T.get(TREND, {}).get("sources"))
check("⛔ a trending token whose mcap is UNKNOWN is not admitted as if it passed", NOMCAP not in T)
check("our own $1M crossing still over $1M is in, sourced to the milestone",
      CROSS in T and "milestone.mcap_1m" in T[CROSS]["sources"], T.get(CROSS, {}).get("sources"))
check("our own $1M crossing now at $80k is NOT", CROSSDEAD not in T)
check("⭐ a graduation now at $3M is in, sourced to the ledger",
      GRAD in T and "graduation" in T[GRAD]["sources"], T.get(GRAD, {}).get("sources"))
check("a CoinGecko-only token is in, on CoinGecko's mcap", CGONLY in T and T[CGONLY]["cg_mcap_usd"] == 3e6)
check("⛔ CoinGecko $2M vs Jupiter $600k: Jupiter's number decides, as pre-committed",
      CGDISAGREE not in T)
check("every member was admitted on a TRADEABLE quote",
      all(e["gate"]["verdict"] == "TRADEABLE" for e in T.values() if e["status"] == "member"))
check("⛔ the unsellable $1.2M listing is REFUSED and KEPT with its verdict",
      T[REFUSE]["status"] == "refused" and T[REFUSE]["gate"]["verdict"] == "NO_BUY_ROUTE")
check("⭐ the market stage's same-pass quote was reused, not quoted twice",
      T[CROSS]["status"] == "member" and CROSS not in QUOTED and m1["gate"]["reused_from_market"] == 1,
      m1["gate"])
check("trending candidates are quoted before the rest", QUOTED[:2] and set(QUOTED[:2]) <= {TREND, GRAD, CATS[0]},
      QUOTED[:3])
check("⭐ A3: a TRADEABLE admission records FDV from chain supply x the price the buy got",
      T[BIG]["admitted_fdv_onchain_usd"] == 4_200_000 and T[BIG]["gate"]["fdv_onchain_usd"] == 4_200_000)
check("⛔ ...an unreadable supply is None, not 0, and does not block admission",
      T[GRAD]["status"] == "member" and T[GRAD]["admitted_fdv_onchain_usd"] is None)
check("...and it is never looked up for a token that failed the gate", REFUSE not in FDV_CALLS)
check("the file keys on contract address; symbols carry their flags",
      all(k == v["token"] and "symbol_flags" in v for k, v in T.items() if v.get("symbol")))
REG = json.load(open(liveness.REG, encoding="utf-8")).get("universe.members") or {}
check("members on disk == what liveness was told, beaten once",
      REG.get("firings") == 1 and REG.get("rows_total") ==
      sum(1 for e in T.values() if e["status"] == "member") == m1["members_on_disk"],
      (REG, m1["members_on_disk"]))
ev1 = events()
check("every discovery and every gate check is an event",
      sum(1 for x in ev1 if x["event"] == "discovered") == len(T)
      and sum(1 for x in ev1 if x["event"] in ("admitted", "refused")) == len(T), len(ev1))
hist = [json.loads(l) for n in os.listdir(U.HISTORY_DIR)
        for l in open(os.path.join(U.HISTORY_DIR, n), encoding="utf-8")]
check("history holds one line for this pass, one row per member",
      len(hist) == 1 and len(hist[0]["rows"]) == sum(1 for e in T.values() if e["status"] == "member"))

section("2b. ⭐ the safety verdict on every tracked token (PRECOMMIT_safety_v1.md)")
T2 = read("members.json")["tokens"]
trk = [m for m, e in T2.items() if e.get("status") in ("member", "refused", "candidate")]
check("every member, refused and candidate token carries a verdict",
      trk and all((T2[m].get("safety") or {}).get("level") for m in trk),
      [m[:8] for m in trk if not (T2[m].get("safety") or {}).get("level")])
check("⛔ a trending member with freeze authority is DANGER - shown, not dropped",
      T2[TREND]["status"] == "member" and T2[TREND]["safety"]["level"] == "DANGER", T2[TREND].get("safety", {}).get("level"))
check("⛔ the refused token is still tracked AND flagged (never hidden)",
      T2[REFUSE]["status"] == "refused" and T2[REFUSE]["safety"]["level"] in ("UNKNOWN", "DANGER"),
      T2[REFUSE].get("safety", {}).get("level"))
check("index counts every level", sum(read("index.json")["counts"]["safety"].values()) == len(trk),
      read("index.json")["counts"]["safety"])
check("the pass records what the safety refresh did", "tracked" in (read("index.json").get("safety") or {}),
      read("index.json").get("safety"))

section("3. narratives: trending x the universe")
N = read("narratives.json")
tn = {r["token"]: r for r in N["trending_now"]}
check("trending_now carries every trending token, with its universe status",
      tn[TREND]["universe_status"] == "member" and tn[NOMCAP]["universe_status"] == "not tracked", tn.get(NOMCAP))
check("⛔ a paid boost is labelled paid", tn[CATS[0]].get("paid") is True)
check("⭐ an untracked boost is NAMED from Jupiter, with the cap and its backing that say why",
      tn[SMALL]["universe_status"] == "not tracked" and tn[SMALL]["symbol"] == "SMALL"
      and tn[SMALL]["mcap_usd"] == 4e5 and tn[SMALL]["resolved_by"] == "jupiter.search"
      and tn[SMALL]["cap_backing_pct"] == market.cap_backing(WORLD[SMALL]["liquidity"], 4e5), tn.get(SMALL))
check("⛔ an untracked trending row carries a verdict too - UNKNOWN (no round trip), never blank",
      tn[SMALL]["safety"] == "UNKNOWN" and tn[GHOST]["safety"] == "UNKNOWN", (tn[SMALL].get("safety"), tn[GHOST].get("safety")))
check("⛔ every trending row says what was NOT checked, beside its verdict",
      all(isinstance(r.get("safety_not_checked"), list) and r["safety_not_checked"] for r in tn.values()
          if r.get("safety") != "not computed"), [(k[:6], r.get("safety_not_checked")) for k, r in tn.items()][:3])
check("...and the untracked verdict says it is PARTIAL (never round-tripped)",
      "partial" in (tn[SMALL].get("safety_scope") or "") and "full" in (tn[TREND].get("safety_scope") or ""),
      (tn[SMALL].get("safety_scope"), tn[TREND].get("safety_scope")))
check("⛔ one Jupiter never heard of stays unknown: None, not a guessed name or a 0",
      tn[GHOST]["symbol"] is None and tn[GHOST]["mcap_usd"] is None
      and tn[GHOST]["cap_backing_pct"] is None and tn[GHOST]["resolved_by"] is None, tn.get(GHOST))
check("the untracked lookup is its own source, so it cannot mask the main search",
      U.SOURCES.get("jupiter.search_untracked_trending", {}).get("status") == "ok"
      and U.SOURCES.get("jupiter.search", {}).get("status") == "ok")
check("⭐ the trending age is published in seconds, and stale means one missed ~2h pass (3h)",
      N["trending_age_s"] == 0 and N["trending_stale"] is False and U.TRENDING_FRESH_H == 3
      and N["trending_stale_after_h"] == 3, {k: N.get(k) for k in ("trending_age_s", "trending_stale")})
nc = N["name_clusters"]
check("⭐ three members named Popcat form one name cluster over the LIVE universe",
      any(c["root"] == "popcat" and c["size"] == 3 for c in nc), [(c["root"], c["size"]) for c in nc])
check("the cluster carries size facts, not a score",
      nc and {"mcap_usd", "volume_usd_24h", "change_24h_pct_mcap_weighted", "trending_now_n"} <= set(nc[0])
      and "score" not in json.dumps(nc))
th = N["themes"]
check("a Dexscreener theme is intersected with the universe (Solana pairs only)",
      th and th[0]["members_n"] == 3 and th[0]["solana_tokens"] == 3, th[:1])

section("3a. ⛔ the cap is never shown without what backs it")
check("cap_backing_pct = the quote half of reported liquidity over the cap",
      T[BIG]["last"]["cap_backing_pct"] == round(900_000 / 2 / 5e6 * 100, 4), T[BIG]["last"].get("cap_backing_pct"))
check("unknown liquidity or cap -> None, never 0",
      U.cap_backing(None, 5e6) is None and U.cap_backing(1000.0, None) is None and U.cap_backing(1000.0, 0) is None)
check("ticker_contracts counts every tracked contract carrying the ticker",
      all(e.get("ticker_contracts") == 1 for e in T.values() if e.get("symbol")))
check("every narrative cluster carries mcap_backed_usd beside mcap_usd",
      all("mcap_backed_usd" in c and "shared_ticker_n" in c for c in N["name_clusters"] + N["themes"]))
check("the caveat saying so is published in the file", any("cap_backing_pct" in c for c in N["caveats"]))

section("4. ⛔ never forgets, never overwrites")
HIDDEN.add(BIG)
WORLD[CROSS]["mcap"] = 4e5
VERDICT[TREND] = "TOTAL_LOSS"
U.REVERIFY_TRENDING_H = 0
m2 = U.build(verbose=False, now=NOW + 3600, rt=fake_rt, gate_s=60)
T2 = read("members.json")["tokens"]
check("a member Jupiter stopped returning is STILL a member, marked missing",
      T2[BIG]["status"] == "member" and T2[BIG].get("jupiter_missing_since") == int(NOW + 3600))
check("a member that fell under $1M is STILL a member, below_floor_since set",
      T2[CROSS]["status"] == "member" and T2[CROSS].get("below_floor_since") == int(NOW + 3600))
check("a trending member whose re-check failed stays, gate failing",
      T2[TREND]["status"] == "member" and T2[TREND]["gate"]["status"] == "failing")
ev2 = events()
check("events are APPEND-ONLY: pass 1's rows are still the first rows", ev2[:len(ev1)] == ev1)
check("the floor crossing is an event", any(x["event"] == "below_floor" and x["token"] == CROSS for x in ev2))
before = open(os.path.join(U.OUT_DIR, "members.json"), "rb").read()
with open(os.path.join(U.OUT_DIR, "members.json"), "w", encoding="utf-8") as f:
    f.write('{"tokens": {"truncated')
bad = open(os.path.join(U.OUT_DIR, "members.json"), "rb").read()
m3 = U.build(verbose=False, now=NOW + 7200, rt=fake_rt, gate_s=60)
check("⛔ an unreadable members.json is NOT overwritten with a fresh universe",
      m3.get("error") and open(os.path.join(U.OUT_DIR, "members.json"), "rb").read() == bad, m3)
with open(os.path.join(U.OUT_DIR, "members.json"), "wb") as f:
    f.write(before)

section("5. the budget: zero seconds quotes nothing and SAYS what it deferred")
WORLD[mint("NEWCOMER")] = jtok(mint("NEWCOMER"), "NEW", 9e6)
VERIFIED.append(WORLD[mint("NEWCOMER")])
QUOTED.clear()
m4 = U.build(verbose=False, now=NOW + 7300, rt=fake_rt, gate_s=0)
T4 = read("members.json")["tokens"]
check("a zero budget quotes nothing", QUOTED == [], QUOTED)
check("the new token waits as a candidate - not admitted, not dropped",
      T4[mint("NEWCOMER")]["status"] == "candidate")
check("index.json counts it as deferred, by status",
      read("index.json")["gate"]["deferred_by_status"].get("candidate", 0) >= 1, read("index.json")["gate"])
q = U.gate_queue(T4, NOW + 7300, {})
check("the queue puts never-quoted candidates first", q and q[0] == mint("NEWCOMER"), q[:3])

print()
bad_ = [r for r in R if not r[1]]
print(f"{len(R) - len(bad_)}/{len(R)} passed")
if bad_:
    print("\nFAILED:")
    for n, _ in bad_:
        print("  -", n)
sys.exit(1 if bad_ else 0)
