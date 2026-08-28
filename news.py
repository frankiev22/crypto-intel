"""
News axis. CryptoPanic is the 0.0.1 source.

Free tier needs CRYPTOPANIC_API_TOKEN. Without it every function here returns
an empty, explicitly-degraded result - nothing raises, nothing invents numbers.
The digest prints the degraded state rather than a fake one.

CryptoPanic has two live API paths and which one a key works against depends on
the plan, so we try developer/v2 first and fall back to v1.
"""
import os, json, time, urllib.request, urllib.error

TOKEN_ENV = "CRYPTOPANIC_API_TOKEN"
V2 = "https://cryptopanic.com/api/developer/v2/posts/"
V1 = "https://cryptopanic.com/api/v1/posts/"
UA = {"User-Agent": "Mozilla/5.0", "Accept": "application/json"}


def token():
    return os.environ.get(TOKEN_ENV, "").strip()


def have():
    return bool(token())


def _get_json(url, timeout=20):
    """Return parsed JSON, or None. CryptoPanic sits behind Cloudflare and will
    hand back an HTML error page on a bad token, so a parse failure is expected
    and is not an exception case."""
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=timeout)
        raw = r.read().decode("utf-8", "ignore")
    except urllib.error.HTTPError as e:
        raw = e.read().decode("utf-8", "ignore")
    except Exception:
        return None
    if not raw.lstrip().startswith(("{", "[")):
        return None
    try:
        return json.loads(raw)
    except Exception:
        return None


def posts(currencies=("BTC", "ETH", "SOL"), limit=20):
    """Recent posts. Returns (list_of_posts, status_string). Empty list means
    degraded, and the status says exactly why."""
    tk = token()
    if not tk:
        return [], f"no {TOKEN_ENV} - news axis off"
    cur = ",".join(currencies)
    for label, base in (("v2", V2), ("v1", V1)):
        d = _get_json(f"{base}?auth_token={tk}&public=true&currencies={cur}")
        if isinstance(d, dict) and isinstance(d.get("results"), list):
            return [_norm(p) for p in d["results"][:limit]], f"ok ({label}, {len(d['results'])} posts)"
        if isinstance(d, dict) and d.get("info"):
            return [], f"cryptopanic: {str(d.get('info'))[:80]}"
        time.sleep(0.4)
    return [], "cryptopanic unreachable or token rejected"


def _norm(p):
    """Flatten the two API shapes into one record."""
    v = p.get("votes") or {}
    inst = p.get("instruments") or p.get("currencies") or []
    return {
        "title":   (p.get("title") or "").strip(),
        "url":     p.get("url") or (p.get("source") or {}).get("url") or "",
        "domain":  (p.get("source") or {}).get("domain") or p.get("domain") or "",
        "published": p.get("published_at") or p.get("created_at") or "",
        "symbols": [c.get("code") for c in inst if isinstance(c, dict) and c.get("code")],
        "positive":  int(v.get("positive") or 0),
        "negative":  int(v.get("negative") or 0),
        "important": int(v.get("important") or 0),
        "liked":     int(v.get("liked") or 0),
        "disliked":  int(v.get("disliked") or 0),
        "panic":     p.get("panic_score"),
    }


def hot(ps, min_important=1):
    """Posts the crowd actually flagged. This is the alert surface, not the feed."""
    scored = [(p["important"] + p["positive"] + p["negative"], p) for p in ps]
    scored = [(s, p) for s, p in scored if p["important"] >= min_important or s >= 3]
    return [p for _, p in sorted(scored, key=lambda t: -t[0])]


# ---------------------------------------------------------------------------
# The Supabase-backed feed. A Supabase Edge Function polls RSS every minute and
# stores items there, so the digest reads what has already been collected rather
# than re-fetching four sites. Anything alert-worthy has already pinged Discord;
# what lands in the digest is the accumulated rest.
# ---------------------------------------------------------------------------
def stored(limit=6, hours=24):
    """Recent items from Supabase. Returns (items, status)."""
    import os, urllib.parse, datetime as dt
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not (base and key):
        return [], "SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not set"
    since = (dt.datetime.now(dt.timezone.utc) - dt.timedelta(hours=hours)).isoformat()
    q = ("crypto_news?select=title,url,outlet,published_at,alert_reason,also_in"
         f"&published_at=gte.{urllib.parse.quote(since)}"
         f"&order=published_at.desc&limit={limit}")
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            f"{base}/rest/v1/{q}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", **UA}), timeout=20)
        rows = json.loads(r.read().decode("utf-8", "ignore"))
        return rows, (f"{len(rows)} from Supabase" if rows else "nothing in the last %dh" % hours)
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"
