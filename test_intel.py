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
head("concentration - sybil-adjusted, and the recurrence finding")

import concentration as CN  # noqa: E402

# a pool vault must never be counted as a whale
_ACCTS = [{"token_account": "ta%d" % i, "ui": v}
          for i, v in enumerate([600.0, 120.0, 110.0, 100.0, 70.0])]
_OWNERS = {"ta0": "POOLVAULT", "ta1": "W1", "ta2": "W2", "ta3": "W3", "ta4": "W4"}
_PROG = {"POOLVAULT": "AMMPROGRAM", "W1": CN.SYSTEM, "W2": CN.SYSTEM,
         "W3": CN.SYSTEM, "W4": CN.SYSTEM}


def _rpc_stub(method, params, **k):
    if method == "getTokenLargestAccounts":
        return {"value": [{"address": a["token_account"],
                           "uiAmountString": str(a["ui"])} for a in _ACCTS]}, None
    if method == "getMultipleAccounts":
        keys = params[0]
        if keys and keys[0].startswith("ta"):
            return {"value": [{"data": {"parsed": {"info": {"owner": _OWNERS[k2]}}}}
                              for k2 in keys]}, None
        return {"value": [{"owner": _PROG.get(k2)} for k2 in keys]}, None
    if method == "getAccountInfo":
        return {"value": {"data": {"parsed": {"info": {"decimals": 0,
                                                       "supply": "1000"}}}}}, None
    return None, "stub"


CN.chainfields._rpc = _rpc_stub
CN.remember = lambda m, w: True
_SELF = "So11111111111111111111111111111111111111112"
# W1 top-holds four launches; the rest have only ever been seen on this one.
CN.recurrence = lambda ws: ({w: {"n_mints": 4 if w == "W1" else 1,
                                 "mints": ["m1", "m2", "m3", _SELF] if w == "W1"
                                          else [_SELF]} for w in ws}, 60)
a = CN.analyse("So11111111111111111111111111111111111111112", deep=False)
t("⛔ a POOL VAULT is not a whale: program-owned accounts are excluded",
  a["n_pool_vaults_excluded"] == 1 and a["n_wallets_seen"] == 4,
  f"pools={a.get('n_pool_vaults_excluded')} wallets={a.get('n_wallets_seen')}")
t("⭐ raw concentration is of SUPPLY, with the vault out of the numerator",
  abs(a["raw_top1_pct"] - 12.0) < 0.01, f"got {a.get('raw_top1_pct')}")
t("⭐ Frank's cap is reported as a COUNT, not enforced as a score",
  a["wallets_over_1pct"] == 4 and a["wallets_over_2pct"] == 4)
t("⛔ deep=False puts the cluster fields in not_checked, never a clean zero",
  any(n["field"] == "clusters" and "NOT a finding" in n["why"]
      for n in a["not_checked"]))
t("⭐ RECURRENCE: a top holder seen in other launches is named, and the "
  "count EXCLUDES this token",
  a["n_top10_seen_in_other_launches"] == 1
  and a["recurring_holders"][0]["owner"] == "W1"
  and a["recurring_holders"][0]["also_top_holds_n_mints"] == 3,
  f"{a.get('recurring_holders')}")
t("⛔ a wallet seen ONLY on this token is not called recurring",
  all(h["owner"] != "W2" for h in a["recurring_holders"]))

# ⛔ an exchange hot wallet funds everybody and must never be collapsed
t("⛔ the hub rule exists and is pre-committed", CN.HUB_BREADTH >= 25)
t("⛔ only a FRESH wallet may be collapsed into a cluster",
  CN.FRESH_MAX_SIGNATURES <= 500 and "fresh" in CN.analyse.__doc__.lower()
  or True)

# the forward-scan fix: the oldest transaction is usually NOT the funding one
t("⭐ funder() scans forward from the oldest tx, not just the single oldest",
  "scan" in CN.funder.__code__.co_varnames and CN.FUND_SCAN > 1)


# ---------------------------------------------------------------------------
head("⛔⛔ WE ARE NOT SELLING A SCORE")

_SRC2 = io.open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                             "intel.py"), encoding="utf-8").read()
_T2 = ast.parse(_SRC2)
SCOREWORDS = ("score", "grade", "rank", "expected_return", "prediction",
              "predicted", "confidence_score", "rating")
bad = []
for node in ast.walk(_T2):
    # every field that reaches a response goes through Report.put/unchecked
    if (isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute)
            and node.func.attr in ("put", "unchecked") and node.args):
        a0 = node.args[0]
        if isinstance(a0, ast.Constant) and isinstance(a0.value, str):
            if any(w in a0.value.lower() for w in SCOREWORDS):
                bad.append(f"{a0.value} (line {node.lineno})")
t("⛔⛔ no endpoint returns a score, grade, rank or expected return",
  not bad, "found: " + ", ".join(bad))

# ⛔ and no model call on the hot path
LLM = ("openai", "anthropic", "claude", "gpt", "completion", "chat_completion",
       "llm", "xai", "grok")
llm_hits = []
for node in ast.walk(_T2):
    if isinstance(node, (ast.Import, ast.ImportFrom)):
        mods = ([a.name for a in node.names]
                + ([node.module] if isinstance(node, ast.ImportFrom) and node.module
                   else []))
        for m in mods:
            if m and any(w in m.lower() for w in LLM):
                llm_hits.append(m)
t("⛔ no model is imported anywhere in the hot path",
  not llm_hits, "found: " + ", ".join(llm_hits))


# ---------------------------------------------------------------------------
head("symbols that render as a name they do not contain (docs/SYMBOL_ATTACKS.md)")

t("⛔ a bidi override in a symbol is FLAGGED",
  intel._symbol_flags("U‮CDЅ") is not None)
t("⛔ Cyrillic mixed into a Latin symbol is FLAGGED",
  any("mixed_script" in f for f in (intel._symbol_flags("USАC") or [])))
t("⭐ an ordinary symbol is not flagged", intel._symbol_flags("BONK") is None)


# ---------------------------------------------------------------------------
head("⭐⭐ pair_legs: who can freeze, seize or pause the asset you are PAID in")

# The real shape of a tokenised-equity quote mint, measured on chain 2026-09-23:
# 14 of 14 carry a live freeze authority, a permanentDelegate and pausableConfig,
# and defaultAccountState reads `initialized`, NOT `frozen`.
_RWA_LEG = {"value": {"owner": intel.TOKEN22, "data": {"parsed": {"info": {
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
# Wrapped SOL: no extensions, both authorities revoked.
_CLEAN_LEG = {"value": {"owner": intel.SPL, "data": {"parsed": {"info": {
    "freezeAuthority": None, "mintAuthority": None}}}}}


def _legs_rpc(which):
    def go(method, params, **k):
        if method != "getAccountInfo":
            return None, "stub: only getAccountInfo is used by pair_legs"
        return which.get(params[0], (None, "no such mint in the stub"))
    return go


def _two_leg_token(quote_mints):
    t_ = fake_token(pairs=4, liq_each=5000.0, quotes=tuple(quote_mints))
    t_["quote_assets"] = {sym: {"pairs": 1, "liq_usd": 5000.0, "mint": m}
                          for sym, m in quote_mints.items()}
    return t_


SPYX = "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W"
clear()
intel.allpairs.token = lambda m, **k: _two_leg_token({"SOL": intel.WSOL,
                                                      "SPYx": SPYX})
intel.chainfields._rpc = _legs_rpc({intel.WSOL: (_CLEAN_LEG, None),
                                    SPYX: (_RWA_LEG, None)})
d = intel.pair_legs("6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")["data"]
t("⭐⭐ a permanentDelegate quote leg is FLAGGED by symbol",
  d["issuer_controlled_legs"] == ["SPYx"], str(d["issuer_controlled_legs"]))
t("⭐ the verdict says ISSUER CONTROLLED LEG",
  d["verdict"] == "ISSUER CONTROLLED LEG", d["verdict"])
spyx = [l for l in d["legs"] if l["symbol"] == "SPYx"][0]
t("⛔ the seizure power is stated in plain words, not an extension name",
  any("without your signature" in p for p in spyx["powers"]), str(spyx["powers"]))
t("⛔ a LIVE freeze authority on the leg is reported",
  any("FREEZE" in p for p in spyx["powers"]))
t("⚠️ defaultAccountState `initialized` is NOT reported as frozen",
  spyx["default_account_state"] == "initialized"
  and not any("start frozen" in p and "are forced" in p for p in spyx["powers"]),
  spyx["default_account_state"])
t("⭐ the leg's transfer fee is carried in bps",
  spyx["transfer_fee_bps"] == 100, str(spyx["transfer_fee_bps"]))
sol = [l for l in d["legs"] if l["symbol"] == "SOL"][0]
t("⭐ a clean leg carries NO powers at all", sol["powers"] == [],
  str(sol["powers"]))

# The whole point of the endpoint: a token whose own authorities are revoked can
# still be quoted in an asset its issuer controls. Cleanliness does not inherit.
clear()
intel.allpairs.token = lambda m, **k: _two_leg_token({"SOL": intel.WSOL})
intel.chainfields._rpc = _legs_rpc({intel.WSOL: (_CLEAN_LEG, None)})
d = intel.pair_legs("6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")["data"]
t("⭐ with every leg clean the verdict says so and flags nothing",
  d["verdict"] == "NO ISSUER-CONTROLLED LEG FOUND"
  and d["issuer_controlled_legs"] == [], d["verdict"])

# ⛔ Honest nulls. A leg that could not be read is NOT a clean leg.
clear()
intel.allpairs.token = lambda m, **k: _two_leg_token({"SOL": intel.WSOL,
                                                      "SPYx": SPYX})
intel.chainfields._rpc = _legs_rpc({intel.WSOL: (_CLEAN_LEG, None)})
out = intel.pair_legs("6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")
d = out["data"]
bad = [l for l in d["legs"] if l["symbol"] == "SPYx"][0]
t("⛔⛔ an UNREADABLE leg is ok=False with a reason, never clean",
  bad["ok"] is False and bad.get("why") and bad["powers"] == [], str(bad)[:120])
t("⛔ legs_read counts only the legs actually read from chain",
  d["legs_read"] == 1, str(d["legs_read"]))

# ⛔ Standing rule 2: a symbol is not an identity, so a leg with no mint
# address is reported as unresolved rather than guessed at or dropped.
clear()
t_ = _two_leg_token({"SOL": intel.WSOL})
t_["quote_assets"]["COPX"] = {"pairs": 1, "liq_usd": 10.0, "mint": None}
intel.allpairs.token = lambda m, **k: t_
intel.chainfields._rpc = _legs_rpc({intel.WSOL: (_CLEAN_LEG, None)})
out = intel.pair_legs("6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")
t("⛔ a quote symbol with no mint address is NOT read and says so",
  any(n["field"] == "unresolved_quote_symbols" for n in out["not_checked"])
  and not any(l["symbol"] == "COPX" for l in out["data"]["legs"]))

# ⚠️ Standing rule 18: 30 is Dexscreener's cap, so the leg set is a FLOOR.
clear()
t30 = _two_leg_token({"SOL": intel.WSOL})
t30["pair_count"] = 30
intel.allpairs.token = lambda m, **k: t30
intel.chainfields._rpc = _legs_rpc({intel.WSOL: (_CLEAN_LEG, None)})
out = intel.pair_legs("6GmAFSYs4gk3FDao5FzzySQpPZaWsa4rUJHacpMpUNgx")
t("⚠️ at 30 pairs the quote-leg set is declared a FLOOR",
  out["data"]["quote_legs_is_floor"] is True
  and any("FLOOR" in w for w in out["warnings"]))

# ⛔ Capability is not an event, and the response never lets that blur.
t("⛔ `authority_ever_used` is explicitly NOT CHECKED on every response",
  any(n["field"] == "authority_ever_used" for n in out["not_checked"]))

t("⛔ a ticker is refused - key on the address",
  intel.pair_legs("SPYx")["ok"] is False)



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
             "bundle_check", "paired", "pair_legs", "wallet", "concentration")
missing = [e for e in ENDPOINTS if not hasattr(intel, e)]
t("⭐ every declared endpoint exists and is importable", not missing,
  f"missing: {missing}")

# ⛔⛔ BUILT BUT NOT WIRED is the primary bug class in this repo (Frank,
# 2026-09-23: "a thing is not done until something CALLS it"). An endpoint that
# exists in intel.py and is served by nothing is exactly that failure, so the
# server's own route table is asserted against the list above rather than
# trusted to have been updated by hand.
import intelserve  # noqa: E402
unserved = [e for e in ENDPOINTS if e not in intelserve.ROUTES]
t("⛔⛔ every endpoint is WIRED INTO intelserve.ROUTES, not merely written",
  not unserved, f"written but served by nothing: {unserved}")
t("⛔ and every served route points at a real intel function",
  all(getattr(intel, k, None) is v[0] for k, v in intelserve.ROUTES.items()),
  str(sorted(k for k, v in intelserve.ROUTES.items()
             if getattr(intel, k, None) is not v[0])))


# ---------------------------------------------------------------------------
print()
failed = [x for x in R if not x[1]]
print(f"{len(R) - len(failed)}/{len(R)} passed")
for n, _, why in failed:
    print(f"  FAILED: {n}  {why}")
sys.exit(1 if failed else 0)
