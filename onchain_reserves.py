"""Pool reserves read from chain, without knowing the DEX's layout.

WHY THIS EXISTS. Every label in this project has come from Dexscreener's own
reserve split, which means the fraud detector and its report card share one
source. If that field is wrong, D1 is unfalsifiable. This reads the same
quantity from Solana directly so the two can disagree.

HOW, without a decoder per DEX. Raydium, Meteora, pumpswap and fluxbeam all
store their vault addresses somewhere inside the pool account, at different
offsets. Rather than maintain a struct layout for each:

    1. fetch the pool account's raw bytes
    2. treat every 8-byte-aligned 32-byte window as a candidate pubkey
    3. ask the chain, in one batch call, which of those are SPL token accounts
    4. keep the ones holding the pool's own base or quote mint

That is layout-independent by construction and costs two RPC calls per pool. It
finds vaults for any AMM that stores them as pubkeys in the pool struct, which
is all of them, because the program itself has to find them the same way.

WHAT IT CANNOT DO. Concentrated-liquidity pools (Meteora DLMM) spread reserves
across many bin accounts rather than two vaults; this will under-read them and
they must be excluded rather than reported low. Validation against known-good
pools is therefore mandatory before any result is quoted - see validate().
"""
import os
import sys

import config
import sources as S

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
STABLES = {USDC: 1.0, USDT: 1.0}


def b58(raw):
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for b in raw:
        if b == 0:
            pad += 1
        else:
            break
    return "1" * pad + out


def _rpc(method, params, url=None):
    try:
        r = S._post(url or config.helius_rpc(),
                    {"jsonrpc": "2.0", "id": 1, "method": method, "params": params})
        return r.get("result"), r.get("error")
    except Exception as e:
        return None, f"{type(e).__name__}"


def vaults(pool_address, mints=None, max_candidates=600, step=1):
    """{mint: ui_amount} for every token account referenced by the pool account.

    `mints` optionally restricts the result to the pair's own two mints, which
    removes fee accounts and unrelated references.
    """
    import base64
    res, err = _rpc("getAccountInfo", [pool_address, {"encoding": "base64"}])
    if err or not res or not (res.get("value") or {}).get("data"):
        return {}, f"pool account unreadable ({err or 'no data'})"
    raw = base64.b64decode((res["value"]["data"])[0])
    cands, seen = [], set()
    # STEP 1, NOT 8. Anchor accounts carry an 8-byte discriminator so their
    # pubkeys land on 8-byte boundaries, but Raydium AMM v4, SPL token-swap and
    # fluxbeam pack structs without that padding. Scanning only 8-aligned
    # offsets found Meteora's vaults and missed every other DEX. One byte at a
    # time costs a few more candidates and finds all of them.
    for off in range(0, max(0, len(raw) - 32) + 1, step):
        w = raw[off:off + 32]
        if len(w) < 32 or w == b"\x00" * 32:
            continue
        k = b58(w)
        if k not in seen:
            seen.add(k)
            cands.append(k)
        if len(cands) >= max_candidates:
            break
    found = {}
    for i in range(0, len(cands), 100):          # getMultipleAccounts caps at 100
        chunk = cands[i:i + 100]
        r2, e2 = _rpc("getMultipleAccounts", [chunk, {"encoding": "jsonParsed"}])
        if e2 or not r2:
            continue
        for acc in (r2.get("value") or []):
            if not acc:
                continue
            # Non-token accounts come back with `data` as a [base64, encoding]
            # list rather than a parsed dict. Skip those rather than crash.
            data = acc.get("data")
            if not isinstance(data, dict):
                continue
            info = (data.get("parsed") or {}).get("info") or {}
            if not info.get("mint") or "tokenAmount" not in info:
                continue
            m = info["mint"]
            if mints and m not in mints:
                continue
            amt = float((info["tokenAmount"] or {}).get("uiAmount") or 0)
            # A pool can reference several accounts of one mint (vault + fees).
            # The reserve is the largest.
            if amt > found.get(m, 0.0):
                found[m] = amt
    return found, None


def quote_price_usd(quote_mint, sol_usd=None):
    """USD per unit of the quote asset. Stables are 1; SOL needs a price."""
    if quote_mint in STABLES:
        return STABLES[quote_mint]
    if quote_mint == WSOL:
        if sol_usd:
            return sol_usd
        try:
            return float(S.prices(("solana",))["solana"]["usd"])
        except Exception:
            return None
    return None


def base_vault_is_plausible(base_mint, found_base):
    """Did we find the pool's REAL base vault, or a smaller unrelated account?

    Caught 2026-09-07 on WET: the scan picked a base account holding 1.27M
    tokens when the mint's largest account held 985M, and therefore also picked
    the wrong quote account - reporting $13 of depth against Dexscreener's
    $10,297. Reported as a finding that would have been a fabrication.

    The pool's base vault is normally the largest holder of a launch token, so
    a found vault far below the largest account means the scan missed and the
    read must be discarded rather than believed.
    """
    if not found_base:
        return False, "no base vault found"
    res, err = _rpc("getTokenLargestAccounts", [base_mint])
    vals = ((res or {}).get("value") or [])
    if err or not vals:
        return None, "cannot verify (largest accounts unreadable)"
    largest = max(float(v.get("uiAmount") or 0) for v in vals)
    if largest <= 0:
        return None, "cannot verify (no balances)"
    share = found_base / largest
    if share < 0.5:
        return False, (f"found base vault holds {found_base:,.0f} vs largest "
                       f"account {largest:,.0f} ({100*share:.1f}%) - scan missed "
                       f"the real vault")
    return True, None


def exit_depth(pool_address, base_mint, quote_mint, sol_usd=None, verify=True):
    """Quote-side USD held by the pool, read from chain. None if not readable."""
    v, err = vaults(pool_address, mints={base_mint, quote_mint})
    if err:
        return None, err, {}
    if quote_mint not in v:
        return None, "quote vault not found in pool account", v
    if verify:
        ok, why = base_vault_is_plausible(base_mint, v.get(base_mint))
        if ok is False:
            return None, f"UNRELIABLE READ: {why}", v
    px = quote_price_usd(quote_mint, sol_usd)
    if px is None:
        return None, f"no USD price for quote mint {quote_mint[:8]}", v
    return v[quote_mint] * px, None, v


def validate(samples, verbose=True):
    """MANDATORY before quoting anything. Compares the on-chain read against
    Dexscreener on pools where both should agree, and reports the distribution
    of the ratio. `samples` is [(pair_address, base_mint, quote_mint, ds_depth)].
    """
    import resolve                                   # noqa: F401  (docs the pair)
    try:
        sol = float(S.prices(("solana",))["solana"]["usd"])
    except Exception:
        sol = None
    rows = []
    for pair, base, quote, ds in samples:
        oc, err, _ = exit_depth(pair, base, quote, sol_usd=sol)
        if oc is None or not ds:
            if verbose:
                print(f"    {pair[:14]}..  unreadable: {err}")
            continue
        rows.append((ds, oc, oc / ds if ds else None))
    return rows


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    print(__doc__)
