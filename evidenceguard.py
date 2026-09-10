"""A check's EXECUTION must never be conditional on another check's OUTPUT.

THE BUG CLASS, found 2026-09-10 at scanner.py:273 and named here so it can be
swept for by machine rather than remembered.

    _act = (row.get("score", 0) >= 70) or paper.qualifies(row)[0]
    if _act:
        row["can_mint"] = onchain.authorities(addr)["can_mint"]   # EVIDENCE

`qualifies()` fails closed when can_mint is None. So a low score suppressed the
lookup, the missing field then read as "unverified contract", and the token was
rejected for lack of evidence we had declined to gather. 328 of 457 known false
negatives scored 0-44: not a fact about those tokens, the mechanism describing
itself. 91.8% of them had both authorities revoked all along.

WHY THIS IS WORSE THAN A BARE EXCEPT. The absence-of-evidence family corrupts
VALUES - a read fails and a default stands in. This family corrupts LABELS: the
verdict determines what gets measured, so the measurement can only ever agree
with the verdict. It is a self-fulfilling prophecy with a data pipeline.

WHAT COUNTS AS A HIT: an `if`/ternary/boolean guard whose test reads a verdict
(score, passed, ok, qualifies, flags, suspect, ...) and whose body gathers
evidence (a network or chain call, or an assignment of a field other code will
later read as a fact).

Not every hit is a bug. Gating an ALERT, a WRITE, or an ANNOUNCEMENT on a
verdict is correct and expected - that is a decision acting on a decision. Only
gating MEASUREMENT is the defect. The report separates them; the judgement is
still a human's.

Run: python evidenceguard.py            (offline, reads source only)
"""
import ast
import io
import os
import sys

SCAN_PATH = ["scanner.py", "collect.py", "track.py", "paper.py", "journal.py",
             "pricecheck.py", "onchain.py", "resolve.py", "milestones.py",
             "watchlist.py", "namecheck.py", "detector.py", "venue.py",
             "clusters.py", "findings.py", "check.py", "dashboard.py",
             "onchain_reserves.py", "sources.py"]

# Names that carry a VERDICT rather than a measurement.
VERDICT = {"score", "passed", "qualifies", "qualified", "ok", "realizable",
           "gate", "gate_ok", "gates", "flags", "suspect", "template_suspect",
           "quarantined", "valid", "approved", "eligible", "act", "_act",
           "impersonation", "blocked", "rejected", "conclusive", "is_win",
           "AUTHORITY_CHECK_SCORE", "SCORE_LO", "SCORE_HI", "MIN_SCORE"}

# Modules whose calls fetch evidence from outside the process.
FETCHERS = {"onchain", "sources", "S", "resolve", "pricecheck", "requests",
            "urllib", "onchain_reserves"}
BUDGET = {"over_budget", "seconds_left", "budget", "CALL_BUDGET", "DEADLINE",
          "SCAN_BUDGET_S", "limit", "STAGE_SECONDS", "elapsed", "deadline",
          "CALLS", "max_calls", "max_seconds"}

FETCH_FNS = {"authorities", "reserves", "dexscreener_pair", "dexscreener_token",
             "new_pools", "trending_pools", "sol_signatures", "validate",
             "_get", "_post", "urlopen", "token_supply", "holders"}


def _names(node):
    out = set()
    for n in ast.walk(node):
        if isinstance(n, ast.Name):
            out.add(n.id)
        elif isinstance(n, ast.Attribute):
            out.add(n.attr)
        elif isinstance(n, ast.Constant) and isinstance(n.value, str):
            out.add(n.value)
    return out


def _enclosing(tree, node):
    """The function containing `node`, for resolving where a gate came from."""
    best = None
    for fn in ast.walk(tree):
        if isinstance(fn, (ast.FunctionDef, ast.AsyncFunctionDef)):
            if fn.lineno <= node.lineno <= (fn.end_lineno or fn.lineno):
                if best is None or fn.lineno > best.lineno:
                    best = fn
    return best


def _resolve(tree, node, names):
    """Follow local assignments so a gate is judged by its DERIVATION.

    `_act = paper.wants_authority_check(row)` reads as a verdict by its name
    alone, but nothing in how it is computed touches one. A gate is clean when
    no verdict appears anywhere in what produced it - that is a real chain of
    evidence, not a suppression list.
    """
    scope = _enclosing(tree, node) or tree
    resolved = set(names)
    for _ in range(4):                      # follow a short chain, not forever
        grew = False
        for a in ast.walk(scope):
            if not isinstance(a, ast.Assign):
                continue
            # A record is not a verdict. Following `row = dict(score=..., ...)`
            # would drag every field name in and flag the whole file.
            if isinstance(a.value, ast.Dict) or (
                    isinstance(a.value, ast.Call)
                    and isinstance(a.value.func, ast.Name)
                    and a.value.func.id == "dict"):
                continue
            for t in a.targets:
                if isinstance(t, ast.Name) and t.id in resolved:
                    new = _names(a.value)
                    if not new <= resolved:
                        resolved |= new
                        resolved.discard(t.id)
                        grew = True
        if not grew:
            break
    return resolved


def _evidence_in(node):
    """Calls that gather evidence, and fields assigned from them."""
    hits = []
    for n in ast.walk(node):
        if isinstance(n, ast.Call):
            f = n.func
            if isinstance(f, ast.Attribute):
                mod = getattr(f.value, "id", None)
                if mod in FETCHERS or f.attr in FETCH_FNS:
                    hits.append(f"{mod + '.' if mod else ''}{f.attr}()")
            elif isinstance(f, ast.Name) and f.id in FETCH_FNS:
                hits.append(f"{f.id}()")
    return hits


def _skips(node):
    """`continue` / `return` / `break` - control flow that SKIPS what follows."""
    return [n for n in ast.walk(node)
            if isinstance(n, (ast.Continue, ast.Break, ast.Return))]


def audit_skips(paths=None):
    """The same defect wearing an early exit.

        for row in rows:
            if row["score"] < 70:
                continue                 # <- skips everything below
            row["can_mint"] = onchain.authorities(...)

    Identical corruption, no `if fetch()` to grep for. Also catches BUDGET
    skips, which are not verdicts but produce the same corrupted label: a token
    left unmeasured because the pass ran out of seconds is indistinguishable
    downstream from one that was measured and failed.
    """
    out = []
    for path in (paths or SCAN_PATH):
        if not os.path.exists(path):
            continue
        src = io.open(path, encoding="utf-8").read()
        lines = src.splitlines()
        for loop in ast.walk(ast.parse(src)):
            if not isinstance(loop, (ast.For, ast.While)):
                continue
            for i, stmt in enumerate(loop.body):
                if not isinstance(stmt, ast.If) or not _skips(stmt):
                    continue
                tree_ = ast.parse(src)
                tnames = _resolve(tree_, stmt, _names(stmt.test))
                verdicts = tnames & VERDICT
                budget = tnames & BUDGET
                if not (verdicts or budget):
                    continue
                ev = []
                for later in loop.body[i + 1:]:
                    ev += _evidence_in(later)
                if not ev:
                    continue
                out.append({
                    "file": path, "line": stmt.lineno,
                    "kind": "VERDICT" if verdicts else "BUDGET",
                    "gated_by": sorted(verdicts or budget),
                    "skips": sorted(set(ev)),
                    "source": lines[stmt.lineno - 1].strip()[:96],
                })
    return out


def audit(paths=None):
    findings = []
    for path in (paths or SCAN_PATH):
        if not os.path.exists(path):
            continue
        src = io.open(path, encoding="utf-8").read()
        tree = ast.parse(src)
        lines = src.splitlines()
        for node in ast.walk(tree):
            tests = []
            body = []
            if isinstance(node, ast.If):
                tests = [node.test]
                body = list(node.body)
            elif isinstance(node, ast.IfExp):
                tests = [node.test]
                body = [node.body]
            elif isinstance(node, ast.BoolOp):
                # `A and fetch()` - the fetch only runs if A held
                if isinstance(node.op, ast.And) and len(node.values) > 1:
                    tests = [node.values[0]]
                    body = node.values[1:]
            if not tests or not body:
                continue
            tnames = set()
            for t in tests:
                tnames |= _names(t)
            verdicts = _resolve(tree, node, tnames) & VERDICT
            if not verdicts:
                continue
            ev = []
            for b in body:
                ev += _evidence_in(b)
            if not ev:
                continue
            findings.append({
                "file": path, "line": node.lineno,
                "verdict": sorted(verdicts), "evidence": sorted(set(ev)),
                "source": (lines[node.lineno - 1].strip()[:96]
                           if node.lineno <= len(lines) else ""),
            })
    return findings


if __name__ == "__main__":
    fs = audit()
    print("=" * 74)
    print("EVIDENCE GATED ON A VERDICT - candidate sites")
    print("=" * 74)
    if not fs:
        print("  none")
    for f in fs:
        print(f"\n  {f['file']}:{f['line']}")
        print(f"    gated by : {', '.join(f['verdict'])}")
        print(f"    gathers  : {', '.join(f['evidence'])}")
        print(f"    source   : {f['source']}")
    print(f"\n{len(fs)} candidate site(s). Gating an alert or a write on a verdict")
    print("is correct; only gating a MEASUREMENT is the defect. Triage each.")
    sk = audit_skips()
    print()
    print("=" * 74)
    print("EVIDENCE SKIPPED BY AN EARLY EXIT - same defect, no `if fetch()`")
    print("=" * 74)
    if not sk:
        print("  none")
    for f in sk:
        print("")
        print("  [" + f["kind"] + "] " + f["file"] + ":" + str(f["line"]))
        print("    gated by : " + ", ".join(f["gated_by"]))
        print("    skips    : " + ", ".join(f["skips"]))
        print("    source   : " + f["source"])
    print("")
    print(str(len(fs)) + " gated call site(s), " + str(len(sk)) + " early-exit site(s).")
    sys.exit(0)
