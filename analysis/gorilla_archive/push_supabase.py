"""Load the archive into Supabase through the secret-gated RPC.

Same shape as `supa.py`: the anon key alone cannot write. The caller must also
present the 'journal' secret, which `private.check_secret` verifies server side.

⛔ The secret is read from .env (gitignored, verified) and is NEVER printed,
logged, echoed into an error message or written to any file. On failure this
prints the HTTP status and the response body with the secret redacted.

⛔ Refuses to run against any project other than rxofejxostyqlgjlzqmk.
"""
import io
import json
import os
import sys
import urllib.error
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import config  # noqa: E402

PROJECT = "rxofejxostyqlgjlzqmk"
BATCH = 40


def env():
    config._load_env()
    url = (os.environ.get("SUPABASE_URL") or "").strip().rstrip("/")
    key = (os.environ.get("SUPABASE_PUBLISHABLE_KEY") or "").strip()
    sec = (os.environ.get("CRYPTO_JOURNAL_SECRET") or "").strip()
    missing = [n for n, v in (("SUPABASE_URL", url),
                              ("SUPABASE_PUBLISHABLE_KEY", key),
                              ("CRYPTO_JOURNAL_SECRET", sec)) if not v]
    if missing:
        raise SystemExit("missing from .env: " + ", ".join(missing))
    if PROJECT not in url:
        raise SystemExit("SUPABASE_URL is not the crypto project; refusing to write")
    return url, key, sec


def redact(s, *secrets):
    for x in secrets:
        if x:
            s = s.replace(x, "<redacted>")
    return s


def main():
    url, key, sec = env()
    rows = json.load(io.open(os.path.join(HERE, "dataset_allpairs.json"), encoding="utf-8"))
    endpoint = url + "/rest/v1/rpc/gorilla_archive_publish"
    sent = 0
    for i in range(0, len(rows), BATCH):
        chunk = rows[i:i + BATCH]
        body = json.dumps({"p_secret": sec, "p_rows": chunk}).encode("utf-8")
        req = urllib.request.Request(endpoint, data=body, headers={
            "apikey": key, "Authorization": "Bearer " + key,
            "Content-Type": "application/json",
            "User-Agent": "crypto-intel/gorilla-archive",
        })
        try:
            with urllib.request.urlopen(req, timeout=60) as r:
                r.read()
            sent += len(chunk)
            print(f"  {sent}/{len(rows)}", flush=True)
        except urllib.error.HTTPError as e:
            msg = redact(e.read().decode("utf-8", "replace")[:400], sec, key)
            raise SystemExit(f"HTTP {e.code} on batch starting {i}: {msg}")
        except Exception as e:
            raise SystemExit(f"{type(e).__name__}: {redact(str(e)[:200], sec, key)}")
    print(f"published {sent} rows to {PROJECT}.public.crypto_gorilla_archive")


if __name__ == "__main__":
    main()
