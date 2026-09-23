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
    out = dict(hook)
    if out.get("authHeader"):
        out["authHeader"] = f"<set, {len(out['authHeader'])} chars>"
    addrs = out.get("accountAddresses") or []
    out["accountAddresses"] = f"{len(addrs)} addresses"
    out["_addresses"] = addrs
    return out


def hooks() -> list[dict]:
    status, body = _call("GET", "/webhooks")
    if status != 200 or not isinstance(body, list):
        raise SystemExit(f"list failed: {status} {body}")
    return body


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


def watched_addresses() -> list[str]:
    return sorted(watch_sync().get("addresses") or [])


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
    with urllib.request.urlopen(req, timeout=30) as f:
        return json.loads(f.read())


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
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
