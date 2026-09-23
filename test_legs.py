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

# ======================================================================
# ⛔⛔ A PRESENT EXTENSION IS NOT AN ACTIVE ONE
# ======================================================================
# Read from chain 2026-09-23: SPYx and COPX both carry `transferHook` with
# programId NULL, and the old sentence said "every transfer runs issuer code
# that can reject it" about both. That is not-happening rendered as happening,
# and it is the direction that cries wolf.
check("⛔⛔ an EXPLICITLY null transfer hook says the slot is empty, not that code runs",
  "no issuer code runs" in (legs.power_sentence(
      "transferHook", {"authority": "a", "programId": None}) or ""),
  legs.power_sentence("transferHook", {"authority": "a", "programId": None}))
check("⛔ but a MISSING programId key is unknown, not empty - it still reports the "
  "capability rather than a clean negative",
  "every transfer runs issuer code" in (legs.power_sentence(
      "transferHook", {"authority": "a"}) or ""),
  legs.power_sentence("transferHook", {"authority": "a"}))
check("⭐ a live hook names the program",
  "program Hook1" in (legs.power_sentence(
      "transferHook", {"programId": "Hook1"}) or ""))
check("⛔⛔ a permanentDelegate whose address could not be read still reports the "
  "power, and says WHO is unknown - silence there is the bug this repo keeps "
  "making",
  "unknown" in (legs.power_sentence("permanentDelegate", {}) or "")
  and "MOVE your tokens" in (legs.power_sentence("permanentDelegate", {}) or ""),
  legs.power_sentence("permanentDelegate", {}))
check("⭐ and a delegate revoked to the zero address reports nothing",
  legs.power_sentence("permanentDelegate",
                      {"delegate": legs.ZERO_ADDRESS}) is None)
check("⛔ `defaultAccountState: initialized` says accounts are NOT frozen today",
  "so they are not" in (legs.power_sentence(
      "defaultAccountState", {"accountState": "initialized"}) or ""))
check("⛔ and `frozen` says so loudly",
  "START FROZEN" in (legs.power_sentence(
      "defaultAccountState", {"accountState": "frozen"}) or ""))
check("⛔ a PAUSED asset is reported as paused right now, not as a capability",
  "PAUSED RIGHT NOW" in (legs.power_sentence(
      "pausableConfig", {"paused": True}) or ""))

# ⭐⭐ The dividend mechanism, read from the mint rather than from marketing.
check("⭐⭐ a scaled-UI multiplier above 1 is reported as the DIVIDEND mechanism, "
  "because that is what an xStock pays instead of cash",
  "dividend without a transfer" in (legs.power_sentence(
      "scaledUiAmountConfig",
      {"multiplier": "1.0039", "newMultiplier": "1.0057"}) or ""))
check("⭐ and a multiplier of exactly 1 reports nothing - COPX does not rebase",
  legs.power_sentence("scaledUiAmountConfig",
                      {"multiplier": "1", "newMultiplier": "1"}) is None)

# ======================================================================
# ⭐⭐ THE ISSUER REGISTRY, keyed on the MINT
# ======================================================================
check("⛔ the issuer registry is keyed on the MINT, never a symbol (standing rule 2 "
  "- six different mints answer to COPX)",
  all(len(k) >= 32 for k in legs.ISSUERS))
check("⭐ SPYx resolves to Backed, and is recorded as NOT the share",
  legs.issuer("XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W")
  ["redeemable_for_the_real_share"] is False)
check("⭐ COPX resolves to Backpack Securities, and IS redeemable for the real share "
  "- so the two RWA legs are materially different instruments",
  legs.issuer("CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5")
  ["redeemable_for_the_real_share"] is True)
check("⛔ an unresearched mint returns None, which means NOT RESEARCHED",
  legs.issuer("So11111111111111111111111111111111111111112") is None)
check("⛔⛔ every researched issuer marks the PROVENANCE of its fields, so a press "
  "claim is never read as our own measurement",
  all({"from_chain", "from_issuer", "from_press"} <= set(v)
      for v in legs.ISSUERS.values()))
check("⚠️ a field we could not establish is None or says NOT ESTABLISHED, never a "
  "confident guess",
  legs.issuer("CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5")
  ["voting_rights"] is None
  and "NOT ESTABLISHED" in legs.issuer(
      "CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5")["us_persons"])

print(f"{len(R) - len(failed)}/{len(R)} passed")
for n in failed:
    print("  FAILED:", n)
sys.exit(1 if failed else 0)
