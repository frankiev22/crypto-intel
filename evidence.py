"""
The track record that ships with an alert.

An alert with no history behind it asks Frank to take it on faith. These helpers
attach what actually happened last time something like this fired, so he can
judge it in the notification without opening anything.

Both functions degrade to None rather than guessing. An alert that says nothing
about its history is honest; an alert that implies a track record it does not
have is not.
"""
import json, os, time, urllib.request

import config  # noqa: F401 - loads .env

_cache = {}
TTL = 600


def _get(path):
    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    if not (base and key):
        return None
    hit = _cache.get(path)
    if hit and time.time() - hit[0] < TTL:
        return hit[1]
    try:
        r = urllib.request.urlopen(urllib.request.Request(
            f"{base}/rest/v1/{path}",
            headers={"apikey": key, "Authorization": f"Bearer {key}",
                     "User-Agent": "crypto-intel/evidence"}), timeout=15)
        data = json.loads(r.read().decode())
        _cache[path] = (time.time(), data)
        return data
    except Exception:
        return None


def score_band_record(score, horizon_h=1, min_n=20):
    """What this score band has historically returned. None when unknown or
    when the sample is too thin to quote."""
    if score is None:
        return None
    rows = _get(f"crypto_score_bands?horizon_h=eq.{horizon_h}&select=band,band_order,closed,"
                f"win_rate_2x_pct,best_mult,total_loss&order=band_order.desc")
    if not rows:
        return None
    band = ("100" if score >= 100 else "85-99" if score >= 85 else "70-84" if score >= 70
            else "60-69" if score >= 60 else "45-59" if score >= 45
            else "30-44" if score >= 30 else "0-29")
    for r in rows:
        if r.get("band") == band:
            n = r.get("closed") or 0
            return {"band": band, "n": n, "win_pct": r.get("win_rate_2x_pct"),
                    "best": r.get("best_mult"), "zeros": r.get("total_loss"),
                    "thin": n < min_n}
    return None


def band_line(score, horizon_h=1):
    """One phone-width sentence, or None. Never fabricates a record."""
    rec = score_band_record(score, horizon_h)
    if not rec or not rec["n"]:
        return None
    if rec["win_pct"] is None:
        return f"Band {rec['band']}: no closed outcomes yet (n={rec['n']})"
    thin = " — thin sample, not a finding" if rec["thin"] else ""
    return (f"Band {rec['band']} history: {rec['win_pct']}% hit 2x at {horizon_h}h "
            f"(n={rec['n']}, {rec['zeros']} went to zero){thin}")


def wallet_record(wallet):
    """What this wallet has actually done, from decoded events we hold.

    NOTE: this is activity, not profitability. Real win rate and closed-position
    count arrive with the PnL-ranked watchlist; until then this says what it
    knows and no more, rather than implying a track record that does not exist.
    """
    if not wallet:
        return None
    rows = _get(f"crypto_whale_events_public?select=usd,action,alerted,occurred_at"
                f"&wallet_short=eq.{wallet[:4]}%E2%80%A6{wallet[-4:]}&limit=200")
    if rows is None:
        return None
    if not rows:
        return {"moves": 0, "alerted": 0, "total_usd": 0.0, "known_pnl": False}
    return {
        "moves": len(rows),
        "alerted": sum(1 for r in rows if r.get("alerted")),
        "total_usd": sum(float(r.get("usd") or 0) for r in rows),
        "biggest": max((float(r.get("usd") or 0) for r in rows), default=0.0),
        "known_pnl": False,   # honest: we do not yet compute realized PnL
    }


def wallet_line(wallet):
    rec = wallet_record(wallet)
    if not rec:
        return None
    if not rec["moves"]:
        return "No decoded history for this wallet yet"
    return (f"Track record: {rec['moves']} decoded moves, biggest ${rec['biggest']:,.0f}"
            f" — win rate not yet computed")


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for s in (100, 85, 70, 45):
        print(f"  score {s:>3} -> {band_line(s)}")
