"""Register and inspect Helius webhooks. Never prints a key or a secret.

Two lanes exist and they must not be confused:

  the WALLET lane   ->  site/api/helius.mjs on Vercel, webhook
                        75056f75-c129-4f43-b686-0f369f8fa669. Whale swaps
                        attributed to a wallet. Untouched by this module.
  the POOL lane     ->  supabase/functions/helius-events. Pool creation,
                        liquidity add, liquidity remove, large transfers.
                        This module owns it.

Read only with respect to the chain. Nothing here can sign or send anything.

    python heliushook.py list                 # every webhook, secrets redacted
    python heliushook.py usage                # what we can and cannot know about credits
    python heliushook.py rate                 # delivered events, measured from our rows
    python heliushook.py probe <ADDRESS>...   # what an address WOULD cost, before registering
    python heliushook.py register             # create the pool webhook
    python heliushook.py sync                 # push chain_watch to the webhook
    python heliushook.py rows                 # what has actually landed
    python heliushook.py health               # ⛔ can Helius REACH us: exits 1 if the
                                              #   Supabase gateway is answering instead
                                              #   of the function (verify_jwt back on)
    python heliushook.py ensure               # ⭐ THE CALLER: reconcile Helius with
                                              #   data/chain_watch.json, beat liveness
                                              #   with the ROW COUNT, and HOLD rather
                                              #   than register into a dead database
"""

from __future__ import annotations

import json
import sys
import time
import urllib.error
import urllib.request

import os

import config          # loads .env into os.environ; never logs a value

API = "https://api.helius.xyz/v0"
RECEIVER = "https://rxofejxostyqlgjlzqmk.supabase.co/functions/v1/helius-events"
UA = "crypto-intel/1.0"

# The webhook we own. Set by register(); read back by list() so a later session
# does not create a second one.
POOL_WEBHOOK_TAG = RECEIVER


# ---------------------------------------------------------------------------
# THE BUDGET, and it is a derivation rather than a discovered threshold.
#
# Helius bills per DELIVERED webhook event. The free tier is 1,000,000 credits a
# month and the same key also serves RPC for chainfields and graduations, so the
# webhook lane gets 600,000 of it and RPC keeps 400,000. 600,000 a month is
#
#     600000 / (30.4 * 86400) = 0.228 delivered events per second
#
# for the WHOLE watchlist. A single address is capped at 0.05/sec (131,000 a
# month) so that no one pool can eat the budget on its own.
#
# WHY THESE EXIST IN CODE AND NOT IN A COMMENT SOMEWHERE. On 2026-09-23 this
# module registered 18 pool addresses without measuring any of them first. They
# delivered 5.55 events/sec - 24 times the whole monthly budget, per second -
# and the resulting load took the shared Supabase REST API down for every table
# in the project. Standing rule 13 says never measure a phenomenon with a sampler
# slower than the phenomenon; the same rule read forwards says never point a
# per-event cost at production without measuring the event rate first.
#
# And it cannot be estimated from liquidity. Measured over the same 88 seconds:
# STONK at $5,136,541 delivered ONE event, JEANPHIL at $323,460 delivered 389.
# A 389x spread in the opposite direction to depth. There is no shortcut.
BUDGET_PER_SEC = 0.228          # whole watchlist, 600k credits/month
ADDR_MAX_PER_SEC = 0.05         # any single address, 131k credits/month
PROBE_WINDOW_S = 600            # how far back a rate probe looks


def _env(name: str) -> str:
    v = os.environ.get(name, "")
    if not v:
        raise SystemExit(f"{name} is not set (grep .env before believing that)")
    return v


def _key() -> str:
    return _env("HELIUS_API_KEY")


def _secret() -> str:
    return _env("HELIUS_WEBHOOK_SECRET")


def _call(method: str, path: str, body: dict | None = None) -> tuple[int, object]:
    sep = "&" if "?" in path else "?"
    url = f"{API}{path}{sep}api-key={_key()}"
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"Content-Type": "application/json", "User-Agent": UA},
    )
    try:
        with urllib.request.urlopen(req, timeout=60) as f:
            raw = f.read().decode()
            return f.status, (json.loads(raw) if raw.strip() else None)
    except urllib.error.HTTPError as e:
        # The URL carries the key, so the message is printed and the URL is not.
        return e.code, e.read().decode()[:400]


def _redact(hook: dict) -> dict:
    """⛔⛔ ABSENT IS NOT ZERO, and getting that wrong cost a whole day.

    `GET /v0/webhooks` (the LIST) does not return `accountAddresses` at all.
    The old code did `out.get("accountAddresses") or []` and rendered the
    missing field as **"0 addresses"**, which is how this module reported
    "watching 0" on 2026-09-23 while the Vercel hook was watching **5** and the
    pool hook **2**, and rows were landing in `chain_events` the whole time.
    `ensure()` read the same zero and HELD all day for no reason.

    That is standing rule 5 and the `authority_live=None` shape, in code I wrote
    the day before. The list endpoint's answer is now **unknown**, and the only
    way to learn the addresses is `hook_addresses()`, which asks per id.
    """
    out = dict(hook)
    if out.get("authHeader"):
        out["authHeader"] = f"<set, {len(out['authHeader'])} chars>"
    addrs = out.get("accountAddresses")
    if isinstance(addrs, list):
        out["accountAddresses"] = f"{len(addrs)} addresses"
        out["_addresses"] = addrs
    else:
        out["accountAddresses"] = ("unknown - the list endpoint omits this "
                                   "field; call hook_addresses(id)")
        out["_addresses"] = None
    return out


def hooks() -> list[dict]:
    status, body = _call("GET", "/webhooks")
    if status != 200 or not isinstance(body, list):
        raise SystemExit(f"list failed: {status} {body}")
    return body


def hook_addresses(webhook_id: str) -> list[str] | None:
    """The addresses ONE webhook actually watches, or None if it cannot be read.

    ⛔ Returns None on any failure, never []. An empty list means "watching
    nothing", which is a decision; None means "we do not know", which is not.
    """
    status, body = _call("GET", "/webhooks/" + webhook_id)
    if status != 200 or not isinstance(body, dict):
        return None
    addrs = body.get("accountAddresses")
    return addrs if isinstance(addrs, list) else None


def usage() -> dict:
    """What we can and cannot know about credit consumption.

    There is NO public Helius endpoint that reports credits used on the free
    tier; the first version of this function guessed at
    /v0/addresses/usage and got "invalid address" back, which is the API
    telling us that path expects an address and not a usage report. The number
    lives in the Helius dashboard only.

    So the credit budget is measured from OUR side instead, which is better
    anyway because it is our own observation: credits are charged per delivered
    event, and every delivered event is one row in chain_events. `rate()` below
    reads that. Never report a credit figure we did not measure.
    """
    return {
        "credits_used": None,
        "why": "no public Helius endpoint reports it; dashboard only",
        "measure_instead": "rate() - delivered events per second, from our own rows",
        "free_tier_credits_per_month": 1_000_000,
    }


def rate() -> dict:
    """The delivery rate, measured from rows we actually received.

    This is the number that decides how many addresses the free tier affords,
    and measured 2026-09-23 it is brutal: 18 pool addresses delivered 5.55
    events/sec, which is 14.6M credits a month against a 1M free tier.

    WHY IT MUST BE MEASURED BEFORE ADDRESSES ARE REGISTERED, NOT AFTER:
    liquidity does not predict event volume and the relationship is INVERTED.
    STONK at $5.1M fired once in 88 seconds; JEANPHIL at $323k fired 389 times.
    See docs/CHAIN_EVENTS.md section 3.
    """
    d = rows()
    return {
        "rows_total": d.get("rows_total"),
        "watching": d.get("watching"),
        "watchlist_read": d.get("watchlist_read"),
        "newest": (d.get("newest_rows") or [None])[0],
        "note": "per-pool rates need a SQL window; see docs/CHAIN_EVENTS.md",
    }


def watch_sync(rows: list[dict] | None = None) -> dict:
    """Read, or upsert then read, the pool watchlist in Supabase.

    The receiver and the webhook must watch the SAME list or events arrive and
    are not attributed, so there is one source and both read it. Nothing on this
    disk holds a service-role key, so this goes through the secret-gated RPC.
    """
    url = f"{os.environ['SUPABASE_URL'].rstrip('/')}/rest/v1/rpc/chain_watch_sync"
    key = _env("SUPABASE_PUBLISHABLE_KEY")
    body = {"p_secret": _env("CRYPTO_WHALE_SECRET")}
    if rows:
        body["p_rows"] = rows
    req = urllib.request.Request(
        url,
        data=json.dumps(body).encode(),
        headers={
            "apikey": key,
            "Authorization": f"Bearer {key}",
            "Content-Type": "application/json",
            "User-Agent": UA,
        },
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as f:
            return json.loads(f.read())
    except urllib.error.HTTPError as e:
        raise SystemExit(f"chain_watch_sync failed: {e.code} {e.read().decode()[:200]}")


# ---------------------------------------------------------------------------
# ⛔ THE WATCHLIST LIVES IN GIT. Supabase is a MIRROR, never the truth.
#
# It lived only in Supabase. When the database stopped answering at 2026-09-23
# 04:06Z the list became unreadable AND unrecoverable in the same instant: the
# webhook could not be restored because the only copy of what to watch was
# behind the outage. CLAUDE.md had already settled this - "State store is git.
# Supabase is a write-only mirror (no SELECT grant), so it cannot serve as
# state" - and this module used it as state anyway.
#
# ⛔ And the old reader was `watch_sync().get("addresses") or []`, so an RPC that
# answered without the key returned an EMPTY LIST. That is the authority_live=None
# shape for the fourth time: not-read rendering as watch-nothing. It now raises.
WATCH_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                          "data", "chain_watch.json")


def watchlist_git() -> dict:
    """The authoritative watchlist, from git. Raises rather than guessing."""
    if not os.path.exists(WATCH_FILE):
        raise SystemExit("no watchlist at %s - refusing to guess what to watch"
                         % WATCH_FILE)
    with open(WATCH_FILE, encoding="utf-8") as f:
        d = json.load(f)
    rows = d.get("addresses")
    if not isinstance(rows, list) or not rows:
        raise SystemExit("%s has no addresses - refusing to register nothing"
                         % WATCH_FILE)
    return d


def watched_addresses() -> list[str]:
    """Active addresses from git. ⛔ Never returns [] quietly - it raises."""
    rows = watchlist_git()["addresses"]
    active = sorted(r["address"] for r in rows if r.get("active"))
    if not active:
        raise SystemExit("every address in %s is active=false - refusing to "
                         "register an empty webhook, which is what made the "
                         "wallet lane silent" % WATCH_FILE)
    return active


def mirror_to_supabase() -> tuple[bool, str]:
    """Best effort. The mirror is never read as truth, so a failure is not fatal.

    ⚠️ Returns (False, reason) instead of raising, deliberately: a mirror that
    can break the thing it mirrors is worse than a stale mirror.
    """
    try:
        rows = [{"address": r["address"], "active": bool(r.get("active")),
                 "note": "%s %s" % (r.get("ticker"), r.get("dex"))}
                for r in watchlist_git()["addresses"]]
        out = watch_sync(rows)
        return True, "mirrored %s rows, upserted %s" % (len(rows), out.get("upserted"))
    except SystemExit as e:
        return False, str(e)[:160]
    except Exception as e:
        return False, "%s: %s" % (type(e).__name__, str(e)[:140])


def probe_rate(address: str, window_s: int = PROBE_WINDOW_S) -> dict:
    """Transactions per second on one address, measured from the chain.

    This is what a webhook on that address would cost, measured BEFORE the
    webhook exists. It pages getSignaturesForAddress backwards until it passes
    `window_s` or runs out, so a quiet address is cheap to probe and a busy one
    is answered by the first page.

    rate=None means the window could not be established. That is "unknown" and
    register() refuses it; it is never treated as zero.
    """
    rpc = config.helius_rpc()
    hdr = {"Content-Type": "application/json", "User-Agent": UA}
    now = time.time()
    oldest_wanted = now - window_s
    seen, before, oldest_seen, ran_out = 0, None, None, False

    for _ in range(10):                      # at most 10,000 signatures
        params = [address, {"limit": 1000}]
        if before:
            params[1]["before"] = before
        req = urllib.request.Request(
            rpc,
            data=json.dumps({"jsonrpc": "2.0", "id": 1,
                             "method": "getSignaturesForAddress",
                             "params": params}).encode(),
            headers=hdr,
        )
        try:
            with urllib.request.urlopen(req, timeout=40) as f:
                res = json.loads(f.read()).get("result") or []
        except Exception as e:
            return {"address": address, "rate": None,
                    "why": "rpc " + type(e).__name__}
        if not res:
            ran_out = True
            break
        passed = False
        for row in res:
            bt = row.get("blockTime")
            if bt is None:
                continue
            if bt < oldest_wanted:
                oldest_seen = bt
                passed = True
                break
            seen += 1
            oldest_seen = bt
        if passed:
            break
        before = res[-1]["signature"]
    else:
        passed = False

    if oldest_seen is None:
        return {"address": address, "rate": None, "why": "no dated signatures"}
    span = max(now - oldest_seen, 1.0)
    return {
        "address": address,
        "txs": seen,
        "span_s": round(span, 1),
        "rate": round(seen / span, 4),
        # A span far short of the window means the address ran out of history,
        # so the rate is over a shorter and possibly unrepresentative period.
        "short_window": span < window_s * 0.5,
        "history_exhausted": ran_out,
        "per_month": int(seen / span * 86400 * 30.4),
    }


def find_pool_hook() -> dict | None:
    for h in hooks():
        if (h.get("webhookURL") or "").rstrip("/") == POOL_WEBHOOK_TAG.rstrip("/"):
            return h
    return None


def register(addresses: list[str], measured: bool = True) -> dict:
    """Create or edit the pool webhook.

    measured=True (the default) PROBES every address first and refuses the whole
    call if the set would exceed BUDGET_PER_SEC, or any one address exceeds
    ADDR_MAX_PER_SEC, or any address's rate cannot be established. Unknown is
    not zero.

    measured=False skips the probe. It exists for one case only: SHRINKING a
    live webhook in a hurry, where the new set is already known to be cheaper
    than what is running.
    """
    if not addresses:
        raise SystemExit("refusing to register a webhook with no addresses: "
                         "an empty list is what made the wallet lane silent")
    if measured:
        probes = [probe_rate(a) for a in addresses]
        unknown = [x for x in probes if x.get("rate") is None]
        hot = [x for x in probes if (x.get("rate") or 0) > ADDR_MAX_PER_SEC]
        total = sum(x.get("rate") or 0 for x in probes)
        if unknown or hot or total > BUDGET_PER_SEC:
            lines = ["REFUSED. measured %.3f events/sec against a %s budget."
                     % (total, BUDGET_PER_SEC)]
            for x in hot:
                lines.append("  over ADDR_MAX_PER_SEC: %s  %s/sec = %s/month%s"
                             % (x["address"], x["rate"], format(x["per_month"], ","),
                                "  (short window)" if x.get("short_window") else ""))
            for x in unknown:
                lines.append("  rate unknown, refused: %s (%s)"
                             % (x["address"], x.get("why")))
            lines.append("  pass measured=False only to SHRINK a live webhook.")
            raise SystemExit(chr(10).join(lines))
    existing = find_pool_hook()
    payload = {
        "webhookURL": RECEIVER,
        "transactionTypes": ["ANY"],
        "accountAddresses": addresses,
        "webhookType": "enhanced",
        "authHeader": _secret(),
    }
    if existing:
        status, body = _call("PUT", f"/webhooks/{existing['webhookID']}", payload)
        action = "edited"
    else:
        status, body = _call("POST", "/webhooks", payload)
        action = "created"
    if status not in (200, 201):
        raise SystemExit(f"{action} failed: {status} {body}")
    return {"action": action, "status": status, "hook": _redact(body)}


def rows(limit: int = 10) -> dict:
    """What has actually landed. The only evidence that counts."""
    req = urllib.request.Request(RECEIVER, headers={"User-Agent": UA})
    with urllib.request.urlopen(req, timeout=60) as f:
        return json.loads(f.read())


def health() -> dict:
    """Can Helius still REACH the receiver at all.

    ⛔ THE FAILURE THIS EXISTS FOR. A Supabase function deploy takes verify_jwt
    and DEFAULTS IT TO TRUE. Redeploying the receiver on 2026-09-23 at 06:10Z
    without passing it explicitly flipped it on, and the Supabase GATEWAY then
    answered every request UNAUTHORIZED_NO_AUTH_HEADER in 0.33s - before a line
    of our code ran, and it would have rejected Helius exactly the same way.
    The deploy itself returned a perfectly healthy 200 with the new version.

    So the deploy's own answer proves nothing, and neither does the source. The
    only thing that proves the receiver is reachable is an unauthenticated GET
    to its real URL coming back 200. That is what this does.

    ⚠️ It says NOTHING about whether the database is up - the probe reports that
    separately and honestly. gateway_blocking is the one question here.
    """
    t0 = time.time()
    try:
        req = urllib.request.Request(RECEIVER, headers={"User-Agent": UA})
        with urllib.request.urlopen(req, timeout=60) as f:
            body = json.loads(f.read())
        out = {
            "reachable": True,
            "gateway_blocking": False,
            "http": 200,
            "elapsed_s": round(time.time() - t0, 2),
        }
    except urllib.error.HTTPError as e:
        detail = e.read()[:200].decode("utf-8", "replace")
        blocked = "UNAUTHORIZED_NO_AUTH_HEADER" in detail or e.code == 401
        return {
            "reachable": False,
            # ⛔ A 401 on an unauthenticated GET means verify_jwt is back on.
            "gateway_blocking": blocked,
            "http": e.code,
            "detail": detail,
            "elapsed_s": round(time.time() - t0, 2),
            "fix": ("redeploy with verify_jwt=false; the receiver authenticates "
                    "with the SHA-256 of the shared secret, not a Supabase JWT"),
        }
    except Exception as e:
        # Unknown is unknown. A network failure is not evidence the gateway is
        # fine, and it is not evidence it is broken either.
        return {
            "reachable": False,
            "gateway_blocking": None,
            "http": None,
            "detail": f"{type(e).__name__}: {str(e)[:160]}",
            "elapsed_s": round(time.time() - t0, 2),
        }
    # Reachable. Pass through what the probe says about the database, unchanged.
    for k in ("rows_total", "watching", "watchlist_read", "read_error",
              "raw_omitted_rows", "raw_full_rows", "storage_budget_working",
              "bytes_per_row", "bytes_per_row_note"):
        out[k] = body.get(k)
    out["database"] = "up" if body.get("watchlist_read") == "ok" else "NOT ANSWERING"
    return out


def ensure(register_fn=None, health_fn=None, beat_fn=None) -> dict:
    """⭐ THE CALLER. Reconcile Helius with the git watchlist, every pass.

    This exists because "built but not wired" is the primary bug in this repo and
    the receiver was its fifth instance: it took real rows at 03:53Z and sat at
    ZERO addresses by 04:06Z, and nobody found out for most of a day. A module
    that only runs when somebody types its name has not shipped.

    ⛔ IT WILL NOT REGISTER INTO A DEAD DATABASE. When the database is not
    answering, every insert fails, the receiver correctly answers 500 so the
    event is not lost, Helius retries, and the retries are exactly what
    saturated PostgREST and caused the outage in the first place. So a dead
    database means HOLD, not sync. Fixing the symptom by re-registering would
    have re-run the outage.

    ⭐ It beats liveness with the ROW COUNT, not with the fact that it ran
    (standing rule 16, and Frank's own words: the registry counts rows, not
    beats). A pass where this fires and no rows exist reads as producing
    nothing, which is what it is doing.

    Returns what it did and why. Never raises: a reconciler that can break the
    pass it runs inside is worse than a stale webhook.
    """
    register_fn = register_fn or register
    health_fn = health_fn or health
    out = {"acted": "none", "why": None, "rows_total": None, "watching": None}
    try:
        want = watched_addresses()
    except SystemExit as e:
        out["why"] = "watchlist unusable: %s" % str(e)[:140]
        return out
    out["want"] = len(want)

    try:
        h = health_fn()
    except Exception as e:
        out["why"] = "health probe threw: %s: %s" % (type(e).__name__, str(e)[:100])
        return out
    out["rows_total"] = h.get("rows_total")
    out["gateway_blocking"] = h.get("gateway_blocking")
    out["database"] = h.get("database")

    # Beat FIRST, with whatever row count the receiver reports, so the liveness
    # registry learns the truth even on a pass that then decides to hold.
    #
    # ⛔ The component name is a LITERAL here on purpose. test_stages.py walks the
    # source for beat("<name>") and fails when a declared component is beaten by
    # nothing, which is the static form of "built but not wired". Passing the name
    # through a variable would defeat the one check that catches this bug class.
    n = h.get("rows_total")
    rows_n = int(n) if isinstance(n, (int, float)) else (
        int(n) if isinstance(n, str) and n.isdigit() else 0)
    detail = "gateway_blocking=%s database=%s" % (h.get("gateway_blocking"),
                                                  h.get("database"))
    if beat_fn is not None:
        try:
            beat_fn("chainevents.rows", n=rows_n, detail=detail)
        except Exception:
            pass
    else:
        try:
            import liveness
            liveness.beat("chainevents.rows", n=rows_n, detail=detail)
        except Exception:
            pass

    if h.get("gateway_blocking"):
        out["acted"] = "hold"
        out["why"] = ("the Supabase gateway is answering instead of the receiver: "
                      "redeploy the function with verify_jwt=false")
        return out
    if h.get("database") != "up":
        out["acted"] = "hold"
        # ⚠️ Worded as the likely cause, not the proven one. The retry
        # storm is the best explanation for how the 04:06Z outage STARTED; it
        # does not explain why it persisted 8h after the addresses went to zero
        # and all inbound traffic stopped (docs/CHAIN_EVENTS.md section 4).
        out["why"] = ("database not answering, so an insert would fail, the "
                      "receiver would answer 500, and Helius would retry - the "
                      "likely cause of the 04:06Z outage. Holding deliberately.")
        return out

    try:
        hook = find_pool_hook()
    except Exception as e:
        out["why"] = "could not list webhooks: %s" % str(e)[:120]
        return out
    # ⛔⛔ ASK PER ID. `GET /v0/webhooks` omits `accountAddresses` entirely,
    # so `hook.get("accountAddresses") or []` was reading ABSENT as ZERO - which
    # is how this reported "watching 0" on 2026-09-23 while the two hooks were
    # watching 5 and 2 and rows were arriving the whole time. Left unguarded it
    # would also have seen permanent drift and re-registered every pass at 100
    # credits a time.
    if not hook:
        out["acted"] = "failed"
        out["why"] = "the pool webhook was not found in the list"
        return out
    have_list = hook_addresses(hook.get("webhookID") or "")
    if have_list is None:
        # ⛔ Unknown is not empty. Drift cannot be computed against an answer
        # we do not have, and re-registering on a guess costs credits and could
        # REMOVE addresses that are live.
        out["acted"] = "hold"
        out["watching"] = None
        out["why"] = ("could not read the webhook's own address list, so drift "
                      "is unknown. Refusing to re-register on a guess.")
        return out
    have = sorted(have_list)
    out["watching"] = len(have)
    if have == sorted(want):
        out["acted"] = "in_sync"
        out["why"] = "%d addresses, unchanged" % len(want)
        return out

    # ⚠️ A webhook edit costs 100 credits, so this only fires on real drift.
    try:
        r = register_fn(want)
    except SystemExit as e:
        out["acted"] = "refused"
        out["why"] = str(e)[:400]
        return out
    except Exception as e:
        out["acted"] = "failed"
        out["why"] = "%s: %s" % (type(e).__name__, str(e)[:140])
        return out
    out["acted"] = r.get("action", "registered")
    out["why"] = "drift %d -> %d addresses" % (len(have), len(want))
    ok, reason = mirror_to_supabase()
    out["mirror"] = reason if ok else "MIRROR FAILED: %s" % reason
    return out


def main(argv: list[str]) -> int:
    cmd = argv[1] if len(argv) > 1 else "list"
    if cmd == "list":
        for h in hooks():
            r = _redact(h)
            addrs = r.pop("_addresses")
            print(json.dumps(r, indent=1))
            if addrs:
                print(f"  first 3: {addrs[:3]}")
    elif cmd == "usage":
        print(json.dumps(usage(), indent=1))
    elif cmd == "rate":
        print(json.dumps(rate(), indent=1))
    elif cmd == "probe":
        addrs = argv[2:] or watched_addresses()
        total = 0.0
        for a in addrs:
            pr = probe_rate(a)
            total += pr.get("rate") or 0
            print(json.dumps(pr))
        print("TOTAL %.3f events/sec against a %s budget = %s credits/month"
              % (total, BUDGET_PER_SEC, format(int(total * 86400 * 30.4), ",")))
    elif cmd == "register":
        addrs = watched_addresses()
        print(f"registering {len(addrs)} addresses from chain_watch")
        print(json.dumps(register(addrs), indent=1))
    elif cmd == "sync":
        addrs = watched_addresses()
        h = find_pool_hook()
        if not h:
            print("no pool webhook yet; run register")
            return 1
        have = set(h.get("accountAddresses") or [])
        if have == set(addrs):
            print(f"already in sync, {len(addrs)} addresses")
            return 0
        print(f"syncing {len(have)} -> {len(addrs)} addresses (edit costs 100 credits)")
        print(json.dumps(register(addrs), indent=1))
    elif cmd == "rows":
        print(json.dumps(rows(), indent=1))
    elif cmd == "health":
        h = health()
        print(json.dumps(h, indent=1))
        # Non-zero when the gateway is in front of us, so this is usable as a
        # check rather than only as something to read.
        if h.get("gateway_blocking"):
            return 1
    elif cmd == "ensure":
        try:
            import liveness
            bf = liveness.beat
        except Exception:
            bf = None
        print(json.dumps(ensure(beat_fn=bf), indent=1))
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
