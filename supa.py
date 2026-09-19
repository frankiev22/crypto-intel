"""Write the live store (supabase/migrations/002_live.sql). One function, one secret.

Every write goes through `live_publish(secret, path, payload)`, the only thing
anon may call, gated by the 'live' secret. Reads are the four public-read
tables; this module never reads them and never needs a privileged key.

⛔ Never logs, prints or returns a key or the secret. Errors are reported as a
status and a short reason, and the caller records them - a path that cannot
write must show up as DOWN on the page, not as a quiet success.
"""
import datetime as dt
import json
import os
import sys
import urllib.error
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config  # noqa: F401  (loads .env into os.environ)

TIMEOUT_S = 20
LAST = {}


def configured():
    """(ok, why). Says WHICH piece is missing, never its value."""
    miss = [n for n in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "CRYPTO_LIVE_SECRET")
            if not os.environ.get(n, "").strip()]
    if miss:
        return False, "not configured: " + ", ".join(miss) + " unset"
    if "rxofejxostyqlgjlzqmk" not in os.environ["SUPABASE_URL"]:
        # ⛔ the crypto project only. Never commingle with any other project.
        return False, "SUPABASE_URL is not the crypto project (rxofejxostyqlgjlzqmk); refusing to write"
    return True, None


def _iso(ts):
    return None if not ts else dt.datetime.fromtimestamp(ts, dt.timezone.utc).isoformat()


def token_row(m, e):
    """A universe entry -> one live_tokens row."""
    g, s = e.get("gate") or {}, e.get("safety") or {}
    return {"mint": m, "symbol": e.get("symbol"), "name": e.get("name"), "class": e.get("class"),
            "status": e.get("status"), "gate_verdict": g.get("verdict"),
            "gate_cost_pct": g.get("rt_cost_pct"), "gate_at": _iso(g.get("ts")),
            "safety_level": s.get("level"), "safety_reasons": s.get("reasons"),
            "safety_not_checked": s.get("not_checked"), "safety_rule": s.get("rule"),
            "safety_at": _iso(s.get("computed_ts")),
            "ticker_contracts": e.get("ticker_contracts"),
            "from_graduation": "graduation" in (e.get("sources") or []),
            "trending": e.get("trending") or [],
            "first_seen_at": _iso(e.get("first_seen_ts")), "admitted_at": _iso(e.get("admitted_ts")),
            "below_floor_since": _iso(e.get("below_floor_since")),
            "failing_since": _iso((e.get("gate") or {}).get("failing_since"))}


def tick_row(m, snap, dex=None, d1=None, source="jupiter.search"):
    """A market snapshot (universe.snapshot shape) -> one live_ticks row."""
    ch = snap.get("change_pct") or {}
    vol = snap.get("volume_usd") or {}
    dx = dex or {}
    return {"mint": m, "price_usd": snap.get("price_usd"), "mcap_usd": snap.get("mcap_usd"),
            "fdv_usd": snap.get("fdv_usd"), "liquidity_usd": snap.get("liquidity_usd_reported"),
            "cap_backing_pct": snap.get("cap_backing_pct"),
            "change_5m": ch.get("5m"), "change_1h": ch.get("1h"), "change_6h": ch.get("6h"),
            "change_24h": ch.get("24h"), "volume_1h": vol.get("1h"), "volume_24h": vol.get("24h"),
            "buys_h1": dx.get("buys_h1"), "sells_h1": dx.get("sells_h1"), "d1": d1,
            "source": source, "observed_at": _iso(snap.get("ts"))}


def publish(path, payload, post=None):
    """(ok, result_or_reason). `post` is injectable so tests never touch the network."""
    ok, why = configured()
    if not ok:
        LAST.update(ok=False, reason=why)
        return False, why
    url = os.environ["SUPABASE_URL"].rstrip("/") + "/rest/v1/rpc/live_publish"
    key = os.environ["SUPABASE_PUBLISHABLE_KEY"].strip()
    body = json.dumps({"p_secret": os.environ["CRYPTO_LIVE_SECRET"].strip(), "p_path": path,
                       "p_payload": payload}, separators=(",", ":"), default=str).encode()
    hdr = {"apikey": key, "Authorization": "Bearer " + key, "Content-Type": "application/json",
           "Content-Profile": "public", "User-Agent": "crypto-intel/live"}
    try:
        if post is not None:
            status, res = post(url, body, hdr)
        else:
            req = urllib.request.Request(url, data=body, headers=hdr, method="POST")
            with urllib.request.urlopen(req, timeout=TIMEOUT_S) as r:
                status, res = r.status, json.loads(r.read().decode("utf-8", "replace") or "null")
    except urllib.error.HTTPError as e:
        # PostgREST says what went wrong in the body; it never echoes our headers.
        try:
            msg = json.loads(e.read().decode("utf-8", "replace")).get("message", "")[:120]
        except Exception:
            msg = ""
        reason = f"HTTP {e.code}" + (f": {msg}" if msg else "")
        if e.code == 404:
            reason += " (002_live.sql not applied?)"
        LAST.update(ok=False, reason=reason)
        return False, reason
    except Exception as e:
        LAST.update(ok=False, reason=type(e).__name__)
        return False, type(e).__name__
    ok = 200 <= (status or 0) < 300
    LAST.update(ok=ok, reason=None if ok else f"HTTP {status}", result=res if ok else None)
    return ok, (res if ok else f"HTTP {status}")
