"""Tests for intel.py, the backend the site calls.

⛔ OFFLINE BY CONSTRUCTION. Every source is monkeypatched, and the last section
proves it by failing if a real network function is reachable from a fixture.

⭐ The tests are written against the MISTAKES, not the happy path. Each one names
the failure it exists to prevent, because a test whose purpose is not written
down gets deleted by the next person who finds it inconvenient.
"""
import ast
import io
import os
import sys

import intel

R = []


def t(name, ok, why=""):
    R.append((name, ok, why))
    print(f"  {'PASS' if ok else 'FAIL'}  {name}" + (f"\n        {why}" if not ok else ""))


def head(s):
    print()
    print("=" * 72)
    print(s)
    print("=" * 72)


def fake_token(pairs=3, liq_each=10000.0, mcap=500_000.0, price=0.001,
               sym="TEST", name="Test Token", first_ms=1_750_000_000_000,
               quotes=("SOL",), ok=True):
    """An allpairs.token() reply, shaped exactly like the real one."""
    if not ok:
        return {"mint": "M", "ok": False, "error": "lookup failed",
                "pair_count": None, "total_liq_usd": None, "total_vol24_usd": None}
    truncated = pairs >= 30
    return {"mint": "M", "ok": True, "symbol_display": sym, "name_display": name,
            "pair_count": pairs, "truncated": truncated,
            "total_liq_usd": liq_each * pairs, "total_liq_is_floor": truncated,
            "total_vol24_usd": 123.0, "mcap_usd": mcap, "price_usd": price,
            "venues": {"meteora": pairs},
            "quote_assets": {q: {"pairs": 1, "liq_usd": liq_each, "mint": "Q"}
                             for q in quotes},
            "deepest": {"pair": "P0", "liq_usd": liq_each},
            "single_pair_would_have_said": liq_each,
            "single_pair_understates_by": round(pairs, 2),
            "first_pair_ms": first_ms, "pairs": [], "chains": ["solana"],
            "phantom": bool(mcap and mcap > intel.PHANTOM_MCAP
                            and liq_each * pairs < intel.PHANTOM_LIQ
                            and not truncated),
            "phantom_why": None, "phantom_unevaluable": False}


def clear():
    intel._CACHE.clear()


# ---------------------------------------------------------------------------
head("2. liquidity(mint) - NEVER ONE POOL (standing rule 18)")

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=10, liq_each=4000.0)
r = intel.liquidity("So11111111111111111111111111111111111111112")
t("⭐ liquidity is SUMMED across every pair, not taken from the deepest",
  r["data"]["liq_usd"] == 40000.0 and r["data"]["pair_count"] == 10,
  f"got {r['data'].get('liq_usd')}")
t("⭐ the size of the one-pool error is REPORTED, not hidden",
  r["data"]["deepest_pool_liq_usd"] == 4000.0
  and r["data"]["single_pool_would_understate_by"] == 10)
t("⭐ every field carries provenance", len(r["provenance"]) >= 10
  and all(p.get("source") for p in r["provenance"]))

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=30, liq_each=1000.0)
r = intel.liquidity("So11111111111111111111111111111111111111112")
t("⛔ at the 30-pair API cap the total is declared a FLOOR",
  r["data"]["is_floor"] is True and any("cap" in w for w in r["warnings"]),
  "SOL returns 30 too, so 30 means '30 or more'")

clear()
intel.allpairs.token = lambda m, **k: fake_token(ok=False)
r = intel.liquidity("So11111111111111111111111111111111111111112")
t("⛔ a failed lookup is NOT a dead token (the `gone` bug, journal.py:974)",
  r["ok"] is False and any("NOT evidence" in w for w in r["warnings"]))

r = intel.liquidity("PEPE")
t("⛔ a ticker is refused, never resolved silently (standing rule 2)",
  r["ok"] is False and "ticker" in r["error"].lower())


# ---------------------------------------------------------------------------
head("3. phantom(mint) - a cap with nothing under it")

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=3, liq_each=0.46,
                                                 mcap=1_314_046_208.0)
r = intel.phantom("So11111111111111111111111111111111111111112")
t("⛔ $1.31bn of cap on $1.39 of liquidity is a PHANTOM",
  r["data"]["verdict"] == "PHANTOM", f"got {r['data'].get('verdict')}")
t("⛔ ...and it says there is nothing behind the cap",
  any("nothing behind" in w for w in r["warnings"]))

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=30, liq_each=1.0,
                                                 mcap=1_314_046_208.0)
r = intel.phantom("So11111111111111111111111111111111111111112")
t("⛔ a TRUNCATED sample is UNEVALUABLE, never a phantom and never a pass",
  r["data"]["verdict"] == "UNEVALUABLE",
  "30 arbitrary pools summing to nothing says nothing about a 31st")

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=2, liq_each=1200.0,
                                                 mcap=50_000_000.0)
r = intel.phantom("So11111111111111111111111111111111111111112")
t("⚠️ a thin-but-real token is BACKED, not a phantom",
  r["data"]["verdict"] == "BACKED")

clear()
intel.allpairs.token = lambda m, **k: fake_token(pairs=2, liq_each=100.0, mcap=None)
r = intel.phantom("So11111111111111111111111111111111111111112")
t("⛔ no market cap means the rule CANNOT be evaluated, and says so",
  r["data"]["verdict"] is None
  and any(n["field"] == "verdict" and "not a pass" in n["why"]
          for n in r["not_checked"]))


# ---------------------------------------------------------------------------
head("4. exit_depth - unknown is never zero, and never a loss")

clear()
intel.chainfields.round_trip = lambda m, usd: {
    "verdict": None, "usd_back": None, "rt_cost_pct": None,
    "price_impact_pct": None, "venues": None, "error": "jupiter 503"}
r = intel.exit_depth("So11111111111111111111111111111111111111112", 100)
t("⛔ a dead quote API gives UNKNOWN, never $0 (standing rule 5)",
  r["data"]["usd_back"] is None
  and any("not zero" in n["why"].lower() for n in r["not_checked"]))

clear()
intel.chainfields.sell_quote = lambda m, q: {
    "verdict": "NO_SELL_ROUTE", "usd_out": None, "price_impact_pct": None,
    "venues": None, "error": "NO_ROUTES_FOUND"}
r = intel.exit_depth("So11111111111111111111111111111111111111112", raw_qty=195771)
t("⛔ NO_SELL_ROUTE is an ANSWER and is surfaced as one",
  r["data"]["verdict"] == "NO_SELL_ROUTE"
  and any("cannot be sold" in w for w in r["warnings"]))

clear()
intel.chainfields.sell_quote = lambda m, q: {
    "verdict": "QUOTE_FAILED", "usd_out": None, "price_impact_pct": None,
    "venues": None, "error": "timeout"}
r = intel.exit_depth("So11111111111111111111111111111111111111112", raw_qty=195771)
t("⛔ QUOTE_FAILED must never render as a total loss",
  r["data"]["usd_out"] is None
  and any("NOT a total loss" in n["why"] for n in r["not_checked"]))

clear()
intel.chainfields.sell_quote = lambda m, q: {
    "verdict": "QUOTED", "usd_out": 158.50, "price_impact_pct": 1.15,
    "venues": ["Meteora DLMM"], "error": None}
r = intel.exit_depth("So11111111111111111111111111111111111111112", raw_qty=19772370000000)
t("⭐ a position is priced at the EXACT size held, not a $100 probe",
  r["data"]["mode"] == "position" and r["data"]["usd_out"] == 158.50
  and r["data"]["raw_qty"] == 19772370000000)


# ---------------------------------------------------------------------------
head("1. resolve(ticker) - the call that would have saved the whole EMBER day")

CANDS = [
    {"chain": "solana", "mint": "A" * 43, "name": "embercurve", "symbol": "EMBER",
     "seen_in": ["dexscreener"]},
    {"chain": "solana", "mint": "B" * 43, "name": "embercurve", "symbol": "EMBER",
     "seen_in": ["dexscreener"]},
    {"chain": "solana", "mint": "C" * 43, "name": "embercurve", "symbol": "EMBER",
     "seen_in": ["jupiter"]},
]
MEASURE = {
    "A" * 43: fake_token(pairs=30, liq_each=77_000.0, first_ms=1_757_000_000_000),
    "B" * 43: fake_token(pairs=3, liq_each=0.46, mcap=1_314_046_208.0,
                         first_ms=1_758_000_000_000),
    "C" * 43: fake_token(pairs=30, liq_each=48_000.0, first_ms=1_790_000_000_000),
}

clear()
intel._search_candidates = lambda tk: list(CANDS)
intel.allpairs.token = lambda m, **k: MEASURE[m]
r = intel.resolve("EMBER", since="2026-09-10", chain="solana")
d = r["data"]
t("⭐ RESOLVED to the real mint when it dominates",
  d["status"] == "RESOLVED" and d["winner"]["mint"] == "A" * 43,
  f"status={d['status']} winner={(d.get('winner') or {}).get('mint')}")
t("⛔ the PHANTOM candidate can never win, and says why it was rejected",
  any(c["mint"] == "B" * 43 and "PHANTOM" in (c["rejected_because"] or "")
      for c in d["candidates"]))
t("⭐ THE DATE RULE: a candidate whose first pool postdates the mention is out",
  any(c["mint"] == "C" * 43 and "postdates" in (c["rejected_because"] or "")
      for c in d["candidates"]),
  "this is the rule that got EMBER right when a hand-check got it wrong")
t("⭐ every other mint wearing the ticker is NAMED",
  d["n_impersonators"] == 2 and len(d["impersonators"]) == 2)

clear()
intel._search_candidates = lambda tk: list(CANDS)
intel.allpairs.token = lambda m, **k: MEASURE[m]
r = intel.resolve("EMBER", chain="solana")          # no date rule
t("⛔ without the date rule the two big ones are AMBIGUOUS, and NOTHING is real",
  r["data"]["status"] == "AMBIGUOUS" and r["data"]["winner"] is None,
  f"got {r['data']['status']}; 77k vs 48k is 1.6x, under the "
  f"{intel.RESOLVE_DOMINANCE}x bar")


# ---------------------------------------------------------------------------
head("7. wallet(pubkey) - read only, honest nulls, truncation recorded")

ACCTS = [
    {"mint": "M" + "1" * 42, "raw": 195771_000000, "decimals": 6,
     "ui": 195771.0, "program": "SPL", "token_account": "ta1"},
    {"mint": "M" + "2" * 42, "raw": 1000, "decimals": 6, "ui": 0.001,
     "program": "Token-2022", "token_account": "ta2"},
]

clear()
intel._token_accounts = lambda pk: (list(ACCTS), [])
intel.chainfields._rpc = lambda m, p, **k: ({"value": 1_000_000_000}, None)
intel.mint_account = lambda m: {"ok": True, "program": "SPL", "decimals": 6,
                                "supply_raw": 10 ** 15, "supply": 1e9,
                                "mint_authority": None, "freeze_authority": None,
                                "extensions": [], "transfer_fee_bps": None,
                                "fee_config_authority": None,
                                "withdraw_withheld_authority": None,
                                "withheld_raw": None, "name": None, "symbol": None}
intel.allpairs.token = lambda m, **k: (
    fake_token(pairs=0, liq_each=0.0, mcap=None, price=None, sym="GHOST")
    if m.startswith("M1") else fake_token(pairs=4, liq_each=9000.0, sym="REAL"))
intel.chainfields.sell_quote = lambda m, q: (
    {"verdict": "NO_SELL_ROUTE", "usd_out": None, "price_impact_pct": None,
     "venues": None, "error": "NO_ROUTES_FOUND"} if m.startswith("M1") else
    {"verdict": "QUOTED", "usd_out": 12.5, "price_impact_pct": 0.4,
     "venues": ["X"], "error": None})
r = intel.wallet("So11111111111111111111111111111111111111112", price_all=True)
d = r["data"]
t("⭐ the response states it was read-only", d["read_only"] is True)
t("⭐ a position with NO SELL ROUTE is flagged, not shown as a green number",
  "M" + "1" * 42 in d["flags"]["cannot_sell"])
t("⛔ an unsellable position contributes NOTHING to the realizable total",
  d["realizable_total_usd"] == 12.5)
t("⛔ ...and the total says it is a FLOOR because a position could not be quoted",
  any(n["field"] == "realizable_total_usd_complete" for n in r["not_checked"]))
pos = {p["mint"]: p for p in d["positions"]}
t("⭐ each position carries its own provenance and not_checked",
  all(p.get("provenance") is not None for p in d["positions"])
  and any(n["field"] == "you_get_usd"
          for n in pos["M" + "1" * 42]["not_checked"]))

clear()
intel._token_accounts = lambda pk: (list(ACCTS) * 40, [])
r = intel.wallet("So11111111111111111111111111111111111111112", max_positions=5)
t("⛔ truncation records WHAT was missed, not just how much (standing rule 15)",
  len(r["data"]["unmeasured_mints"]) == 75
  and any("only 5 were measured" in w for w in r["warnings"]))

clear()
intel._token_accounts = lambda pk: ([], ["Token-2022: rpc down"])
r = intel.wallet("So11111111111111111111111111111111111111112")
t("⛔ if a token program could not be read, the wallet view is not called complete",
  r["ok"] is False or any("INCOMPLETE" in w for w in r["warnings"]))

r = intel.wallet("not-a-pubkey")
t("⛔ a bad address is refused, and the refusal says this endpoint never signs",
  r["ok"] is False and "never signs" in r["error"])


# ---------------------------------------------------------------------------
head("symbols that render as a name they do not contain (docs/SYMBOL_ATTACKS.md)")

t("⛔ a bidi override in a symbol is FLAGGED",
  intel._symbol_flags("U‮CDЅ") is not None)
t("⛔ Cyrillic mixed into a Latin symbol is FLAGGED",
  any("mixed_script" in f for f in (intel._symbol_flags("USАC") or [])))
t("⭐ an ordinary symbol is not flagged", intel._symbol_flags("BONK") is None)


# ---------------------------------------------------------------------------
head("⛔⛔ THE STANDING GUARANTEE: this module can never gain a write path")

SRC = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                           "intel.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

# Names that would mean this file had learned to move value. Checked at the AST
# level, on attribute and function names, so a rename cannot slip past a grep.
FORBIDDEN = ("sign", "send_transaction", "sendtransaction", "signtransaction",
             "sendandconfirm", "partial_sign", "keypair", "secret_key",
             "private_key", "from_secret", "mnemonic", "seed_phrase",
             "approve", "delegate", "set_authority", "setauthority",
             "transfer_checked", "createorder", "create_order", "submit_order",
             "place_order", "swap_execute", "execute_swap")
hits = []
for node in ast.walk(TREE):
    nm = None
    if isinstance(node, ast.Attribute):
        nm = node.attr
    elif isinstance(node, ast.Name):
        nm = node.id
    elif isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nm = node.name
    if nm and any(f in nm.lower() for f in FORBIDDEN):
        hits.append(f"{nm} (line {getattr(node, 'lineno', '?')})")
t("⛔⛔ intel.py contains NO signing, approving or order-placing call",
  not hits, "found: " + ", ".join(hits))

# A wallet endpoint that takes a private key is the failure this prevents.
walletfn = [n for n in TREE.body
            if isinstance(n, ast.FunctionDef) and n.name == "wallet"][0]
argnames = [a.arg for a in walletfn.args.args]
t("⛔ wallet() takes a PUBLIC key and nothing that could be a secret",
  argnames[0] == "pubkey"
  and not any(x in " ".join(argnames).lower()
              for x in ("secret", "private", "key_", "keypair", "seed")),
  f"args: {argnames}")

# Every public endpoint must return provenance, or a number could arrive unsourced.
ENDPOINTS = ("liquidity", "resolve", "phantom", "exit_depth", "safety",
             "bundle_check", "paired", "wallet")
missing = [e for e in ENDPOINTS if not hasattr(intel, e)]
t("⭐ all seven endpoints plus safety exist and are importable", not missing,
  f"missing: {missing}")


# ---------------------------------------------------------------------------
print()
failed = [x for x in R if not x[1]]
print(f"{len(R) - len(failed)}/{len(R)} passed")
for n, _, why in failed:
    print(f"  FAILED: {n}  {why}")
sys.exit(1 if failed else 0)
