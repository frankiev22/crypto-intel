"""The live path: every ~10 seconds, what the tracked universe is doing now.

    python live.py                    # run forever (the always-on process)
    python live.py --once             # one full cycle, then exit (for checks)

One PATH among several, on purpose (Frank, 2026-09-19: "multiple different
working methods in conjunction"). It shares no host, network or schedule with
the GitHub runner, and it records WHAT IT SAW under its own path name, so two
paths disagreeing is visible instead of averaged away.

    every HOT_S (10s)    trending + the biggest 1h movers, <=100 tokens:
                         one Jupiter search call, published as ticks
    every TREND_S (15s)  Jupiter toptrending 1h (their cache is 15s)
    every FULL_S (60s)   every tracked token: Jupiter search (100 per call)
                         and Dexscreener pairs (30 per call) for D1, the safety
                         verdict recomputed, all of it published
    every MEMBERS_S      membership re-read from the public repo, the same
                         file the site reads - never from this working tree

⛔ It never stops on an error. Each step is caught, recorded, and retried on
the next tick; a path that cannot write says so in live_paths and in
.live/status.json, and the page shows it as down.
⛔ It never commits, never touches data/, never trades, never holds a wallet.
Jupiter and Dexscreener are read-only market data; the only write is our own
Supabase store.
"""
import datetime as dt
import json
import os
import socket
import sys
import time
import traceback
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: F401  (loads .env)
import safety
import supa
import universe

PATH = os.environ.get("CRYPTO_LIVE_PATH", "desktop")
HOT_S = float(os.environ.get("CRYPTO_LIVE_HOT_S", "10"))
TREND_S = float(os.environ.get("CRYPTO_LIVE_TREND_S", "15"))
FULL_S = float(os.environ.get("CRYPTO_LIVE_FULL_S", "60"))
MEMBERS_S = float(os.environ.get("CRYPTO_LIVE_MEMBERS_S", "600"))
HOT_N = 100
RUGCHECK_PER_FULL_S = 8          # trickle: ~8 RugCheck reports a minute, a full cycle in ~2h
MEMBERS_URL = "https://raw.githubusercontent.com/frankiev22/crypto-intel/master/data/universe/members.json"
STATE_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), ".live")
UA = {"User-Agent": "Mozilla/5.0 (crypto-intel live; +https://crypto-intel-one-eta.vercel.app)"}

STATUS = {"path": PATH, "host": socket.gethostname(), "started_at": None, "steps": {}}


def _now():
    return time.time()


def _iso(ts):
    return dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat(timespec="seconds")


def log(msg):
    os.makedirs(STATE_DIR, exist_ok=True)
    line = f"{_iso(_now())} {msg}"
    print(line, flush=True)
    p = os.path.join(STATE_DIR, "live.log")
    try:
        if os.path.exists(p) and os.path.getsize(p) > 5_000_000:
            os.replace(p, p + ".1")          # one rotation; the log is a convenience, not a record
        with open(p, "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except OSError:
        pass


def step(name, ok, n=0, err=None):
    s = STATUS["steps"].setdefault(name, {"ok": 0, "fail": 0})
    s["ok" if ok else "fail"] += 1
    s["last_at"] = _iso(_now())
    s["last_n"] = n
    if not ok:
        s["last_error"], s["last_error_at"] = err, _iso(_now())
    try:
        os.makedirs(STATE_DIR, exist_ok=True)
        tmp = os.path.join(STATE_DIR, "status.json.tmp")
        with open(tmp, "w", encoding="utf-8") as f:
            json.dump(STATUS, f, indent=1)
        os.replace(tmp, os.path.join(STATE_DIR, "status.json"))
    except OSError:
        pass


def fetch_members(get=None):
    """{mint: entry} for member / refused / candidate, from the public repo."""
    if get is not None:
        d = get(MEMBERS_URL)
    else:
        req = urllib.request.Request(MEMBERS_URL, headers=UA)
        with urllib.request.urlopen(req, timeout=60) as r:
            d = json.loads(r.read().decode("utf-8"))
    return {m: e for m, e in (d.get("tokens") or {}).items()
            if e.get("status") in ("member", "refused", "candidate")}


def trending_list():
    """[(rank, mint, symbol)] from Jupiter toptrending 1h."""
    d = universe._fetch("live.jupiter.toptrending", f"{universe.JUP_TOKENS}/toptrending/1h?limit=50", jupiter=True)
    return [(i + 1, t["id"], t.get("symbol")) for i, t in enumerate(d or []) if isinstance(t, dict) and t.get("id")]


def hot_set(tokens, trend):
    """Trending first, then the biggest absolute 1h moves among tracked tokens."""
    out = [m for _, m, _ in trend][:HOT_N]
    movers = sorted((m for m, e in tokens.items() if ((e.get("last") or {}).get("change_pct") or {}).get("1h") is not None),
                    key=lambda m: -abs(tokens[m]["last"]["change_pct"]["1h"]))
    for m in movers:
        if len(out) >= HOT_N:
            break
        if m not in out:
            out.append(m)
    return out


def ticks_for(mints, tokens, now, with_dex=False):
    """Jupiter search -> snapshot per mint, stored on the entry; -> tick rows."""
    got = universe.jupiter_search(mints, label="live.jupiter.search")
    rows = []
    for m, t in got.items():
        snap = universe.snapshot(t, now)
        e = tokens.get(m)
        if e is not None:
            e["last"] = snap
        dx = ((e or {}).get("dex") or {}).get("facts") if with_dex else None
        rows.append(supa.tick_row(m, snap, dex=dx, d1=(safety.d1(dx) if dx else None)))
    return rows, len(got)


def publish(payload, what):
    payload = dict(payload, host=STATUS["host"], kind=f"poll {HOT_S:g}s/{FULL_S:g}s", interval_s=int(HOT_S))
    ok, res = supa.publish(PATH, payload)
    step(f"publish.{what}", ok, 0, None if ok else str(res))
    return ok, res


def cycle_full(tokens, now):
    rows, n = ticks_for(list(tokens), tokens, now)
    step("jupiter.full", n > 0, n, None if n else "no rows")
    st = safety.refresh(tokens, now, budget_s=45, rugcheck_budget_s=RUGCHECK_PER_FULL_S)
    step("safety", True, st.get("tracked", 0))
    # the D1 reading lands on the ticks after the pair refresh
    by = {r["mint"]: r for r in rows}
    for m, e in tokens.items():
        dx = (e.get("dex") or {}).get("facts")
        if m in by and dx:
            by[m].update(buys_h1=dx.get("buys_h1"), sells_h1=dx.get("sells_h1"), d1=safety.d1(dx))
    toks = [supa.token_row(m, e) for m, e in tokens.items()]
    return publish({"tokens": toks, "ticks": rows,
                    "detail": {"full": True, "tokens": len(toks), "ticks": len(rows),
                               "safety_levels": st.get("levels"), "rugcheck_deferred": st.get("rugcheck_deferred")}},
                   "full")


def run(once=False, members_get=None, clock=_now, sleep=time.sleep):
    STATUS["started_at"] = _iso(clock())
    log(f"live path '{PATH}' starting on {STATUS['host']}; supabase: {supa.configured()[1] or 'configured'}")
    tokens, next_members, next_full, next_trend = {}, 0.0, 0.0, 0.0
    trend = []
    while True:
        t0 = clock()
        try:
            if t0 >= next_members or not tokens:
                try:
                    fresh = fetch_members(members_get)
                    for m, e in fresh.items():             # keep what this path already fetched
                        old = tokens.get(m) or {}
                        for k in ("chain", "dex", "rugcheck"):
                            if old.get(k) and not e.get(k):
                                e[k] = old[k]
                    tokens = fresh
                    step("members", True, len(tokens))
                    next_members = t0 + MEMBERS_S
                except Exception as ex:
                    step("members", False, 0, type(ex).__name__)
                    next_members = t0 + 60
            if t0 >= next_trend:
                try:
                    trend = trending_list()
                    step("trending", bool(trend), len(trend), None if trend else "empty")
                    publish({"trending": {"jupiter.toptrending.1h": [
                        {"rank": r, "mint": m, "symbol": s} for r, m, s in trend]}}, "trending")
                except Exception as ex:
                    step("trending", False, 0, type(ex).__name__)
                next_trend = t0 + TREND_S
            if tokens and t0 >= next_full:
                try:
                    cycle_full(tokens, t0)
                except Exception as ex:
                    step("full", False, 0, f"{type(ex).__name__}: {ex}"[:160])
                    log("full cycle failed: " + traceback.format_exc(limit=2).replace("\n", " | "))
                next_full = t0 + FULL_S
            elif tokens:
                try:
                    rows, n = ticks_for(hot_set(tokens, trend), tokens, t0)
                    step("jupiter.hot", n > 0, n, None if n else "no rows")
                    publish({"ticks": rows, "detail": {"hot": True, "ticks": len(rows)}}, "hot")
                except Exception as ex:
                    step("hot", False, 0, type(ex).__name__)
        except Exception as ex:                              # never die
            step("loop", False, 0, f"{type(ex).__name__}")
            log("loop error: " + traceback.format_exc(limit=2).replace("\n", " | "))
        if once:
            return STATUS
        sleep(max(0.5, HOT_S - (clock() - t0)))


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    run(once="--once" in sys.argv)
