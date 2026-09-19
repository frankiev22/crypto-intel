"""The live path and its writer: no secret ever leaks, no error ever stops it,
and every token it publishes carries its safety verdict.
Run: python test_live.py      (offline: every network call is faked)
"""
import io
import json
import os
import sys
import urllib.error

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
testsandbox.activate()
import live
import safety
import supa
import universe

R = []
NOW = 1_790_000_000.0
SECRET, KEY = "s3cret-VALUE-never-shown", "sb_publishable_KEYVALUE"


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


def env(url="https://rxofejxostyqlgjlzqmk.supabase.co", key=KEY, secret=SECRET):
    for k, v in (("SUPABASE_URL", url), ("SUPABASE_PUBLISHABLE_KEY", key), ("CRYPTO_LIVE_SECRET", secret)):
        if v is None:
            os.environ.pop(k, None)
        else:
            os.environ[k] = v


section("1. ⛔ the writer: the crypto project only, and nothing secret in any message")
env(secret=None)
ok, why = supa.configured()
check("an unset secret is named, and the call is refused", not ok and "CRYPTO_LIVE_SECRET unset" in why, why)
env(url="https://gsgydqdgeonwyhgeggjn.supabase.co")
ok, why = supa.configured()
check("⛔ any other Supabase project is REFUSED (never commingle)", not ok and "rxofejxostyqlgjlzqmk" in why, why)
env()
seen = {}


def post_ok(url, body, hdr):
    seen.update(url=url, body=json.loads(body), hdr=hdr)
    return 200, {"tokens": 1, "ticks": 0, "trending": 0}


ok, res = supa.publish("desktop", {"tokens": [{"mint": "M"}]}, post=post_ok)
check("a write goes to the one RPC, as the path it names", ok and seen["url"].endswith("/rest/v1/rpc/live_publish")
      and seen["body"]["p_path"] == "desktop" and seen["body"]["p_payload"]["tokens"][0]["mint"] == "M")


def post_404(url, body, hdr):
    raise urllib.error.HTTPError(url, 404, "nf", {}, io.BytesIO(b'{"message":"Could not find the function public.live_publish"}'))


ok, why = supa.publish("desktop", {}, post=post_404)
check("the migration not being applied is SAID, not swallowed", not ok and "002_live.sql not applied" in why, why)


def post_boom(url, body, hdr):
    raise TimeoutError("slow")


ok2, why2 = supa.publish("desktop", {}, post=post_boom)
check("⛔ no reason ever carries the key or the secret",
      all(SECRET not in str(x) and KEY not in str(x) for x in (why, why2, supa.LAST)), [why, why2])

section("2. rows: unknown stays None")
e = {"status": "member", "symbol": "S", "class": "token", "sources": ["graduation"],
     "gate": {"verdict": "TRADEABLE", "rt_cost_pct": 0.3, "ts": NOW},
     "safety": {"level": "WARN", "reasons": ["S8: x"], "not_checked": ["fake volume"], "rule": "r", "computed_ts": NOW}}
t = supa.token_row("M1", e)
check("a token row carries the verdict, its reasons and what was NOT checked",
      t["safety_level"] == "WARN" and t["safety_not_checked"] == ["fake volume"] and t["from_graduation"] is True)
check("absent timestamps are None, never epoch 0", t["admitted_at"] is None and t["below_floor_since"] is None)
k = supa.tick_row("M1", {"ts": NOW, "price_usd": 1.0, "change_pct": {"1h": 5.0}, "volume_usd": {}})
check("a tick with no pair data has None for D1 and the trade counts",
      k["d1"] is None and k["buys_h1"] is None and k["change_1h"] == 5.0 and k["change_5m"] is None)

section("3. ⭐ one live cycle, end to end, against fakes")
MINTS = [f"Mint{i:02d}" + "x" * 38 for i in range(5)]
MEMBERS = {"tokens": {m: {"status": "member" if i < 4 else "refused", "class": "token", "symbol": f"T{i}",
                          "sources": ["jupiter.verified"],
                          "gate": {"verdict": "TRADEABLE" if i < 4 else "TOTAL_LOSS", "rt_cost_pct": 0.5, "ts": NOW},
                          "last": {"change_pct": {"1h": float(i)}}}
                      for i, m in enumerate(MINTS)} | {"GoneMint" + "x" * 36: {"status": "gone"}}}


def jtok(m):
    return {"id": m, "symbol": "X", "usdPrice": 1.0, "mcap": 2e6, "fdv": 2e6, "liquidity": 4e5,
            "holderCount": 3000, "stats1h": {"priceChange": 2.0}, "stats24h": {"priceChange": 9.0},
            "audit": {"topHoldersPercentage": 20.0}}


def fake_get(url, timeout=30):
    if "/toptrending/" in url:
        return 200, [jtok(MINTS[3]), jtok("NotTracked" + "x" * 34)]
    if "/search?query=" in url:
        return 200, [jtok(m) for m in url.split("query=")[1].split(",") if m in MINTS]
    return 404, None


def fake_http(url, body=None, timeout=20):
    if body is not None:
        return 200, {"result": {"value": [{"data": {"program": "spl-token", "parsed": {"info": {
            "mintAuthority": None, "freezeAuthority": None, "extensions": []}}}} for _ in body["params"][0]]}}
    if "dexscreener" in url:
        return 200, [{"chainId": "solana", "baseToken": {"address": m}, "liquidity": {"usd": 4e5}, "fdv": 2e6,
                      "txns": {"h1": {"buys": 50, "sells": 40}}} for m in url.rsplit("/", 1)[1].split(",")]
    return 404, None


universe._get = fake_get
safety._http = fake_http
safety.RUGCHECK_GAP_S = 0
PUB = []
supa.publish = lambda path, payload, post=None: (PUB.append((path, payload)) or True, {"ok": 1})
st = live.run(once=True, members_get=lambda url: MEMBERS, clock=lambda: NOW, sleep=lambda s: None)
kinds = [("full" if p.get("tokens") else "trending" if p.get("trending") else "hot") for _, p in PUB]
check("the first cycle publishes trending AND a full pass", "trending" in kinds and "full" in kinds, kinds)
full = next(p for _, p in PUB if p.get("tokens"))
check("⛔ only tracked tokens are published (a 'gone' one is not)",
      sorted(x["mint"] for x in full["tokens"]) == sorted(MINTS), len(full["tokens"]))
check("⭐ every published token carries a safety verdict",
      all(x["safety_level"] for x in full["tokens"]), [x["safety_level"] for x in full["tokens"]])
check("⛔ the unsellable one is published FLAGGED (DANGER), not dropped",
      next(x for x in full["tokens"] if x["mint"] == MINTS[4])["safety_level"] == "DANGER")
check("ticks carry D1 from the pair refresh (False here: 40 sells)",
      full["ticks"] and all(x["d1"] is False and x["sells_h1"] == 40 for x in full["ticks"]))
check("every write says which host and path it came from",
      all(p.get("host") and path == live.PATH for path, p in PUB))
check("the path's status lands on disk, per step", os.path.exists(os.path.join(live.STATE_DIR, "status.json"))
      and st["steps"]["members"]["ok"] == 1 and st["steps"]["jupiter.full"]["last_n"] == 5, st["steps"].keys())
HS = {m: {"last": {"change_pct": {"1h": [1.0, -9.0, 3.0, -2.0, 7.0][i]}}} for i, m in enumerate(MINTS)}
check("hot set: trending first, then the biggest ABSOLUTE 1h moves (a -9% counts)",
      live.hot_set(HS, [(1, MINTS[2], "T2")])[:4] == [MINTS[2], MINTS[1], MINTS[4], MINTS[3]],
      live.hot_set(HS, [(1, MINTS[2], "T2")])[:4])

section("4. ⛔ an error never stops the path")
PUB.clear()


def boom(url):
    raise ConnectionError("github down")


st2 = live.run(once=True, members_get=boom, clock=lambda: NOW + 999, sleep=lambda s: None)
check("members unreachable: recorded as a failure, the cycle still returns",
      st2["steps"]["members"]["fail"] >= 1 and st2["steps"]["members"]["last_error"] == "ConnectionError")
check("...and trending was still published", any(p.get("trending") for _, p in PUB))

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
