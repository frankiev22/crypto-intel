"""Find a mint's REAL pools from the CONTRACT ADDRESS, on chain, without asking
an indexer and without knowing any AMM's account layout.

Rule: PRECOMMIT_pool_discovery.md, written before a single sample contract was
read. Instrument validated first on a mint outside the sample.

⛔ WHY THIS EXISTS. `record_outcome` writes `gone` when two INDEXER lookups of
the pair address fail (`journal.py:974`). That collapses "we could not find it"
into "it does not exist", which is the `authority_live=None` bug class. And the
pair address on those rows is usually a pump.fun BONDING CURVE (BACKLOG A52:
243 rows on 135 contracts were scored against a curve after our own ledger
recorded the migration), so the row points at an account the token has LEFT.
The real pool after bonding is one we never recorded.

⛔ MY OWN FIRST ATTEMPT WAS A TAUTOLOGY. `analysis/gone_onchain/probe.py` read
`getAccountInfo` on the recorded pool address and found 54 of 54 present. All 54
were curve accounts, and a curve account is never closed when a token bonds, so
that result was guaranteed before the first RPC.

HOW THIS WORKS, and why it needs no layouts. A pool's reserves live in ordinary
SPL token accounts. The SPL token-account layout is fixed and public:

    mint   @  0  (32 bytes)
    owner  @ 32  (32 bytes)
    amount @ 64  (u64 little endian)

So: enumerate the token accounts OF THE MINT, look at each account's `owner`,
and ask what program owns that owner. An owner owned by an AMM program is a
pool. No AMM struct is ever parsed.

⚠️ DISCOVERY IS A FLOOR, NEVER A PROOF OF ABSENCE. Resolving every holder is not
affordable (measured: 60,691 token accounts for EMBER, and batching all their
owners returned HTTP 429 immediately), so the ladder reaches the largest holders
only. Finding a pool is proof. Finding none is not.

Usage:
    python pooldiscovery.py <MINT>
    import pooldiscovery; pooldiscovery.discover(mint)
"""
import base64
import json
import os
import struct
import sys
import time
import urllib.error
import urllib.request

import config

UA = "Mozilla/5.0 (crypto-intel research; contact via github)"

TOKEN_PROGRAM = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN_2022 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"
SYSTEM_PROGRAM = "11111111111111111111111111111111"

# ⛔ PRE-COMMITTED in PRECOMMIT_pool_discovery.md before any sample read.
RUNG1_TOP = 20            # getTokenLargestAccounts returns at most this
RUNG2_TOP = 100           # owners resolved from a full enumeration
MAX_VAULTS_PER_POOL = 50  # more than this means a SHARED authority, not a pool
PACE_S = 0.14             # Helius free tier answered 429 on an unpaced batch
RETRY_429 = 3

# Known AMM / launchpad program owners. Same map as analysis/gone_onchain.
AMM_OWNERS = {
    "675kPX9MHTjS2zt1qfr1NYHuzeLXfQM9H24wFSUt1Mp8": "raydium_v4",
    "CPMMoo8L3F4NbTegBCKVNunggL7H1ZpdTHKxQB5qKP1C": "raydium_cpmm",
    "CAMMCzo5YL8w4VFF8KVHrK22GGUsp5VTaW7grrKgrWqK": "raydium_clmm",
    "LBUZKhRxPF3XUpBCjp4YzTKgLccjZhTSDM9YuVaPwxo": "meteora_dlmm",
    "Eo7WjKq67rjJQSZxS6z3YkapzY3eMj6Xy8X5EQVn5UaB": "meteora_dynamic",
    "dbcij3LWUppWqq96dh6gJWwBifmcGfLSB5D4DuSMaqN": "meteora_dbc",
    "whirLbMiicVdio4qvUfM5KAg6Ct8VwpYzGff3uctyCc": "orca_whirlpool",
    "pAMMBay6oceH9fJKBRHGP5D4bD4sWpmSwMn52FMfXEA": "pumpswap",
    "6EF8rrecthR5Dkzon8Nwu78hRvfCKubJ14M5uBEwF6P": "pumpfun_curve",
    "srmqPvymJeFKQ4zGQed1GFppgkRHL9kaELCbyksJtPX": "openbook",
    "SoLFiHG9TfgtdUXUjWAxi3LtvYuFyDLVhBWxdMZxyCe": "solfi",
    "obriQD1zbpyLz95G5n7nJe6a4DPjpFwa5XYPoNm113y": "obric",
    "MoonCVVNZFSYkqNXP6bxHLPL6QQJiMagDL3qcqUQTrG": "moonshot",
    "5jnapfrAN47UYkLkEf7HnprPPBCQLvkYWGZDeKkaP5hv": "raydium_launchlab",
    # ⭐⭐ FOUND BY MEASUREMENT 2026-09-23, and it was entirely missing.
    # The offset probe hit 7 of 48 sampled pools under this program and our
    # map had no name for it. The indexer labels its pools `DYN2` under
    # dexId `meteora`, and one of them is EMBER/MET - which matters, because
    # EMBER is a Meteora pairing-launchpad token and we would have read its
    # pools as "unknown program" and excluded them.
    "cpamdpZCGKUy5JxQXB4dcpGPiikHawvSWAd6mEn1sGG": "meteora_damm_v2",
    # ⭐ FOUND BY MEASUREMENT 2026-09-23. It owns the recorded pair of 1 of the
    # 120 backfill contracts, it is executable, and our map had no name for it.
    # Its pool is the 324-byte SPL-token-swap shape (mint slots 131 and 163) and
    # it keeps its vaults under a separate authority, which is why
    # `vaults_from_struct` had to exist before this entry was usable.
    "FLUXubRmkEi2q6K3Y9kBPg9248ggaZVsoSFhtJHSrm1X": "fluxbeam",
    # ⚠️ One sample only, offset measured at 131 but on a single pool, so it
    # is carried with low confidence and named by its program id.
    "9W959DqEETiGZocYWCQPaJ6sBmUzgfxXfqGeTEdp3aQP": "unnamed_amm_9W959Dq",
}

# ⛔ PROGRAM-OWNED IS NOT POOL-OWNED, and the negative control caught me counting
# it that way. The phantom EMBER surfaced EIGHT accounts owned by
# `pfeeUxB6…`, the pump.fun FEE program, each holding ~112 trillion base units
# and 3-10 SOL of lamports. Those are accumulated creator and protocol fees, not
# liquidity, and nobody can sell into them. The pre-commit says a pool is an
# owner owned by a KNOWN AMM program, and my first version said "any program",
# which would have graded almost every mint as having a pool.
#
# ⚠️ They are still RECORDED, per standing rule 15: an owner we excluded is
# reported with its program id, so a venue genuinely missing from AMM_OWNERS is
# visible rather than silently dropped.
NOT_POOLS = {
    "pfeeUxB6jkeY1Hxd7CsFCAjcbHA9rWtchMGdZ6VojVZ": "pumpfun_fee_program",
    # ⭐ MEASURED, not assumed. This program owns `HWGoJ1HaMFUiDgfD7FVxMaYJAE2A5-
    # JjF7si6CgWSvRFQ`, one account holding **31,487 token accounts across 31,479
    # distinct mints** plus 233.96 WSOL. A pool holds ONE pair; an account holding
    # thirty-one thousand mints is a router or sweeper. It appeared on 10 of the
    # 120 sample rows, and adding it here changes **no verdict** - all 10 had
    # already found a real pool - which is why this is a method fix and not
    # post-hoc tuning of the result.
    "3s1rAymURnacreXreMy718GfqW6kygQsLNka1xDyW8pC": "many_mint_infrastructure",
    "ATokenGPvbdGVxr1b2hvZbsiqW5xWH25efTNsLJA8knL": "associated_token_program",
    "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA": "token_program",
    "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb": "token_2022_program",
}

# ⛔ Only these are VALUED, per the pre-commit. Everything else is COUNTED and
# reported with a NULL usd value, never as 0 (standing rule 5).
VALUED = {
    "So11111111111111111111111111111111111111112": ("SOL", 9),
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v": ("USDC", 6),
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB": ("USDT", 6),
}

_B58 = "123456789ABCDEFGHJKLMNPQRSTUVWXYZabcdefghijkmnopqrstuvwxyz"


def b58encode(raw):
    n = int.from_bytes(raw, "big")
    out = ""
    while n:
        n, r = divmod(n, 58)
        out = _B58[r] + out
    pad = 0
    for b in raw:
        if b:
            break
        pad += 1
    return "1" * pad + (out or "")


class Budget(object):
    """Counts every RPC so a run can say what it spent and what it truncated."""

    def __init__(self):
        self.calls = 0
        self.errors = 0
        self.rate_limited = 0
        self.seconds = 0.0


BUDGET = Budget()


def rpc(method, params, timeout=60, budget=None):
    """One paced JSON-RPC call. Returns (result, error_string_or_None).

    ⛔ A 429 is retried with backoff and, if it still fails, returned as an
    ERROR. It is never allowed to look like an empty result, because an empty
    result would read as "no pool" (standing rule 16).
    """
    b = budget or BUDGET
    body = json.dumps({"jsonrpc": "2.0", "id": 1, "method": method,
                       "params": params}).encode()
    for attempt in range(RETRY_429 + 1):
        time.sleep(PACE_S)
        t0 = time.time()
        b.calls += 1
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                config.helius_rpc(), data=body,
                headers={"Content-Type": "application/json",
                         "User-Agent": UA}), timeout=timeout)
            d = json.loads(r.read())
            b.seconds += time.time() - t0
            if d.get("error"):
                b.errors += 1
                return None, "rpc_error: %s" % str(d["error"])[:160]
            return d.get("result"), None
        except urllib.error.HTTPError as e:
            b.seconds += time.time() - t0
            if e.code == 429:
                b.rate_limited += 1
                if attempt < RETRY_429:
                    time.sleep(1.5 * (attempt + 1))
                    continue
            b.errors += 1
            return None, "http_%d" % e.code
        except Exception as e:
            b.seconds += time.time() - t0
            b.errors += 1
            return None, "%s: %s" % (type(e).__name__, str(e)[:120])
    return None, "http_429_exhausted"


def _accounts_info(pubkeys, budget=None, parsed=True):
    """getMultipleAccounts in chunks of 100. Returns {pubkey: account_or_None}.

    ⛔ A chunk that fails is recorded as an ERROR key, never as absent accounts.
    """
    out = {}
    errs = []
    enc = "jsonParsed" if parsed else "base64"
    for i in range(0, len(pubkeys), 100):
        chunk = pubkeys[i:i + 100]
        res, err = rpc("getMultipleAccounts", [chunk, {"encoding": enc}],
                       budget=budget)
        if err or not res:
            errs.append(err or "empty")
            continue
        for pk, acc in zip(chunk, res.get("value") or []):
            out[pk] = acc
    return out, errs


def _largest(mint, budget=None):
    """Rung 1: the mint's largest token accounts, straight from the RPC."""
    res, err = rpc("getTokenLargestAccounts", [mint, {"commitment": "confirmed"}],
                   budget=budget)
    if err:
        return None, err
    vals = (res or {}).get("value") or []
    return [{"account": v["address"],
             "amount": int(v.get("amount") or 0)} for v in vals], None


def _enumerate_all(mint, budget=None):
    """Rung 2: EVERY token account of the mint, from both token programs.

    Layout-free: a dataSlice of 40 bytes from offset 32 gives owner + amount.
    Measured on EMBER: 60,691 accounts in 6.5s. This is exact, not a sample.
    """
    rows = []
    errs = []
    for prog in (TOKEN_PROGRAM, TOKEN_2022):
        flt = [{"memcmp": {"offset": 0, "bytes": mint}}]
        if prog == TOKEN_PROGRAM:
            flt.insert(0, {"dataSize": 165})
        res, err = rpc("getProgramAccounts", [prog, {
            "encoding": "base64",
            "commitment": "confirmed",
            "filters": flt,
            "dataSlice": {"offset": 32, "length": 40},
        }], timeout=120, budget=budget)
        if err:
            errs.append("%s: %s" % (prog[:8], err))
            continue
        import base64
        for it in res or []:
            try:
                raw = base64.b64decode(it["account"]["data"][0])
                rows.append({"account": it["pubkey"],
                             "owner": b58encode(raw[:32]),
                             "amount": struct.unpack("<Q", raw[32:40])[0]})
            except Exception:
                continue
    return rows, errs


def _owner_programs(owners, budget=None):
    """What program owns each of these accounts. A program-owned account that an
    AMM program owns is a pool."""
    info, errs = _accounts_info(sorted(set(owners)), budget=budget)
    out = {}
    for pk, acc in info.items():
        out[pk] = (acc or {}).get("owner")
    return out, errs


# ⛔ Raydium v4 puts every pool's vaults under ONE authority PDA, so
# getTokenAccountsByOwner on it returns tens of thousands of vaults belonging to
# other pools. The quote side cannot be attributed to one pool that way, so it is
# reported UNREADABLE rather than guessed.
SHARED_AUTHORITIES = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1": "raydium_v4_authority",
}


def _vaults(pool, budget=None):
    """Every token vault this pool owns, which is what gives the QUOTE side.

    ⛔ More than MAX_VAULTS_PER_POOL means the owner is a SHARED AUTHORITY (a
    Raydium v4 authority owns every v4 pool's vaults), so the quote side cannot
    be attributed to one pool. That is reported UNREADABLE, never guessed.
    """
    if pool in SHARED_AUTHORITIES:
        return [], ["shared_authority_" + SHARED_AUTHORITIES[pool]]
    rows = []
    errs = []
    for prog in (TOKEN_PROGRAM, TOKEN_2022):
        res, err = rpc("getTokenAccountsByOwner",
                       [pool, {"programId": prog}, {"encoding": "jsonParsed"}],
                       budget=budget)
        if err:
            errs.append(err)
            continue
        for v in (res or {}).get("value") or []:
            try:
                info = v["account"]["data"]["parsed"]["info"]
                rows.append({
                    "vault": v["pubkey"],
                    "mint": info["mint"],
                    "amount": int(info["tokenAmount"]["amount"]),
                    "decimals": int(info["tokenAmount"]["decimals"]),
                    "ui": float(info["tokenAmount"].get("uiAmountString") or 0),
                })
            except Exception:
                continue
    if len(rows) > MAX_VAULTS_PER_POOL:
        return [], ["shared_authority_%d_vaults" % len(rows)]
    return rows, errs


# ---------------------------------------------------------------------------
# ⭐⭐ THE VAULTS A POOL DOES NOT OWN, found by scanning its own bytes.
#
# MEASURED 2026-09-23, and it is the bug behind "which pool holds the money".
# `_vaults` asks getTokenAccountsByOwner(pool). That works when the pool account
# is itself the vault owner (pump.fun curve, PumpSwap). ⛔ It returns ZERO for a
# venue that keeps its vaults under a separate authority, and zero vaults read as
# $0.00 of quote side with nothing unvalued - a CONFIDENT ZERO THAT WAS NEVER
# READ. Measured: all 3 sampled Meteora DBC pools and the one FluxBeam pool
# return 0 vaults, and 12 of 120 recorded pairs in the backfill sample are DBC.
#
# ⭐ The fix assumes NO LAYOUT. Every 32-byte window of the pool's own data is a
# CANDIDATE pubkey; we ask the chain which of those candidates are real SPL token
# accounts, and keep the ones whose mint is a real mint. A vault address is in the
# struct by definition, so this finds it without knowing where it sits.
# ---------------------------------------------------------------------------
def vaults_from_struct(pool, budget=None, max_candidates=600):
    """Vaults referenced INSIDE the pool account, for venues that own none.

    Same row shape as `_vaults`. Returns (rows, errors, candidates_checked).
    ⛔ An RPC failure returns an error, never an empty vault list, because empty
    is what this function exists to stop being published as zero.
    """
    res, err = rpc("getAccountInfo",
                   [pool, {"encoding": "base64", "commitment": "confirmed"}],
                   budget=budget)
    if err:
        return [], ["struct_read: " + err], 0
    val = (res or {}).get("value")
    if not val:
        return [], ["struct_read: account absent"], 0
    try:
        raw = base64.b64decode(val["data"][0])
    except Exception as e:
        return [], ["struct_decode: %s" % str(e)[:60], ], 0

    import solpda
    seen = set()
    cand = []
    for i in range(0, max(0, len(raw) - 31)):
        w = raw[i:i + 32]
        if w in seen or not any(w):
            continue
        seen.add(w)
        cand.append(solpda.b58encode(w))
        if len(cand) >= max_candidates:
            break

    rows = []
    errs = []
    for i in range(0, len(cand), 100):
        chunk = cand[i:i + 100]
        r2, e2 = rpc("getMultipleAccounts",
                     [chunk, {"encoding": "jsonParsed"}], budget=budget)
        if e2 or not r2:
            errs.append("candidates: " + (e2 or "empty"))
            continue
        for pk, acc in zip(chunk, r2.get("value") or []):
            if not acc or acc.get("owner") not in (TOKEN_PROGRAM, TOKEN_2022):
                continue
            try:
                info = acc["data"]["parsed"]["info"]
                if info.get("state") is None and "mint" not in info:
                    continue
                rows.append({
                    "vault": pk,
                    "mint": info["mint"],
                    # ⛔ the vault's AUTHORITY. A pool struct can reference an
                    # account that is not its own (a protocol fee vault, a
                    # router), and summing one of those as this pool's quote side
                    # would OVERSTATE it. The caller keeps one authority group.
                    "vault_owner": info.get("owner"),
                    "amount": int(info["tokenAmount"]["amount"]),
                    "decimals": int(info["tokenAmount"]["decimals"]),
                    "ui": float(info["tokenAmount"].get("uiAmountString") or 0),
                    "how": "struct-scan",
                })
            except Exception:
                continue
    # ⚠️ A struct can reference a vault belonging to something else, so this is
    # attributed only when the caller checks the mints against the pair.
    return rows, errs, len(cand)


# ⭐ A pump.fun bonding curve's quote side is NATIVE SOL in its own lamports, so
# getTokenAccountsByOwner cannot see it and our reader called it $0. MEASURED on
# 26 live curves from the backfill sample: 2 hold >= $10 above rent and one holds
# 1.978990 SOL = $226.61. Labelling that `curve_died` with "$0 quote" was wrong.
_RENT_MIN = {}


def rent_exempt(data_len, budget=None):
    """The rent-exempt minimum for this data length, asked once per length.

    ⛔ None on failure, never a guess, because the caller subtracts it.
    """
    if data_len in _RENT_MIN:
        return _RENT_MIN[data_len]
    res, err = rpc("getMinimumBalanceForRentExemption", [int(data_len)],
                   budget=budget)
    if err or res is None:
        return None
    _RENT_MIN[data_len] = int(res)
    return int(res)


def sol_price():
    """One SOL price for the whole run, with its source and read time on it."""
    for url, pick in (
        ("https://lite-api.jup.ag/price/v3?ids=" + list(VALUED)[0],
         lambda d: float(d[list(VALUED)[0]]["usdPrice"])),
        ("https://api.coingecko.com/api/v3/simple/price"
         "?ids=solana&vs_currencies=usd", lambda d: float(d["solana"]["usd"])),
    ):
        try:
            r = urllib.request.urlopen(urllib.request.Request(
                url, headers={"User-Agent": UA}), timeout=25)
            return pick(json.loads(r.read())), url.split("/")[2], int(time.time())
        except Exception:
            continue
    return None, None, int(time.time())


def quote_value(vaults, mint, sol_usd):
    """USD of the QUOTE side of one pool, plus what could not be valued.

    ⛔ The base mint's own vault is NOT quote side. A pool holding a billion of
    its own worthless token has no exit in it.
    ⛔ A vault in an asset we do not price is COUNTED with a NULL value.
    """
    usd = 0.0
    valued = []
    unvalued = []
    for v in vaults:
        if v["mint"] == mint:
            continue
        spec = VALUED.get(v["mint"])
        if not spec:
            unvalued.append({"mint": v["mint"], "ui": v["ui"], "usd": None})
            continue
        name, dec = spec
        ui = v["amount"] / float(10 ** dec)
        px = sol_usd if name == "SOL" else 1.0
        if px is None:
            unvalued.append({"mint": v["mint"], "ui": ui, "usd": None,
                             "why": "no_sol_price"})
            continue
        usd += ui * px
        valued.append({"asset": name, "ui": ui, "usd": ui * px})
    return usd, valued, unvalued


def discover(mint, sol_usd=None, budget=None, allow_rung2=True):
    """Every pool of this mint the ladder can reach, with its quote side.

    Returns a dict that always says WHICH RUNG answered, what it spent, and that
    a negative is a FLOOR. ⛔ `pools_found` == 0 never means "no pool exists".
    """
    b = budget or Budget()
    t0 = time.time()
    out = {
        "mint": mint,
        "rung": None,
        "pools": [],
        "pool_count": 0,
        "holders_reached": 0,
        "holders_total_known": None,
        "quote_usd_max": 0.0,
        "quote_usd_total": 0.0,
        "unvalued_vaults": 0,
        "sol_usd": sol_usd,
        "errors": [],
        "excluded_owners": [],
        "unknown_programs": [],
        "verdict": None,
        # ⛔ Stated on every single row, so no reader can mistake a null for a
        # proof. This is the whole point of the module.
        "absence_is_a_floor": True,
        "floor_note": ("discovery reaches the largest holders only, so "
                       "NO_POOL_FOUND means we did not find one, NOT that "
                       "none exists"),
    }

    # -------------------------------------------------- rung 1
    largest, err = _largest(mint, budget=b)
    if err:
        out["errors"].append("largest: " + err)
        out["verdict"] = "UNREADABLE"
        out["elapsed_s"] = round(time.time() - t0, 2)
        return out
    out["rung"] = 1
    out["holders_reached"] = len(largest)
    cand = {}
    if largest:
        info, errs = _accounts_info([r["account"] for r in largest], budget=b)
        out["errors"].extend("largest_info: " + e for e in errs)
        for r in largest:
            acc = info.get(r["account"])
            try:
                owner = acc["data"]["parsed"]["info"]["owner"]
            except Exception:
                continue
            cand.setdefault(owner, 0)
            cand[owner] += r["amount"]

    pools = _pools_from(cand, out, b)

    # -------------------------------------------------- rung 2
    if not pools and allow_rung2:
        rows, errs = _enumerate_all(mint, budget=b)
        out["errors"].extend("enumerate: " + e for e in errs)
        if errs and not rows:
            out["verdict"] = "UNREADABLE"
            out["elapsed_s"] = round(time.time() - t0, 2)
            return out
        out["rung"] = 2
        out["holders_total_known"] = len(rows)
        rows.sort(key=lambda r: -r["amount"])
        top = rows[:RUNG2_TOP]
        out["holders_reached"] = len(top)
        out["truncated_holders"] = max(0, len(rows) - len(top))
        cand = {}
        for r in top:
            cand.setdefault(r["owner"], 0)
            cand[r["owner"]] += r["amount"]
        pools = _pools_from(cand, out, b)

    # -------------------------------------------------- quote side
    for p in pools:
        vaults, errs = _vaults(p["pool"], budget=b)
        if errs:
            p["vault_errors"] = errs
        usd, valued, unvalued = quote_value(vaults, mint, sol_usd)
        p["vaults"] = valued
        p["unvalued"] = unvalued
        p["quote_usd"] = usd if valued else (None if unvalued else 0.0)
        p["vault_count"] = len(vaults)
        out["unvalued_vaults"] += len(unvalued)
        if usd:
            out["quote_usd_total"] += usd
            out["quote_usd_max"] = max(out["quote_usd_max"], usd)

    out["pools"] = pools
    out["pool_count"] = len(pools)
    out["verdict"] = _verdict(out)
    out["rpc_calls"] = b.calls
    out["rpc_errors"] = b.errors
    out["rate_limited"] = b.rate_limited
    out["elapsed_s"] = round(time.time() - t0, 2)
    return out


def _pools_from(cand, out, budget):
    """Which of these candidate owners are AMM-owned, and their lamports."""
    if not cand:
        return []
    progs, errs = _owner_programs(list(cand), budget=budget)
    out["errors"].extend("owner_prog: " + e for e in errs)
    info, errs2 = _accounts_info(list(cand), budget=budget)
    out["errors"].extend("owner_info: " + e for e in errs2)
    pools = []
    excluded = []
    for owner, held in sorted(cand.items(), key=lambda kv: -kv[1]):
        prog = progs.get(owner)
        if not prog or prog == SYSTEM_PROGRAM:
            continue
        acc = info.get(owner) or {}
        if prog not in AMM_OWNERS:
            # ⚠️ Recorded, never silently dropped. If a real venue is missing
            # from AMM_OWNERS this is where it shows up.
            excluded.append({"owner": owner, "program": prog,
                             "known_non_pool": NOT_POOLS.get(prog),
                             "base_amount": held,
                             "lamports": acc.get("lamports")})
            continue
        pools.append({
            "pool": owner,
            "program": prog,
            "venue": AMM_OWNERS[prog],
            "known_amm": True,
            "base_amount": held,
            # ⚠️ Recorded, NOT counted as tradeable reserves: a pump.fun curve
            # holds SOL natively, and lamports also include rent.
            "lamports": acc.get("lamports"),
        })
    out.setdefault("excluded_owners", []).extend(excluded)
    out["unknown_programs"] = sorted({e["program"] for e in excluded
                                      if not e["known_non_pool"]})
    return pools


def _verdict(out):
    """⛔ The pre-committed bands. UNVALUED is its own bucket, never DUST."""
    if not out["pools"]:
        return "NO_POOL_FOUND"
    if out["quote_usd_max"] >= 100:
        return "POOL_QUOTE_100"
    if out["quote_usd_max"] >= 10:
        return "POOL_QUOTE_10"
    if out["quote_usd_max"] <= 0 and out["unvalued_vaults"]:
        return "POOL_QUOTE_UNVALUED"
    return "POOL_QUOTE_DUST"


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        return 2
    px, src, ts = sol_price()
    print("SOL $%s from %s at %d\n" % (px, src, ts))
    for mint in argv[1:]:
        d = discover(mint, sol_usd=px)
        print("%s  %s  rung %s  pools %d  quote_max $%.2f  %d calls %.1fs" % (
            mint[:12], d["verdict"], d["rung"], d["pool_count"],
            d["quote_usd_max"], d.get("rpc_calls", 0), d["elapsed_s"]))
        for p in d["pools"]:
            print("    %-16s %s  base %d  quote $%s  lamports %s" % (
                p["venue"], p["pool"][:16], p["base_amount"],
                p["quote_usd"], p["lamports"]))
        if d["errors"]:
            print("    errors:", d["errors"][:3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
