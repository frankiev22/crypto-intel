"""Re-measure every archive row with ALL PAIRS summed, and name the impersonators.

Frank, 2026-09-22: *"the archive extraction now REQUIRES a verified contract
address per ticker, resolved with all-pairs liquidity, with impersonators named.
Write it to the repo and to Supabase, not just a report."*

⛔ What the first build did wrong: `current_liquidity_usd` came from a single
pair. On the real EMBER that is a 3.51x understatement, and it is worst exactly
on the pairing-launchpad assets that are now the interesting class.

⛔ And one call per mint, never batched. Measured 2026-09-23: three mints in one
`/latest/dex/tokens/a,b,c` call returned **30 pairs TOTAL, split 15/14/1**. The
cap is 30 per RESPONSE, not per mint, so batching silently reproduces the bug.

⚠️ `pair_count == 30` means "30 or more" (SOL returns 30), so a total at the cap
is a FLOOR. Carried through as `liq_is_floor`.

⭐ Every row gets a verified_status, and the rule is pre-committed here before the
run (standing rule 6):

  VERIFIED_LIQUID     resolution HIGH or MEDIUM, all-pairs liq >= $25,000
  VERIFIED_THIN       resolution HIGH or MEDIUM, all-pairs liq $1,000-$25,000
  VERIFIED_DEAD       resolution HIGH or MEDIUM, all-pairs liq < $1,000
  PHANTOM             mcap > $1m on < $1,000 of liq, complete sample
  UNVERIFIED          resolution LOW or NONE: several live tokens wear the ticker
  LOOKUP_FAILED       the measurement itself did not answer (never "dead")

⛔ VERIFIED means "this address is the one Gorilla most likely meant, and these
are its real numbers now". It does NOT mean his call was good. No hit rate is
computable from a ticker - see docs/GORILLA_ARCHIVE.md 4b.
"""
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)
import allpairs  # noqa: E402

OUT = os.path.join(HERE, "dataset_allpairs.json")
PACE_S = 0.45


def status(row, t):
    conf = (row.get("resolution_confidence") or "").upper()
    if not row.get("address"):
        return "UNVERIFIED", "no contract chosen"
    if not t.get("ok"):
        return "LOOKUP_FAILED", "the measurement did not answer - not evidence of death"
    if t.get("phantom"):
        return "PHANTOM", t.get("phantom_why")
    liq = t.get("total_liq_usd")
    if conf not in ("HIGH", "MEDIUM"):
        return "UNVERIFIED", (f"{row.get('n_candidates')} live tokens carry this ticker; "
                              f"confidence {conf or 'NONE'}")
    if liq is None:
        return "LOOKUP_FAILED", "no liquidity reading"
    if liq < 1_000:
        return "VERIFIED_DEAD", f"${liq:,.0f} across all {t.get('pair_count')} pairs"
    if liq < 25_000:
        return "VERIFIED_THIN", f"${liq:,.0f} across all {t.get('pair_count')} pairs"
    return "VERIFIED_LIQUID", f"${liq:,.0f} across all {t.get('pair_count')} pairs"


def main():
    rows = json.load(io.open(os.path.join(HERE, "dataset.json"), encoding="utf-8"))
    done = {}
    if os.path.exists(OUT):
        try:
            done = {r["ticker"]: r for r in json.load(io.open(OUT, encoding="utf-8"))}
        except Exception:
            done = {}

    out, t0, n_call = [], time.time(), 0
    for i, row in enumerate(rows):
        if row["ticker"] in done and done[row["ticker"]].get("verified_status") != "LOOKUP_FAILED":
            out.append(done[row["ticker"]])
            continue
        addr = row.get("address")
        t = allpairs.token(addr) if addr else {"ok": False, "error": "no address"}
        if addr:
            n_call += 1
            time.sleep(PACE_S)
        st, why = status(row, t)
        # ⭐ impersonators: every OTHER live mint wearing this ticker, already
        # collected at resolution time, so this costs no extra call.
        others = row.get("other_candidates") or []
        new = dict(row)
        new.update({
            "verified_status": st,
            "verified_why": why,
            "pair_count": t.get("pair_count"),
            "pairs_truncated": t.get("truncated"),
            "liq_all_pairs_usd": t.get("total_liq_usd"),
            "liq_is_floor": t.get("total_liq_is_floor"),
            "vol24_all_pairs_usd": t.get("total_vol24_usd"),
            "mcap_all_pairs_usd": t.get("mcap_usd"),
            "price_all_pairs_usd": t.get("price_usd"),
            "venues": t.get("venues"),
            "quote_assets": {k: round(v["liq_usd"])
                             for k, v in list((t.get("quote_assets") or {}).items())[:8]},
            "deepest_pool_liq_usd": t.get("single_pair_would_have_said"),
            "single_pair_understates_by": t.get("single_pair_understates_by"),
            "impersonators": others[:12],
            "n_impersonators": len(others),
            "measured_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        })
        out.append(new)
        if (i + 1) % 40 == 0:
            el = time.time() - t0
            print(f"  {i+1}/{len(rows)}  {el:.0f}s  {n_call} calls  "
                  f"~{el/max(n_call,1)*(len(rows)-i-1):.0f}s left", flush=True)
            json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1,
                      ensure_ascii=False, default=str)
    json.dump(out, io.open(OUT, "w", encoding="utf-8"), indent=1,
              ensure_ascii=False, default=str)

    from collections import Counter
    c = Counter(r["verified_status"] for r in out)
    print("\nverified_status:", dict(c))
    old = Counter(r.get("outcome") for r in rows)
    print("previous outcome:", dict(old))
    understate = [r["single_pair_understates_by"] for r in out
                  if r.get("single_pair_understates_by")]
    if understate:
        understate.sort()
        print(f"single-pair understatement: median {understate[len(understate)//2]}x, "
              f"max {understate[-1]}x, n={len(understate)}")
    imp = sum(r.get("n_impersonators") or 0 for r in out)
    print(f"impersonators named: {imp} across {sum(1 for r in out if r.get('n_impersonators'))} tickers")


if __name__ == "__main__":
    main()
