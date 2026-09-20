"""Graduation ledger: every pump.fun graduation, not the ~2% a pass happens to see.

BACKLOG C14. Measured 2026-09-18 (coverage_probe.py): of 257 sampled
graduations the journal had seen 5 - 1.95% [0.83, 4.47], no better than random
launches. A `/new_pools` window expires between passes; a signer's signature
history does not. So this pages the migration authority's signatures since the
last cursor and reads each transaction: every graduation, late by up to one
pass gap, but complete.

  39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg  pump.fun migration authority

⭐ EVERY SIGNATURE IS ACCOUNTED FOR, not just the ones that look right. A row is
written for each: `graduation` (CreatePool in the logs, exactly one non-SOL
mint), `not_target` (the authority also lands no-op race transactions),
`ambiguous` (more than one mint - recorded with the mints, never guessed), or
`fetch_failed` (retried on later passes, never skipped). The counts must add up
to what was paged; index.json carries both.

⚠️ NOT A GRADUATION RATE YET. The probe saw ~1,650 successful authority
transactions a day, ~72% with CreatePool - ~1,100 a day, against a published
base rate of 0.198% of creates (~70 a day). That is unreconciled, and every row
keeps its instruction set so this ledger can reconcile it instead of assuming.

⛔ The RPC URL carries the Helius key when one is set. It is never printed.

Run: python graduations.py [--seconds N]
"""
import datetime as dt
import json
import os
import sys
import threading
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config
import liveness

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "data", "graduations")
MIGRATION_AUTHORITY = "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY2qW7fZ2PqBRGrQ"
# Quote currencies are not the token that graduated. Measured on the seed
# (2026-09-19): 15 of 54 "ambiguous" rows were one pump mint plus USDC.
QUOTES = {WSOL, USDC, USDT}
TARGET = {"CreatePool"}
BOOTSTRAP_H = 24          # first run only: how far back the ledger starts
SECONDS = float(os.environ.get("CRYPTO_GRAD_S", "150"))
RETRY_CAP = 500
PAGE_LIMIT = 1000         # getSignaturesForAddress maximum
PAGE_CAP = 20             # 20,000 signatures - ~12 days of this authority

CALLS = {"n": 0, "errors": 0}
_CALL_LOCK = threading.Lock()
# Transactions fetched at once. Each worker still paces itself by _gap(), so
# four workers sit inside the free tier's ~10/s. ⛔ Results are consumed in
# INPUT ORDER whatever order they arrive in: the cursor may only advance across
# a contiguous prefix of processed signatures, or the ledger grows a hole.
WORKERS = int(os.environ.get("CRYPTO_GRAD_WORKERS", "4"))


def _rpc_url():
    return config.helius_rpc()


def _gap():
    # Helius free tier takes ~10/s; the public endpoint rate-limits getTransaction
    # far harder, and the runner has no key (CLAUDE.md, "The runner has NO .env").
    return 0.11 if "helius" in _rpc_url() else 0.3


def rpc(method, params, tries=3):
    """(result, error). Transport failures and 429s are retried; an RPC-level
    error is an ANSWER - the same request gets the same error - so it returns
    at once instead of burning ~9s of the pass on retries."""
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method, "params": params}).encode()
    err = None
    for i in range(tries):
        with _CALL_LOCK:
            CALLS["n"] += 1
        try:
            req = urllib.request.Request(_rpc_url(), data=body, headers={
                "Content-Type": "application/json", "User-Agent": "crypto-intel/1.0"})
            with urllib.request.urlopen(req, timeout=40) as f:
                d = json.loads(f.read())
        except Exception as e:
            with _CALL_LOCK:
                CALLS["errors"] += 1
            err = type(e).__name__ + (f" {e.code}" if hasattr(e, "code") else "")
            time.sleep(1.5 * (i + 1))
            continue
        if "error" in d:
            with _CALL_LOCK:
                CALLS["errors"] += 1
            return None, f"rpc error {(d.get('error') or {}).get('code')}"
        return d.get("result"), None
    return None, err


def classify(tx):
    """(kind, mint, instructions, mints) for one getTransaction result."""
    meta = (tx or {}).get("meta") or {}
    ins = sorted({l.split("Instruction: ", 1)[1].strip() for l in (meta.get("logMessages") or [])
                  if "Instruction: " in l})
    mints = sorted({b["mint"] for b in (meta.get("preTokenBalances") or [])
                    if b.get("mint") and b["mint"] not in QUOTES})
    if not (set(ins) & TARGET):
        return "not_target", None, ins, mints
    if len(mints) != 1:
        return "ambiguous", None, ins, mints
    return "graduation", mints[0], ins, mints


def _path(name):
    return os.path.join(DIR, name)


def load_cursor():
    try:
        with open(_path("cursor.json"), encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return None
    except Exception as e:
        raise RuntimeError(f"cursor.json unreadable ({type(e).__name__}) - refusing to restart "
                           f"the ledger from scratch, which would double-record")


def _write_json(name, obj):
    os.makedirs(DIR, exist_ok=True)
    p = _path(name)
    with open(p + ".tmp", "w", encoding="utf-8", newline="\n") as f:
        json.dump(obj, f, separators=(",", ":"))
    os.replace(p + ".tmp", p)


def _append(rows):
    by_month = {}
    for r in rows:
        m = dt.datetime.fromtimestamp(r.get("block_time") or r["recorded_ts"],
                                      dt.timezone.utc).strftime("%Y-%m")
        by_month.setdefault(m, []).append(r)
    os.makedirs(DIR, exist_ok=True)
    for m, rs in by_month.items():
        with open(_path(f"{m}.jsonl"), "a", encoding="utf-8", newline="\n") as f:
            for r in rs:
                f.write(json.dumps(r, separators=(",", ":")) + "\n")


def page_since(cursor_sig, lower_ts):
    """Successful signatures newer than cursor_sig (or than lower_ts on the first
    run), OLDEST FIRST. Returns (sigs, failed_n, error, truncated).

    ⛔ Paging runs newest to oldest, so a cap cuts the OLDEST end - the part
    right after the cursor. `truncated` says so, and build() records the gap as
    a row rather than advancing the cursor across it silently (rule 15)."""
    out, failed, before, truncated = [], 0, None, True
    for _ in range(PAGE_CAP):
        p = {"limit": PAGE_LIMIT}
        if before:
            p["before"] = before
        if cursor_sig:
            p["until"] = cursor_sig
        page, err = rpc("getSignaturesForAddress", [MIGRATION_AUTHORITY, p])
        if page is None:
            return None, failed, err, False
        if not page:
            truncated = False
            break
        for x in page:
            if lower_ts and (x.get("blockTime") or 0) < lower_ts:
                continue
            if x.get("err") is None:
                out.append({"sig": x["signature"], "block_time": x.get("blockTime")})
            else:
                failed += 1
        before = page[-1]["signature"]
        if len(page) < PAGE_LIMIT or (lower_ts and (page[-1].get("blockTime") or 0) < lower_ts):
            truncated = False
            break
        time.sleep(_gap())
    out.reverse()
    return out, failed, None, truncated


def build(verbose=True, now=None, seconds=None, workers=None):
    now = time.time() if now is None else now
    seconds = SECONDS if seconds is None else seconds
    workers = WORKERS if workers is None else max(1, int(workers))
    t0 = time.time()
    CALLS["n"] = CALLS["errors"] = 0
    origin = os.environ.get("CRYPTO_ORIGIN") or liveness.origin()
    cur = load_cursor()
    first_run = cur is None
    cur = cur or {"sig": None, "block_time": None, "retry": []}
    sigs, failed_n, err, truncated = page_since(cur.get("sig"),
                                                (now - BOOTSTRAP_H * 3600) if first_run else None)
    if sigs is None:
        m = {"built_ts": int(now), "origin": origin, "error": f"paging failed: {err}"}
        _write_json("index.json", dict(_read_index(), last_error=m))
        print(f"  graduations: paging failed ({err}); cursor unchanged")
        return m
    retry = [r for r in (cur.get("retry") or []) if r.get("sig")]
    counts = {"graduation": 0, "not_target": 0, "ambiguous": 0, "fetch_failed": 0,
              "retried_ok": 0}
    rows = []
    if truncated and sigs:
        # The ledger has a hole between the old cursor and the oldest page we
        # could reach. Say so on the record; never paper over it.
        rows.append({"kind": "gap", "after_sig": cur.get("sig"),
                     "after_block_time": cur.get("block_time"),
                     "before_block_time": sigs[0].get("block_time"),
                     "block_time": sigs[0].get("block_time"), "recorded_ts": int(time.time()),
                     "origin": origin})

    def one(item, is_retry):
        # ⛔ Version 1, not 0. Measured 2026-09-19: 3 of 60 recent authority
        # transactions (and 3 of 60 creates) are v1, and a v0 request returns
        # -32015 for them. With 0 here ~5% of graduations were fetch failures.
        tx, e = rpc("getTransaction", [item["sig"], {"maxSupportedTransactionVersion": 1,
                                                     "encoding": "json"}])
        time.sleep(_gap())
        if tx is None:
            return {"sig": item["sig"], "block_time": item.get("block_time"),
                    "kind": "fetch_failed", "error": e}
        kind, mint, ins, mints = classify(tx)
        r = {"sig": item["sig"], "block_time": tx.get("blockTime") or item.get("block_time"),
             "kind": kind, "mint": mint, "instructions": ins}
        if kind == "ambiguous":
            r["mints"] = mints[:6]
        if is_retry:
            r["retried"] = True
        return r

    def batch(items, is_retry):
        """Fetch a batch at once, and hand the results back IN INPUT ORDER.

        ⛔ The order is not cosmetic. The cursor advances to the last
        signature consumed, so consuming out of order would advance it past a
        signature that was never fetched and the ledger would lose it silently.
        """
        if workers <= 1 or len(items) == 1:
            return [one(x, is_retry) for x in items]
        with ThreadPoolExecutor(max_workers=min(workers, len(items))) as ex:
            return list(ex.map(lambda x: one(x, is_retry), items))

    still_failing = []
    i = 0
    while i < len(retry):
        if time.time() - t0 >= seconds / 3:
            still_failing.extend(retry[i:])
            break
        chunk = retry[i:i + workers]
        for item, r in zip(chunk, batch(chunk, True)):
            if r["kind"] == "fetch_failed":
                still_failing.append(item)
                continue
            counts["retried_ok"] += 1
            counts[r["kind"]] += 1
            rows.append(dict(r, recorded_ts=int(time.time()), origin=origin))
        i += len(chunk)
    done = 0
    i = 0
    while i < len(sigs):
        if time.time() - t0 >= seconds:
            break
        chunk = sigs[i:i + workers]
        for item, r in zip(chunk, batch(chunk, False)):
            counts[r["kind"]] += 1
            if r["kind"] == "fetch_failed":
                still_failing.append({"sig": item["sig"], "block_time": item.get("block_time")})
            rows.append(dict(r, recorded_ts=int(time.time()), origin=origin))
            cur["sig"], cur["block_time"] = item["sig"], item.get("block_time")
            done += 1
        i += len(chunk)
    _append(rows)
    backlog = len(sigs) - done
    cur["retry"] = still_failing[-RETRY_CAP:]
    cur["updated_ts"] = int(now)
    _write_json("cursor.json", cur)
    lag = (now - cur["block_time"]) if cur.get("block_time") else None
    idx = _read_index()
    tot = idx.get("totals") or {}
    for k in ("graduation", "not_target", "ambiguous", "fetch_failed"):
        tot[k] = tot.get(k, 0) + counts[k]
    m = {"built_at": dt.datetime.fromtimestamp(now, dt.timezone.utc).isoformat(timespec="seconds"),
         "built_ts": int(now), "origin": origin, "first_run": first_run,
         "paged": len(sigs), "failed_txs_skipped": failed_n, "processed": done,
         "gap_recorded": bool(truncated and sigs),
         "backlog": backlog, "retry_queue": len(cur["retry"]), "counts": counts,
         # every paged signature is accounted for: processed + backlog == paged
         "accounted": done + backlog == len(sigs),
         "cursor_block_time": cur.get("block_time"), "lag_s": round(lag) if lag is not None else None,
         "rpc": "helius" if "helius" in _rpc_url() else "public", "rpc_calls": CALLS["n"],
         "rpc_errors": CALLS["errors"], "elapsed_s": round(time.time() - t0, 1),
         "workers": workers, "budget_s": round(seconds, 1), "totals": tot}
    try:
        import market
        last = getattr(market, "LAST", None) or {}
        seen = last.get("seen") if now - last.get("ts", 0) < 3600 else None
        m["journal_coverage"] = coverage(now, seen)
    except Exception as e:
        m["journal_coverage"] = {"status": f"error: {type(e).__name__}"}
    _write_json("index.json", m)
    liveness.beat("graduations.ledger", len(rows),
                  detail=f"{counts['graduation']} graduations of {done} processed, backlog {backlog}")
    if verbose:
        print(f"  graduations: {counts['graduation']} graduations, {counts['not_target']} not target, "
              f"{counts['ambiguous']} ambiguous, {counts['fetch_failed']} fetch failed "
              f"of {done} processed; backlog {backlog}, lag "
              f"{'?' if lag is None else f'{lag / 3600:.1f}h'} ({m['rpc']} RPC, {m['elapsed_s']}s)")
    return m


def coverage(now, seen):
    """What share of graduations did our journal EVER see? C13, on every pass.

    Same window as coverage_probe.py - [now-26h, now-2h], so every graduation has
    had time to be seen by at least one pass - but the WHOLE ledger in that
    window, not a sample. `seen` is the set of contracts in the journal; None
    means it was not loaded this pass, and the figure is then not computed
    rather than guessed."""
    if seen is None:
        return {"status": "not computed: journal not loaded this pass"}
    lo, hi = now - 26 * 3600, now - 2 * 3600
    grads = set()
    try:
        names = sorted(n for n in os.listdir(DIR) if n[:4].isdigit() and n.endswith(".jsonl"))
    except OSError:
        names = []
    for n in names[-2:]:
        with open(_path(n), encoding="utf-8") as f:
            for line in f:
                if '"graduation"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if r.get("kind") == "graduation" and r.get("mint") and lo <= (r.get("block_time") or 0) <= hi:
                    grads.add(r["mint"])
    n = len(grads)
    if not n:
        return {"status": "no graduations in the window yet", "window_h": [26, 2], "n": 0}
    k = len(grads & seen)
    z = 1.96
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return {"status": "ok", "window_h": [26, 2], "graduations": n, "seen_by_journal": k,
            "rate": round(p, 4), "wilson95": [round((c - a) / d, 4), round((c + a) / d, 4)]}


def _read_index():
    try:
        with open(_path("index.json"), encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def recent_mints(since_ts):
    """Mints that graduated at or after since_ts, from the ledger on disk."""
    out = set()
    try:
        names = sorted(n for n in os.listdir(DIR) if n[:4].isdigit() and n.endswith(".jsonl"))
    except OSError:
        return out
    for n in names[-2:]:
        with open(_path(n), encoding="utf-8") as f:
            for line in f:
                if '"graduation"' not in line and '"ambiguous"' not in line:
                    continue
                try:
                    r = json.loads(line)
                except ValueError:
                    continue
                if (r.get("block_time") or 0) < since_ts:
                    continue
                m = r.get("mint") if r.get("kind") == "graduation" else None
                if r.get("kind") == "ambiguous":
                    # Rows written before USDC/USDT counted as quotes: derived
                    # from the mints the row itself recorded, never guessed.
                    rest = [x for x in (r.get("mints") or []) if x not in QUOTES]
                    m = rest[0] if len(rest) == 1 else None
                if m:
                    out.add(m)
    return out


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    s = None
    if "--seconds" in sys.argv:
        s = float(sys.argv[sys.argv.index("--seconds") + 1])
    build(seconds=s)
