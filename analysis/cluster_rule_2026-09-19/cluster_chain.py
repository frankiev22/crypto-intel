"""Pool price and quote-side depth at a moment, from the pool's own vaults.

PRECOMMIT_cluster_rule.md: entry = the pool price in the first transaction AFTER
the fire; outcome = the pool at +6h / +24h after entry, with >= $500 of
quote-side depth. Nothing here reads a reported field.

- price: |d quote_vault| / |d base_vault| of a swap on THIS pool (vault deltas of
  opposite sign). Works for constant-product and concentrated pools alike.
- depth: the quote vault's post balance in the latest transaction touching it at
  or before the moment - a liquidity removal counts, so a rug shows as no depth.
- seeking by time: a signature from the block at time T is passed as `before`
  to getSignaturesForAddress(pool) (verified 2026-09-19 on Helius).
"""
import json
import os
import sys
import time
import urllib.request

sys.path.insert(0, r"C:\Users\Frankie\Desktop\Projects\crypto-intel")
import config  # noqa: E402

URL = config.helius_rpc()
WSOL = "So11111111111111111111111111111111111111112"
USDC = "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v"
USDT = "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB"
CALLS = {"n": 0}
_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58decode(s):
    n = 0
    for c in s:
        n = n * 58 + _B58.index(c)
    raw = n.to_bytes((n.bit_length() + 7) // 8, "big") if n else b""
    pad = len(s) - len(s.lstrip("1"))
    return b"\x00" * pad + raw


def rpc(method, params):
    err = None
    for i in range(6):
        try:
            CALLS["n"] += 1
            req = urllib.request.Request(
                URL, data=json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                                      "params": params}).encode(),
                headers={"Content-Type": "application/json", "User-Agent": "crypto-intel/cluster"})
            r = json.load(urllib.request.urlopen(req, timeout=60))
            if "error" in r:
                e = r["error"]
                # skipped slot / missing block: a real answer, not a transport failure
                if isinstance(e, dict) and e.get("code") in (-32007, -32009, -32004):
                    return None
                raise RuntimeError(e)
            time.sleep(0.05)
            return r["result"]
        except Exception as e:
            err = e
            time.sleep(1.5 * (i + 1))
    raise err


# ---------------------------------------------------------------- time -> signature
_SLOTS = {}


def _block_time(slot):
    if slot not in _SLOTS:
        _SLOTS[slot] = rpc("getBlockTime", [slot])
    return _SLOTS[slot]


def _nearest(slot):
    for k in range(0, 40):
        bt = _block_time(slot + k)
        if bt is not None:
            return slot + k, bt
    raise RuntimeError(f"no block near slot {slot}")


_REF = {}


def slot_at(t):
    """A produced slot whose block time is within ~2s of t (secant search)."""
    if not _REF:
        s = rpc("getSlot", [])
        _REF["a"] = _nearest(s - 50)
    s0, t0 = _REF["a"]
    guess = int(s0 - (t0 - t) / 0.4)
    s1, t1 = _nearest(guess)
    for _ in range(8):
        if abs(t1 - t) <= 2:
            break
        rate = (t1 - t0) / (s1 - s0) if s1 != s0 else 0.4
        rate = rate if 0.3 < rate < 0.6 else 0.4
        s0, t0 = s1, t1
        s1, t1 = _nearest(int(s1 - (t1 - t) / rate))
    return s1


def anchor_sig(t):
    """A signature landed at ~t (from the block at slot_at(t))."""
    s = slot_at(t)
    for k in range(0, 40):
        b = rpc("getBlock", [s + k, {"transactionDetails": "signatures", "rewards": False,
                                     "maxSupportedTransactionVersion": 1}])
        if b and b.get("signatures"):
            return b["signatures"][0], b.get("blockTime")
    raise RuntimeError(f"no signature near {t}")


def sigs_before(addr, before, limit=1000):
    return rpc("getSignaturesForAddress", [addr, {"before": before, "limit": limit}]) or []


_TX = {}


def tx(sig):
    if sig not in _TX:
        _TX[sig] = rpc("getTransaction", [sig, {"encoding": "jsonParsed",
                                                "maxSupportedTransactionVersion": 1}])
    return _TX[sig]


# ---------------------------------------------------------------- the pool's vaults
def _balances(t):
    m = t["meta"]
    keys = [k["pubkey"] for k in t["transaction"]["message"]["accountKeys"]]
    pre = {b["accountIndex"]: b for b in (m.get("preTokenBalances") or [])}
    post = {b["accountIndex"]: b for b in (m.get("postTokenBalances") or [])}
    out = {}
    for i in set(pre) | set(post):
        b = post.get(i) or pre.get(i)
        v0 = float((pre.get(i) or {}).get("uiTokenAmount", {}).get("uiAmountString") or 0)
        v1 = float((post.get(i) or {}).get("uiTokenAmount", {}).get("uiAmountString") or 0)
        out[keys[i]] = {"mint": b["mint"], "pre": v0, "post": v1}
    return out


def vaults(pool, token, sample_sigs):
    """(base_vault, quote_vault, quote_mint): token accounts named in the pool's
    own account data, found in a transaction on the pool."""
    acc = rpc("getAccountInfo", [pool, {"encoding": "base64"}])
    import base64
    data = base64.b64decode(acc["value"]["data"][0]) if acc and acc.get("value") else b""
    for s in sample_sigs[:6]:
        t = tx(s)
        if not t or t["meta"].get("err"):
            continue
        base = quote = qmint = None
        for addr, b in _balances(t).items():
            if b58decode(addr) in data:
                if b["mint"] == token:
                    base = addr
                elif b["mint"] in (WSOL, USDC, USDT):
                    quote, qmint = addr, b["mint"]
        if base and quote:
            return base, quote, qmint
    return None


def swap_in(t, base_v, quote_v):
    """(price quote/token, quote_post, base_post) if t swaps on this pool."""
    if not t or t["meta"].get("err"):
        return None
    bal = _balances(t)
    b, q = bal.get(base_v), bal.get(quote_v)
    if not b or not q:
        return None
    db, dq = b["post"] - b["pre"], q["post"] - q["pre"]
    if db == 0 or dq == 0 or (db > 0) == (dq > 0):
        return None
    return abs(dq) / abs(db), q["post"], b["post"]


def quote_post(t, quote_v):
    if not t or t["meta"].get("err"):
        return None
    q = _balances(t).get(quote_v)
    return q["post"] if q else None


# ---------------------------------------------------------------- moments
def first_swap_after(pool, base_v, quote_v, T, max_window=36 * 3600, max_tx=10):
    """First swap on the pool with blockTime > T. None if none within max_window."""
    w = 600
    while w <= max_window:
        a, _ = anchor_sig(T + w)
        got, before = [], a
        for _ in range(30):
            page = sigs_before(pool, before)
            if not page:
                break
            got += [p for p in page if (p.get("blockTime") or 0) > T]
            if (page[-1].get("blockTime") or 0) <= T or len(page) < 1000:
                break
            before = page[-1]["signature"]
        cands = sorted([p for p in got if not p.get("err")], key=lambda p: p["blockTime"])
        for p in cands[:max_tx]:
            s = swap_in(tx(p["signature"]), base_v, quote_v)
            if s:
                return {"sig": p["signature"], "ts": p["blockTime"], "price": s[0], "quote": s[1]}
        if cands and len(cands) >= max_tx:
            return None  # busy pool, none of the first 10 were swaps: recorded as unpriced
        w *= 4
    return None


def state_at(pool, base_v, quote_v, T, floor_ts, max_tx=12):
    """At time T: price from the last swap at or before T, depth from the latest
    transaction touching the quote vault at or before T. Never looks before floor_ts."""
    a, _ = anchor_sig(T)
    page = [p for p in sigs_before(pool, a, limit=200) if not p.get("err")
            and (p.get("blockTime") or 0) >= floor_ts]
    price = depth = None
    last_ts = None
    for p in page[:max_tx]:
        t = tx(p["signature"])
        if depth is None:
            d = quote_post(t, quote_v)
            if d is not None:
                depth, last_ts = d, p["blockTime"]
        s = swap_in(t, base_v, quote_v)
        if s:
            price = s[0]
            break
    return {"price": price, "quote": depth, "last_tx_ts": last_ts}
