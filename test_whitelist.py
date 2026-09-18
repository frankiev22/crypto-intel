"""The whitelist guard, and the socials fields it was built to protect.

Five fields have been silently dropped by journal.record()'s whitelist:
vol_to_liq, vol_burst, the news NameError, paper_v2_arm, and info.socials.
Every one was found by a human noticing an absence, long after the data was
lost. This file makes number six a build failure instead.

Writes to a temp directory. Touches no real data file.
"""
# ⛔ Before anything that writes. A full suite run was appending rows to
# data/liveness/ - the file that answers "is the collector alive" - so the
# tests were writing into the health signal they are meant to check.
# run_tests.py fails if data/ changes at all; this is how a suite complies.
import testsandbox
testsandbox.activate()

import json
import os
import sys
import tempfile

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import journal
import scanner

FAIL = []


def check(ok, label, detail=""):
    print(("  ok   " if ok else "  FAIL ") + label + (f"  {detail}" if detail else ""))
    if not ok:
        FAIL.append(label)


# --------------------------------------------------------------------------
print("1. scanner.socials_of() reads the payload shape Dexscreener actually sends")

full = {"info": {"socials": [{"url": "https://t.me/x", "type": "telegram"},
                             {"url": "https://twitter.com/x", "type": "twitter"},
                             {"url": "https://discord.gg/x", "type": "discord"}],
                 "websites": [{"url": "https://example.com", "label": "Website"}]}}
s = scanner.socials_of(full)
check(s["has_telegram"] is True, "telegram detected")
check(s["has_twitter"] is True, "twitter detected")
check(s["has_website"] is True, "website detected")
check(s["social_count"] == 4, "social_count counts distinct kinds + website",
      f"got {s['social_count']}, expected 4 (tg, tw, discord, site)")

# The rename. Dexscreener has used both spellings.
s = scanner.socials_of({"info": {"socials": [{"url": "u", "type": "X"}]}})
check(s["has_twitter"] is True, "type 'X' counts as twitter")

# Duplicates are one kind, not two.
s = scanner.socials_of({"info": {"socials": [{"type": "telegram"}, {"type": "telegram"}]}})
check(s["social_count"] == 1, "two telegram links are one kind", f"got {s['social_count']}")

# Absent info block - the common case for a token with no links.
for empty in ({}, {"info": None}, {"info": {}}, None):
    s = scanner.socials_of(empty)
    check(s == {"has_telegram": False, "has_twitter": False,
                "has_website": False, "social_count": 0},
          f"no-info payload {str(empty)[:18]!r} -> all false, count 0")

# --------------------------------------------------------------------------
print("\n2. the four fields survive journal.record() and land on disk")

tmp = tempfile.mkdtemp(prefix="crypto_wl_")
_real_obs, _real_push = journal.OBS, journal._push
journal.OBS = os.path.join(tmp, "observations")
journal._push = lambda *a, **k: None
os.makedirs(journal.OBS, exist_ok=True)

row = {"addr": "TestCA1111111111111111111111111111111111111", "name": "TEST",
       "pair": "TestPair111111111111111111111111111111111", "score": 50,
       "liq": 1000.0, "fdv": 50000.0, "vol_h1": 1.0, "v24": 2.0,
       "txns_h1": 3, "buys_h1": 2, "sells_h1": 1,
       "has_telegram": True, "has_twitter": True,
       "has_website": False, "social_count": 2}
try:
    journal.record([dict(row)], "solana")
    path = journal._path(journal.OBS)
    written = [json.loads(l) for l in open(path, encoding="utf-8") if l.strip()]
    check(len(written) == 1, "one row written", path)
    w = written[-1]
    for k, want in (("has_telegram", True), ("has_twitter", True),
                    ("has_website", False), ("social_count", 2)):
        check(k in w, f"{k} present in the WRITTEN row")
        check(w.get(k) == want, f"{k} == {want}", f"got {w.get(k)!r}")
    check(journal.LAST_WHITELIST_DROP == set(),
          "clean row drops nothing", str(journal.LAST_WHITELIST_DROP))

    # ----------------------------------------------------------------------
    print("\n3. the guard CATCHES a field that is computed and not persisted")
    #     This is the whole point. A new field added to the scanner and not to
    #     the whitelist must be impossible to ship.
    dirty = dict(row)
    dirty["brand_new_signal"] = 0.99
    journal.record([dirty], "solana")
    check("brand_new_signal" in journal.LAST_WHITELIST_DROP,
          "unpersisted field is reported", str(sorted(journal.LAST_WHITELIST_DROP)))

    print("\n4. deliberately transient fields are NOT reported")
    quiet = dict(row)
    for k in journal.TRANSIENT_ROW_KEYS:
        quiet[k] = "x"
    journal.record([quiet], "solana")
    check(journal.LAST_WHITELIST_DROP == set(),
          "TRANSIENT_ROW_KEYS stay silent", str(sorted(journal.LAST_WHITELIST_DROP)))

    print("\n5. the guard never costs a row")
    journal.record([dict(row, another_orphan=1)], "solana")
    written = [json.loads(l) for l in open(journal._path(journal.OBS), encoding="utf-8")
               if l.strip()]
    check(len(written) == 4, "all four rows on disk despite drops",
          f"got {len(written)}")
finally:
    journal.OBS, journal._push = _real_obs, _real_push

# --------------------------------------------------------------------------
# ⛔ 6. THE ALARM MUST REACH THE RUNTIME, NOT JUST THIS TEST.
#
# Backlog A10. Until 2026-09-18 `LAST_WHITELIST_DROP` was written by journal.py
# and read by THIS FILE AND NOTHING ELSE - the comment beside it claimed
# "printed by collect.py" and collect.py never referenced it. So the guard that
# was built to stop a sixth silent drop reported only to a test, which means it
# could not have stopped number six either. Detection without an alarm is not a
# guard.
# --------------------------------------------------------------------------
print()
print("6. the alarm reaches collect.py, not just this test")
csrc = open(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                       "collect.py"), encoding="utf-8").read()
check("journal.PASS_WHITELIST_DROP" in csrc,
      "collect.py reads the pass-level tally")
check("journal.reset_pass_drops()" in csrc,
      "collect.py resets it once per pass")
check("WHITELIST ALARM" in csrc,
      "and it alarms by name, not silently")
check("GITHUB_STEP_SUMMARY" in csrc and "WHITELIST DROP" in csrc,
      "⭐ and surfaces it where a human looks, not only in the log")

# The pass tally must SURVIVE a second record() call; LAST_WHITELIST_DROP does
# not, and that difference is the point of having two.
_o, _p2 = journal.OBS, journal._push
try:
    journal.OBS = tempfile.mkdtemp()
    journal._push = lambda *a, **k: None
    journal.reset_pass_drops()
    base = {"addr": "A" * 44, "pair": "P1", "name": "T", "score": 10,
            "venue_type": "amm", "chain": "solana"}
    journal.record([dict(base, first_orphan=1)], "solana")
    journal.record([dict(base, pair="P2", second_orphan=2)], "solana")
    check({"first_orphan", "second_orphan"} <= journal.PASS_WHITELIST_DROP,
          "⭐ the PASS tally keeps both drops across two record() calls",
          str(sorted(journal.PASS_WHITELIST_DROP)))
    check("first_orphan" not in journal.LAST_WHITELIST_DROP,
          "⚠️ while LAST_ keeps only the most recent - which is why it was "
          "the wrong thing to alarm on",
          str(sorted(journal.LAST_WHITELIST_DROP)))
    journal.reset_pass_drops()
    check(journal.PASS_WHITELIST_DROP == set(), "reset_pass_drops() clears it")
finally:
    journal.OBS, journal._push = _o, _p2

print()
if FAIL:
    print(f"FAILED: {len(FAIL)}")
    for f in FAIL:
        print("   -", f)
    sys.exit(1)
print("all whitelist guard checks passed")
