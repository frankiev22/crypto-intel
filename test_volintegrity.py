"""The volume rule is the pre-committed one, and no trades is never clean.
Run: python test_volintegrity.py      (offline)
"""
import os
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
testsandbox.activate()
import volintegrity as V

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


print("1. ⛔ the code carries the numbers the doc pre-committed")
doc = open(os.path.join(os.path.dirname(V.__file__), "docs", "VOLUME_INTEGRITY.md"), encoding="utf-8").read()
block = doc[doc.index("VOLUME_SUSPECT if"):doc.index("otherwise      VOLUME_UNKNOWN")]
nums = [float(x) for x in re.findall(r"(?:>=|<=|<)\s*([0-9.]+)", block)]
check("doc §3 thresholds == code constants, in order (0.50, 4, 0.25, 1)",
      nums == [V.SUSPECT_DUP, V.SUSPECT_SLOTS, V.CLEAN_DUP, V.CLEAN_SLOTS], nums)
check("the sample is the 60 transactions the doc measured on", V.SAMPLE == 60)

print("2. the verdict, at every boundary")
check("dup exactly 0.50 is SUSPECT", V.verdict(0.50, 0) == "VOLUME_SUSPECT")
check("4 multi-tx slots is SUSPECT whatever dup says", V.verdict(0.0, 4) == "VOLUME_SUSPECT")
check("dup 0.2499 and 1 slot is CLEAN", V.verdict(0.2499, 1) == "VOLUME_CLEAN")
check("dup exactly 0.25 is UNKNOWN - not clean", V.verdict(0.25, 0) == "VOLUME_UNKNOWN")
check("2 slots with clean dup is UNKNOWN", V.verdict(0.1, 2) == "VOLUME_UNKNOWN")
check("⛔ no dup reading can never be CLEAN", V.verdict(None, 0) == "VOLUME_UNKNOWN")
check("...but 4 slots still flags it SUSPECT", V.verdict(None, 5) == "VOLUME_SUSPECT")

print("3. M1/M2 from transactions")
M = "MintAAAA" + "1" * 36


def tx(slot, delta, mint=M):
    return {"slot": slot, "meta": {
        "preTokenBalances": [{"accountIndex": 1, "mint": mint, "uiTokenAmount": {"uiAmount": 1000.0}}],
        "postTokenBalances": [{"accountIndex": 1, "mint": mint, "uiTokenAmount": {"uiAmount": 1000.0 + delta}}]}}


bot = V.profile_from(M, [tx(i, 123.4567) for i in range(10)])
# The 09-17 code counts EVERY delta in a repeated-size group, the first
# included - so one size looped 10 times is 1.0, not 0.9. Kept as measured,
# because the thresholds were set against that computation.
check("a bot looping one size: dup_amount_share 1.0 (the 09-17 computation)",
      bot["dup_amount_share"] == 1.0 and bot["verdict"] == "VOLUME_SUSPECT", bot)
human = V.profile_from(M, [tx(i, 10.0 * (i + 1)) for i in range(10)])
check("distinct sizes: dup 0, one tx per slot -> CLEAN",
      human["dup_amount_share"] == 0 and human["multi_tx_slots"] == 0 and human["verdict"] == "VOLUME_CLEAN", human)
slotty = V.profile_from(M, [tx(i // 2, 10.0 * (i + 1)) for i in range(10)])
check("pairs in one slot: 5 multi-tx slots -> SUSPECT", slotty["multi_tx_slots"] == 5
      and slotty["verdict"] == "VOLUME_SUSPECT", slotty)
dead = V.profile_from(M, [])
check("⛔ a token with no transactions is UNKNOWN with None fields, never CLEAN",
      dead["verdict"] == "VOLUME_UNKNOWN" and dead["dup_amount_share"] is None
      and dead["multi_tx_slots"] is None, dead)
other = V.profile_from(M, [tx(i, 5.0, mint="SomeOtherMint") for i in range(5)])
check("⛔ transactions that never move THIS mint give no dup reading, not a zero",
      other["dup_amount_share"] is None and other["verdict"] == "VOLUME_UNKNOWN", other)
def swap(slot, amt):
    """One ordinary swap: the pool's account loses amt, the trader's gains it."""
    return {"slot": slot, "meta": {
        "preTokenBalances": [{"accountIndex": 1, "mint": M, "uiTokenAmount": {"uiAmount": 5000.0}},
                             {"accountIndex": 2, "mint": M, "uiTokenAmount": {"uiAmount": 0.0}}],
        "postTokenBalances": [{"accountIndex": 1, "mint": M, "uiTokenAmount": {"uiAmount": 5000.0 - amt}},
                              {"accountIndex": 2, "mint": M, "uiTokenAmount": {"uiAmount": amt}}]}}


legs = V.profile_from(M, [swap(i, 10.0 * (i + 1)) for i in range(10)])
check("⛔ §3b: ten DIFFERENT ordinary swaps score dup 1.0 on the 09-17 computation (both legs)",
      legs["dup_amount_share"] == 1.0 and legs["verdict"] == "VOLUME_SUSPECT", legs)
check("...and 0.0 on M1', where one transfer is one size -> CLEAN_V2",
      legs["dup_amount_share_tx"] == 0.0 and legs["verdict_v2"] == "VOLUME_CLEAN", legs)
loop = V.profile_from(M, [swap(i, 77.7) for i in range(10)])
check("a bot looping one size is still 1.0 on M1'", loop["dup_amount_share_tx"] == 1.0
      and loop["verdict_v2"] == "VOLUME_SUSPECT")
check("§3d M1' alone: 0.50 SUSPECT, 0.2499 CLEAN, 0.25 UNKNOWN, None UNKNOWN",
      [V.verdict_m1p(x) for x in (0.5, 0.2499, 0.25, None)]
      == ["VOLUME_SUSPECT", "VOLUME_CLEAN", "VOLUME_UNKNOWN", "VOLUME_UNKNOWN"])
src = open(V.__file__, encoding="utf-8").read()
check("transactions are requested at version 1", '"maxSupportedTransactionVersion": 1' in src)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
sys.exit(1 if bad else 0)
