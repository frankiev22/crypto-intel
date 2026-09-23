"""The quote-asset registry publishes what the ISSUER of the asset you are PAID
in can do to it. Run: python test_legs.py

Frank asked for exactly one check on 2026-09-23: do the xStocks and PreStocks
quote assets used as pairs on Stonk Fun retain freeze authority on chain. They do,
and more: 14 of 14 also carry a `permanentDelegate`, which lets the issuer move a
holder's balance with no signature from the holder.

This suite pins the behaviour that makes the answer trustworthy rather than the
answer itself: unknown stays unknown, a failed read never erases a good one,
`initialized` is never reported as `frozen`, and the file says out loud what it
has not checked.
"""
import ast
import io
import json
import os
import sys
import tempfile
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

import testsandbox
testsandbox.activate()

import legs

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}"
          + (f"   <- {detail}" if detail and not cond else ""))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


TMP = tempfile.mkdtemp(prefix="legs_test_")
legs.DIR = TMP
legs.REGISTRY = os.path.join(TMP, "quote_assets.json")
legs.OUTCOMES = os.path.join(TMP, "outcomes")
os.makedirs(legs.OUTCOMES, exist_ok=True)

SPYX = "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"
CLEAN = "So11111111111111111111111111111111111111112"

RWA = {"value": {"owner": legs.TOKEN22, "data": {"parsed": {"info": {
    "freezeAuthority": "JDq14BWvqCRFNu1krb12bcRpbGtJZ1FLEakMw6FdxJNs",
    "mintAuthority": "JDq14BWvqCRFNu1krb12bcRpbGtJZ1FLEakMw6FdxJNs",
    "extensions": [
        {"extension": "permanentDelegate"},
        {"extension": "pausableConfig"},
        {"extension": "defaultAccountState",
         "state": {"accountState": "initialized"}},
        {"extension": "transferFeeConfig",
         "state": {"newerTransferFee": {"transferFeeBasisPoints": 100}}},
    ]}}}}}
WSOL = {"value": {"owner": legs.SPL, "data": {"parsed": {"info": {
    "freezeAuthority": None, "mintAuthority": None}}}}}


def rpc_ok(method, params, **k):
    return ({SPYX: RWA, CLEAN: WSOL}.get(params[0]), None)


def rpc_dead(method, params, **k):
    return None, "connection reset"


# ---------------------------------------------------------------------------
section("1. one quote mint, read from chain")

a = legs.read_mint(SPYX, rpc=rpc_ok)
check("⭐ the read succeeds", a["ok"])
check("⛔⛔ a LIVE freeze authority is reported", bool(a["freeze_authority"]))
check("⛔⛔ permanentDelegate makes it ISSUER CONTROLLED",
      a["issuer_controlled"] is True)
check("⭐ the powers are plain sentences, not extension names",
      any("without your signature" in p for p in a["powers"]), str(a["powers"]))
check("⭐ the transfer fee is carried in bps", a["transfer_fee_bps"] == 100)
check("⚠️ defaultAccountState is reported VERBATIM as `initialized`",
      a["default_account_state"] == "initialized", a["default_account_state"])
check("⚠️ ...and the mint is never described as frozen today",
      "forced to start frozen" in " ".join(a["powers"])
      and a["default_account_state"] != "frozen")
check("⭐ Token-2022 ownership is recorded", a["is_token_2022"] is True)

b = legs.read_mint(CLEAN, rpc=rpc_ok)
check("⭐ a clean mint has no powers and is not issuer controlled",
      b["ok"] and b["powers"] == [] and b["issuer_controlled"] is False,
      str(b))

c = legs.read_mint(SPYX, rpc=rpc_dead)
check("⛔ a failed read is ok=False WITH A REASON, never a clean answer",
      c["ok"] is False and c.get("why"), str(c))
check("⛔ and it does not invent an issuer_controlled verdict",
      "issuer_controlled" not in c, str(c))


# ---------------------------------------------------------------------------
section("2. the registry file, and what it refuses to lose")

legs.SEED.clear()
legs.SEED.update({SPYX: "SPYx", CLEAN: "SOL"})
sm = legs.build(verbose=False, rpc=rpc_ok)
check("⭐ both mints land in the registry", sm["known"] == 2, json.dumps(sm))
check("⭐ the issuer-controlled one is counted and NAMED",
      sm["issuer_controlled"] == 1 and sm["issuer_controlled_symbols"] == ["SPYx"],
      json.dumps(sm))
check("⭐ lookup() answers from the file with no network",
      (legs.lookup(SPYX) or {}).get("issuer_controlled") is True)

d = json.load(io.open(legs.REGISTRY, encoding="utf-8"))
check("⛔ every row records WHEN it was read",
      all(r.get("checked_at") for r in d["assets"].values()))
check("⛔ every row records WHERE it came from - seed or harvest",
      all(r.get("source") for r in d["assets"].values()))
check("⛔⛔ the FILE ITSELF says what it has not checked",
      any("capability, not an" in n for n in d["not_checked"])
      and any("forward-only" in n for n in d["not_checked"]),
      json.dumps(d["not_checked"]))
check("⚠️ and it says `initialized` is not `frozen`, in the file",
      any("initialized" in n and "frozen" in n for n in d["not_checked"]))

# ⛔ The journal.py:974 bug class: one failed lookup must not overwrite a fact.
for r in d["assets"].values():
    r["checked_ts"] = 0          # force everything stale
legs._save(d)
legs.build(verbose=False, rpc=rpc_dead)
after = legs.lookup(SPYX)
check("⛔⛔ a FAILED re-read does NOT erase a known issuer-controlled answer",
      after.get("ok") is True and after.get("issuer_controlled") is True,
      json.dumps(after))
check("⛔ ...and the failure is recorded on the row, not hidden",
      after.get("last_read_failed_why"), json.dumps(after)[:160])

# A mint never read successfully must stay unread, not become clean.
NEW = "NeverReadableMint11111111111111111111111111"
legs.SEED[NEW] = "GHOST"
legs.build(verbose=False, rpc=rpc_dead)
g = legs.lookup(NEW)
check("⛔ a mint that has NEVER been read is ok=False, not clean",
      g and g.get("ok") is False and g.get("why"), json.dumps(g))


# ---------------------------------------------------------------------------
section("3. the harvest: quote mints come from rows, not from a typed list")

row = {"token": "SomeToken1111111111111111111111111111111111",
       "quote_mints": [{"symbol": "SPYx", "mint": SPYX, "liq_usd": 9000.0},
                       {"symbol": "SOL", "mint": CLEAN, "liq_usd": 100.0},
                       {"symbol": "NOMINT", "mint": None, "liq_usd": 5.0}]}
with io.open(os.path.join(legs.OUTCOMES, "2026-09-23.jsonl"), "w",
             encoding="utf-8") as f:
    f.write(json.dumps(row) + "\n")
legs.SEED.clear()
found = legs.harvest(days=2)
check("⭐ the harvest reads quote mints off real outcome rows",
      found.get(SPYX) == "SPYx" and found.get(CLEAN) == "SOL", str(found))
check("⛔ a quote asset with NO mint address is skipped, never guessed from "
      "its symbol (standing rule 2)",
      "NOMINT" not in json.dumps(found) and len(found) == 2, str(found))

# ⛔ The budget must never starve a mint that has never been read.
legs.SEED.clear()
legs.SEED.update({SPYX: "SPYx", CLEAN: "SOL", NEW: "GHOST"})
d = legs._load()
d["assets"][SPYX]["checked_ts"] = time.time()      # fresh
legs._save(d)
sm = legs.build(verbose=False, rpc=rpc_ok, max_reads=1)
check("⛔ with a budget of 1, exactly one read happens",
      sm["read_this_pass"] == 1, json.dumps(sm))
check("⛔ and the registry says how many are still stale",
      sm["stale_remaining"] >= 1, json.dumps(sm))


# ---------------------------------------------------------------------------
section("4. ⛔ the standing guarantees")

import collect  # noqa: E402
import liveness  # noqa: E402

SRC = io.open(os.path.join(HERE, "legs.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)
bad = []
for n in ast.walk(TREE):
    nm = getattr(n, "attr", None) or getattr(n, "id", None)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nm = n.name
    if nm and any(w in nm.lower() for w in
                  ("score", "grade", "rank", "rating", "prediction",
                   "expected_return", "keypair", "approve", "set_authority")):
        bad.append(f"{nm}:{getattr(n, 'lineno', '?')}")
check("⛔ no score term and no write path anywhere in this module",
      not bad, ", ".join(bad))
check("⛔ it is declared as a liveness component",
      "legs.registry" in liveness.COMPONENTS)
check("⛔ and it BEATS that component by literal name",
      any(isinstance(n, ast.Call)
          and getattr(n.func, "attr", None) == "beat"
          and n.args and isinstance(n.args[0], ast.Constant)
          and n.args[0].value == "legs.registry"
          for n in ast.walk(TREE)))
check("⛔⛔ the market stage FIRES it - something CALLS this, not just tests",
      "legs.registry" in collect.STAGE_FIRES["market"])
check("⚠️ the docstring does not overstate the seed",
      "Two mints are seeded, not fourteen" in SRC)


# ---------------------------------------------------------------------------
print()
failed = [n for n, ok_ in R if not ok_]
print(f"{len(R) - len(failed)}/{len(R)} passed")
for n in failed:
    print("  FAILED:", n)
sys.exit(1 if failed else 0)
