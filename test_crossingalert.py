"""The crossing lane fires on a crossing with a market and stays SILENT on one
without. Run: python test_crossingalert.py

⛔ WHY THIS SUITE EXISTS. In the 24h to 2026-09-23 there were **61** crossings of
$1M or $5M on **34 distinct contracts** and **zero** crossing pings, because there
was no crossing lane at all. 45 of 60 had under $1,000 of exit depth at the
crossing, so most of that silence was right - by accident - and the 15 that
cleared the bar were silent for exactly the same reason.

⛔ AND IT IS ASSERTED ON OUTPUT, NOT EXECUTION (standing rule 16). The end-to-end
section calls `journal.record_outcome()` with a real crossing and asserts the
alert came out of it. Reading `track.py` and seeing the callback wired up is what
"built but not wired" looks like from the inside.
"""
import ast
import io
import json
import os
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
HERE = os.path.dirname(os.path.abspath(__file__))

import testsandbox
testsandbox.activate()

# ⛔ Never write to the real Supabase mirror from a test.
for _k in ("SUPABASE_URL", "SUPABASE_PUBLISHABLE_KEY", "CRYPTO_JOURNAL_SECRET"):
    os.environ.pop(_k, None)

import crossingalert as C
import findings
import journal
import liveness
import milestones

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


# ---------------------------------------------------------------------------
section("1. the rule, over every shape a crossing can arrive in")

CASES = [
    # milestone, meta, expected action
    ("mcap_1m", {"exit_depth_at_crossing": 9123.40}, C.ALERT),
    ("mcap_5m", {"exit_depth_at_crossing": 1000.00}, C.ALERT),   # the bar itself
    ("mcap_1m", {"exit_depth_at_crossing": 999.99}, C.SILENT_THIN),
    ("mcap_1m", {"exit_depth_at_crossing": 0.0}, C.SILENT_THIN),
    ("mcap_1m", {"exit_depth_at_crossing": None}, C.SILENT_UNMEASURED),
    ("mcap_1m", {}, C.SILENT_UNMEASURED),
    ("mcap_1m", None, C.SILENT_UNMEASURED),
    # ⛔ THE ONE THAT MATTERS: a depth that LOOKS fine but was not measured.
    ("mcap_1m", {"exit_depth_at_crossing": 50_000.0,
                 "depth_unmeasured_at_crossing": True}, C.SILENT_UNMEASURED),
    ("mcap_1m", {"exit_depth_at_crossing": "not a number"}, C.SILENT_UNMEASURED),
    # tiers that may never alert, however deep
    ("mcap_100k", {"exit_depth_at_crossing": 900_000.0}, C.NOT_A_CROSSING),
    ("mcap_200k", {"exit_depth_at_crossing": 900_000.0}, C.NOT_A_CROSSING),
    ("realizable_3x", {"exit_depth_at_crossing": 900_000.0}, C.NOT_A_CROSSING),
]
for ms, meta, want in CASES:
    got, why, sig = C.decide(ms, meta)
    check(f"{ms:<14} depth={str((meta or {}).get('exit_depth_at_crossing')):<13}"
          f" unmeasured={str((meta or {}).get('depth_unmeasured_at_crossing')):<5}"
          f" -> {want}", got == want, f"got {got}")

check("⛔⛔ a 50k depth flagged UNMEASURED is silent - not checked never reads "
      "as passed",
      C.decide("mcap_1m", {"exit_depth_at_crossing": 50_000.0,
                           "depth_unmeasured_at_crossing": True})[0]
      == C.SILENT_UNMEASURED)
check("⭐ every silence carries a reason in words",
      all(C.decide(ms, meta)[1] for ms, meta, _ in CASES))
check("⛔ only an ALERT carries a significance; a silence carries None",
      all((sig is not None) == (act == C.ALERT)
          for ms, meta, _ in CASES
          for act, _w, sig in [C.decide(ms, meta)]))


# ---------------------------------------------------------------------------
section("2. the bar is the PRE-COMMITTED one, and the file says so")

PRE = io.open(os.path.join(HERE, "PRECOMMIT_crossing_alert.md"),
              encoding="utf-8").read()
check("⭐ PRECOMMIT_crossing_alert.md exists", bool(PRE))
check("⛔ it names the $1,000 bar", "$1,000" in PRE)
check("⛔ the code's bar IS $1,000", C.DEPTH_BAR_USD == 1_000.0,
      str(C.DEPTH_BAR_USD))
check("⛔ it names all three outcomes, silences included",
      all(w in PRE for w in ("ALERT", "SILENT_THIN", "SILENT_UNMEASURED")))
check("⛔ it says what would make the rule WRONG, before it ran",
      "WRONG" in PRE.upper())
check("⭐ it names the lane budget and the significance scale",
      "3 pings/hour" in PRE and "significance" in PRE.lower())
check("⭐ the alerting tiers are 1m and 5m only",
      set(C.ALERTING_TIERS) == {"mcap_1m", "mcap_5m"}, str(C.ALERTING_TIERS))
check("⭐ significance is depth/1000, so $3,000 scores 3.0 like a 3x does",
      C.decide("mcap_1m", {"exit_depth_at_crossing": 3000.0})[2] == 3.0)


# ---------------------------------------------------------------------------
section("2b. ⛔⛔ the two bugs the REAL replay caught, before it ever fired")

# BUG 1: an uncapped depth/1000 scale made the lane budget decorative. The
# deepest real crossing in the 24h sample carried $711,654 of quote-side depth.
check("⛔⛔ significance is CAPPED, so a spent budget still binds",
      C.decide("mcap_1m", {"exit_depth_at_crossing": 711_654.0})[2] == C.SIG_CAP,
      str(C.decide("mcap_1m", {"exit_depth_at_crossing": 711_654.0})[2]))
check("⛔ two crossings past the cap score the SAME, so the second cannot "
      "break through on significance",
      C.decide("mcap_1m", {"exit_depth_at_crossing": 50_000.0})[2]
      == C.decide("mcap_1m", {"exit_depth_at_crossing": 900_000.0})[2])
check("⭐ and ordering still holds BELOW the cap",
      C.decide("mcap_1m", {"exit_depth_at_crossing": 2_000.0})[2]
      < C.decide("mcap_1m", {"exit_depth_at_crossing": 8_000.0})[2])
check("⚠️ the amendment is recorded in the pre-commit, not edited in "
      "silently",
      "AMENDMENT" in PRE and "711,654" in PRE and "SIG_CAP" in PRE)

# BUG 2: the top row of the real 24h sample was symbolled with U+202E. The alert
# put the raw symbol in its message, so it would have named a token it is not.
_BIDI_SYM = chr(0x202E) + "TACZ"
check("⛔⛔ a bidi override is STRIPPED from the alert text",
      chr(0x202E) not in C.safe_symbol(_BIDI_SYM), C.safe_symbol(_BIDI_SYM))
check("⛔ and its removal is NAMED, never silent",
      "BIDI" in C.safe_symbol(_BIDI_SYM))
check("⛔ Cyrillic inside a Latin symbol is named too",
      "MIXED-SCRIPT" in C.safe_symbol("USD" + chr(0x0421)))
check("⭐ an ordinary symbol passes through untouched",
      C.safe_symbol("VSOF") == "VSOF")
check("⛔ an absent symbol reads `unknown`, never blank (rule 5)",
      C.safe_symbol(None) == "unknown" and C.safe_symbol("") == "unknown")

SENT_B = []
C.reset()
C.on_milestone("BidiAlertMint5555555555555555555555555555", "mcap_1m",
               {"symbol": _BIDI_SYM, "value": 1_500_000.0,
                "exit_depth_at_crossing": 5_000.0},
               record=lambda *a, **k: SENT_B.append((a, k)))
_txt = json.dumps(SENT_B, ensure_ascii=False)
check("⛔⛔ END TO END: no bidi control reaches the emitted finding",
      chr(0x202E) not in _txt, "found U+202E in the emitted text")
check("⛔ ...and the warning travels with it",
      "BIDI" in _txt)

# ⚠️ The message text is plain, not HTML - an alert is not a web page.
check("⚠️ safe_symbol returns PLAIN TEXT, not HTML like "
      "dashboard.safe_sym does",
      "<span" not in C.safe_symbol(_BIDI_SYM)
      and C.safe_symbol("A&B") == "A&B",
      C.safe_symbol("A&B"))


# ---------------------------------------------------------------------------
section("3. what on_milestone actually emits, captured")

SENT = []


def fake_record(kind, key, msg, detail=None, significance=None, **kw):
    SENT.append({"kind": kind, "key": key, "msg": msg, "detail": detail,
                 "significance": significance, **kw})
    return True


TOK = "CrossAlertTestMint1111111111111111111111111"
C.reset()
SENT.clear()
act = C.on_milestone(TOK, "mcap_1m",
                     {"symbol": "TESTCOIN", "value": 1_234_567.0,
                      "exit_depth_at_crossing": 4321.0,
                      "exit_pair_at_crossing": "PoolAddr123"},
                     record=fake_record)
check("⭐ a crossing over the bar ALERTS", act == C.ALERT, act)
check("⭐ exactly one finding was emitted", len(SENT) == 1, str(len(SENT)))
f = SENT[0] if SENT else {}
check("⛔⛔ the finding is KEYED ON THE CONTRACT ADDRESS, not the ticker",
      f.get("key") == TOK, str(f.get("key")))
check("⛔ and the symbol appears nowhere in the key",
      "TESTCOIN" not in str(f.get("key")))
check("⭐ the kind is mcap-crossing", f.get("kind") == "mcap-crossing")
check("⭐ the message states the depth that was measured",
      "4,321" in (f.get("msg") or ""), f.get("msg"))
check("⛔⛔ it says IN WORDS that this is not a sell quote",
      "NOT A SELL QUOTE" in (f.get("detail") or "").upper())
check("⛔ it says most crossings are never announced, so silence is not a bug",
      "75%" in (f.get("detail") or ""))
check("⛔ it refuses to claim anything forward-looking (Marino)",
      "says nothing about what happens next" in (f.get("detail") or ""))
check("⭐ the detail carries the contract address in full",
      TOK in (f.get("detail") or ""))
check("⭐ significance is 4.321, so it outranks a 3x in its own lane",
      f.get("significance") == 4.321, str(f.get("significance")))

for ms, meta in [("mcap_1m", {"symbol": "THIN", "exit_depth_at_crossing": 12.0}),
                 ("mcap_1m", {"symbol": "UNK", "exit_depth_at_crossing": None}),
                 ("mcap_100k", {"symbol": "SMALL",
                                "exit_depth_at_crossing": 99_000.0})]:
    SENT.clear()
    C.on_milestone(TOK, ms, meta, record=fake_record)
    check(f"⛔ {ms} / depth {meta.get('exit_depth_at_crossing')} emits NOTHING",
          not SENT, str(SENT))

check("⭐ and every one of those decisions was still COUNTED",
      C.LAST["evaluated"] == 4
      and C.LAST[C.ALERT] == 1 and C.LAST[C.SILENT_THIN] == 1
      and C.LAST[C.SILENT_UNMEASURED] == 1 and C.LAST[C.NOT_A_CROSSING] == 1,
      json.dumps(C.LAST))

BEATS = []
C.beat(beat_fn=lambda name, n=None, detail=None: BEATS.append((name, n, detail)))
check("⛔ the beat counts DECISIONS, not alerts",
      BEATS and BEATS[0][0] == "crossing.decisions" and BEATS[0][1] == 4,
      str(BEATS))
check("⭐ and its detail breaks the silences out",
      BEATS and "thin=1" in BEATS[0][2] and "unmeasured=1" in BEATS[0][2],
      str(BEATS))

# ⛔ A raising findings.record must not take the pass down with it.
C.reset()


def boom(*a, **k):
    raise RuntimeError("discord is down")


check("⛔ a failing announcement is non-fatal and still returns ALERT",
      C.on_milestone(TOK, "mcap_1m",
                     {"symbol": "X", "exit_depth_at_crossing": 5000.0},
                     record=boom) == C.ALERT)


# ---------------------------------------------------------------------------
section("4. the lane, its budget and its liveness row")

check("⭐ mcap-crossing lands in its OWN lane",
      findings.lane_of("mcap-crossing") == "crossing",
      findings.lane_of("mcap-crossing"))
check("⛔ so a crossing storm cannot exhaust the outcome lane",
      findings.LANE_BUDGET.get("crossing") is not None
      and findings.lane_of("outcome-win") == "outcome")
check("⭐ the crossing budget is 3 an hour",
      findings.LANE_BUDGET["crossing"] == 3,
      str(findings.LANE_BUDGET.get("crossing")))
check("⛔ crossing.decisions is a DECLARED liveness component",
      "crossing.decisions" in liveness.COMPONENTS,
      str(sorted(liveness.COMPONENTS))[:120])

# ⛔ test_stages.py matches components against `beat("literal")` at the AST
# level, so a name reached through a variable is invisible to it. Assert the
# literal is really there, in a call spelled beat(...).
CSRC = io.open(os.path.join(HERE, "crossingalert.py"), encoding="utf-8").read()
_lit = [n for n in ast.walk(ast.parse(CSRC))
        if isinstance(n, ast.Call)
        and (getattr(n.func, "attr", None) == "beat"
             or getattr(n.func, "id", None) == "beat")
        and n.args and isinstance(n.args[0], ast.Constant)
        and n.args[0].value == "crossing.decisions"]
check("⛔ the component name is a LITERAL inside a beat() call",
      len(_lit) >= 1, f"found {len(_lit)}")
# ⚠️ And the OTHER call site, the injected one, is deliberately NOT
# detectable this way - `beat_fn(...)` reaches the name through a variable. That
# is fine because the injected path is only used by tests; what matters is that
# the PRODUCTION path is a literal, which is what the assertion above pins.
check("⚠️ the injected beat_fn path is the test-only one",
      "beat_fn(" in CSRC and "liveness.beat(" in CSRC)


# ---------------------------------------------------------------------------
section("5. ⛔⛔ END TO END: record_outcome FIRES it. Output, not execution.")

FIRED = []
SENT.clear()
TOK2 = "CrossAlertEndToEndMint2222222222222222222222"
PAIR2 = "CrossAlertEndToEndPair2222222222222222222222"

# A crossing with real depth: mcap over $1M, exit depth over the bar. The depth
# journal writes onto the claim is the one IT measured, so it is passed in.
st, mult, ok, failed = journal.record_outcome(
    PAIR2, time.time() - 3700, 1, price=2.0, liq=60_000.0, vol24=9_000.0,
    base_price=1.0, base_liq=50_000.0, symbol="E2ECOIN", token=TOK2,
    exit_depth=7_500.0, mcap=2_500_000.0,
    on_milestone=lambda tk, name, meta: (
        FIRED.append((tk, name, meta)),
        C.on_milestone(tk, name, meta, record=fake_record)))

check("⭐ record_outcome CALLED the milestone callback",
      bool(FIRED), str(FIRED)[:100])
names = [n for _t, n, _m in FIRED]
check("⭐ and it fired for every tier newly crossed",
      "mcap_1m" in names and "mcap_100k" in names, str(names))
check("⛔ the callback received the CONTRACT ADDRESS, not the pair",
      all(t == TOK2 for t, _n, _m in FIRED), str([t for t, _n, _m in FIRED]))
check("⭐ the meta it received carries the depth measured in that same call",
      all(m.get("exit_depth_at_crossing") == 7_500.0 for _t, _n, m in FIRED),
      str([m.get("exit_depth_at_crossing") for _t, _n, m in FIRED]))

_crossings = [s for s in SENT if s["kind"] == "mcap-crossing"]
check("⛔⛔ AND A REAL ALERT CAME OUT OF IT",
      len(_crossings) == 1, f"{len(_crossings)} emitted: {[s['key'] for s in _crossings]}")
check("⭐ once, for mcap_1m only - 100k and 200k stayed silent",
      _crossings and "mcap_1m" in (_crossings[0]["detail"] or ""))
check("⭐ keyed on the address end to end",
      _crossings and _crossings[0]["key"] == TOK2)

# The second identical call must be silent: the O_EXCL claim already exists.
FIRED.clear()
SENT.clear()
journal.record_outcome(
    PAIR2 + "b", time.time() - 3700, 1, price=2.0, liq=60_000.0, vol24=9_000.0,
    base_price=1.0, base_liq=50_000.0, symbol="E2ECOIN", token=TOK2,
    exit_depth=7_500.0, mcap=2_500_000.0,
    on_milestone=lambda tk, name, meta: (
        FIRED.append((tk, name, meta)),
        C.on_milestone(tk, name, meta, record=fake_record)))
check("⛔⛔ the SAME contract crossing again announces NOTHING - the O_EXCL "
      "claim is the dedupe, not a convention",
      not FIRED and not SENT, f"fired {FIRED}, sent {[s['key'] for s in SENT]}")

# A thin crossing must reach the callback and produce no finding.
FIRED.clear()
SENT.clear()
TOK3 = "CrossAlertThinMint333333333333333333333333"
journal.record_outcome(
    "CrossAlertThinPair3333333333333333333333333", time.time() - 3700, 1,
    price=2.0, liq=60_000.0, vol24=9_000.0, base_price=1.0, base_liq=50_000.0,
    symbol="THINCOIN", token=TOK3, exit_depth=4.0, mcap=2_500_000.0,
    on_milestone=lambda tk, name, meta: (
        FIRED.append((tk, name, meta)),
        C.on_milestone(tk, name, meta, record=fake_record)))
check("⭐ a THIN $2.5M crossing is evaluated...", bool(FIRED))
check("⛔ ...and announces nothing at all",
      not [s for s in SENT if s["kind"] == "mcap-crossing"],
      str([s["key"] for s in SENT]))

# ⛔ A raising callback must never lose a claim that is already on disk.
_before = len(milestones.crossings("mcap_1m"))
journal.record_outcome(
    "CrossAlertRaisePair44444444444444444444444", time.time() - 3700, 1,
    price=2.0, liq=60_000.0, vol24=9_000.0, base_price=1.0, base_liq=50_000.0,
    symbol="RAISECOIN", token="CrossAlertRaiseMint44444444444444444444444",
    exit_depth=9_000.0, mcap=2_500_000.0,
    on_milestone=lambda *a: (_ for _ in ()).throw(RuntimeError("callback boom")))
check("⛔ a RAISING callback does not lose the claim or kill the row",
      len(milestones.crossings("mcap_1m")) == _before + 1,
      f"{_before} -> {len(milestones.crossings('mcap_1m'))}")


# ---------------------------------------------------------------------------
section("6. ⛔ the standing guarantees, at the AST level")

TREE = ast.parse(CSRC)
_names = []
for n in ast.walk(TREE):
    nm = getattr(n, "attr", None) or getattr(n, "id", None)
    if isinstance(n, (ast.FunctionDef, ast.AsyncFunctionDef)):
        nm = n.name
    if nm and any(b in nm.lower() for b in
                  ("score", "grade", "rank", "rating", "prediction",
                   "expected_return")):
        _names.append(f"{nm}:{getattr(n, 'lineno', '?')}")
check("⛔ no score, grade, rank or prediction term anywhere in the lane",
      not _names, ", ".join(_names))

# Standing rule 2, and it is the bug that silenced six BASKET contracts.
_fallback = []
for n in ast.walk(TREE):
    if isinstance(n, ast.BoolOp) and isinstance(n.op, ast.Or):
        txt = ast.unparse(n)
        if "symbol" in txt and "token" in txt:
            _fallback.append(txt[:70])
check("⛔⛔ no `token or symbol` fallback: a findings key can never be a ticker",
      not _fallback, "; ".join(_fallback))

# ⚠️ Checked on the AST, not on the unparsed TEXT: the docstring says the
# word "import" and a substring test passed on the docstring instead of the code.
_decide = [f for f in TREE.body
           if isinstance(f, ast.FunctionDef) and f.name == "decide"][0]
_imports = [ast.unparse(n) for n in ast.walk(_decide)
            if isinstance(n, (ast.Import, ast.ImportFrom))]
check("⭐ decide() is pure - no import statement anywhere inside it",
      not _imports, "; ".join(_imports))
_opens = [ast.unparse(n) for n in ast.walk(_decide)
          if isinstance(n, ast.Call)
          and getattr(n.func, "id", None) in ("open", "print")]
check("⭐ decide() opens no file and prints nothing - it only decides",
      not _opens, "; ".join(_opens))


# ---------------------------------------------------------------------------
print()
failed = [n for n, ok_ in R if not ok_]
print(f"{len(R) - len(failed)}/{len(R)} passed")
for n in failed:
    print("  FAILED:", n)
sys.exit(1 if failed else 0)
