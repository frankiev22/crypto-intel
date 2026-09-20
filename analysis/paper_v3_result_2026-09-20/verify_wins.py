"""Every v3 exit at >= 2.0x through journal.verify_win, with the evidence
measured AT THE EXIT MOMENT from the pool's own vaults.

The first attempt got two inputs wrong and failed all six for the wrong reason:
it passed `usd_out` (dollars taken out, ~$217) where the gate wants quote-side
DEPTH against an $8,000 floor, and it judged `alive` from today's Jupiter quote
rather than from the moment the position actually closed. Both are fixed here.

Nothing is executed. Depth and direction come from the chain; no field is read
from a third party's API.
"""
import json
import os
import statistics
import sys
import time

REPO = r"C:\Users\Frankie\Desktop\Projects\crypto-intel"
sys.path.insert(0, REPO)
sys.path.insert(0, os.path.join(REPO, "analysis", "cluster_rule_2026-09-19"))
os.chdir(REPO)

import cluster_chain as C
import journal
import onchain

# SOL/USD by hour from our own observation rows (price_usd / price_native on
# SOL-quoted pairs; the hourly median discards the USDC-quoted ones).
_sol = {}
for fn in sorted(os.listdir("data/observations")):
    if not fn.startswith("2026-09"):
        continue
    for line in open(os.path.join("data/observations", fn), encoding="utf-8"):
        try:
            r = json.loads(line)
            pu, pn = float(r.get("price_usd") or 0), float(r.get("price_native") or 0)
        except Exception:
            continue
        if pu > 0 and pn > 0 and 20 < pu / pn < 2000:
            _sol.setdefault(int(r["ts"]) // 3600, []).append(pu / pn)
SOLH = {h: statistics.median(v) for h, v in _sol.items() if len(v) >= 3}


def sol_usd(t):
    h = int(t) // 3600
    for d in range(48):
        for k in (h - d, h + d):
            if k in SOLH:
                return SOLH[k]
    return None


def to_usd(qmint, amount, t):
    if amount is None:
        return None
    if qmint in (C.USDC, C.USDT):
        return amount
    s = sol_usd(t)
    return None if s is None else amount * s


def flow(pool, base_v, quote_v, T, back_s=7200, max_tx=40):
    """(sells, buys) on this pool in [T-back_s, T], from the direction of each
    swap's quote movement. Quote leaving the pool is a SELL of the token."""
    a, _ = C.anchor_sig(T)
    page = [p for p in C.sigs_before(pool, a, limit=300) if not p.get("err")
            and (p.get("blockTime") or 0) >= T - back_s]
    sells = buys = 0
    for p in page[:max_tx]:
        t = C.tx(p["signature"])
        if not t or t["meta"].get("err"):
            continue
        bal = C._balances(t)
        b, q = bal.get(base_v), bal.get(quote_v)
        if not b or not q:
            continue
        db, dq = b["post"] - b["pre"], q["post"] - q["pre"]
        if db == 0 or dq == 0 or (db > 0) == (dq > 0):
            continue
        if dq < 0:
            sells += 1
        else:
            buys += 1
    return sells, buys, len(page[:max_tx])


rows = [json.loads(l) for l in open("data/paper/ledger_v3.jsonl", encoding="utf-8") if l.strip()]
entries = {r["hash"]: r for r in rows if r.get("type") == "entry"}
wins = [r for r in rows if r.get("type") == "exit" and (r.get("realizable_multiple") or 0) >= 2.0]
wins.sort(key=lambda r: -(r.get("realizable_multiple") or 0))

out = []
for x in wins:
    e = entries.get(x.get("entry_id")) or {}
    ca, pool = x["contract"], e.get("pair")
    T = int(x.get("exit_quote_ts") or 0)
    print(f"\n=== {x.get('symbol')}  {ca[:16]}  {x['realizable_multiple']:.3f}x  "
          f"exit {x['ts']} ===", flush=True)
    rec = {"symbol": x.get("symbol"), "contract": ca, "pool": pool,
           "mult": x["realizable_multiple"], "usd_in": x.get("usd_in"),
           "usd_out": x.get("usd_out"), "elapsed_h": x.get("elapsed_h"),
           "entry_ts": e.get("ts"), "exit_ts": x["ts"], "exit_quote_ts": T,
           "exit_quote_verdict": x.get("exit_quote_verdict"),
           "exit_impact_pct": x.get("exit_price_impact_pct"),
           "shadow_quotes": x.get("shadow_quotes"),
           "entry_verdict": e.get("entry_verdict"),
           "holders_at_entry": e.get("holders_at_entry"),
           "entry_rule": e.get("rule")}

    auth = onchain.authorities(ca)
    rec.update(mint_authority=auth["mint_authority"], freeze_authority=auth["freeze_authority"],
               auth_err=auth["authorities_error"])
    print(f"  chain authorities now: mint={auth['mint_authority']} "
          f"freeze={auth['freeze_authority']}", flush=True)

    depth_usd = sells = buys = None
    try:
        newest = C.rpc("getSignaturesForAddress", [pool, {"limit": 10}]) or []
        v = C.vaults(pool, ca, [s["signature"] for s in newest])
        if not v:
            a, _ = C.anchor_sig(T)
            near = C.sigs_before(pool, a, limit=10)
            v = C.vaults(pool, ca, [s["signature"] for s in near])
        if v:
            base_v, quote_v, qmint = v
            st = C.state_at(pool, base_v, quote_v, T, T - 30 * 86400)
            depth_usd = to_usd(qmint, st["quote"], T)
            sells, buys, seen = flow(pool, base_v, quote_v, T)
            print(f"  at the exit moment: quote-side depth ${depth_usd:,.0f}" if depth_usd
                  else "  at the exit moment: depth unknown", flush=True)
            print(f"  flow in the 2h before the exit: {sells} sells, {buys} buys "
                  f"(of {seen} txs read)", flush=True)
        else:
            rec["chain_error"] = "no SOL/USDC/USDT vault pair found in the pool's data"
            print("  " + rec["chain_error"], flush=True)
    except Exception as ex:
        rec["chain_error"] = f"{type(ex).__name__}: {ex}"
        print(f"  chain read failed: {rec['chain_error']}", flush=True)

    rec.update(exit_depth_usd=depth_usd, sells_before_exit=sells, buys_before_exit=buys)

    ok, failed = journal.verify_win(
        status="alive" if x.get("exit_quote_verdict") == "QUOTED" else "dead",
        liq=None,
        mult=x["realizable_multiple"],
        exit_depth=depth_usd,
        pair=pool, exit_pair=pool,
        price_verdict=None,
        elapsed_h=x.get("elapsed_h"),
        reasons=[],
        sells_h24=sells, buys_h24=buys,
        authority_live=(bool(auth["mint_authority"]) or bool(auth["freeze_authority"])
                        if auth["authorities_error"] is None else None),
    )
    rec.update(gate_pass=ok, gate_failed=failed)
    print(f"  GATE: {'PASS' if ok else 'FAIL ' + ','.join(failed)}", flush=True)
    out.append(rec)

p = os.path.join(os.path.dirname(os.path.abspath(__file__)), "win_verdicts2.json")
with open(p, "w", encoding="utf-8") as f:
    json.dump(out, f, indent=1)
print("\n---- SUMMARY ----")
for o in out:
    d = o.get("exit_depth_usd")
    print(f"  {str(o['symbol']):10} {o['mult']:.2f}x  depth "
          f"{('$%.0f' % d) if d else 'unknown':>10}  "
          f"{o['sells_before_exit']}s/{o['buys_before_exit']}b  "
          f"{'PASS' if o['gate_pass'] else 'FAIL: ' + ','.join(o['gate_failed'])}")
print(f"\n{C.CALLS['n']} RPC calls")
