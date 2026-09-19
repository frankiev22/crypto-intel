"""The safety verdict is the pre-committed one, unknown never passes, and nothing is hidden.
Run: python test_safety.py      (offline: the network is faked)
"""
import json
import os
import re
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
testsandbox.activate()
import safety as S

R = []
NOW = 1_790_000_000


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


section("1. ⛔ the code carries the numbers the pre-commit fixed")
doc = open(os.path.join(os.path.dirname(S.__file__), "PRECOMMIT_safety_v1.md"), encoding="utf-8").read()
check("S4 fee: DANGER at >= 10%", "transfer fee ≥ 10%" in doc and S.FEE_DANGER_BPS == 1000)
check("S7: cap_backing_pct < 1", "`cap_backing_pct < 1`" in doc and S.CAP_BACKING_WARN_PCT == 1.0)
check("S8: top holders > 50%, fewer than 100 holders",
      "top holders > 50%" in doc and "fewer than 100 holders" in doc
      and S.TOP_HOLDERS_WARN_PCT == 50.0 and S.MIN_HOLDERS_WARN == 100)
check("S11: LP locked < 50%", "LP locked < 50%" in doc and S.LP_LOCKED_WARN_PCT == 50.0)
check("S1: TOTAL_LOSS and NO_SELL_ROUTE are DANGER, COSTLY is WARN",
      S.SELL_DANGER == ("TOTAL_LOSS", "NO_SELL_ROUTE") and S.SELL_WARN == ("COSTLY",))
check("the amendment that changed the class names is IN the file, declared",
      "Amendment v1.1" in doc and S.ISSUER_CLASSES == ("base", "stock") and S.RULE_VERSION == "v1.1")


section("2. the mint account, parsed from chain")


def mint_acct(program="spl-token-2022", mint_auth=None, freeze=None, exts=()):
    return {"data": {"program": program, "parsed": {"type": "mint", "info": {
        "decimals": 6, "supply": "1000", "mintAuthority": mint_auth, "freezeAuthority": freeze,
        "extensions": list(exts)}}}}


f = S.parse_mint(mint_acct(exts=[
    {"extension": "permanentDelegate", "state": {"delegate": "Del1"}},
    {"extension": "transferFeeConfig", "state": {"olderTransferFee": {"transferFeeBasisPoints": 100},
                                                 "newerTransferFee": {"transferFeeBasisPoints": 300}}},
    {"extension": "transferHook", "state": {"programId": None}},
    {"extension": "defaultAccountState", "state": {"accountState": "frozen"}},
    {"extension": "pausableConfig", "state": {"paused": True}}]))
check("a live permanent delegate is recorded", f["permanent_delegate"] == "Del1")
check("the transfer fee is the HIGHER of the two epochs (300 bps)", f["transfer_fee_bps"] == 300)
check("a transfer hook with no program is NOT live", f["transfer_hook_program"] is None)
check("default-frozen, pausable and paused are read", f["default_state_frozen"] and f["pausable"] and f["paused"])
check("an account that is not parsed is None - unknown, never clean", S.parse_mint({"data": ["x", "base64"]}) is None
      and S.parse_mint(None) is None)
dead = S.parse_mint(mint_acct(exts=[{"extension": "permanentDelegate", "state": {"delegate": None}}]))
check("a permanent-delegate extension with no delegate set cannot be used", dead["permanent_delegate"] is None)


section("3. ⛔ the verdict, check by check")


def entry(verdict="TRADEABLE", cls="token", chain=None, dex=None, rc=None, gate_age_h=1,
          top=20.0, holders=5000, cb=5.0, sources=("jupiter.verified",), ticker=1):
    e = {"status": "member", "class": cls, "sources": list(sources), "ticker_contracts": ticker,
         "gate": {"verdict": verdict, "rt_cost_pct": 0.4, "ts": NOW - gate_age_h * 3600} if verdict else {},
         "last": {"top_holders_pct": top, "holders": holders, "cap_backing_pct": cb}}
    if chain is not None:
        e["chain"] = {"facts": chain, "ts": NOW}
    if dex is not None:
        e["dex"] = {"facts": dex, "ts": NOW}
    if rc is not None:
        e["rugcheck"] = {"facts": rc, "ts": NOW}
    return e


CLEAN_CHAIN = {"program": "spl-token", "mint_authority": None, "freeze_authority": None, "extensions": [],
               "transfer_fee_bps": None, "permanent_delegate": None, "transfer_hook_program": None,
               "default_state_frozen": False, "non_transferable": False, "pausable": False, "paused": False}
CLEAN_DEX = {"liq": 500_000.0, "fdv": 20_000_000.0, "buys_h1": 300, "sells_h1": 280, "txns_h1": 580}
CLEAN_RC = {"rugged": False, "risks": [], "insider_networks": [], "lp_locked_pct": 100}
lv = lambda e: S.verdict(e, NOW)["level"]

ok = S.verdict(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, rc=CLEAN_RC), NOW)
check("everything clean -> NO FLAGS", ok["level"] == "NO FLAGS", ok["reasons"])
check("⛔ ...and it still lists what was NOT checked: fake volume and bundles, in words",
      any("fake volume" in x for x in ok["not_checked"]) and any("bundles" in x for x in ok["not_checked"]))
check("⛔ the word 'safe' appears nowhere in a verdict (the rule's filename aside)",
      not re.search(r"\bsafe\b", json.dumps(ok).lower()))
check("S1 TOTAL_LOSS -> DANGER", lv(entry("TOTAL_LOSS", chain=CLEAN_CHAIN)) == "DANGER")
check("S1 NO_SELL_ROUTE -> DANGER", lv(entry("NO_SELL_ROUTE", chain=CLEAN_CHAIN)) == "DANGER")
check("S1 COSTLY -> WARN", lv(entry("COSTLY", chain=CLEAN_CHAIN, dex=CLEAN_DEX)) == "WARN")
check("⛔ S1 never quoted -> UNKNOWN, never NO FLAGS", lv(entry(None, chain=CLEAN_CHAIN, dex=CLEAN_DEX)) == "UNKNOWN")
check("S1 a TRADEABLE checked 49h ago -> WARN (stale)", lv(entry(gate_age_h=49, chain=CLEAN_CHAIN, dex=CLEAN_DEX)) == "WARN")
check("DANGER outranks UNKNOWN", lv(entry(None, chain=dict(CLEAN_CHAIN, freeze_authority="F"))) == "DANGER")
check("S2 freeze authority on a token -> DANGER", lv(entry(chain=dict(CLEAN_CHAIN, freeze_authority="F"))) == "DANGER")
b = S.verdict(entry(cls="base", chain=dict(CLEAN_CHAIN, freeze_authority="F"), dex=CLEAN_DEX), NOW)
check("S2 freeze authority on a base asset -> info, said to be by design, not DANGER",
      b["level"] == "NO FLAGS" and "by design" in b["checks"]["S2"]["detail"], b["checks"]["S2"])
check("S3 mint authority on a token -> WARN", lv(entry(chain=dict(CLEAN_CHAIN, mint_authority="M"), dex=CLEAN_DEX)) == "WARN")
check("S4 permanent delegate on a TOKEN -> DANGER", lv(entry(chain=dict(CLEAN_CHAIN, permanent_delegate="D"))) == "DANGER")
st = S.verdict(entry(cls="stock", chain=dict(CLEAN_CHAIN, permanent_delegate="D", pausable=True), dex=CLEAN_DEX), NOW)
check("S4 permanent delegate on a STOCK -> info, 'issuer-controlled by design' (v1.1)",
      st["level"] == "NO FLAGS" and "by design" in st["checks"]["S4"]["detail"], st["checks"]["S4"])
check("S4 fee 10% -> DANGER, 3% -> WARN",
      lv(entry(chain=dict(CLEAN_CHAIN, transfer_fee_bps=1000))) == "DANGER"
      and lv(entry(chain=dict(CLEAN_CHAIN, transfer_fee_bps=300), dex=CLEAN_DEX)) == "WARN")
check("S4 a live transfer hook -> WARN", lv(entry(chain=dict(CLEAN_CHAIN, transfer_hook_program="H"), dex=CLEAN_DEX)) == "WARN")
check("S4 non-transferable -> DANGER whatever the class",
      lv(entry(cls="stock", chain=dict(CLEAN_CHAIN, non_transferable=True))) == "DANGER")
d1 = dict(CLEAN_DEX, liq=990_000.0, fdv=1_000_000.0, buys_h1=12, sells_h1=0, txns_h1=12)
check("⭐ S5 D1 fires (pool ~ supply, 12 buys, 0 sells) -> DANGER", lv(entry(chain=CLEAN_CHAIN, dex=d1)) == "DANGER")
d2 = dict(CLEAN_DEX, liq=2_000_000.0, buys_h1=2, sells_h1=1, txns_h1=3)
v2 = S.verdict(entry(chain=CLEAN_CHAIN, dex=d2, rc=CLEAN_RC), NOW)
check("⛔ S6 D2 fires but is unvalidated: shown as info, the level is untouched",
      "S6" in v2["checks"] and v2["checks"]["S6"]["level"] == "info" and v2["level"] == "NO FLAGS")
farm = S.verdict(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, cb=0.2, sources=("graduation",), ticker=6), NOW)
check("S7 the farm signature -> WARN, 'likely fiction'", farm["level"] == "WARN" and "fiction" in farm["checks"]["S7"]["detail"])
check("S7 low backing WITHOUT the farm signature -> info only",
      lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, cb=0.2)) == "NO FLAGS")
check("S8 top holders 51% -> WARN; 99 holders -> WARN",
      lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, top=51.0)) == "WARN"
      and lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, holders=99)) == "WARN")
check("S9 RugCheck rugged -> DANGER", lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, rc=dict(CLEAN_RC, rugged=True))) == "DANGER")
check("S9 a RugCheck danger-level risk -> WARN, attributed",
      "RugCheck:" in " ".join(S.verdict(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX,
                                               rc=dict(CLEAN_RC, risks=[{"name": "Copycat token", "level": "danger"}])), NOW)["reasons"]))
big = dict(CLEAN_RC, insider_networks=[{"size": 35335, "type": "transfer", "pct_supply": 98.0}])
check("⛔ v1.1: an insider network 'holding 98%' changes NOTHING (BONK reads that)",
      lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, rc=big)) == "NO FLAGS")
check("S11 LP 20% locked -> WARN", lv(entry(chain=CLEAN_CHAIN, dex=CLEAN_DEX, rc=dict(CLEAN_RC, lp_locked_pct=20))) == "WARN")
# ⛔ 2026-09-19 (site session, defect A): reasons sorted as strings put "S11" (a
# warn) ahead of "S2" (a danger), and a page shows only the first few.
_mix = S.verdict(entry(chain=dict(CLEAN_CHAIN, freeze_authority="X"), dex=CLEAN_DEX,
                       rc=dict(CLEAN_RC, lp_locked_pct=20), top=80.0), NOW)["reasons"]
check("⛔ reasons: every DANGER before any WARN",
      _mix and _mix[0].startswith("S2:") and all(not r.startswith("S2:") for r in _mix[1:]), _mix)
_ids = [int(r.split(":")[0][1:]) for r in _mix[1:]]
check("...and warns in check NUMBER order (S8 before S11, not string order)", _ids == sorted(_ids), _mix)
unk = S.verdict(entry(), NOW)
check("⛔ no chain, no pair, no RugCheck read: each is LISTED as not checked, none passes",
      len([x for x in unk["not_checked"] if any(w in x for w in ("mint account", "D1", "RugCheck"))]) == 3
      and not any(k in unk["checks"] for k in ("S2", "S3", "S4", "S5", "S9")), unk["not_checked"])


section("4. refresh: fetch what is due, count what did not fit, never go blank")
calls = []


def fake_http(url, body=None, timeout=20):
    calls.append(url.split("?")[0][:40])
    if body is not None:                       # getMultipleAccounts
        if FAIL_CHAIN:
            return 429, None
        return 200, {"result": {"value": [mint_acct("spl-token") for _ in body["params"][0]]}}
    if "dexscreener" in url:
        ms = url.rsplit("/", 1)[1].split(",")
        return 200, [{"chainId": "solana", "baseToken": {"address": m}, "pairAddress": "P" + m[:4], "dexId": "x",
                      "liquidity": {"usd": 1000.0 * (i + 1)}, "fdv": 5e6, "txns": {"h1": {"buys": 5, "sells": 4}}}
                     for i, m in enumerate(ms[:-1])]            # the LAST mint gets no pair
    if "rugcheck" in url:
        return 200, {"rugged": False, "risks": [], "markets": [], "token": {"supply": 1, "decimals": 6}}
    return 404, None


S._http = fake_http
S.RUGCHECK_GAP_S = 0
FAIL_CHAIN = True
toks = {f"M{i:03d}" + "x" * 40: dict(entry(), trending=[]) for i in range(5)}
toks["GONE" + "x" * 40] = {"status": "gone"}
st = S.refresh(toks, NOW, budget_s=60, rugcheck_budget_s=0)
tracked = [m for m, e in toks.items() if e.get("status") != "gone"]
check("every tracked token has a verdict, the untracked one does not",
      all("safety" in toks[m] for m in tracked) and "safety" not in toks["GONE" + "x" * 40])
check("⛔ a failed chain read leaves facts None with ts 0 - retried next pass, never 'clean'",
      all(toks[m]["chain"] == {"facts": None, "ts": 0} for m in tracked) and st["chain_read"] == 0)
check("the Dexscreener reply lacking one token leaves THAT one None, not zeros",
      sum(1 for m in tracked if toks[m]["dex"]["facts"] is None) == 1 and st["dex_read"] == 4)
check("⛔ RugCheck that did not fit is COUNTED as deferred (rule 15)",
      st["rugcheck_deferred"] == 5 and st["rugcheck_read"] == 0, st)
FAIL_CHAIN = False
st2 = S.refresh(toks, NOW + 60, budget_s=60, rugcheck_budget_s=60)
check("next pass: the failed chain read is retried and lands", st2["chain_read"] == 5 and st2["rugcheck_read"] == 5)
st3 = S.refresh(toks, NOW + 120, budget_s=60, rugcheck_budget_s=60)
check("...and is NOT refetched inside 24h (chain and RugCheck are daily)",
      st3["chain_due"] == 0 and st3["rugcheck_due"] == 0, st3)
check("levels are counted over the tracked tokens", sum(st3["levels"].values()) == 5, st3["levels"])

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
