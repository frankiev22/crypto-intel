"""What fraction of Solana launches does our journal ever see? Measured from chain.

Run: python coverage_probe.py [sample_n]      (~2 min, ~850 Helius credits)

⛔ The 1.9% in docs/CHAINS.md and GAPS.md W2 was ARITHMETIC: a ~234s discovery
window per pass times ~7 passes a day over 86,400s. It was never checked against
the launch stream itself. This checks it directly:

  1. Every pump.fun create is signed by its mint authority
     TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM, and every graduation by its
     migration authority 39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg. Paging
     getSignaturesForAddress over [now-26h, now-2h] enumerates both streams for
     the last complete 24h - a LEDGER, not a window, so nothing ages out.
  2. A seeded random sample of each is fetched with getTransaction, kept only if
     its logs show the instruction we expect (CreateV2 / CreatePool - the
     migration authority also lands no-op race transactions) and exactly one
     non-SOL mint is involved.
  3. Each mint is looked up in every observation the journal has EVER recorded.

The 2h tail gives every token time to be seen by at least one pass. Nothing is
printed that is not public chain data; no key is printed.

MEASURED 2026-09-18 (window 2026-09-17 ~21:00Z -> 2026-09-18 ~21:00Z):
    creates      36,568 successful in 24h (1,524/h)
                 seen 4 / 317  = 1.26%  Wilson95 [0.49%, 3.20%]
    graduations  seen 5 / 257  = 1.95%  Wilson95 [0.83%, 4.47%]
Triangulates with the arithmetic: median window 190s/pass (n=30, p90 288s) x
~7 passes/day = 1.54%. See COVERAGE.md (repo root).

⚠️ THE 2026-09-18 RUN ASKED FOR maxSupportedTransactionVersion 0. Measured
2026-09-19, ~5% of both streams are v1 transactions (3/60 creates, 3/60
authority txs) and a v0 request fails on them, so they landed in `fetch_failed`
and out of both numerator and denominator. The rates above move only if v1
launches differ in whether our journal saw them; the next run uses version 1.

⚠️ NOT A GRADUATION RATE. 1,647 migration-authority transactions in 24h, of
which ~72% carry CreatePool, implies ~1,100 graduations a day - ~3% of creates,
against a published base rate of 0.198% (Kamat) and our 0.22%. That is not
reconciled, and nothing here is fit to quote as a graduation rate.
"""
import glob
import json
import math
import os
import random
import sys
import time
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import config

WSOL = "So11111111111111111111111111111111111111112"
MINT_AUTHORITY = "TSLvdd1pWpHVjahSpsvCXUbgwsL3JAcvokwaKt1eokM"
MIGRATION_AUTHORITY = "39azUYFWPz3VHgKCf3VChUwbpURdCHRxjWVowf5jUJjg"
SEED = 20260918


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    a = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return ((c - a) / d, (c + a) / d)


def seen_tokens():
    out = set()
    for f in glob.glob(os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                    "data", "observations", "*.jsonl")):
        with open(f, encoding="utf-8") as fh:
            for line in fh:
                try:
                    t = json.loads(line).get("token")
                except ValueError:
                    continue
                if t:
                    out.add(t)
    return out


def main(n_sample=400):
    rpc_url = config.helius_rpc()

    def rpc(method, params, tries=4):
        body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                           "params": params}).encode()
        for i in range(tries):
            try:
                req = urllib.request.Request(rpc_url, data=body, headers={
                    "Content-Type": "application/json", "User-Agent": "crypto-intel/1.0"})
                with urllib.request.urlopen(req, timeout=40) as f:
                    return json.loads(f.read()).get("result")
            except Exception:
                time.sleep(1.5 * (i + 1))
        return None

    now = time.time()
    lo, hi = now - 26 * 3600, now - 2 * 3600

    def window(acct):
        out, before = [], None
        while True:
            p = {"limit": 1000}
            if before:
                p["before"] = before
            page = rpc("getSignaturesForAddress", [acct, p]) or []
            if not page:
                break
            out += [x for x in page if x.get("err") is None and x.get("blockTime")
                    and lo <= x["blockTime"] <= hi]
            before = page[-1]["signature"]
            if (page[-1].get("blockTime") or now) < lo:
                break
            time.sleep(0.15)
        return out

    def mint_of(sig, pre):
        t = rpc("getTransaction", [sig, {"maxSupportedTransactionVersion": 1,
                                          "encoding": "json"}])
        if not t:
            return None, None
        meta = t.get("meta") or {}
        ins = {l.split("Instruction: ")[1] for l in (meta.get("logMessages") or [])
               if "Instruction: " in l}
        bal = meta.get("preTokenBalances" if pre else "postTokenBalances") or []
        return ins, sorted({b["mint"] for b in bal if b.get("mint") and b["mint"] != WSOL})

    seen = seen_tokens()
    report = {"window_utc": [time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(lo)),
                             time.strftime("%Y-%m-%dT%H:%MZ", time.gmtime(hi))],
              "journal_tokens": len(seen)}
    for label, acct, pre, want in (("creates", MINT_AUTHORITY, False, {"Create", "CreateV2"}),
                                   ("graduations", MIGRATION_AUTHORITY, True, {"CreatePool"})):
        sigs = window(acct)
        random.seed(SEED)
        sample = random.sample(sigs, min(n_sample, len(sigs)))
        c = {"fetch_failed": 0, "not_target": 0, "ambiguous_mint": 0}
        usable = []
        for x in sample:
            ins, mints = mint_of(x["signature"], pre)
            time.sleep(0.11)
            if ins is None:
                c["fetch_failed"] += 1
            elif not (ins & want):
                c["not_target"] += 1
            elif len(mints) != 1:
                c["ambiguous_mint"] += 1
            else:
                usable.append(mints[0])
        k = sum(1 for m in usable if m in seen)
        w = wilson(k, len(usable))
        report[label] = dict(c, txs_24h=len(sigs), sampled=len(sample), usable=len(usable),
                             seen=k, rate=(k / len(usable) if usable else None),
                             wilson95=w)
        print(f"{label:12} {len(sigs):,} txs/24h  sampled {len(sample)}  {c}  "
              f"seen {k}/{len(usable)}"
              + (f" = {k / len(usable):.2%} [{w[0]:.2%}, {w[1]:.2%}]" if usable else ""))
    return report


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass
    print(json.dumps(main(int(sys.argv[1]) if len(sys.argv) > 1 else 400), indent=1))
