"""
Publishes a digest to Supabase so the public dashboard can render it.

Deliberately NOT using a service_role key. That database also holds wedding
guests, CRM leads and Stripe events, and a service key sitting on a desktop
that runs a scheduled scraper is a bad trade. This talks to one SECURITY
DEFINER function guarded by a shared secret, so the worst a leak of these
credentials buys you is the ability to append crypto digests.

Env:
    SUPABASE_URL               https://<ref>.supabase.co
    SUPABASE_PUBLISHABLE_KEY   sb_publishable_...   (safe in a browser too)
    CRYPTO_PUBLISH_SECRET      the write gate; NEVER goes to the browser
"""
import os, json, urllib.request, urllib.error

import config  # noqa: F401  - importing this is what loads .env

RPC = "/rest/v1/rpc/publish_crypto_digest"


def _cfg():
    return (os.environ.get("SUPABASE_URL", "").rstrip("/"),
            os.environ.get("SUPABASE_PUBLISHABLE_KEY", "").strip(),
            os.environ.get("CRYPTO_PUBLISH_SECRET", "").strip())


def configured():
    return all(_cfg())


def publish(d):
    """Push one digest. Returns (row_id_or_None, status_string). Never raises -
    a dead dashboard must not take the Discord alert down with it."""
    url, key, secret = _cfg()
    if not all((url, key, secret)):
        missing = [n for n, v in zip(
            ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "CRYPTO_PUBLISH_SECRET"),
            (url, key, secret)) if not v]
        return None, "not configured: " + ", ".join(missing)

    body = json.dumps({
        "p_secret":      secret,
        "p_captured_at": d["ts"],
        "p_version":     d.get("version", "0.0.1"),
        "p_payload":     d,
    }).encode()
    req = urllib.request.Request(
        url + RPC, data=body, method="POST",
        headers={"apikey": key, "Authorization": f"Bearer {key}",
                 "Content-Type": "application/json",
                 "User-Agent": "crypto-intel/0.0.1"})
    try:
        r = urllib.request.urlopen(req, timeout=20)
        raw = r.read().decode("utf-8", "ignore").strip()
        return (json.loads(raw) if raw else None), "ok"
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", "ignore")[:160].replace(secret, "***")
        return None, f"HTTP {e.code}: {detail}"
    except Exception as e:
        return None, f"{type(e).__name__}: {str(e).replace(secret, '***')[:120]}"
