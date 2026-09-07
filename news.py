"""
News axis. CryptoPanic is the 0.0.1 source.

Free tier needs CRYPTOPANIC_API_TOKEN. Without it every function here returns
an empty, explicitly-degraded result - nothing raises, nothing invents numbers.
The digest prints the degraded state rather than a fake one.

CryptoPanic has two live API paths and which one a key works against depends on
the plan, so we try developer/v2 first and fall back to v1.
"""
import os, json, time, urllib.request, urllib.error
import liveness

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


# ---------------------------------------------------------------------------
# Per-outlet freshness. Added 2026-09-06 after a 6x drop in daily article count
# was spotted by hand rather than by an alert.
#
# THE DROP WAS WEEKEND VOLUME, NOT A FAILURE. Measured over 14 days:
#
#     weekdays  55, 57, 57, 62, 66, 67, 67, 67, 74, 74     median ~66/day
#     weekends   3, 7, 13, 15, 19                          median ~13/day
#
# Every weekend in the record drops 4-5x, and all four outlets drop together,
# which is editorial cadence rather than a broken feed. So a naive
# volume-threshold alert would fire two days in seven, forever, and be muted
# within a week. That is why this checks PER-OUTLET STALENESS instead: a real
# failure is one outlet going quiet while the others keep publishing, and that
# is visible on a weekend too.
#
# THE THRESHOLDS ARE SET FROM THE OBSERVED GAP DISTRIBUTION, 21 days, so that
# nothing in the historical record would have fired:
#
#     outlet          weekday p95 / max      weekend p95 / max
#     CoinDesk           5.26h / 12.82h        17.87h / 21.72h
#     Cointelegraph      4.33h /  8.49h        23.29h / 26.01h
#     Decrypt           10.54h / 18.30h        20.05h / 21.00h
#     The Block          6.65h / 11.78h        20.96h / 21.51h
#
# 24h weekday sits above every observed weekday maximum (worst 18.30h) and 36h
# weekend sits above every observed weekend maximum (worst 26.01h). Zero false
# positives against the whole record, while still catching a genuine outage
# inside a day.
# ---------------------------------------------------------------------------
OUTLETS = ("CoinDesk", "Decrypt", "Cointelegraph", "The Block")
STALE_WEEKDAY_H = float(os.environ.get("CRYPTO_NEWS_STALE_WEEKDAY_H", "24"))
STALE_WEEKEND_H = float(os.environ.get("CRYPTO_NEWS_STALE_WEEKEND_H", "36"))


def _threshold(now=None):
    import datetime as dt
    now = now or dt.datetime.now(dt.timezone.utc)
    # isoweekday: 6=Sat, 7=Sun. Monday morning still reflects weekend cadence,
    # so Monday before 12:00 UTC keeps the weekend allowance.
    weekend = now.isoweekday() >= 6 or (now.isoweekday() == 1 and now.hour < 12)
    return (STALE_WEEKEND_H if weekend else STALE_WEEKDAY_H), weekend


def freshness(lookback_h=192):
    """Per-outlet staleness. Returns (rows, status). One Supabase call.

    An outlet that has published NOTHING in the lookback window does not appear
    in the response at all - which is the loudest possible signal and the exact
    case a volume aggregate hides. OUTLETS is therefore the denominator, not
    whatever the query happens to return.
    """
    import datetime as dt
    import urllib.parse
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not (base and key):
        return [], "SUPABASE_URL / SUPABASE_PUBLISHABLE_KEY not set"
    now = dt.datetime.now(dt.timezone.utc)
    since = (now - dt.timedelta(hours=lookback_h)).isoformat()
    q = ("crypto_news?select=outlet,published_at"
         f"&published_at=gte.{urllib.parse.quote(since)}"
         "&order=published_at.desc&limit=2000")
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            f"{base}/rest/v1/{q}",
            headers={"apikey": key, "Authorization": f"Bearer {key}", **UA}), timeout=20)
        rows = json.loads(r.read().decode("utf-8", "ignore"))
    except Exception as e:
        return [], f"{type(e).__name__}: {str(e)[:80]}"

    latest, counts = {}, {}
    for row in rows:
        o, p = row.get("outlet"), row.get("published_at")
        if not o or not p:
            continue
        counts[o] = counts.get(o, 0) + 1
        if o not in latest or p > latest[o]:
            latest[o] = p
    thr, weekend = _threshold(now)
    out = []
    for o in OUTLETS:
        p = latest.get(o)
        if p:
            try:
                t = dt.datetime.fromisoformat(p.replace("Z", "+00:00"))
                if t.tzinfo is None:
                    t = t.replace(tzinfo=dt.timezone.utc)
                stale_h = (now - t).total_seconds() / 3600.0
            except Exception:
                stale_h = None
        else:
            stale_h = float(lookback_h)   # nothing at all in the window
        out.append({"outlet": o, "latest": p, "hours_stale": (
                        round(stale_h, 2) if stale_h is not None else None),
                    "articles_in_window": counts.get(o, 0),
                    "threshold_h": thr, "weekend": weekend,
                    "stale": bool(stale_h is not None and stale_h > thr)})
    out.sort(key=lambda r: -(r["hours_stale"] or 0))
    n_stale = sum(1 for r in out if r["stale"])
    return out, (f"{len(OUTLETS) - n_stale}/{len(OUTLETS)} fresh, threshold "
                 f"{thr:.0f}h ({'weekend' if weekend else 'weekday'})")


def check_freshness(record=None, verbose=True):
    """Emit a finding for any outlet past its threshold. Returns the stale rows.

    Deliberately one finding PER OUTLET, keyed on the outlet name, so that
    duration escalation and deduplication work per source - a single
    'news is stale' ping would collapse four independent failures into one.
    """
    rows, status = freshness()
    if not rows:
        if verbose:
            print(f"  news freshness: {status}")
        return []
    stale = [r for r in rows if r["stale"]]
    if verbose:
        print(f"  news freshness: {status}")
        for r in rows:
            mark = "STALE" if r["stale"] else "ok"
            print(f"    {r['outlet']:<15} {str(r['hours_stale']):>7}h  "
                  f"{r['articles_in_window']:>3} articles  {mark}")
    if record:
        for r in stale:
            record("news-stale", r["outlet"],
                   f"{r['outlet']} has published nothing for "
                   f"{r['hours_stale']:.1f}h (threshold {r['threshold_h']:.0f}h)",
                   detail=(f"Last item {r['latest']}. "
                           f"{r['articles_in_window']} articles in the 8-day window. "
                           f"Threshold is {'weekend' if r['weekend'] else 'weekday'} "
                           f"cadence. The other outlets are checked independently - "
                           f"if they are fresh, this is THIS feed failing, not "
                           f"quiet news."))
    liveness.beat("news.freshness", detail=f"{len(stale)} stale outlet(s)")
    return stale


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    check_freshness()
