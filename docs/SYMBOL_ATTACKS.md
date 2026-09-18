# Symbols that render as a different token

**2026-09-18. Found while picking contracts for a live paperv3 run — the script
crashed on a `UnicodeEncodeError` and the character it choked on turned out to be
an attack.**

---

## 1. ⛔ The finding

**112 distinct contracts in our corpus carry a bidi or zero-width control
character in the token symbol**, and **48 more mix alphabets**. Out of 36,075
observations.

The one that surfaced it claimed **the highest liquidity of 2026-09-18 —
$35,028,013 — with zero sells in an hour**:

```
stored:   'U‮CDЅ'
          U + RIGHT-TO-LEFT OVERRIDE + C + D + CYRILLIC CAPITAL DZE
renders:  USDC
```

⭐ **Two independent tricks stacked in four characters.** U+202E reverses
everything after it, so `CDЅ` displays as `ЅDC`. And the `Ѕ` is **U+0405 Cyrillic
Dze**, not Latin `S` — so even a reader who pastes the rendered string and
compares it to "USDC" gets a mismatch they cannot see.

## 2. What the 112 actually display as

```
stored symbol        renders as     n
'‮NEW'          WEN            5
'‮TDSU'         USDT           3
'‮yhtomiJ'      Jimothy        3
'‮NIUGNEP'      PENGUIN        2
'‮draobno'      onboard        2
'‮GNEDOOM'      MOODENG        1
'‮LEXIP'        PIXEL          1
'‮knoB'         Bonk           1
'‮LLORT'        TROLL          1
'‮2egoD'        Doge2          1
'‮tacyloP'      Polycat        1
'‮ETAC'         CATE           1
```

⚠️ **And 8 contracts whose symbol is a lone U+200E** — they render as **nothing
at all**. A token with an invisible name. Two more are U+200E separated by
spaces, so they render as whitespace.

## 3. The homoglyph half — 48 contracts, mostly Cyrillic

```
Cyrillic + Latin   45
Greek + Latin       3

'АNSEM'     Cyrillic А      (twice, two different contracts)
'MAХI'      Cyrillic Х
'Тaс'       Cyrillic Т, с
'Frаg'      Cyrillic а
'diсkbutt'  Cyrillic с
```

⭐ **`АNSEM` appears on two separate contracts.** Ansem is a real and very
well-known Solana trader; a token that renders as his handle is a targeted
impersonation, and it is invisible to any string comparison against the Latin
spelling.

⛔ **Homoglyphs cannot be stripped.** The symbol genuinely is that string. They
can only be **flagged**, which is what we now do.

## 4. Why this was invisible to us

`dashboard.py` rendered symbols with `html.escape()`. That is correct and
necessary — it stops markup injection — and it does **nothing** to U+202E, which
is not markup. So the escaping looked like sanitisation and was not.

⛔ **For as long as that was true, the row above displayed as "USDC" in Frank's
own dashboard.** Standing rule 2 — *key on the contract address, never the
ticker* — exists for precisely this, and the UI was quietly undermining it.

⚠️ **This is a different mechanism from the 398 contracts already recorded as
impersonating an incumbent name.** Those are detectable by comparing strings.
These are not: the stored string does not match the incumbent, only the rendered
one does.

## 5. The fix, and the part of it that matters

`dashboard.safe_sym()`:

1. **Strips all 15 bidi and zero-width controls** (U+202A–202E, U+2066–2069,
   U+200E/200F, U+200B–200D, U+FEFF) **and appends a visible `⛔BIDI` marker.**
   ⭐ **Silently deleting the control would hide the deception with our
   fingerprints on it** — the point is to make the trick the thing you notice.
2. **Flags mixed Latin/Cyrillic/Greek as `⛔MIXED-SCRIPT`**, naming the alphabets.
3. Still escapes HTML, still caps length, still renders absent as `unknown`.

**Verified on the built artifact, not just the function:** `data/dashboard.html`
now contains **zero** bidi control characters, with 4 `BIDI` and 1
`MIXED-SCRIPT` markers rendered. `test_symbols.py` (14 checks) covers the two
live attacks, all 15 control characters, ten ordinary symbols that must NOT
warn, HTML safety, and the built file.

## 6. ⚠️ What this does NOT do

- **It is a display fix, not a detector.** Nothing scores a token down for it,
  nothing filters on it, and no alert fires. That is deliberate: this session has
  no evidence that a bidi symbol predicts an outcome, and inventing a rule from
  160 contracts nobody has labelled is the error this repo keeps retracting.
- **The 112 and 48 are not deduplicated against each other**, and both are counts
  of contracts *seen*, not of scams *confirmed*. `WEN`, `Bonk` and `USDT` reading
  as impersonations is an inference from the rendered name, not a verdict.
- ⛔ **`check.py` does not yet look at this.** Whether it should is an open
  question, and the honest bar is the same as everything else: a labelled sample
  and a pre-committed threshold before it influences anything.

## 7. Open

- Extend the scan to **pool names and social handles**, not just symbols.
- **Confusables beyond Cyrillic/Greek** — full Unicode confusables mapping, which
  would catch `ｕｓｄｃ` (fullwidth) and `υ` (Greek upsilon) styles we do not
  currently separate.
- Measure whether a bidi symbol correlates with `NO_SELL_ROUTE` at all. **n=112
  is enough to look; it is not enough to act on.**
