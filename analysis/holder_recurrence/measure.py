"""⭐⭐ Do the same wallets top-hold many different new launches? Measure it.

Found by running the sybil-cluster code rather than by planning it. Two pump.fun
graduations picked at random from our own ledger share **three** of their top-10
holders: `EDk7Qte...`, `BLTnkVG...`, `7JUZ9or...`. None of the top holders of
either token is a fresh wallet; every one carries 3,000+ signatures.

⛔ **That kills the sybil-cluster framing for this population and replaces it
with a better one.** Frank's worry was *"nobody should ever be able to buy more
than 1%-2% of a coin that early on"*, and the raw numbers look exactly like that
worry: **top-10 holds 54% and 64%, with 8 to 10 wallets over 2%.** But those
wallets are not one person splitting a buy across fresh addresses. They are
industrial participants who are top holders of launch after launch.

⭐ **So the fact worth publishing is RECURRENCE: for each top holder of a token,
how many OTHER launches is this same wallet also a top holder of?** A wallet
top-holding one token is a whale. The same wallet top-holding 200 is a sniper or
a market maker, and "11.5% of supply" means something completely different.

⚠️ PRE-COMMITTED before the run (standing rule 6):
  - population: distinct mints from our own graduation ledger, newest first
  - per mint: `getTokenLargestAccounts`, pool vaults and program-owned accounts
    excluded, top 10 WALLET holders kept
  - a wallet's recurrence = the number of DISTINCT mints in the sample where it
    appears in that top 10
  - reported with n and a Wilson interval, and the sample size stated

⛔ This is description, not prediction. It says what is true now and makes no
claim about what any token does next.
"""
import io
import json
import os
import sys
import time
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import concentration as C  # noqa: E402

OUT = os.path.join(HERE, "recurrence.json")
TOP_N = 10


def wilson(k, n, z=1.96):
    if not n:
        return (None, None)
    p = k / n
    d = 1 + z * z / n
    c = p + z * z / (2 * n)
    m = z * ((p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5)
    return (round(100 * (c - m) / d, 1), round(100 * (c + m) / d, 1))


def load_mints(limit):
    """Newest graduations from our own ledger, deduped, newest first."""
    path = os.path.join(ROOT, "data", "graduations", "2026-09.jsonl")
    seen, out = set(), []
    rows = [json.loads(l) for l in io.open(path, encoding="utf-8") if l.strip()]
    for r in reversed(rows):
        m = r.get("mint")
        if m and m not in seen:
            seen.add(m)
            out.append(m)
        if len(out) >= limit:
            break
    return out


def main(limit=60):
    mints = load_mints(limit)
    print(f"population: {len(mints)} distinct mints, newest graduations first\n")
    done = {}
    if os.path.exists(OUT):
        try:
            done = json.load(io.open(OUT, encoding="utf-8")).get("per_mint", {})
        except Exception:
            done = {}

    per_mint, t0 = dict(done), time.time()
    for i, m in enumerate(mints):
        if m in per_mint:
            continue
        w, pools, err = C.holders(m)
        if err or not w:
            per_mint[m] = {"error": err or "no wallet holders", "top": []}
        else:
            per_mint[m] = {"error": None,
                           "n_pool_vaults": len(pools),
                           "top": [x["owner"] for x in w[:TOP_N] if x.get("owner")]}
        if (i + 1) % 10 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(mints)}  {el:.0f}s", flush=True)
            json.dump({"per_mint": per_mint}, io.open(OUT, "w", encoding="utf-8"),
                      indent=1)
        time.sleep(0.1)

    ok = {m: v for m, v in per_mint.items() if not v.get("error") and v["top"]}
    wallet_mints = defaultdict(set)
    for m, v in ok.items():
        for w in v["top"]:
            wallet_mints[w].add(m)

    n = len(ok)
    counts = Counter(len(v) for v in wallet_mints.values())
    multi = {w: len(v) for w, v in wallet_mints.items() if len(v) > 1}
    n_wallets = len(wallet_mints)
    k_multi = len(multi)

    print(f"\nmints measured: {n}")
    print(f"distinct top-{TOP_N} wallets across them: {n_wallets}")
    lo, hi = wilson(k_multi, n_wallets)
    print(f"\n⭐ wallets appearing in the top {TOP_N} of MORE THAN ONE mint: "
          f"{k_multi}/{n_wallets} = {100*k_multi/n_wallets:.1f}% [{lo}, {hi}]")
    print("\nrecurrence distribution (mints per wallet):")
    for k in sorted(counts):
        print(f"   {k:>3} mint(s): {counts[k]:>5} wallets")

    print(f"\n⭐ the most recurrent wallets:")
    for w, c in sorted(multi.items(), key=lambda kv: -kv[1])[:15]:
        print(f"   {w}  top-{TOP_N} holder of {c} of {n} mints "
              f"({100*c/n:.0f}%)")

    # ⭐ The number that reframes concentration: how much of a token's top 10 is
    # made of wallets that are ALSO top holders elsewhere?
    shares = []
    for m, v in ok.items():
        k = sum(1 for w in v["top"] if len(wallet_mints[w]) > 1)
        shares.append(k / max(len(v["top"]), 1))
    shares.sort()
    med = shares[len(shares) // 2] if shares else None
    print(f"\n⭐ share of a token's top {TOP_N} that also top-hold another mint "
          f"in this sample: median {100*med:.0f}%, n={len(shares)}")
    print(f"   ⚠️ a FLOOR: the sample is only {n} mints out of every launch there is.")

    json.dump({"ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
               "n_mints": n, "top_n": TOP_N, "per_mint": per_mint,
               "n_distinct_wallets": n_wallets,
               "n_wallets_multi": k_multi,
               "pct_multi": round(100 * k_multi / n_wallets, 2) if n_wallets else None,
               "wilson_multi": [lo, hi],
               "recurrence_distribution": {str(k): v for k, v in sorted(counts.items())},
               "most_recurrent": sorted(multi.items(), key=lambda kv: -kv[1])[:60],
               "median_share_of_top_recurring": round(med, 4) if med is not None else None},
              io.open(OUT, "w", encoding="utf-8"), indent=1)
    print(f"\nwritten {OUT}")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 60)
