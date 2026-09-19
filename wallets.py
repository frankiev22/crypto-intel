"""
Wallet tracker.

The premise: the strongest available signal is what wallets that have ALREADY
made money are buying, in the first minutes. Twitter is downstream of this.

Two modes.
  build_watchlist()  - backfill. Given tokens that ran, find who bought early.
                       Works today on the public RPC, just slowly.
  watch()            - live. Needs Helius websockets to be genuinely real-time.
"""
import json, time, collections
import config, sources as S

import safeload

WATCHLIST = "data/watchlist.json"

def _rpc(method, params):
    return S._post(config.helius_rpc(), {"jsonrpc":"2.0","id":1,"method":method,"params":params})

def early_buyers(token_mint, max_sigs=200):
    """Wallets that transacted a mint earliest. Oldest signatures = first in."""
    sigs = _rpc("getSignaturesForAddress", [token_mint, {"limit": max_sigs}]).get("result", [])
    if not sigs: return []
    sigs = sorted(sigs, key=lambda s: s.get("blockTime") or 0)[:60]
    buyers = collections.Counter()
    for s_ in sigs:
        try:
            tx = _rpc("getTransaction", [s_["signature"],
                    {"encoding":"jsonParsed","maxSupportedTransactionVersion":1}]).get("result")
            if not tx: continue
            for acct in tx["transaction"]["message"]["accountKeys"]:
                if acct.get("signer"):
                    buyers[acct["pubkey"]] += 1
        except Exception:
            pass
        time.sleep(0.12 if config.have("helius") else 0.45)
    return buyers.most_common()

def build_watchlist(winning_mints, min_hits=2):
    """A wallet that was early on MULTIPLE winners is signal. Once is luck."""
    tally = collections.Counter()
    for m in winning_mints:
        print(f"  scanning {m[:12]}...")
        for w, _ in early_buyers(m):
            tally[w] += 1
    keep = {w: n for w, n in tally.items() if n >= min_hits}
    import os; os.makedirs("data", exist_ok=True)
    safeload.save_json(WATCHLIST, keep, allow_empty=True)
    print(f"  {len(keep)} wallets early on >= {min_hits} winners -> {WATCHLIST}")
    return keep

def load_watchlist():
    """Absent -> {}. Present-but-corrupt -> safeload.LoadFailed.

    Latent rather than fired: the file does not exist yet, so this has always
    taken the absent path. It is fixed now because it is the same shape, and
    the moment the file exists the shape becomes a live data-loss path.
    """
    return safeload.load_json(WATCHLIST)

def recent_activity(wallet, limit=10):
    return _rpc("getSignaturesForAddress", [wallet, {"limit": limit}]).get("result", [])

def watch(poll_seconds=30):
    """Polling fallback. With HELIUS_API_KEY this should be replaced by a
    websocket subscription - that is tomorrow's wiring job."""
    wl = load_watchlist()
    if not wl:
        print("  watchlist empty. run build_watchlist() with mints that actually ran."); return
    print(f"  polling {len(wl)} wallets every {poll_seconds}s"
          f"{' (public RPC - expect rate limits)' if not config.have('helius') else ''}")
    seen = set()
    while True:
        for w in wl:
            for s_ in recent_activity(w, 5):
                sig = s_["signature"]
                if sig in seen: continue
                seen.add(sig)
                if s_.get("blockTime", 0) > time.time() - poll_seconds * 2:
                    print(f"  {w[:8]}... -> {sig[:16]}...")
            time.sleep(0.3)
        time.sleep(poll_seconds)


# ---------------------------------------------------------------------------
# v0.0.1 additions. Helius is live now, so polling stops being bare signature
# lists and starts being parsed transactions. The loop above still works; these
# are the pull-based functions the digest calls.
# ---------------------------------------------------------------------------
NOISE = {
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA",
    "11111111111111111111111111111111",
    "ComputeBudget111111111111111111111111111111",
}


def helius_enhanced(address, limit=10):
    """Parsed transaction history from the Helius Enhanced API - types, amounts
    and a human description instead of a naked signature. Helius key required;
    returns [] without one so callers degrade instead of breaking."""
    k = config.key("helius")
    if not k:
        return []
    try:
        return S._get(f"https://api.helius.xyz/v0/addresses/{address}/transactions"
                      f"?api-key={k}&limit={limit}", tries=2)
    except Exception:
        return []


def recent_moves(wallet_list=None, window_s=3600, per_wallet=5):
    """What the watchlist actually DID inside the window.

    Everything is routed through moves.describe, which drops transactions where
    the wallet was merely mentioned and refuses to dress up an undecodable
    transaction as an action. Returns (records, stats)."""
    import moves
    wl = wallet_list if wallet_list is not None else list(load_watchlist_v2()[0])
    cutoff = time.time() - window_s
    out, bystander, undecoded = [], 0, 0
    for w in wl:
        for tx in helius_enhanced(w, per_wallet) or []:
            if (tx.get("timestamp") or 0) < cutoff:
                continue
            rec = moves.describe(tx, w)
            if rec is None:
                bystander += 1
                continue
            if not rec["known"]:
                undecoded += 1
                continue
            out.append(rec)
        time.sleep(0.08 if config.have("helius") else 0.5)
    out.sort(key=lambda r: -(r.get("usd") or 0))
    return out, {"bystander": bystander, "undecoded": undecoded, "wallets": len(wl)}


def seed_from_trending(n_tokens=3, min_hits=2, sigs=120):
    """Build a watchlist from live data: wallets that were early on MULTIPLE
    currently-trending Solana tokens. Being early once is luck, twice is a
    pattern. Falls back to single-hit wallets only if the strict filter is
    empty, and says which mode it used."""
    import os
    pools = S.trending_pools("solana")[:n_tokens]
    mints, names = [], []
    for p in pools:
        attrs = p.get("attributes", {})
        rel = (p.get("relationships") or {}).get("base_token", {}).get("data", {})
        mint = (rel.get("id") or "").split("_")[-1]
        if mint:
            mints.append(mint)
            names.append(attrs.get("name", mint[:10]))
    tally = collections.Counter()
    for m, nm in zip(mints, names):
        print(f"  early buyers of {nm}...")
        for w, _ in early_buyers(m, max_sigs=sigs):
            if w not in NOISE:
                tally[w] += 1
    keep = {w: n for w, n in tally.items() if n >= min_hits}
    mode = f"early on >={min_hits} of {len(mints)} trending tokens"
    if not keep:
        keep = dict(tally.most_common(25))
        mode = f"early on 1 of {len(mints)} trending tokens (strict filter empty)"
    os.makedirs("data", exist_ok=True)
    safeload.save_json(WATCHLIST,
                       {"wallets": keep, "mode": mode, "tokens": names,
                        "built": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime())},
                       allow_empty=True)
    print(f"  {len(keep)} wallets - {mode} -> {WATCHLIST}")
    return keep, mode


def load_watchlist_v2():
    """Reads either the old flat {wallet: hits} file or the new wrapped one."""
    try:
        d = json.load(open(WATCHLIST))
    except Exception:
        return {}, "no watchlist"
    if isinstance(d, dict) and "wallets" in d:
        return d["wallets"], d.get("mode", "")
    return d, "legacy watchlist"


if __name__ == "__main__":
    import sys
    if "seed" in sys.argv:
        seed_from_trending()
    else:
        wl, mode = load_watchlist_v2()
        print(f"  {len(wl)} wallets ({mode})")
