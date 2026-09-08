"""Assert that every field a feature computes actually lands in storage.

WHY. Three silent-drop bugs in two days, all the same shape:

    2026-09-06  vol_to_liq / vol_burst   computed in scanner.scan(), never
                                         added to journal.record()'s whitelist.
                                         Silently discarded for a full day.
    2026-09-06  news freshness check     wired into main(), which has no
                                         `verbose` local. NameError on every
                                         pass; the check never ran.
    2026-09-07  mint / freeze authority  computed on every actionable row,
                                         never added to the whitelist.

A FIELD COMPUTED AND NOT PERSISTED IS A FIELD THAT DOES NOT EXIST. The cost is
not the missing column, it is that analysis proceeds against data it believes is
there, and nobody finds out until someone spot-checks by hand. Two of the three
above were caught by a human noticing; the third by luck.

`journal.record()` builds an explicit whitelist dict. That is the right design -
an accidental passthrough of everything would let junk into the archive - but it
means adding a field to a computation and forgetting the whitelist is a silent
loss rather than an error. This module closes that gap: it diffs what the
scanner PRODUCES against what the journal PERSISTS and fails on anything that
falls between.

DELIBERATELY NOT PERSISTED fields are listed explicitly in TRANSIENT, so
"not stored" is always a decision someone wrote down rather than an oversight.
"""
import json
import os

# Fields the scanner produces that are intentionally NOT journalled. Each needs
# a reason, because the whole point is that omission must be deliberate.
TRANSIENT = {
    "url",              # reconstructible from the pair address
    "addr",             # journalled as `token`
    "name",             # journalled as `symbol`
    "v24",              # journalled as `vol_h24`
    "age_h",            # journalled as `age_hours`
    "gt_dex",           # provenance of dex_id; dex_id is what matters
    "gates",            # per-gate booleans, superseded by `reasons`/`flags`
    "paper_entry",      # a hash into the paper ledger, not an observation fact
    "watchlisted",      # membership lives in data/watchlist, not the journal
    "liquidity_plausible", "template_suspect", "liq_to_fdv_ratio",
    "integrity_flags",  # all four are DERIVED ON READ by plausibility.annotate
    "venue", "is_graduated",   # venue.annotate re-derives these on read
}

# Renames: scanner key -> journal key. Listed so a rename is not mistaken for
# a drop.
RENAMED = {"addr": "token", "name": "symbol", "v24": "vol_h24", "age_h": "age_hours"}


def journal_fields():
    """The keys journal.record() actually writes, read from the source itself
    rather than from a second list that could drift out of step."""
    import journal
    import inspect
    src = inspect.getsource(journal.record)
    keys = set()
    # the whitelist literal plus every obj["..."] = assignment after it
    for tok in src.split('"'):
        pass
    import re
    for m in re.finditer(r'"([a-z_0-9]+)"\s*:', src):
        keys.add(m.group(1))
    for m in re.finditer(r'obj\[\s*"([a-z_0-9]+)"\s*\]\s*=', src):
        keys.add(m.group(1))
    return keys


def _fields_of(fn):
    """The keys a writer actually persists, read from its own source."""
    import inspect
    import re
    src = inspect.getsource(fn)
    keys = set()
    for m in re.finditer(r'"([a-z_0-9]+)"\s*:', src):
        keys.add(m.group(1))
    for m in re.finditer(r'obj\[\s*"([a-z_0-9]+)"\s*\]\s*=', src):
        keys.add(m.group(1))
    return keys


def outcome_fields():
    """The keys journal.record_outcome() persists.

    THIS GUARD DID NOT EXIST, AND THAT IS WHY THE FIFTH DROP SURVIVED.
    fieldguard covered journal.record() - observations - and nothing covered
    record_outcome(). `token` was accepted as an argument, used to key
    milestones, and never written: 0 of 88,235 outcome rows carried a contract
    address, so no outcome row on the record could obey the standing rule to
    key on contract address rather than ticker. A guard aimed at one of two
    writers is not a guard, it is a reason to believe you have one.
    """
    import journal
    return _fields_of(journal.record_outcome)


def check_outcome(row):
    """Diff a produced outcome row against what record_outcome persists."""
    produced = {k for k, v in row.items() if v is not None}
    dropped = produced - outcome_fields() - TRANSIENT
    return (not dropped), sorted(dropped)


def check(row, strict=True):
    """Diff one produced row against what the journal persists.

    Returns (ok, dropped). `dropped` is the set of computed fields that would
    be silently discarded.
    """
    produced = {k for k, v in row.items() if v is not None}
    persisted = journal_fields()
    dropped = produced - persisted - TRANSIENT
    return (not dropped), sorted(dropped)


def assert_row(row, verbose=True):
    """Fail LOUDLY. Called once per pass with a real scanned row."""
    ok, dropped = check(row)
    if not ok:
        msg = ("FIELD GUARD: the scanner computes fields the journal does not "
               f"persist: {dropped}. A field computed and not persisted is a "
               "field that does not exist. Add them to journal.record()'s "
               "whitelist, or to fieldguard.TRANSIENT with a reason.")
        raise AssertionError(msg)
    if verbose:
        print(f"  field guard: {len(row)} computed fields, all persisted or "
              f"declared transient")
    return True


if __name__ == "__main__":
    import sys
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    import journal
    obs = journal.observations()
    if not obs:
        print("no observations to check against")
        sys.exit(0)
    # Check the WIDEST row we have - the one with the most fields set - since a
    # sparse row cannot reveal a missing column.
    widest = max(obs, key=lambda o: sum(1 for v in o.values() if v is not None))
    print(f"journal persists {len(journal_fields())} distinct keys")
    print(f"widest stored observation carries {sum(1 for v in widest.values() if v is not None)}")
    import scanner
    print("\nrunning a live scan to diff produced vs persisted...")
    rows = scanner.scan("solana", pages=1, verbose=False, budget_s=90)
    if not rows:
        print("  no rows scanned")
        sys.exit(0)
    w = max(rows, key=lambda r: sum(1 for v in r.values() if v is not None))
    ok, dropped = check(w)
    print(f"  widest scanned row: {sum(1 for v in w.values() if v is not None)} fields set")
    if ok:
        print("  OK - every computed field is persisted or declared transient")
    else:
        print(f"  DROPPED SILENTLY: {dropped}")
        sys.exit(1)
