"""Redirect every module-level data path into a temp dir. Import FIRST in a test.

⛔ WHY THIS EXISTS. On 2026-09-18 a full suite run appended 24 rows to
`data/liveness/2026-09.jsonl` and 3 to `data/findings/2026-09-18.md`. The tests
were redirecting the one state file each case was about to rewrite and leaving
every other output path pointed at the real journal.

That is not untidiness. `liveness` is the thing that answers "is the collector
alive", so a suite that beats it makes the health signal partly a record of
*running the tests*. Standing rule 8 means the rows already committed stay; the
fix is that no future run adds more. Same family as standing rules 13/14 - the
instrument was changing the thing it measured.

⚠️ This is best-effort by design: it redirects what exists and ignores what does
not, so adding a module does not break every suite. The real enforcement is
`run_tests.py`, which hashes `data/` before and after and FAILS if it changed -
an assertion on the OUTPUT, not on whether this file was imported.
"""
import importlib
import os
import tempfile

ROOT = None

# module -> attributes holding a path. A directory attr gets a directory; a
# file attr gets a file path inside the sandbox, keeping its basename so any
# code that parses the name still works.
_PATHS = {
    "findings":   ["DIR", "SEEN", "BUDGET_FILE"],
    "liveness":   ["REG", "LEDGER_DIR"],
    "journal":    ["OBS", "OUT", "COV", "PASS_STATE", "HEARTBEAT"],
    "paper":      ["LOG_DIR", "LEDGER"],
    "paperv2":    ["LEDGER"],
    "paperv3":    ["LEDGER"],
    "watchlist":  ["DIR", "ACTIVE", "LEDGER", "RETIRED"],
    "wallets":    ["WATCHLIST"],
    "milestones": ["DIR", "CLAIMS"],
    "resolve":    ["SRC_LOG"],
    "scanner":    ["CARRY_PATH"],
    "tokens":     ["CACHE"],
    "tickers":    ["IDX"],
    "dashboard":  ["OUT"],
    "chainfields": ["USAGE_PATH"],
    "pricecheck": ["QUARANTINE", "QUARANTINE_LOG"],
    "market":     ["OUT_DIR", "HISTORY_DIR"],
    "universe":   ["OUT_DIR", "EVENTS_DIR", "HISTORY_DIR"],
    "graduations": ["DIR"],
}


def activate(root=None):
    """Point every known data path at a temp tree. Returns the root."""
    global ROOT
    ROOT = root or tempfile.mkdtemp(prefix="crypto-test-")
    for modname, attrs in _PATHS.items():
        try:
            m = importlib.import_module(modname)
        except Exception:
            continue                      # optional dependency, or a live-only module
        for a in attrs:
            cur = getattr(m, a, None)
            if not isinstance(cur, str):
                continue
            base = os.path.basename(cur.rstrip("/\\")) or a.lower()
            dest = os.path.join(ROOT, modname, base)
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            # A path with no extension is a directory in every case above.
            if not os.path.splitext(base)[1]:
                os.makedirs(dest, exist_ok=True)
            setattr(m, a, dest)
    return ROOT
