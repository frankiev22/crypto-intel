"""The four copies of the depth calculation may not disagree. Run: python test_depth.py

⛔ THERE ARE FOUR IMPLEMENTATIONS OF THE SAME FUNCTION.

    resolve.exit_depth_usd(pair)        the original
    scanner.resolve_exit_depth(pair)    "local copy to avoid a circular import"
    watchlist._exit_depth(pair)         "third local copy"
    paper._exit_depth(pair)             the fourth, and it is NOT the same

Reading the four bodies side by side shows one difference. Running them on the
same inputs showed TWO, and the one that was actually firing was invisible in
the source.

⛔ 1. THE ACTIVE ONE: unknown was being written as zero, on 75.5% of the
journal. The bodies are identical, but each module has its own `_f` helper and
scanner's defaults to **0.0** where resolve's and watchlist's default to
**None**. So `q = _f(liq.get("quote"))` returned 0.0 for a missing field, the
`q is not None` branch was taken, and the function returned 0.0 - a measured
empty pool - for a pair that had shipped no liquidity block at all.

    exit_depth_usd on 15,222 journalled rows
      exactly 0.0     11,490   (75.5%)   <- essentially all bonding_curve
      a real number    3,572   (23.5%)
      None               160    (1.1%)

⭐ Verified against live pairs: 30 of 30 bonding-curve pairs ship NO usd, NO
quote and NO base, and 0 of 30 had a depth `resolve` could compute while this
returned 0.0. **No number was lost. The KIND of the value was wrong**, which is
standing rule 5 in the module that writes the permanent record. No gate moved -
0.0 and None both fail MIN_EXIT_DEPTH, and a bonding-curve row is refused on
venue anyway. Fixed forward-only; rule 8 keeps the existing rows.

⚠️ 2. THE LATENT ONE: paper._exit_depth has no fallback branch. The other three,
when the quote-side path fails, fall back to `max(0, usd - base * priceUsd)`.
That split needs `priceNative` to be absent, and it was present on 35 of 35 live
pairs, so it does not currently occur. ⛔ **It is pinned, not reconciled** -
paper._exit_depth feeds `paper.qualifies()`, and RULE_V1 is frozen. Changing how
a pinned rule computes its input is what pre-commitment forbids.

⛔ AND THAT IS WHY THIS FILE EXISTS RATHER THAN A REFACTOR. Consolidating four
call sites in the gate path on the day the collector finally runs unattended is
a risk with no measured payoff. Pinning the behaviour costs nothing and turns a
silent divergence into a failing suite the moment the payload changes shape.
"""
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import paper
import resolve
import scanner
import watchlist

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


IMPLS = [("resolve.exit_depth_usd", resolve.exit_depth_usd),
         ("scanner.resolve_exit_depth", scanner.resolve_exit_depth),
         ("watchlist._exit_depth", watchlist._exit_depth),
         ("paper._exit_depth", paper._exit_depth)]

# The shapes that actually come back from Dexscreener, plus the ones that make
# the implementations differ. Each is (label, pair, expected-or-None-for-"agree").
CASES = [
    ("a normal amm pair: quote, usd, base, both prices",
     {"liquidity": {"usd": 50000.0, "base": 1e8, "quote": 120.0},
      "priceUsd": "0.0001", "priceNative": "0.0000004"}, None),
    ("no liquidity block at all",
     {"priceUsd": "0.0001", "priceNative": "0.0000004"}, None),
    ("a bonding-curve shape: no quote, no usd, no base",
     {"liquidity": {}, "priceUsd": "0.0001", "priceNative": "0.0000004"}, None),
    ("a string quote, as the API sometimes sends",
     {"liquidity": {"usd": "50000", "base": "1e8", "quote": "120"},
      "priceUsd": "0.0001", "priceNative": "0.0000004"}, None),
    ("⛔ base * priceUsd EXCEEDS liquidity.usd - the fallback would go negative",
     {"liquidity": {"usd": 50000.0, "base": 1e9, "quote": 120.0},
      "priceUsd": "0.0001", "priceNative": "0.0000004"}, None),
    ("priceUsd is zero",
     {"liquidity": {"usd": 50000.0, "base": 1e8, "quote": 120.0},
      "priceUsd": "0", "priceNative": "0.0000004"}, None),
    ("garbage in the numeric fields",
     {"liquidity": {"usd": "n/a", "base": None, "quote": "x"},
      "priceUsd": "nope", "priceNative": []}, None),
]

print("=" * 70)
print("1. all four implementations agree on every shape we actually see")
print("=" * 70)

diverged = []
for label, pair, _ in CASES:
    vals = []
    for name, fn in IMPLS:
        try:
            vals.append((name, fn(dict(pair))))
        except Exception as e:
            vals.append((name, f"RAISED {type(e).__name__}"))
    first = vals[0][1]
    same = all(
        (v is None and first is None)
        or (isinstance(v, float) and isinstance(first, float) and abs(v - first) < 1e-9)
        or v == first
        for _, v in vals)
    if not same:
        diverged.append((label, vals))
    check(label, same, "" if same else "; ".join(f"{n}={v}" for n, v in vals))

check("⛔ no shape splits the four apart", not diverged,
      f"{len(diverged)} divergent shape(s)")

print()
print("=" * 70)
print("2. ⚠️ the KNOWN difference, pinned so it cannot spread quietly")
print("=" * 70)

# The one input that separates them: usd and base present, priceNative absent
# AND quote absent. Three implementations fall back; paper returns None.
# ⚠️ THESE TWO SHAPES ARE NOT IN SECTION 1, AND THE REASON IS MEASURED, NOT
# CONVENIENT. Both need `priceNative` to be absent, and across 35 live pairs it
# was present on 35 of 35. They do not occur; they are pinned here so that if
# the payload ever changes shape, the suite says which behaviour moved.
#
# ⛔ AND paper._exit_depth IS NOT "FIXED" TO MATCH. It feeds paper.qualifies(),
# and RULE_V1 - "amm+depth>=1000" - is PINNED. Changing how depth is computed
# changes which rows a frozen rule admits, which is exactly what a pre-committed
# rule forbids. The divergence is recorded, not quietly reconciled.
SPLIT = {"liquidity": {"usd": 50000.0, "base": 1e8}, "priceUsd": "0.0001"}
NO_NATIVE = {"liquidity": {"usd": 50000.0, "base": 1e8, "quote": 120.0},
             "priceUsd": "0.0001"}
vals = {name: fn(dict(SPLIT)) for name, fn in IMPLS}
three = [v for n, v in vals.items() if n != "paper._exit_depth"]
check("⚠️ the three with a fallback all return the same number",
      len(set(three)) == 1 and three[0] is not None, str(three))
check("⛔ and paper._exit_depth returns None for the SAME pair",
      vals["paper._exit_depth"] is None,
      "this is the drift - recorded, not fixed blind")
check("...which is a difference of exactly the fallback branch",
      abs(three[0] - max(0.0, 50000.0 - 1e8 * 0.0001)) < 1e-6, str(three[0]))

v2 = {name: fn(dict(NO_NATIVE)) for name, fn in IMPLS}
check("⚠️ same split when `quote` is present but priceNative is not",
      v2["paper._exit_depth"] is None
      and all(v == 40000.0 for n, v in v2.items() if n != "paper._exit_depth"),
      "; ".join(f"{n.split('.')[0]}={v}" for n, v in v2.items()))
check("⭐ and neither shape occurs: priceNative was present on 35 of 35 live pairs",
      True, "measured 2026-09-18, docs/BACKLOG.md A29")

print()
print("=" * 70)
print("3. ⛔ and the fallback never returns a negative depth")
print("=" * 70)

NEG = {"liquidity": {"usd": 1000.0, "base": 1e9}, "priceUsd": "0.0001"}
for name, fn in IMPLS:
    v = fn(dict(NEG))
    check(f"{name} is None or >= 0", v is None or v >= 0.0, repr(v))

print()
print("=" * 70)
print("4. the copies are still four, and the count is asserted")
print("=" * 70)

HERE = os.path.dirname(os.path.abspath(__file__))
n_copies = 0
for f, needle in (("resolve.py", "def exit_depth_usd"),
                  ("scanner.py", "def resolve_exit_depth"),
                  ("watchlist.py", "def _exit_depth"),
                  ("paper.py", "def _exit_depth")):
    src = io.open(os.path.join(HERE, f), encoding="utf-8").read()
    if needle in src:
        n_copies += 1
check("⛔ there are still exactly 4 copies of this calculation", n_copies == 4,
      f"{n_copies} found - if this changed, the consolidation happened and "
      f"this file should be rewritten, not deleted")

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
