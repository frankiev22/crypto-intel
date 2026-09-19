"""The graduation ledger accounts for every signature and never skips one.
Run: python test_graduations.py      (offline - the RPC is a canned chain)

⛔ Assertions are on the LEDGER ROWS and cursor written to disk. A cursor that
advanced past a signature nobody recorded is a hole that nothing downstream can
see, which is the silent-truncation failure of standing rule 15.
"""
import json
import os
import sys
import types

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import testsandbox
ROOT = testsandbox.activate()

import graduations as G
import liveness

R = []


def check(name, cond, detail=""):
    R.append((name, bool(cond)))
    print(f"  {'PASS' if cond else 'FAIL'}  {name}" + (f"  [{detail}]" if detail else ""))


def section(t):
    print()
    print("=" * 70)
    print(t)
    print("=" * 70)


# A fake clock: every getTransaction costs exactly one second, so a budget of
# N seconds processes exactly N signatures - no timing flake.
CLOCK = {"t": 1_789_000_000.0}
G.time = types.SimpleNamespace(time=lambda: CLOCK["t"], sleep=lambda s: None)
G._gap = lambda: 0

T0 = 1_789_000_000
# The chain, newest LAST. Each: sig, blockTime, err, and the tx it resolves to.
CHAIN = []


def add(i, kind="grad", err=None):
    sig = f"sig{i:05d}"
    mint = f"Mint{i:05d}" + "x" * 35 + "pump"
    if kind == "grad":
        tx = {"blockTime": T0 + i, "meta": {"logMessages": ["Program log: Instruction: CreatePool",
                                                             "Program log: Instruction: MigrateV2"],
                                            "preTokenBalances": [{"mint": mint}, {"mint": G.WSOL}]}}
    elif kind == "noop":
        tx = {"blockTime": T0 + i, "meta": {"logMessages": ["Program log: Instruction: MigrateV2"],
                                            "preTokenBalances": [{"mint": mint}]}}
    else:  # two mints
        tx = {"blockTime": T0 + i, "meta": {"logMessages": ["Program log: Instruction: CreatePool"],
                                            "preTokenBalances": [{"mint": mint}, {"mint": "Other" + mint[5:]}]}}
    CHAIN.append({"signature": sig, "blockTime": T0 + i, "err": err, "tx": tx, "mint": mint})


for i in range(10):
    add(i, "noop" if i == 3 else ("two" if i == 5 else "grad"), err={"x": 1} if i == 7 else None)
FAIL_ONCE = {"sig00004"}


def fake_rpc(method, params, tries=3):
    if method == "getSignaturesForAddress":
        opts = params[1]
        newest_first = list(reversed(CHAIN))
        if opts.get("until"):
            cut = next(i for i, x in enumerate(newest_first) if x["signature"] == opts["until"])
            newest_first = newest_first[:cut]
        if opts.get("before"):
            cut = next(i for i, x in enumerate(newest_first) if x["signature"] == opts["before"])
            newest_first = newest_first[cut + 1:]
        return [{"signature": x["signature"], "blockTime": x["blockTime"], "err": x["err"]}
                for x in newest_first[:opts["limit"]]], None
    if method == "getTransaction":
        CLOCK["t"] += 1
        sig = params[0]
        if sig in FAIL_ONCE:
            FAIL_ONCE.discard(sig)
            return None, "URLError"
        return next(x["tx"] for x in CHAIN if x["signature"] == sig), None
    raise AssertionError(method)


REAL_RPC = G.rpc
G.rpc = fake_rpc


def ledger():
    out = []
    for n in sorted(os.listdir(G.DIR)):
        if n[:4].isdigit() and n.endswith(".jsonl"):
            with open(os.path.join(G.DIR, n), encoding="utf-8") as f:
                out += [json.loads(l) for l in f if l.strip()]
    return out


def cursor():
    with open(os.path.join(G.DIR, "cursor.json"), encoding="utf-8") as f:
        return json.load(f)


section("1. classify: the instruction and the mint decide, nothing else")
k = [G.classify(x["tx"])[0] for x in CHAIN]
check("CreatePool + one non-SOL mint -> graduation", k[0] == "graduation")
check("the authority's no-op race tx -> not_target, never a graduation", k[3] == "not_target")
check("⛔ two mints -> ambiguous, never guessed", k[5] == "ambiguous" and G.classify(CHAIN[5]["tx"])[1] is None)
usdc_tx = {"meta": {"logMessages": ["Program log: Instruction: CreatePool"],
                    "preTokenBalances": [{"mint": "PumpMintAbc" + "x" * 29 + "pump"}, {"mint": G.USDC}]}}
check("a USDC-quoted pool is a graduation of the OTHER mint - USDC is a quote, like SOL",
      G.classify(usdc_tx)[:2] == ("graduation", "PumpMintAbc" + "x" * 29 + "pump"))

section("1b. an RPC error is an answer; a transport error is retried")
import io
import urllib.error
_calls = {"n": 0}


class _Resp(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _urlopen_rpc_error(req, timeout=None):
    _calls["n"] += 1
    return _Resp(json.dumps({"jsonrpc": "2.0", "id": 1, "error": {
        "code": -32015, "message": "Transaction version (1) is not supported"}}).encode())


def _urlopen_down(req, timeout=None):
    _calls["n"] += 1
    raise urllib.error.URLError("down")


_real_urlopen = G.urllib.request.urlopen
G.urllib.request.urlopen = _urlopen_rpc_error
res, err = REAL_RPC("getTransaction", ["x", {}])
check("⛔ a -32015 comes back once, not retried three times",
      res is None and _calls["n"] == 1 and "-32015" in err, (_calls, err))
_calls["n"] = 0
G.urllib.request.urlopen = _urlopen_down
res, err = REAL_RPC("getTransaction", ["x", {}])
check("a transport failure is retried, then reported", res is None and _calls["n"] == 3 and err, (_calls, err))
G.urllib.request.urlopen = _real_urlopen
src = open(G.__file__, encoding="utf-8").read()
check("⛔ transactions are requested at version 1 (5% of the stream is v1)",
      '"maxSupportedTransactionVersion": 1' in src and '"maxSupportedTransactionVersion": 0' not in src)

section("2. first run, cut by the budget: processed oldest-first, the rest owed")
m1 = G.build(verbose=False, now=T0 + 20, seconds=4)
rows = ledger()
check("exactly 4 processed on a 4-second budget", m1["processed"] == 4, m1["processed"])
check("oldest first: the ledger starts at the oldest signature",
      [r["sig"] for r in rows] == ["sig00000", "sig00001", "sig00002", "sig00003"], [r["sig"] for r in rows])
check("the failed on-chain tx is counted, not fetched", m1["failed_txs_skipped"] == 1)
check("⭐ every paged signature is accounted for: processed + backlog == paged",
      m1["accounted"] and m1["processed"] + m1["backlog"] == m1["paged"] == 9, m1)
check("the cursor stops at the last one PROCESSED, not the last one paged",
      cursor()["sig"] == "sig00003")

section("3. second run continues from the cursor - no duplicate, no hole")
m2 = G.build(verbose=False, now=T0 + 40, seconds=100)
rows = ledger()
sigs = [r["sig"] for r in rows]
check("no signature recorded twice (a retried fetch is the only repeat)",
      len([s for s in sigs if sigs.count(s) > 1 and s != "sig00004"]) == 0, sigs)
check("⭐ every successful signature is in the ledger",
      {x["signature"] for x in CHAIN if not x["err"]} <= set(sigs))
check("a fetch that failed is RECORDED as failed and queued for retry",
      any(r["sig"] == "sig00004" and r["kind"] == "fetch_failed" for r in rows)
      and cursor()["retry"] and cursor()["retry"][0]["sig"] == "sig00004", cursor().get("retry"))
m3 = G.build(verbose=False, now=T0 + 60, seconds=100)
rows = ledger()
check("...and the next pass retries it and records the graduation",
      any(r["sig"] == "sig00004" and r["kind"] == "graduation" and r.get("retried") for r in rows)
      and cursor()["retry"] == [], cursor().get("retry"))
check("the graduation row keys on the MINT, with its instructions kept",
      all(r.get("mint") and "CreatePool" in r["instructions"] for r in rows if r["kind"] == "graduation"))
check("recent_mints() returns graduations since a time, from disk",
      G.recent_mints(T0 + 5) == {x["mint"] for x in CHAIN[5:] if G.classify(x["tx"])[0] == "graduation"
                                 and not x["err"]})
reg = json.load(open(liveness.REG, encoding="utf-8")).get("graduations.ledger") or {}
check("liveness counts ROWS written, across the three passes",
      reg.get("firings") == 3 and reg.get("rows_total") == len(rows), (reg.get("rows_total"), len(rows)))

OLD_AMB = {"kind": "ambiguous", "block_time": T0 + 9, "mints": [G.USDC, "LegacyAmbig" + "y" * 33]}
with open(os.path.join(G.DIR, "2026-09.jsonl"), "a", encoding="utf-8") as f:
    f.write(json.dumps(OLD_AMB) + chr(10))
check("an old 'ambiguous' row with one non-quote mint is read as that mint - from its own record",
      ("LegacyAmbig" + "y" * 33) in G.recent_mints(T0))

section("3b. C13 on every pass: what share of graduations the journal ever saw")
cov = G.coverage(T0 + 2 * 3600 + 20, {CHAIN[0]["mint"], CHAIN[1]["mint"], "NotAGraduation"})
g_in = [x["mint"] for x in CHAIN if G.classify(x["tx"])[0] == "graduation" and not x["err"]]
check("the WHOLE ledger in the window is the denominator, not a sample",
      cov.get("graduations") == len(g_in) and cov.get("seen_by_journal") == 2, cov)
check("it carries a Wilson interval", cov.get("wilson95") and cov["wilson95"][0] <= cov["rate"] <= cov["wilson95"][1])
check("⛔ no journal loaded -> 'not computed', never 0%",
      G.coverage(T0, None)["status"].startswith("not computed"))

section("4. ⛔ a paging cap records the hole instead of stepping over it")
for i in range(10, 16):
    add(i)
G.PAGE_CAP, G.PAGE_LIMIT = 2, 2
m4 = G.build(verbose=False, now=T0 + 80, seconds=100)
rows = ledger()
gaps = [r for r in rows if r["kind"] == "gap"]
check("a capped page run writes a gap row naming both ends",
      m4["gap_recorded"] and len(gaps) == 1 and gaps[0]["after_sig"] == "sig00009"
      and gaps[0]["before_block_time"] == T0 + 12, gaps)
G.PAGE_CAP, G.PAGE_LIMIT = 20, 1000

section("5. ⛔ a corrupt cursor stops the ledger rather than restarting it")
with open(os.path.join(G.DIR, "cursor.json"), "w", encoding="utf-8") as f:
    f.write('{"sig": "sig000')
n_before = len(ledger())
try:
    G.build(verbose=False, now=T0 + 100, seconds=100)
    raised = False
except RuntimeError:
    raised = True
check("build() refuses - a fresh start would double-record the last 24h",
      raised and len(ledger()) == n_before)

print()
bad = [r for r in R if not r[1]]
print(f"{len(R) - len(bad)}/{len(R)} passed")
if bad:
    print("\nFAILED:")
    for n, _ in bad:
        print("  -", n)
sys.exit(1 if bad else 0)
