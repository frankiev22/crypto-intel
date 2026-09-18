"""A token symbol may never render as a different token. Run: python test_symbols.py

⛔ FOUND LIVE, not hypothetically. `data/observations/2026-09-18.jsonl` contains
a token whose symbol is:

    'U\\u202eCD\\u0405'   =  U + RIGHT-TO-LEFT OVERRIDE + C + D + CYRILLIC DZE

⭐ A browser renders that as **USDC**. The row claimed the highest liquidity of
the day - $35,028,013 - with ZERO sells in an hour. A second token used
'\\u202eEKOP', which renders as **POKE**.

`html.escape()` does not touch U+202E, so for as long as the dashboard used it
alone, that row displayed as USDC in the one place a human reads. Standing rule
2 - "key on the contract address, never the ticker" - is written for exactly
this, and the UI was undermining it.

⚠️ Two distinct abuses, and only one is fixable by stripping:
  - BIDI / zero-width controls: removed, and replaced with a VISIBLE marker.
    Silently deleting them would hide the deception with our fingerprints on it.
  - HOMOGLYPHS (Cyrillic/Greek letters inside Latin text): not removable - the
    symbol is what it is - so they are FLAGGED.
"""
import html
import io
import os
import sys

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


import dashboard

RLO = "‮"
ATTACK = "U" + RLO + "CDЅ"          # renders as USDC
ATTACK2 = RLO + "EKOP"                   # renders as POKE
BIDI_CHARS = [0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
              0x2066, 0x2067, 0x2068, 0x2069, 0x200E, 0x200F,
              0x200B, 0x200C, 0x200D, 0xFEFF]

print("=" * 70)
print("1. the live attack is neutralised")
print("=" * 70)

out = dashboard.safe_sym(ATTACK)
check("⛔ no bidi control survives into the output",
      not any(chr(c) in out for c in BIDI_CHARS))
check("⭐ the deception is MARKED, not silently removed", "BIDI" in out)
check("the homoglyph is flagged as mixed-script", "MIXED-SCRIPT" in out)
check("and the alphabets are named", "Cyrillic" in out and "Latin" in out)

out2 = dashboard.safe_sym(ATTACK2)
check("the second live attack is neutralised too",
      not any(chr(c) in out2 for c in BIDI_CHARS) and "BIDI" in out2)

print()
print("=" * 70)
print("2. every bidi and zero-width control, not just the one we found")
print("=" * 70)

for c in BIDI_CHARS:
    o = dashboard.safe_sym("AB" + chr(c) + "CD")
    if chr(c) in o or "BIDI" not in o:
        check(f"U+{c:04X} is stripped and marked", False, repr(o[:40]))
        break
else:
    check(f"all {len(BIDI_CHARS)} control characters are stripped and marked", True)

print()
print("=" * 70)
print("3. ⚠️ it does not cry wolf on ordinary symbols")
print("=" * 70)

for s in ("USDC", "BONK", "Arc", "NTDA", "OpenClaw", "SHEEPLE", "wif", "$MOTHER",
          "pepe2.0", "AI16Z"):
    o = dashboard.safe_sym(s)
    if "BIDI" in o or "MIXED-SCRIPT" in o:
        check(f"{s!r} is left alone", False, o[:60])
        break
else:
    check("ten ordinary symbols produce no warning at all", True)

check("a real USDC is untouched", dashboard.safe_sym("USDC") == "USDC")
check("⚠️ unknown renders as 'unknown', never blank (standing rule 5)",
      dashboard.safe_sym(None) == html.escape("unknown")
      and dashboard.safe_sym("") == html.escape("unknown"))

print()
print("=" * 70)
print("4. it is still HTML-safe - the new code must not undo the old guarantee")
print("=" * 70)

x = dashboard.safe_sym('<img src=x onerror=alert(1)>')
check("⛔ markup in a symbol is still escaped",
      "<img" not in x and "&lt;img" in x, x[:50])
check("quotes are escaped", "&quot;" in dashboard.safe_sym('a"b')
      or "&#x27;" in dashboard.safe_sym("a'b"))
check("a symbol is still length-capped", len(dashboard.safe_sym("Z" * 200)) < 120)

print()
print("=" * 70)
print("5. ⛔ the BUILT dashboard contains no bidi control at all")
print("=" * 70)

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "dashboard.html")
if os.path.exists(p):
    h = io.open(p, encoding="utf-8").read()
    found = sorted({hex(ord(c)) for c in h if ord(c) in BIDI_CHARS})
    check("no bidi control character in data/dashboard.html", not found,
          ", ".join(found))
    check("and the markers did render", "BIDI" in h, "run dashboard.py to refresh")
else:
    check("data/dashboard.html exists to check", False, "run dashboard.py first")

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
