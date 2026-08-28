"""
The scoring weights, and where they come from.

Until now scanner.py carried six hand-picked point values that never changed no
matter what the tokens actually did. This module makes the scorer read weights
that were derived from real outcomes, so the loop closes.

Two rules that matter more than the code:

  1. FALLBACK IS SAFE. If Supabase is unreachable, or no weight version has
     been activated yet, the scanner keeps its original hand-set weights and
     records version 0. A network problem must never silently change how
     tokens are scored.

  2. EVERY SCORE RECORDS ITS VERSION. journal writes weights_version alongside
     the score. Without that the scoreboard becomes uninterpretable the moment
     weights are retuned, because a 66 from v2 and a 66 from v5 would not mean
     the same thing.

Measured lift on the first derivation (train n=1099, 1h realizable outcomes):

    liquidity  154.9x   -> weight 43
    vol/liq     18.4x   -> weight 25
    vol 1h      15.9x   -> weight 23
    txns         3.0x   -> weight  9
    buy/sell     0.6x   -> weight  0   INVERTED, was worth 15 points
    age            n/a  -> weight  0   1501 of 1522 pass it; no variance to measure
"""
import json, os, time, urllib.request

import config  # noqa: F401 - loads .env

# The original hand-set weights. Used when nothing has been activated yet.
FALLBACK = {"liquidity": 20, "txns": 15, "vol1h": 15,
            "volliq": 20, "buysell": 15, "age": 15}
FALLBACK_VERSION = 0

_cache = {"at": 0, "weights": None, "version": None, "threshold": None}
TTL = 900


def active():
    """(weights dict, version, alert_threshold_or_None). Never raises."""
    if _cache["weights"] and time.time() - _cache["at"] < TTL:
        return _cache["weights"], _cache["version"], _cache["threshold"]

    base = os.environ.get("SUPABASE_URL", "").rstrip("/")
    key = os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip()
    w, ver, thr = FALLBACK, FALLBACK_VERSION, None
    if base and key:
        try:
            q = ("crypto_score_weights?select=version,weights,alert_threshold"
                 "&active=is.true&order=version.desc&limit=1")
            r = urllib.request.urlopen(urllib.request.Request(
                f"{base}/rest/v1/{q}",
                headers={"apikey": key, "Authorization": f"Bearer {key}",
                         "User-Agent": "crypto-intel/weights"}), timeout=15)
            rows = json.loads(r.read().decode())
            if rows:
                row = rows[0]
                w = {k: int(v) for k, v in (row.get("weights") or {}).items()}
                ver = row.get("version")
                t = row.get("alert_threshold")
                thr = t if (t is not None and t >= 0) else None
        except Exception:
            pass  # fallback already in place

    _cache.update(at=time.time(), weights=w, version=ver, threshold=thr)
    return w, ver, thr


def explain(gates, weights=None):
    """Human-readable breakdown of a score. Frank must be able to read WHY a
    token scored what it scored, so this is part of the contract, not a debug
    helper."""
    w = weights or active()[0]
    parts = []
    for gate, passed in gates.items():
        pts = w.get(gate, 0)
        if pts == 0:
            continue                      # a zero-weight gate is not evidence
        parts.append(f"{gate} {'+' if passed else '0/'}{pts}")
    return ", ".join(parts) or "no weighted gate contributed"


if __name__ == "__main__":
    w, ver, thr = active()
    print(f"\n  active weights version : {ver}"
          f"{'  (FALLBACK - nothing activated yet)' if ver == FALLBACK_VERSION else ''}")
    print(f"  alert threshold        : {thr if thr is not None else 'not set - insufficient outcome data'}")
    for k, v in sorted(w.items(), key=lambda kv: -kv[1]):
        print(f"    {k:<12} {v:>3}")
    print(f"  total                  : {sum(w.values())}\n")
