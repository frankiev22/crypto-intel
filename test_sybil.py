"""The stacked-signal coordination detector. Run: python test_sybil.py

⛔ WHAT THIS SUITE IS REALLY GUARDING. The sybil framing already FAILED once on
this population: measured 2026-09-23, top holders of fresh pump.fun graduates are
not fresh wallets, every one carried 3,000+ signatures, and 0 of the top 10 of
two tested graduates was fresh. Collapsing those by shared funder would have
manufactured clusters out of ordinary market participants.

So the assertions below are mostly about RESTRAINT: that a defeated signal cannot
carry a verdict, that a thin sample is not a clean token, that an unknown wallet
age is neither fresh nor established, and that the module can say "these are all
established traders" out loud.
"""
import ast
import io
import json
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

import testsandbox
testsandbox.activate()

import sybil as S

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


def buys(spec):
    """spec: [(wallet, slot, ts)] -> buy rows."""
    return [{"wallet": w, "slot": sl, "ts": ts, "amount": 1.0,
             "signature": "sig_" + w} for w, sl, ts in spec]


# ---------------------------------------------------------------------------
section("1. S1, same-slot co-buying: the signal hardest to defeat")

b = buys([("w1", 100, 10), ("w2", 100, 10), ("w3", 100, 10),
          ("w4", 200, 20), ("w5", 300, 30)])
s1 = S.s1_same_slot(b)
check("⭐ three wallets in one slot FIRES S1", s1["fired"], json.dumps(s1)[:120])
check("⭐ the group size is reported", s1["max_group"] == 3, str(s1["max_group"]))
check("⭐ the co-buy share is reported", s1["co_buy_share"] == 0.6,
      str(s1["co_buy_share"]))
check("⭐ and the grouped wallets are NAMED, not just counted",
      "w1" in json.dumps(s1["groups"]))

s1b = S.s1_same_slot(buys([("w1", 100, 10), ("w2", 100, 10),
                           ("w3", 200, 20), ("w4", 200, 20)]))
check("⭐ two groups of two also fires", s1b["fired"] and s1b["n_groups"] == 2)

s1c = S.s1_same_slot(buys([("w1", 100, 10), ("w2", 200, 20), ("w3", 300, 30)]))
check("⛔ wallets in different slots do NOT fire", not s1c["fired"])
check("⛔ ...and it still reports its measurement when it did not fire",
      s1c["co_buy_share"] == 0.0 and s1c["max_group"] == 0, json.dumps(s1c)[:140])

# ⛔ PRECOMMIT section 7: a pump.fun graduation migrates in ONE transaction, so
# the migration slot is not a co-buy. Excluded by slot, never explained away.
s1d = S.s1_same_slot(buys([("w1", 100, 10), ("w2", 100, 10), ("w3", 100, 10)]),
                     migration_slots=(100,))
check("⛔⛔ the MIGRATION slot is excluded, so a migration is not a co-buy",
      not s1d["fired"] and s1d["max_group"] == 0, json.dumps(s1d)[:140])
check("⭐ and the exclusion is recorded on the row",
      s1d["migration_slots_excluded"] == [100])


# ---------------------------------------------------------------------------
section("2. S2, wallet age: unknown is neither fresh nor established")

b4 = buys([("w1", 1, 1), ("w2", 2, 2), ("w3", 3, 3), ("w4", 4, 4)])
s2 = S.s2_wallet_age(b4, age_fn=lambda w, sig: {"had_prior": w in ("w3", "w4")})
check("⭐ wallets with no prior activity are FRESH",
      s2["n_fresh"] == 2 and set(s2["fresh"]) == {"w1", "w2"}, json.dumps(s2)[:150])
check("⭐ 50% fresh fires S2", s2["fired"] and s2["fresh_share"] == 0.5)

# ⛔ had_prior=None means the QUERY FAILED. It is not "brand new".
s2b = S.s2_wallet_age(b4, age_fn=lambda w, sig: {"had_prior": None})
check("⛔⛔ had_prior=None is UNKNOWN, never counted as fresh",
      s2b["n_fresh"] == 0 and s2b["n_age_unknown"] == 4
      and s2b["fresh_share"] is None, json.dumps(s2b)[:150])
check("⛔ ...and with nothing datable S2 cannot fire", not s2b["fired"])

s2c = S.s2_wallet_age(b4, age_fn=lambda w, sig: {"had_prior": True})
check("⭐ all-established does NOT fire", not s2c["fired"])
check("⭐⭐ and the module SAYS the negative out loud instead of leaving a zero",
      s2c["note"] and "NORM" in s2c["note"], str(s2c.get("note"))[:90])

s2d = S.s2_wallet_age(b4, age_fn=lambda w, sig: 1 / 0)
check("⛔ a raising age lookup counts as unknown, never as fresh",
      s2d["n_age_unknown"] == 4 and s2d["n_fresh"] == 0)


# ---------------------------------------------------------------------------
section("3. S3, exit correlation: the part that is hard to disguise")

bb = buys([("w%d" % i, i, i) for i in range(1, 7)])
sells = [{"wallet": "w1", "slot": 900, "ts": 5000, "amount": 1},
         {"wallet": "w2", "slot": 901, "ts": 5100, "amount": 1},
         {"wallet": "w3", "slot": 902, "ts": 5200, "amount": 1},
         {"wallet": "w4", "slot": 999, "ts": 90000, "amount": 1}]
s3 = S.s3_exit_correlation(bb, sells)
check("⭐ three wallets exiting inside the window FIRES S3", s3["fired"],
      json.dumps(s3)[:150])
check("⭐ the cluster size and its members are reported",
      s3["largest_exit_cluster"] == 3 and "w1" in s3["cluster_wallets"])
check("⛔ a wallet that never bought is not counted as an exit",
      S.s3_exit_correlation(bb, [{"wallet": "stranger", "ts": 5000,
                                  "slot": 1, "amount": 1}])["n_sellers"] == 0)
check("⛔ no sells at all does not fire and says so",
      S.s3_exit_correlation(bb, [])["n_sellers"] == 0
      and not S.s3_exit_correlation(bb, [])["fired"])

# ⛔⛔ THE PRECONDITION S3 WAS MISSING, and its own control exposed it: the
# first version scored exit_share 1.000 on all nine control mints, including
# mints with ONE seller, because flows() reads only a mint's first ~300
# signatures and every sell in that sample is inside 600s by construction.
# Standing rule 13: a sampler narrower than the thing measured cannot measure it.
narrow = [{"wallet": "w1", "ts": 100, "slot": 1, "amount": 1},
          {"wallet": "w2", "ts": 150, "slot": 2, "amount": 1},
          {"wallet": "w3", "ts": 200, "slot": 3, "amount": 1}]
s3n = S.s3_exit_correlation(bb, narrow)
check("⛔⛔ a sell sample NARROWER than the window is UNEVALUABLE, not clean",
      s3n["fired"] is None and s3n["unevaluable"] is True,
      json.dumps(s3n)[:160])
check("⛔ ...and it says the span it saw and why that is not a negative",
      s3n["observed_sell_span_s"] == 100
      and "BY CONSTRUCTION" in s3n["unevaluable_why"]
      and "NOT a clean negative" in s3n["unevaluable_why"])
check("⛔ one seller alone is unevaluable too",
      S.s3_exit_correlation(bb, narrow[:1])["fired"] is None)
check("⭐ a sample WIDER than the window is evaluated normally",
      S.s3_exit_correlation(bb, sells)["unevaluable"] is False
      and S.s3_exit_correlation(bb, sells)["fired"] is True)
check("⛔ an unevaluable S3 contributes NO points",
      S.level_from([s3n], 20, False)[1] == 0)


# ---------------------------------------------------------------------------
section("4. ⛔ S4 is DEMOTED: a defeated signal can never carry a verdict")

b5 = buys([("w%d" % i, i, i) for i in range(1, 6)])
s4 = S.s4_shared_funder(b5, funder_fn=lambda w: "HUB" if w != "w5" else "OTHER")
check("⭐ four buyers sharing one funder fires S4", s4["fired"],
      json.dumps(s4)[:140])
check("⭐ the hub is NAMED", "HUB" in s4["hubs"])

lvl, pts, why = S.level_from([s4], n_buyers=20, truncated=False)
check("⛔⛔ S4 ALONE is capped at WEAK however many wallets share the funder",
      lvl == S.WEAK, f"{lvl} / {pts}")
check("⛔ ...and the response says WHY it is capped",
      "defeated" in why, why)
# ⛔⛔ S1 WAS KILLED BY ITS OWN CONTROL on the day it was written: it fired on
# 9 of 9 ordinary graduations, co-buy share 0.625 to 0.933. A Solana slot is
# ~400ms and a launch is a frenzy, so sharing a slot is the BASE RATE. The
# pre-commit said the weight must go to 0 rather than be re-tuned.
check("⛔⛔ S1's weight is ZERO - killed by its own control, not re-tuned",
      S.WEIGHTS["S1_same_slot"] == 0, json.dumps(S.WEIGHTS))
check("⭐ S4 is the weakest signal that still carries any weight",
      S.WEIGHTS["S4_shared_funder"]
      == min(w for w in S.WEIGHTS.values() if w > 0), json.dumps(S.WEIGHTS))
check("⛔ the RESULT is recorded in the pre-commit, not just in the code",
      "S1 AS SPECIFIED IS DEAD" in io.open(
          os.path.join(HERE, "PRECOMMIT_sybil_v1.md"), encoding="utf-8").read())


# ---------------------------------------------------------------------------
section("5. the level, and the caps that bind before the points table")

fired = lambda n, w: {"signal": n, "fired": True, "weight": w}  # noqa: E731

check("⭐ nothing fired reads NONE OBSERVED",
      S.level_from([], 20, False)[0] == S.NONE)
check("⭐ S1 alone (3 points) is MODERATE",
      S.level_from([fired("S1_same_slot", 3)], 20, False)[0] == S.MODERATE)
check("⭐ S1 + S2 (5 points) is STRONG",
      S.level_from([fired("S1_same_slot", 3), fired("S2_wallet_age", 2)],
                   20, False)[0] == S.STRONG)
check("⭐ S2 alone (2 points) is WEAK",
      S.level_from([fired("S2_wallet_age", 2)], 20, False)[0] == S.WEAK)

lvl, _p, why = S.level_from([fired("S1_same_slot", 3)], n_buyers=5,
                            truncated=False)
check("⛔⛔ under 8 buyers the answer is INSUFFICIENT DATA, not a level",
      lvl == S.INSUFFICIENT, lvl)
check("⛔ ...and it says a thin sample is not a clean token",
      "thin sample is not a clean token" in why, why)

_l, _p, why_t = S.level_from([fired("S1_same_slot", 3)], 20, truncated=True)
check("⚠️ a TRUNCATED walk makes the answer a FLOOR, in words",
      "FLOOR" in why_t and "never absence" in why_t, why_t)


# ---------------------------------------------------------------------------
section("6. analyse(): what a whole run records, including what did NOT fire")

FLOW = {"ok": True, "truncated": False, "n_signatures_seen": 40,
        "buys": buys([("w1", 100, 10), ("w2", 100, 10), ("w3", 100, 10),
                      ("w4", 101, 11), ("w5", 102, 12), ("w6", 103, 13),
                      ("w7", 104, 14), ("w8", 105, 15), ("w9", 106, 16)]),
        "sells": []}
out = S.analyse("MintUnderTest1111111111111111111111111111",
                flows_fn=lambda m, **k: FLOW,
                age_fn=lambda w, sig: {"had_prior": True},
                funder_fn=lambda w: None)
# ⛔ S1 fires on this fixture (three wallets in slot 100) and S2/S3/S4 do not,
# so the level is NONE OBSERVED. That is the S1 result working: a signal that
# fires on every ordinary launch may no longer produce a verdict on its own.
check("⛔⛔ S1 firing ALONE no longer produces a level, and that is the point",
      out["level"] == S.NONE and out["points"] == 0,
      f"{out['level']} / {out['points']}")
check("⭐ ...but S1's measurement is still RECORDED for a future baseline",
      any(s["signal"] == "S1_same_slot" and s["fired"] is True
          and s["max_group"] == 3 for s in out["signals"]))
check("⛔⛔ EVERY signal is recorded, fired or not",
      len(out["signals"]) == 4
      and {s["signal"] for s in out["signals"]} == set(S.WEIGHTS),
      str([s["signal"] for s in out["signals"]]))
check("⛔ the non-firing signals carry their own measurements",
      any(s["signal"] == "S2_wallet_age" and s["fired"] is False
          and s["n_established"] == 9 for s in out["signals"]))
check("⭐ the run names the rule file it was judged against",
      out["rule"] == "PRECOMMIT_sybil_v1.md")
check("⛔ it states what it did NOT check",
      any("intent" in n for n in out["not_checked"]))
check("⛔⛔ and it states in words that it is not a prediction",
      "not a prediction" in out["never_claims"])

# ⛔ A skipped signal is SKIPPED, never "did not fire".
shallow = S.analyse("MintUnderTest1111111111111111111111111111",
                    flows_fn=lambda m, **k: FLOW, deep=False)
skipped = [s for s in shallow["signals"] if s.get("skipped")]
check("⛔⛔ deep=False marks signals SKIPPED with fired=None, not False",
      len(skipped) == 3 and all(s["fired"] is None for s in skipped),
      json.dumps(skipped)[:140])
check("⛔ ...and says not checked is not clean",
      all("not clean" in s["why"] for s in skipped))

dead = S.analyse("MintUnderTest1111111111111111111111111111",
                 flows_fn=lambda m, **k: {"ok": False, "why": "rpc down"})
check("⛔ an unreadable mint is INSUFFICIENT DATA with the reason, not NONE",
      dead["level"] == S.INSUFFICIENT and "rpc down" in dead["why"], dead["why"])


# ---------------------------------------------------------------------------
section("7. the cluster-buy lane: an observation, NEVER a buy signal")

CB = {"ok": True, "truncated": False,
      "buys": buys([("known1", 1, 1000), ("known2", 2, 1200),
                    ("known3", 3, 1400), ("stranger", 4, 1500),
                    ("known4", 5, 99000)]),
      "sells": []}
c = S.cluster_buys("MintX", known={"known1", "known2", "known3", "known4"},
                   flows_fn=lambda m, **k: CB)
check("⭐ three registry wallets inside the window FIRES", c["fired"],
      json.dumps(c)[:150])
check("⭐ the cluster size excludes the one outside the window",
      c["largest_window_cluster"] == 3, str(c["largest_window_cluster"]))
check("⭐ the wallets are named", "known1" in c["wallets"])
check("⛔⛔ it states IN THE RESPONSE that it is not a buy signal",
      "NEVER a buy signal" in c["never_claims"])
check("⛔ ...and carries the measured reason why copying loses money",
      "6.0%" in c["never_claims"])
check("⚠️ combined size is explicitly NOT checked",
      any("not priced" in n for n in c["not_checked"]))

c2 = S.cluster_buys("MintX", known={"known1"}, flows_fn=lambda m, **k: CB)
check("⛔ one known wallet does not fire", not c2["fired"])


# ---------------------------------------------------------------------------
section("8. ⛔ the standing guarantees, at the AST level")

SRC = io.open(os.path.join(HERE, "sybil.py"), encoding="utf-8").read()
TREE = ast.parse(SRC)

bad = []
for n in ast.walk(TREE):
    nm = getattr(n, "attr", None) or getattr(n, "id", None)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nm = n.name
    if nm and any(w in nm.lower() for w in
                  ("score", "grade", "rank", "rating", "prediction",
                   "expected_return", "keypair", "sign_", "approve",
                   "set_authority", "send_transaction")):
        bad.append(f"{nm}:{getattr(n, 'lineno', '?')}")
check("⛔⛔ no score, grade or rank term, and no write path",
      not bad, ", ".join(bad))

PRE = io.open(os.path.join(HERE, "PRECOMMIT_sybil_v1.md"), encoding="utf-8").read()
# ⚠️ Markdown wraps and bolds, so a phrase can be split across lines by
# "**" and a newline. Normalise before asserting on wording, or the test fails on
# the formatting rather than on the content.
FLAT = re.sub(r"[\s*`]+", " ", PRE)
check("⭐ the pre-commit exists", bool(PRE))
for name, val in [("N_BUYERS", S.N_BUYERS),
                  ("MIN_BUYERS_TO_JUDGE", S.MIN_BUYERS_TO_JUDGE),
                  ("EXIT_WINDOW_S", S.EXIT_WINDOW_S),
                  ("CLUSTER_MIN_WALLETS", S.CLUSTER_MIN_WALLETS),
                  ("CLUSTER_WINDOW_S", S.CLUSTER_WINDOW_S)]:
    check(f"⛔ {name} = {val} matches the pre-commit",
          f"{name} = {val}" in PRE or f"`{name} = {val}`" in PRE
          or f"{name}` = {val}" in PRE or str(val) in PRE)
check("⛔ the pre-commit ranks the signals by how hard they are to DEFEAT",
      "hard to defeat" in PRE.lower())
check("⛔ it names what would make v1 WRONG before it ran",
      "WRONG" in FLAT.upper()
      and "migration slot is not a co-buy" in FLAT, FLAT[-400:])
check("⛔⛔ it forbids a binary verdict",
      "never a binary verdict" in FLAT.lower()
      and "no binary" in FLAT.lower(), "not found")

check("⛔ sybil.analysed is a DECLARED liveness component",
      "sybil.analysed" in __import__("liveness").COMPONENTS)
check("⛔ and it is beaten by literal name",
      any(isinstance(n, ast.Call)
          and getattr(n.func, "attr", None) == "beat"
          and n.args and isinstance(n.args[0], ast.Constant)
          and n.args[0].value == "sybil.analysed"
          for n in ast.walk(TREE)))


# ---------------------------------------------------------------------------
print()
failed = [n for n, ok_ in R if not ok_]
print(f"{len(R) - len(failed)}/{len(R)} passed")
for n in failed:
    print("  FAILED:", n)
sys.exit(1 if failed else 0)
