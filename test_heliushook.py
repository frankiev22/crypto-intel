"""The webhook control plane cannot spend the credit budget or leak a key.

OFFLINE BY CONSTRUCTION. Nothing here touches Helius, Supabase or the chain: the
probe and the HTTP call are both injected. A test that needs the network is a
test that gets skipped in CI and then does not exist.

WHY THIS FILE EXISTS. On 2026-09-23 heliushook.register() pointed a webhook at 18
pool addresses without measuring one of them. They delivered 5.55 events/sec
against a budget of 0.228, and the resulting load took the shared Supabase REST
API down for every table in the project for a quarter of an hour. The guard that
now prevents that is only worth having if something fails when it is removed.
"""
import ast
import io
import sys

import heliushook

PASS, FAIL = [], []


def check(name, cond):
    (PASS if cond else FAIL).append(name)
    print(f"  {'PASS' if cond else 'FAIL'}  {name}")


def section(title):
    print("=" * 72)
    print(title)
    print("=" * 72)


def refuses(fn, *a, **kw):
    """True when fn raises SystemExit. Returns (refused, message)."""
    try:
        fn(*a, **kw)
        return False, ""
    except SystemExit as e:
        return True, str(e)


# ---------------------------------------------------------------------------
section("⛔ The credit budget is enforced, not documented")

check("BUDGET_PER_SEC derives from the free tier: 600k/month within 1%",
      abs(heliushook.BUDGET_PER_SEC * 86400 * 30.4 - 600_000) / 600_000 < 0.01)
check("ADDR_MAX_PER_SEC is below the whole-set budget",
      0 < heliushook.ADDR_MAX_PER_SEC < heliushook.BUDGET_PER_SEC)

# An empty list is what made the wallet lane silent for months.
refused, _ = refuses(heliushook.register, [])
check("⛔ register() refuses an EMPTY address list", refused)


def fake_probe(rates):
    """Replace probe_rate with a lookup, so no RPC is touched."""
    def probe(address, window_s=None):
        r = rates.get(address)
        if r is None:
            return {"address": address, "rate": None, "why": "test"}
        return {"address": address, "rate": r, "per_month": int(r * 86400 * 30.4),
                "short_window": False, "txs": 1, "span_s": 600.0}
    return probe


real_probe = heliushook.probe_rate
real_hooks = heliushook.hooks
real_call = heliushook._call
heliushook.hooks = lambda: []            # no existing webhook
calls = []
heliushook._call = lambda m, p, b=None: (calls.append((m, p, b)), (201, {"webhookID": "x"}))[1]

try:
    # One address that alone blows the per-address cap. This is JEANPHIL's real
    # measured chain rate: 38.2459 tx/sec, 100,455,258 a month.
    heliushook.probe_rate = fake_probe({"JEANPHIL": 38.2459})
    refused, msg = refuses(heliushook.register, ["JEANPHIL"])
    check("⛔ register() refuses ONE address over ADDR_MAX_PER_SEC", refused)
    # The monthly figure is computed by the fixture, so assert its SHAPE rather
    # than its digits: hardcoding a number from a live probe run is how a test
    # starts failing for a reason that is not a bug.
    check("   ...and the refusal names the address and a comma-grouped monthly cost",
          "JEANPHIL" in msg and "/month" in msg
          and any(c == "," for c in msg.split("/month")[0][-12:]))
    check("   ...and nothing was sent to Helius", not calls)

    # Several addresses each under the per-address cap but over the set budget.
    many = {f"a{i}": 0.04 for i in range(10)}      # 0.40/sec total
    heliushook.probe_rate = fake_probe(many)
    refused, msg = refuses(heliushook.register, list(many))
    check("⛔ register() refuses a SET over BUDGET_PER_SEC even when each address passes",
          refused and "0.400" in msg)
    check("   ...and nothing was sent to Helius", not calls)

    # ⛔ Unknown is not zero. This is the authority_live=None shape.
    heliushook.probe_rate = fake_probe({"quiet": 0.001})      # "unknown" is absent
    refused, msg = refuses(heliushook.register, ["quiet", "unknown"])
    check("⛔⛔ an address whose rate is UNKNOWN is refused, never treated as 0",
          refused and "rate unknown" in msg)
    check("   ...and nothing was sent to Helius", not calls)

    # The real measured set that passes: ZCAT raydium, KNOTS raydium, LOOP x2.
    ok = {"zcat": 0.0307, "knots": 0.0388, "loop1": 0.0044, "loop2": 0.0184}
    heliushook.probe_rate = fake_probe(ok)
    refused, msg = refuses(heliushook.register, list(ok))
    check("⭐ register() ALLOWS the four addresses measured under the budget",
          not refused)
    check("   ...and it actually called Helius once, with POST", len(calls) == 1
          and calls[0][0] == "POST")
    check("   ...and it sent all four addresses",
          sorted((calls[0][2] or {}).get("accountAddresses", [])) == sorted(ok))

    # measured=False is the escape hatch and it must be explicit.
    calls.clear()
    heliushook.probe_rate = fake_probe({})     # every rate unknown
    refused, _ = refuses(heliushook.register, ["anything"], measured=False)
    check("measured=False skips the probe (the shrink-in-a-hurry path)", not refused)
finally:
    heliushook.probe_rate = real_probe
    heliushook.hooks = real_hooks
    heliushook._call = real_call


# ---------------------------------------------------------------------------
section("⛔ A failed probe reports UNKNOWN, never a rate")

real_urlopen = heliushook.urllib.request.urlopen


def boom(*a, **kw):
    raise OSError("network down")


heliushook.urllib.request.urlopen = boom
try:
    p = heliushook.probe_rate("whatever")
    check("⛔ probe_rate() returns rate=None when the RPC fails", p["rate"] is None)
    check("   ...and says why", "rpc" in (p.get("why") or ""))
    check("   ...and never returns rate=0, which would read as 'quiet'",
          p.get("rate") != 0)
finally:
    heliushook.urllib.request.urlopen = real_urlopen


# ---------------------------------------------------------------------------
section("⛔ No secret can reach a log, and no trade can be placed")

src = io.open("heliushook.py", encoding="utf-8").read()
tree = ast.parse(src)

# The shared secret and the api key must never be an argument to print().
leaks = []
for node in ast.walk(tree):
    if not (isinstance(node, ast.Call) and isinstance(node.func, ast.Name)
            and node.func.id == "print"):
        continue
    for arg in ast.walk(node):
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                and arg.func.id in ("_key", "_secret"):
            leaks.append(getattr(node, "lineno", 0))
        if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name) \
                and arg.func.id == "_env":
            leaks.append(getattr(node, "lineno", 0))
check("⛔⛔ no print() anywhere takes _key(), _secret() or _env()", not leaks)

# _redact must replace the authHeader rather than pass it through.
red = heliushook._redact({"authHeader": "a-secret-value-33-chars-long-----",
                          "accountAddresses": ["one", "two"]})
check("⛔ _redact() replaces authHeader with a length, not the value",
      "a-secret-value" not in str(red) and "33 chars" in red["authHeader"])
check("   ...and collapses the address list to a count",
      red["accountAddresses"] == "2 addresses")

FORBIDDEN = {
    "sign", "sign_transaction", "signTransaction", "send_transaction",
    "sendTransaction", "signAndSendTransaction", "approve", "set_authority",
    "transfer", "swap", "place_order", "createOrder", "initializeOrder",
    "sendRawTransaction", "requestAirdrop", "Keypair", "from_secret_key",
}
found = sorted({n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id
                for n in ast.walk(tree)
                if isinstance(n, ast.Call)
                and (isinstance(n.func, ast.Attribute) or isinstance(n.func, ast.Name))
                and (n.func.attr if isinstance(n.func, ast.Attribute) else n.func.id)
                in FORBIDDEN})
check("⛔⛔ heliushook.py contains NO signing, sending or order-placing call",
      not found)
if found:
    print("       found:", found)

# The wallet lane must stay untouched: its URL must never appear as a target.
check("⛔ the Vercel wallet receiver is never written to by this module",
      "crypto-intel-one-eta.vercel.app/api/helius" not in src.replace(
          "site/api/helius.mjs", ""))


# ---------------------------------------------------------------------------
section("The receiver and the webhook read ONE list")

# ⛔⛔ CHANGED 2026-09-23, and the old assertion was pointing at the wrong
# source. It required `watch_sync`, the Supabase RPC. Supabase has no SELECT
# grant and is a write-only mirror, so it cannot BE the state (CLAUDE.md), and on
# 2026-09-23 it proved it by refusing connections for eight hours while the
# reconciler still needed to know what to watch. The authoritative list is now
# `data/chain_watch.json` in git, which is the same store as every other piece of
# state in this repo, and Supabase is mirrored to on a best effort.
_body = src.split("def watched_addresses")[1].split("\ndef ")[0]
check("watched_addresses() comes from chain_watch IN GIT, not Supabase",
      "watchlist_git" in _body and "watch_sync" not in _body)
check("⛔ an empty or missing watchlist RAISES - it never registers nothing",
      "SystemExit" in src.split("def watchlist_git")[1].split("\ndef ")[0]
      and "SystemExit" in _body)
check("⭐ usage() reports credits_used=None rather than inventing a number",
      heliushook.usage()["credits_used"] is None)

print()
print(f"{len(PASS)}/{len(PASS) + len(FAIL)} passed")
if FAIL:
    for f in FAIL:
        print("  FAILED:", f)
sys.exit(1 if FAIL else 0)
