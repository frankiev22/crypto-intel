"""Does the pre-committed $100 chain-vault band actually predict SELLABILITY?

⛔ This is not part of the `gone` experiment and must never be folded into it.
It is instrument validation on a DIFFERENT, ALREADY-LABELLED population: the 15
contracts in `data/findings/REPORT_2026-09-22_pushback.md`, each of which already
carries a live Jupiter $100 round-trip answer from 2026-09-22.

⚠️ WHY IT IS NEEDED. My pre-commit says existence is not liquidity. The first
control run showed why in one line: a contract with $23.53 of WSOL in its pool
returned NO_SELL_ROUTE from Jupiter. So POOL_QUOTE_10 cannot be read as "you can
sell", and the headline band has to be the one that tracks a real exit.

⛔ AND IT CATCHES A TRAP I WALKED INTO. I first resolved these by SYMBOL from our
own rows and got THREE OF FOUR WRONG: the report's OWL is
`671dNhKr12xRoPmfkevzG1daqi4c9KMAA9J83ExyMWJ7`, while the newest row symbol'd OWL
is `GVhegCjHmy2GByvdEAq9ZYtd7hrpHnPB5XZHWvg2pump`. Different contracts, same
ticker. Standing rule 2. Addresses below are read from the rerun JSON, never from
a symbol.

Run: python analysis/gone_pools/validate_threshold.py
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import chainfields  # noqa: E402
import pooldiscovery as pd  # noqa: E402

RERUN = os.path.join(ROOT, "analysis", "daily_2026-09-22", "pushback",
                     "allpairs_rerun.json")

# The report's own Jupiter $100 answer per contract, 2026-09-22, keyed on the
# ADDRESS. `None` means the report recorded no sell route.
REPORT_JUP = {
    "FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh": 0.32,
    "GPqoXbff7NPyvbngpsUz7mP1byZq7Xfh94E8Gu56HR6T": None,
    "3gAXa6khcC6G7tq6XBnonsiS7GQtq3auKnXCvdZvQtfJ": 0.02,
    "671dNhKr12xRoPmfkevzG1daqi4c9KMAA9J83ExyMWJ7": None,
    "BsE3aa5FdE6FVEkWvA8ShAGpzZasEgJbfSqRC4LmErTK": 1.44,
    "MjimYVjNMjBu5g9t5R66wjVknJbSFnotsS6WG5epump": 89.44,
    "HGNPr1ztbHLU4eo9zQEcxCGXJHF6iQ246M3iobFxpump": None,
    "EHY56TBNQ1jX6zUQx7gTPwbdGo7zfKMUH6kvXLbSpump": 90.07,
    "5vg9KLxC8QdKCaidkmCfjg3ttAXD1CFKuyeQHSK3pump": 89.47,
    "k4WcTJwcK8x11E7RFhXsYsdiWZWwfo6FzKEmcCPpump": None,
    "9KmeDWVt7TtrEZT2567kxeDkDZxd3cDoTZ1ZrLow9soG": 94.11,
    "54c53NaoMDLcxv9ECjN35GLJjX4JDbpbwpSiFwbspump": 90.12,
    "CdhZy8wrRxNxoV8HtoByXKN7mvS46avtuZ1b39tKfx7": 95.56,
    "BLSuVTxKYDL4vm4XmG3oEJfsSGfJZF3cgy98ri68pump": 97.65,
    "HXQ66zSRqynwJQ6vYEYa85qGY9C2Ycz8rnYQHgApn391": 96.45,
}

SELLABLE_USD = 50.0  # the report's own split: ~$89+ back, or essentially nothing


def main():
    rerun = json.load(io.open(RERUN, encoding="utf-8"))
    px, src, ts = pd.sol_price()
    print("SOL $%.2f from %s at %d\n" % (px, src, ts))
    print("%-10s %-44s %-18s %10s | %-14s %8s | %s" % (
        "symbol", "contract", "chain verdict", "chain $", "jup now", "$ back",
        "report 09-22"))
    rows = []
    for r in rerun["rows"]:
        mint = r["mint"]
        d = pd.discover(mint, sol_usd=px)
        try:
            j = chainfields.round_trip(mint, usd=100)
            jv, jb = j.get("verdict"), j.get("usd_back")
        except Exception as e:
            jv, jb = "QUOTE_FAILED", None
        rows.append({
            "mint": mint, "symbol": r.get("symbol"),
            "chain_verdict": d["verdict"], "chain_quote_usd": d["quote_usd_max"],
            "pool_count": d["pool_count"],
            "venues": sorted({p["venue"] for p in d["pools"]}),
            "jupiter_verdict_now": jv, "jupiter_usd_back_now": jb,
            "report_jupiter_0922": REPORT_JUP.get(mint),
            "report_single_pool_quote": r.get("old_single_pool_quote_usd"),
        })
        print("%-10s %-44s %-18s %10.2f | %-14s %8s | %s" % (
            (r.get("symbol") or "")[:10], mint, d["verdict"],
            d["quote_usd_max"], jv, jb, REPORT_JUP.get(mint)))
        sys.stdout.flush()

    # ---- does the pre-committed $100 band separate sellable from not?
    tp = fp = tn = fn = 0
    unknown = 0
    for r in rows:
        back = r["jupiter_usd_back_now"]
        if r["jupiter_verdict_now"] == "QUOTE_FAILED":
            unknown += 1
            continue
        sellable = bool(back and back >= SELLABLE_USD)
        flagged = r["chain_quote_usd"] >= 100
        if flagged and sellable:
            tp += 1
        elif flagged and not sellable:
            fp += 1
        elif not flagged and sellable:
            fn += 1
        else:
            tn += 1
    out = {
        "what_this_is": ("instrument validation on an ALREADY-LABELLED set, NOT "
                         "part of the gone experiment"),
        "ran_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "sol_usd": px, "sol_usd_source": src,
        "sellable_threshold_usd_back": SELLABLE_USD,
        "chain_band_usd": 100,
        "n": len(rows), "quote_failed": unknown,
        "chain_flags_and_sellable": tp,
        "chain_flags_but_not_sellable": fp,
        "chain_clears_and_sellable_MISSED": fn,
        "chain_clears_and_not_sellable": tn,
        "agreement_pct": (round(100.0 * (tp + tn) / (tp + tn + fp + fn), 1)
                          if (tp + tn + fp + fn) else None),
        "rows": rows,
    }
    p = os.path.join(HERE, "threshold_validation.json")
    io.open(p, "w", encoding="utf-8").write(json.dumps(out, indent=1,
                                                       sort_keys=True))
    print("\n$100 chain band vs a live $100 Jupiter sell, n=%d" % len(rows))
    print("  flags AND sellable        %d" % tp)
    print("  flags but NOT sellable    %d   (a chain read that overstates)" % fp)
    print("  clears but IS sellable    %d   (a chain read that MISSES)" % fn)
    print("  clears and not sellable   %d" % tn)
    print("  agreement                 %s%%" % out["agreement_pct"])
    print("\nwrote", p)
    return 0


if __name__ == "__main__":
    sys.exit(main())
