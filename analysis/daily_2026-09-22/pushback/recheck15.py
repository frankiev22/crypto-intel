"""Re-check every contract that logged a gate-passing 2x on 09-21, from CHAIN.

This morning's table came from ONE Dexscreener field. EMBER proved that wrong in
the direction that matters: its pool held 2,690 SOL (about $317k) at 10:36:32Z
today and was emptied by a Withdraw at 11:09:37Z, 2m33s before our 24h check.
"Never real" and "rugged at a knowable instant" are different claims and we made
the wrong one.

For each contract: every pool on every venue from chain (pool_probe), the live
Jupiter $100 round trip, and - for pools that are now empty - WHEN and HOW the
quote side left, via Helius' parsed transaction history on the pool account.

WITHDRAW = the LP was pulled (a rug, by a person, at a timestamp).
SWAP-only decline = buyers sold it down (a market outcome).

⛔ The Helius key is read from config and never printed: the URL is built inside
the request call and no URL is logged.
"""
import io
import json
import os
import sys
import time
import urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", "..", ".."))
sys.path.insert(0, ROOT)
import config  # noqa: E402
import chainfields  # noqa: E402
from pool_probe import probe, UA  # noqa: E402

WINNERS = [
    ("FLCr9vGMTkbDcRCoirP5Hx8gB7TW1Azt3pkw3qp2HTsh", "EMBER"),
    ("GPqoXbff7NPyvbngpsUz7mP1byZq7Xfh94E8Gu56HR6T", "USDCAT"),
    ("3gAXa6khcC6G7tq6XBnonsiS7GQtq3auKnXCvdZvQtfJ", "TSLA"),
    ("671dNhKr12xRoPmfkevzG1daqi4c9KMAA9J83ExyMWJ7", "OWL"),
    ("BsE3aa5FdE6FVEkWvA8ShAGpzZasEgJbfSqRC4LmErTK", "X7"),
    ("MjimYVjNMjBu5g9t5R66wjVknJbSFnotsS6WG5epump", "ChatGPT"),
    ("HGNPr1ztbHLU4eo9zQEcxCGXJHF6iQ246M3iobFxpump", "MrBeast"),
    ("EHY56TBNQ1jX6zUQx7gTPwbdGo7zfKMUH6kvXLbSpump", "tradecat"),
    ("5vg9KLxC8QdKCaidkmCfjg3ttAXD1CFKuyeQHSK3pump", "Vortex"),
    ("k4WcTJwcK8x11E7RFhXsYsdiWZWwfo6FzKEmcCPpump", "UOTF"),
    ("9KmeDWVt7TtrEZT2567kxeDkDZxd3cDoTZ1ZrLow9soG", "STONKBROS"),
    ("54c53NaoMDLcxv9ECjN35GLJjX4JDbpbwpSiFwbspump", "VSOF"),
    ("CdhZy8wrRxNxoV8HtoByXKN7mvS46avtuZ1b39tKfx7", "X7b"),
    ("BLSuVTxKYDL4vm4XmG3oEJfsSGfJZF3cgy98ri68pump", "CATEWALK"),
    ("HXQ66zSRqynwJQ6vYEYa85qGY9C2Ycz8rnYQHgApn391", "GO"),
]


def parsed_history(address, before=None, limit=100):
    """Helius parsed transactions for an address. Returns (rows, error).

    The key is interpolated here and nowhere else; no caller sees the URL.
    """
    config._load_env()
    k = os.environ.get("HELIUS_API_KEY", "")
    if not k:
        return None, "no key"
    url = f"https://api.helius.xyz/v0/addresses/{address}/transactions?api-key={k}&limit={limit}"
    if before:
        url += "&before=" + before
    try:
        r = urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60)
        return json.loads(r.read()), None
    except Exception as e:
        # Never let the key reach the message.
        return None, f"{type(e).__name__}: {str(e).replace(k, 'REDACTED')[:100]}"


def find_drain(pool, quote_vault, max_pages=40):
    """Walk the pool's history newest-first; report the last big quote outflow."""
    before, pages, seen = None, 0, 0
    events = []
    while pages < max_pages:
        rows, err = parsed_history(pool, before=before)
        if err:
            return {"error": err, "pages": pages, "txs_scanned": seen}
        if not rows:
            break
        for t in rows:
            seen += 1
            for tr in (t.get("tokenTransfers") or []):
                if tr.get("fromUserAccount") == pool or tr.get("fromTokenAccount") == quote_vault:
                    amt = float(tr.get("tokenAmount") or 0)
                    if tr.get("mint") == "So11111111111111111111111111111111111111112" and amt >= 50:
                        events.append({"ts": t.get("timestamp"), "sig": t.get("signature"),
                                       "type": t.get("type"), "sol_out": amt,
                                       "to": tr.get("toUserAccount"),
                                       "desc": (t.get("description") or "")[:140]})
            for na in (t.get("nativeTransfers") or []):
                if na.get("fromUserAccount") == pool and (na.get("amount") or 0) >= 50e9:
                    events.append({"ts": t.get("timestamp"), "sig": t.get("signature"),
                                   "type": t.get("type"), "sol_out": na["amount"] / 1e9,
                                   "to": na.get("toUserAccount"),
                                   "desc": (t.get("description") or "")[:140]})
        before = rows[-1].get("signature")
        pages += 1
        if events:
            break
    return {"events": sorted(events, key=lambda e: -(e.get("sol_out") or 0))[:5],
            "pages": pages, "txs_scanned": seen}


if __name__ == "__main__":
    os.makedirs(os.path.join(HERE, "probe"), exist_ok=True)
    out = []
    for mint, sym in WINNERS:
        t0 = time.time()
        try:
            r = probe(mint)
        except Exception as e:
            print(f"{sym:10s} PROBE FAILED {type(e).__name__}: {e}")
            out.append({"mint": mint, "symbol": sym, "error": f"{type(e).__name__}: {e}"})
            continue
        p = os.path.join(HERE, "probe", mint + ".json")
        tmp = p + ".tmp"
        with io.open(tmp, "w", encoding="utf-8") as f:
            json.dump(r, f, indent=1, ensure_ascii=False, default=str)
        os.replace(tmp, p)
        rt = (r.get("third_party") or {}).get("jupiter_round_trip_100") or {}
        jt = (r.get("third_party") or {}).get("jupiter_token") or {}
        row = {"mint": mint, "symbol": sym, "chain_quote_usd": round(r["chain_quote_usd_total"], 2),
               "n_pools": len(r["pools"]), "holders_chain": r.get("holders_nonzero"),
               "jup_verdict": rt.get("verdict"), "jup_usd_back": rt.get("usd_back"),
               "jup_holders": jt.get("holderCount"), "jup_vol24": jt.get("volume24h"),
               "launchpad": jt.get("launchpad"), "graduated_at": jt.get("graduatedAt"),
               "mint_auth": (r.get("mint_account") or {}).get("mint_authority"),
               "freeze_auth": (r.get("mint_account") or {}).get("freeze_authority"),
               "deepest": (r["pools"][0] if r["pools"] else None)}
        out.append(row)
        print(f"{sym:10s} chain ${row['chain_quote_usd']:>12,.2f}  pools {row['n_pools']:>2}  "
              f"holders {str(row['holders_chain']):>6}  jup {str(row['jup_verdict']):<12} "
              f"${str(row['jup_usd_back']):<8} {row['launchpad'] or ''} {time.time()-t0:.0f}s")
        with io.open(os.path.join(HERE, "recheck15.json"), "w", encoding="utf-8") as f:
            json.dump(out, f, indent=1, ensure_ascii=False, default=str)
    print("written recheck15.json")
