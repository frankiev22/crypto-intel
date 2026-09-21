"""⛔ NOTHING MAY BE GROUPED, DEDUPED OR KEYED ON A TICKER.

Standing rule 2: key on the contract address, never the ticker. 398 contracts in
our data impersonate an incumbent name, 112 carry a bidi control in the symbol,
and a ticker is simply not identity - there are 25 distinct FLORK contracts and
six distinct BASKET contracts inside one hour of 2026-09-20.

WHAT WENT WRONG, and why this file exists (2026-09-21):

  * `collect.scan_stage` deduped surfaced rows on `r.get("addr") or r.get("name")`.
    `addr` defaults to `""`, which is falsy, so a row with no address fell back to
    the SYMBOL and merged with an unrelated contract of the same name.
  * The scanner-hit findings lane existed ONLY as prose in the desktop task's
    SKILL.md, and that prose said `--key <SYMBOL>` one paragraph above telling the
    agent to key the TRAP lane on the contract address. Six BASKET contracts, two
    of them graded 100, collapsed into one `scanner-hit:basket` class; everything
    after the first was suppressed and never pinged. Measured over the four days
    `grade` has existed: 23 classes held more than one distinct grade-85+
    contract, covering 34 contracts, 11 of them inside a single hour.
  * `track.py`'s outcome-win key carried `o.get("token") or o.get("symbol", "?")`.
    Dormant - `token` is on 100% of outcome rows from 2026-09-09 - but the same
    shape.

⭐ The test is on the SOURCE, at the AST level, because the failure is a habit
rather than a value: a comment saying "keyed on the address" is what the score
band had, twice, while the code said otherwise.

Run: python test_tickerkey.py
"""
import ast
import io
import os
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

HERE = os.path.dirname(os.path.abspath(__file__))

# Fields that hold a DISPLAY name. None of these is identity.
TICKER_FIELDS = {"name", "symbol", "ticker", "sym", "base_symbol", "baseSymbol"}
# Fields that hold identity.
ADDRESS_FIELDS = {"addr", "address", "token", "contract", "mint", "ca",
                  "pair", "pool", "pair_address", "pairAddress"}

# Findings lanes whose key is legitimately NOT a contract: the thing they are
# about is not a token. Each needs a reason, and the reason is the point.
NON_TOKEN_LANES = {
    "collector-error": "keyed on the exception class - the defect is the code path",
    "lookup-outage": "keyed on the horizon - the defect is the horizon's source",
    "horizon-drift": "keyed on the horizon",
    "news-stale": "keyed per OUTLET so four feeds cannot collapse into one",
    "detector-drift": "the detector, not a token",
    "slug-collision": "keyed on the colliding class itself",
    "funnel-narrowing": "keyed on the stage",
    "reporting-path": "keyed on the path",
    "correction": "keyed on what is being corrected",
    "data-destroyed": "keyed on what was destroyed",
    "paper-v3-result": "keyed on the rule",
    # A liveness component's `name` IS its identity - "scan.observations" is not
    # a display name for a token. The exemption is the lane, not the field.
    "liveness": "keyed on the liveness component's own name",
}

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL':4}  {name}" + (f"  [{detail}]" if detail and not cond else ""))


def section(t):
    print(f"\n{t}\n" + "=" * 70)


def py_files():
    for fn in sorted(os.listdir(HERE)):
        if fn.endswith(".py") and not fn.startswith("test_"):
            yield fn


def field_names(node):
    """Every string used as a field lookup anywhere inside `node`.

    Covers r["symbol"], r.get("symbol"), r.get("symbol", "?") and attribute
    access r.symbol.
    """
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Subscript) and isinstance(n.slice, ast.Constant) \
                and isinstance(n.slice.value, str):
            out.add(n.slice.value)
        elif isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "get" and n.args \
                and isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str):
            out.add(n.args[0].value)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
    return out


def resolve(node, scope):
    """One level of local assignment, so a key held in a local still reads.

    `k = (r.get("addr") or "").strip()` then `record(..., k, ...)` must not look
    like a key with no fields in it - that is how a check passes vacuously.
    """
    if isinstance(node, ast.Name) and scope is not None:
        for n in ast.walk(scope):
            if isinstance(n, ast.Assign) and any(
                    isinstance(t, ast.Name) and t.id == node.id for t in n.targets):
                return n.value
    return node


def record_calls(tree):
    """(kind, key_node, lineno) for every findings record call with a literal kind."""
    for n in ast.walk(tree):
        if not isinstance(n, ast.Call):
            continue
        f = n.func
        nm = f.attr if isinstance(f, ast.Attribute) else (f.id if isinstance(f, ast.Name) else "")
        if nm not in ("record", "record_finding"):
            continue
        if len(n.args) < 2:
            continue
        if not (isinstance(n.args[0], ast.Constant) and isinstance(n.args[0].value, str)):
            continue
        yield n.args[0].value, n.args[1], n.lineno


# --------------------------------------------------------------------------
section("1. ⛔ no findings key may mention a ticker field, not even as a fallback")
bad = []
n_calls = 0
for fn in py_files():
    src = io.open(os.path.join(HERE, fn), encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError as e:
        check(f"{fn} parses", False, str(e))
        continue
    funcs = [n for n in ast.walk(tree) if isinstance(n, ast.FunctionDef)]
    for kind, key, line in record_calls(tree):
        n_calls += 1
        if kind in NON_TOKEN_LANES:
            continue            # declared, with a reason, at the top of this file
        scope = next((f for f in funcs
                      if f.lineno <= line <= (getattr(f, "end_lineno", None) or line)), None)
        hit = field_names(resolve(key, scope)) & TICKER_FIELDS
        if hit:
            bad.append(f"{fn}:{line} lane {kind!r} keys on {sorted(hit)}")
check(f"every findings key is ticker-free ({n_calls} call sites read, "
      f"{len(NON_TOKEN_LANES)} lanes exempt with a stated reason)",
      not bad, "; ".join(bad))
check("...and there were call sites to read (the walk is not vacuous)", n_calls >= 5, n_calls)

section("2. ⛔ no `address or ticker` fallback anywhere - the exact bug shape")
falls = []
for fn in py_files():
    src = io.open(os.path.join(HERE, fn), encoding="utf-8").read()
    try:
        tree = ast.parse(src)
    except SyntaxError:
        continue
    for n in ast.walk(tree):
        if not (isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or)):
            continue
        names = field_names(n)
        if (names & ADDRESS_FIELDS) and (names & TICKER_FIELDS):
            falls.append(f"{fn}:{n.lineno} `{sorted(names & ADDRESS_FIELDS)} or "
                         f"{sorted(names & TICKER_FIELDS)}`")
check("no expression falls back from an address to a ticker", not falls, "; ".join(falls))

section("3. ⭐ the scan stage records its hits, and keys them on the address")
src = io.open(os.path.join(HERE, "collect.py"), encoding="utf-8").read()
tree = ast.parse(src)
scan = next((n for n in ast.walk(tree)
             if isinstance(n, ast.FunctionDef) and n.name == "scan_stage"), None)
check("collect.scan_stage exists", scan is not None)
hits = [(k, key) for k, key, _ in record_calls(scan)] if scan else []
check("⭐ it records a scanner-hit itself, rather than leaving it to a prose instruction",
      any(k == "scanner-hit" for k, _ in hits), [k for k, _ in hits])
for k, key in hits:
    if k != "scanner-hit":
        continue
    names = field_names(resolve(key, scan))
    check("...and the scanner-hit key mentions no ticker field", not (names & TICKER_FIELDS),
          sorted(names))
    check("...and it is derived from an address field", bool(names & ADDRESS_FIELDS),
          sorted(names))

section("4. ⛔ the dedupe inside scan_stage never groups on a ticker")
# The `seen`/`uniq` collapse: whatever is added to the seen set must not be a
# ticker. Checked by reading every value added to a set inside the function.
added = []
if scan:
    for n in ast.walk(scan):
        if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute) \
                and n.func.attr == "add" and n.args:
            added.append((n.lineno, field_names(n.args[0])))
        # `k = ...` feeding that add
        if isinstance(n, ast.Assign) and len(n.targets) == 1 \
                and isinstance(n.targets[0], ast.Name) and n.targets[0].id in ("k", "key"):
            added.append((n.lineno, field_names(n.value)))
check("the dedupe key is built from something", bool(added), added)
tick = [(l, sorted(f & TICKER_FIELDS)) for l, f in added if f & TICKER_FIELDS]
check("⛔ nothing added to a dedupe set mentions a ticker field", not tick, tick)

section("5. the desktop task's prompt does not ask for a ticker-keyed finding")
SKILL = os.path.join(os.path.expanduser("~"), "Documents", "Claude", "Scheduled",
                     "crypto-collect-hourly", "SKILL.md")
if not os.path.exists(SKILL):
    check("SKILL.md found (skipped - not on this host)", True)
else:
    txt = io.open(SKILL, encoding="utf-8").read()
    lines = [l for l in txt.splitlines()
             if "--kind" in l and "--key" in l and not l.lstrip().startswith("#")]
    check("SKILL.md declares findings commands", bool(lines), len(lines))
    offend = [l.strip()[:90] for l in lines
              if "--key <SYMBOL>" in l or "--key <TICKER>" in l]
    check("⛔ no command in it passes a SYMBOL as the finding key", not offend, offend)
    check("...and the scanner-hit example keys on the contract address",
          any("scanner-hit" in l and "CONTRACT_ADDRESS" in l for l in lines),
          [l.strip()[:60] for l in lines if "scanner-hit" in l])

section("6. ⚠ the address survives findings._slug, which strips digits")
# `_slug` removes digits, so two addresses differing only in digits WOULD
# collide. That is safe empirically rather than by construction: a base58 mint
# is 32-44 characters and the letters alone are 26-44 of them. Measured, not
# assumed - if it ever stops being true we learn here and not from a silenced
# alert. Read-only; touches no journal file.
import collections as _c
import json as _j
import findings as _f
_cas = set()
_obs = os.path.join(HERE, "data", "observations")
if os.path.isdir(_obs):
    for _fn in sorted(os.listdir(_obs)):
        if not _fn.endswith(".jsonl"):
            continue
        for _l in io.open(os.path.join(_obs, _fn), encoding="utf-8"):
            try:
                _t = _j.loads(_l).get("token")
            except ValueError:
                continue
            if _t:
                _cas.add(_t)
_g = _c.defaultdict(set)
for _c2 in _cas:
    _g[_f._slug(_c2)].add(_c2)
_coll = {k: v for k, v in _g.items() if len(v) > 1}
check(f"the corpus is big enough to mean something ({len(_cas)} addresses)", len(_cas) > 1000,
      len(_cas))
check("⛔ no two distinct contract addresses share a dedupe class",
      not _coll, list(_coll.items())[:3])

ok = sum(1 for _, c in R if c)
print(f"\n{ok}/{len(R)} passed")
if ok != len(R):
    print("\nFAILED:")
    for n, c in R:
        if not c:
            print("  -", n)
sys.exit(0 if ok == len(R) else 1)
