"""
Token-name safety checks.

Found the hard way: the only token that survived 6 hours in the first batch was
called "‮TDSU" - a right-to-left override character followed by TDSU, which
RENDERS as "USDT". A deliberate impersonation of the largest stablecoin, using a
Unicode control character to reverse the display.

It scored well on every numeric metric because scam tokens are often the ones
with real liquidity - that is the bait. Numbers alone cannot catch this.
"""
import unicodedata

# invisible or direction-manipulating characters, no legitimate use in a ticker
DANGEROUS = {
    "‪","‫","‬","‭","‮",   # LTR/RTL overrides
    "​","‌","‍","⁠","﻿",   # zero-width
    "‎","‏","؜",                     # directional marks
    "⁦","⁧","⁨","⁩",            # isolates
}

MAJORS = {"USDT","USDC","SOL","ETH","BTC","WBTC","WETH","DAI","BNB","USD",
          "JUP","BONK","WIF","RAY","PYTH","JTO"}

CYRILLIC_LOOKALIKE = {"а":"a","е":"e","о":"o","р":"p","с":"c","у":"y","х":"x",
                      "А":"A","В":"B","Е":"E","К":"K","М":"M","Н":"H","О":"O",
                      "Р":"P","С":"C","Т":"T","У":"Y","Х":"X"}

def check(symbol, name=""):
    """Returns a list of flags. Empty list means the name looks clean."""
    flags = []
    for field, label in ((symbol or "", "symbol"), (name or "", "name")):
        bad = [c for c in field if c in DANGEROUS]
        if bad:
            codes = ", ".join(f"U+{ord(c):04X}" for c in bad)
            flags.append(f"IMPERSONATION RISK: {label} contains hidden control chars ({codes})")

        if any(c in CYRILLIC_LOOKALIKE for c in field):
            latin = "".join(CYRILLIC_LOOKALIKE.get(c, c) for c in field)
            if latin.upper() in MAJORS:
                flags.append(f"IMPERSONATION RISK: {label} uses Cyrillic lookalikes to spell {latin.upper()}")
            else:
                flags.append(f"{label} mixes Cyrillic and Latin characters")

        # reversed-display check
        stripped = "".join(c for c in field if c not in DANGEROUS)
        if stripped and stripped[::-1].upper() in MAJORS and stripped.upper() not in MAJORS:
            flags.append(f"IMPERSONATION RISK: {label} renders as {stripped[::-1].upper()} reversed")

        for c in field:
            if unicodedata.category(c) in ("Cf", "Co", "Cs"):
                if c not in DANGEROUS:
                    flags.append(f"{label} contains a format/private-use character U+{ord(c):04X}")
                break
    return flags

if __name__ == "__main__":
    for s in ["‮TDSU", "USDC", "USDТ", "BONK", "​SOL", "PEPE"]:
        f = check(s)
        print(f"  {repr(s):<16} {'CLEAN' if not f else f}")
