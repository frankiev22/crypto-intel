"""DERIVE a mint's pools, then say what state each pool is actually in.

Rule: PRECOMMIT_pool_state.md, written before this ran against the record.

Frank: "I would probably rather fix pool discovery. That's been a problem for us.
We can't publish shit data."

⛔ WHY THIS REPLACES THE LADDER AS THE PRIMARY PATH. `pooldiscovery.discover()`
finds pools by enumerating the mint's token accounts and asking who owns the
biggest ones. That is venue-agnostic and it works, but it is a LADDER: it reaches
the largest holders only, and it missed 2 of 15 sellable tokens in its own
validation because one pool's vault was not in the top 100 by base amount.

⭐ Derivation has no such failure mode. A pool's address is either a pure function
of the mint (a PDA) or directly queryable by the mint (a memcmp against the pool's
own mint field). Neither depends on how much the pool holds.

⛔⛔ AND NO STRUCT OFFSET IS ASSUMED HERE. Every memcmp offset was MEASURED by
`analysis/pool_offsets/probe.py`, which finds the mint's 32 raw bytes inside a
pool we already know belongs to it, and writes the result to
`data/pools/offsets.json` with the pool it was measured on. A venue whose offset
could not be measured is NOT QUERIED, because a guessed offset returns zero rows
and zero rows reads as "no pool" - the authority_live=None bug again.

⭐ Measurement already paid for itself: the probe found `cpamdpZC…`
(Meteora DAMM v2, the indexer labels it DYN2) holding 7 of 48 sampled pools with
NO ENTRY in our AMM map at all. One of those pools is EMBER/MET.

The states, pre-committed: pool_closed / pool_emptied / curve_died / pool_live /
not_found / unreadable. ⛔ None of them claims the token is sellable. A pool
holding $41.07 of WSOL returns NO_SELL_ROUTE, measured. The exit is
`chainfields.round_trip()` and only that.

Usage:
    python poolstate.py <MINT>
    import poolstate; poolstate.state(mint)
"""
import io
import json
import os
import sys
import time

import pooldiscovery as pd
import solpda

OFFSETS_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "pools", "offsets.json")

# ⛔ PRE-COMMITTED in PRECOMMIT_pool_state.md section 3. Same $10 dust boundary
# as PRECOMMIT_pool_discovery.md section 6, deliberately not re-tuned.
DUST_USD = 10.0

STATES = ("pool_live", "pool_emptied", "curve_died", "pool_closed",
          "not_found", "unreadable")

_OFFSETS = None


def offsets(reload=False):
    """The MEASURED mint offsets per venue. ⛔ Empty dict if never measured."""
    global _OFFSETS
    if _OFFSETS is None or reload:
        try:
            _OFFSETS = json.load(io.open(OFFSETS_PATH, encoding="utf-8"))
        except Exception:
            _OFFSETS = {"venues": {}, "note": "NEVER MEASURED"}
    return _OFFSETS


def queryable_venues():
    """(venue, program, [offsets]) for every venue whose offset was MEASURED.

    ⛔ A venue missing from here is not queried and its absence from a result is
    not evidence. That is the whole point of returning it explicitly.
    """
    out = []
    for venue, x in sorted((offsets().get("venues") or {}).items()):
        if x.get("verified") and x.get("mint_offsets"):
            out.append((venue, x["program"], list(x["mint_offsets"])))
    return out


# Venues reached by PDA derivation, which needs no struct offset at all. Listing
# these as "not queryable" was wrong: the pump.fun curve is derived exactly, and
# reporting it as unreachable understated our own coverage.
PDA_COVERED = {solpda.PUMPFUN_PROGRAM: "pumpfun_curve"}


def unqueryable_venues():
    """Venues in the AMM map with NO measured offset AND no PDA route.

    ⛔ Named out loud on every response, because a venue we never asked cannot
    have its absence read as evidence.
    """
    have = {p for _v, p, _o in queryable_venues()} | set(PDA_COVERED)
    return sorted((pd.AMM_OWNERS[p], p) for p in pd.AMM_OWNERS if p not in have)


# ---------------------------------------------------------------------------
# derivation
# ---------------------------------------------------------------------------
def derive_pools(mint, budget=None):
    """Every pool of this mint, by PDA and by measured-offset memcmp.

    ⛔ Records HOW each pool was found and which venues it could not ask.
    """
    b = budget or pd.Budget()
    found = {}
    errors = []
    methods = []

    # ---- 1. PDA, a pure function of the mint. No query needed to know it.
    try:
        curve = solpda.pumpfun_bonding_curve(mint)
        methods.append({"method": "pda", "venue": "pumpfun_curve",
                        "address": curve})
        found[curve] = {"pool": curve, "venue": "pumpfun_curve",
                        "how": "pda:bonding-curve", "exists": None}
    except Exception as e:
        errors.append("pda pumpfun: %s" % str(e)[:80])

    # ---- 2. memcmp on each venue's MEASURED mint offset, both slots
    for venue, program, offs in queryable_venues():
        for off in offs:
            res, err = pd.rpc("getProgramAccounts", [program, {
                "encoding": "base64",
                "commitment": "confirmed",
                "dataSlice": {"offset": 0, "length": 0},
                "filters": [{"memcmp": {"offset": int(off), "bytes": mint}}],
            }], timeout=90, budget=b)
            methods.append({"method": "memcmp", "venue": venue,
                            "offset": int(off),
                            "hits": (None if err else len(res or [])),
                            "error": err})
            if err:
                errors.append("%s@%d: %s" % (venue, off, err))
                continue
            for it in res or []:
                pk = it["pubkey"]
                if pk not in found:
                    found[pk] = {"pool": pk, "venue": venue,
                                 "how": "memcmp@%d" % off, "exists": True}

    return {"mint": mint, "pools": found, "methods": methods,
            "errors": errors,
            "venues_queried": [v for v, _p, _o in queryable_venues()],
            "venues_NOT_queryable": [v for v, _p in unqueryable_venues()],
            "budget": b}


def state(mint, sol_usd=None, budget=None, with_ladder=True, known_pair=None):
    """The pre-committed state of this mint's pools, measured from chain.

    `known_pair` is a pool address we have INDEPENDENT evidence once existed,
    normally the address an outcome row actually priced. ⛔ It is the only thing
    that can produce `pool_closed`, for the reason in the amendment note below.
    """
    b = budget or pd.Budget()
    t0 = time.time()
    d = derive_pools(mint, budget=b)
    pools = d["pools"]

    # ---- confirm existence and read each pool's quote side
    addrs = sorted(pools)
    if addrs:
        info, errs = pd._accounts_info(addrs, budget=b, parsed=False)
        d["errors"].extend("exists: " + e for e in errs)
        for a in addrs:
            acc = info.get(a)
            pools[a]["exists"] = bool(acc)
            pools[a]["lamports"] = (acc or {}).get("lamports")
            pools[a]["owner_program"] = (acc or {}).get("owner")
            # data length, only so the rent floor below can be exact
            try:
                import base64 as _b64
                pools[a]["data_len"] = len(_b64.b64decode(acc["data"][0]))
            except Exception:
                pools[a]["data_len"] = None

    # ⭐ The ladder stays as a SUPPLEMENT so a venue with no measured offset can
    # still surface. It is never the primary path any more.
    ladder = None
    if with_ladder:
        try:
            ladder = pd.discover(mint, sol_usd=sol_usd, budget=b)
            for p in ladder["pools"]:
                if p["pool"] not in pools:
                    pools[p["pool"]] = {
                        "pool": p["pool"], "venue": p["venue"],
                        "how": "ladder(token-account enumeration)",
                        "exists": True, "lamports": p.get("lamports")}
        except Exception as e:
            d["errors"].append("ladder: %s" % str(e)[:80])

    # ---- quote side from each live pool's own vaults
    #
    # ⛔⛔ AND THE PAIR GUARD, which the offset measurement forced. `raydium_clmm`
    # measured mint offsets [73, 105, 454]: the first two are the traded pair, and
    # 454 is a REWARD mint slot. A memcmp at 454 would return pools where our mint
    # is an incentive token and not a traded asset at all, and we would publish
    # those as this token's pools. So a candidate only counts as a pool of this
    # mint if the pool ITSELF HOLDS A VAULT OF THIS MINT.
    #
    # ⚠️ An unreadable vault set is NOT a rejection. Raydium v4 keeps every pool's
    # vaults under one shared authority, so `_vaults` cannot attribute them, and
    # treating that as "not a pair" would silently delete a whole venue. Those
    # rows get `pair_verified: None`, which is a third answer, not a pass.
    quote_max = 0.0
    unvalued = 0
    rejected = []
    for a, p in list(pools.items()):
        if not p.get("exists"):
            p["quote_usd"] = None
            p["pair_verified"] = None
            continue
        vaults, verrs = pd._vaults(a, budget=b)
        p["vaults_via"] = "owned" if vaults else None
        if not vaults:
            # ⭐⭐ MEASURED 2026-09-23: Meteora DBC and FluxBeam own NO token
            # accounts, so getTokenAccountsByOwner returns zero and our reader
            # published $0.00 of quote side with nothing unvalued - a confident
            # zero that was never read. 12 of 120 recorded pairs in the backfill
            # sample are DBC. The vaults are named inside the pool's own bytes,
            # so ask the struct.
            vaults, verrs2, ncand = pd.vaults_from_struct(a, budget=b)
            verrs = list(verrs or []) + list(verrs2 or [])
            p["struct_candidates"] = ncand
            p["vaults_via"] = "struct-scan" if vaults else None
            # ⛔⛔ ONE AUTHORITY GROUP ONLY. A struct can name an account that is
            # not the pool's - a protocol fee vault, a router's account - and
            # summing it would OVERSTATE this pool's quote side, which is the one
            # direction we must never err in. So keep the authority group that
            # holds OUR mint, and record what was dropped.
            if vaults:
                _mine = [v["vault_owner"] for v in vaults
                         if v["mint"] == mint and v.get("vault_owner")]
                _auth = _mine[0] if _mine else None
                if _auth:
                    _keep = [v for v in vaults if v.get("vault_owner") == _auth]
                    if len(_keep) != len(vaults):
                        p["struct_vaults_dropped"] = [
                            {"vault": v["vault"], "mint": v["mint"],
                             "vault_owner": v.get("vault_owner"),
                             "why": "a different authority from our mint's vault"}
                            for v in vaults if v.get("vault_owner") != _auth]
                    vaults = _keep
                    p["vault_authority"] = _auth
                else:
                    # ⚠️ No vault of our mint in the struct, so there is no
                    # authority to anchor on. The pair guard below will reject
                    # this pool anyway; we do not sum a foreign quote side.
                    p["struct_no_anchor"] = True
                    vaults = []
        if verrs:
            p["vault_errors"] = verrs
        vault_mints = {v["mint"] for v in vaults}
        if vaults:
            p["pair_verified"] = mint in vault_mints
        else:
            p["pair_verified"] = None          # unreadable, not a rejection
        if p["pair_verified"] is False:
            p["rejected_why"] = ("this pool holds no vault of our mint, so the "
                                 "memcmp hit is a non-pair slot (a reward mint)")
            rejected.append(pools.pop(a))
            continue
        usd, valued, unval = pd.quote_value(vaults, mint, sol_usd)
        p["vaults_valued"] = valued
        p["vaults_unvalued"] = unval
        unvalued += len(unval)

        # ⭐⭐ A pump.fun bonding curve's quote side is NATIVE SOL in its own
        # lamports. getTokenAccountsByOwner cannot see native SOL, so every curve
        # read $0. MEASURED on 26 live curves from the backfill sample: 2 hold
        # >= $10 above the rent floor and one holds 1.978990 SOL = $226.61.
        # Calling that "the pool exists and is empty" was simply wrong.
        if p["venue"] == "pumpfun_curve":
            lam = p.get("lamports")
            floor = (pd.rent_exempt(p["data_len"], budget=b)
                     if p.get("data_len") else None)
            if lam is None or floor is None or sol_usd is None:
                # ⛔ rule 5: unknown renders as unknown, never as 0
                p["quote_usd"] = None
                p["quote_unreadable_why"] = (
                    "native SOL needs lamports, the rent floor and a SOL price; "
                    "one of them is missing")
            else:
                p["quote_usd"] = max(0, lam - floor) / 1e9 * sol_usd
                p["quote_source"] = "native SOL above the rent-exempt floor"
                p["lamports_above_rent"] = max(0, lam - floor)
        elif not vaults:
            # ⛔ rule 5 again, and this is the whole reason the struct scan
            # exists: NO READABLE VAULT IS NOT $0 OF QUOTE SIDE.
            p["quote_usd"] = None
            p["quote_unreadable_why"] = (
                "no vault is owned by this pool and none could be read out of "
                "its own bytes, so the quote side was NEVER READ. It is not $0.")
        else:
            p["quote_usd"] = usd if valued else (None if unval else 0.0)
            p["quote_source"] = "vaults (%s)" % p.get("vaults_via")
        if p["quote_usd"]:
            quote_max = max(quote_max, p["quote_usd"])

    live = [p for p in pools.values() if p.get("exists")]
    absent = [p for p in pools.values() if p.get("exists") is False]
    amm_live = [p for p in live if p["venue"] != "pumpfun_curve"]

    # ---- the pre-committed state
    #
    # ⛔⛔ AMENDED 2026-09-23, SAME DAY, AFTER 28 BACKFILL ROWS EXPOSED IT. The
    # pre-commit said `pool_closed` means "the derived pool account does not
    # exist on chain". That wording is TOO LOOSE and it produced a wrong label
    # immediately: `BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh` (symbol
    # "business") does NOT end in `pump`, so it never launched on pump.fun, so
    # the bonding-curve PDA we derived for it WAS NEVER CREATED. An address that
    # was never created is an ABSENT VENUE, not a closed pool.
    #
    # ⭐ So `pool_closed` now requires evidence the pool ONCE EXISTED, and the
    # only such evidence we hold is the pool an outcome row actually priced
    # (`known_pair`). A speculatively derived PDA that does not exist yields
    # `not_found`, which is correctly described as OUR UNCERTAINTY.
    #
    # ⚠️ This is a CORRECTION TO A PRE-COMMITTED RULE and it is recorded as an
    # amendment in PRECOMMIT_pool_state.md rather than edited in silently.
    known_pair_absent = False
    if known_pair:
        kp = pools.get(known_pair)
        if kp is not None:
            known_pair_absent = kp.get("exists") is False
        else:
            info2, _e2 = pd._accounts_info([known_pair], budget=b, parsed=False)
            if known_pair in info2:
                known_pair_absent = not info2[known_pair]

    # ⛔⛔ AND A SECOND AMENDMENT, same day (§3b): a pool whose quote side could
    # not be READ may never fall through to `pool_emptied` or `curve_died`. Both
    # of those say "there is no money in it", which is a measurement. When the
    # measurement did not happen the answer is `unreadable`.
    quote_unread = [p for p in live if p.get("quote_usd") is None]
    if live and quote_max >= DUST_USD:
        st = "pool_live"
    elif live and quote_unread:
        st = "unreadable"
    elif live and not amm_live:
        st = "curve_died"
    elif live:
        st = "pool_emptied"
    elif known_pair_absent:
        st = "pool_closed"
    elif d["errors"] and not absent:
        st = "unreadable"
    else:
        st = "not_found"

    return {
        "mint": mint,
        "pool_state": st,
        "known_pair": known_pair,
        "known_pair_absent": known_pair_absent if known_pair else None,
        "pool_state_measured_at": int(time.time()),
        "quote_usd_max": round(quote_max, 6),
        "unvalued_vaults": unvalued,
        "pools": sorted(pools.values(), key=lambda p: -(p.get("quote_usd") or 0)),
        "pool_count": len(pools),
        "pools_existing": len(live),
        "pools_absent": len(absent),
        "venues": sorted({p["venue"] for p in live}),
        "how_found": sorted({p["how"].split("(")[0] for p in pools.values()}),
        "venues_queried": d["venues_queried"],
        "venues_NOT_queryable": d["venues_NOT_queryable"],
        "methods": d["methods"],
        "errors": d["errors"][:6],
        "ladder_verdict": (ladder or {}).get("verdict"),
        # ⛔ Candidates the pair guard threw out, kept visible so a venue that
        # genuinely vanishes from results has a reason on the record.
        "rejected_non_pairs": [{"pool": r["pool"], "venue": r["venue"],
                                "how": r["how"], "why": r.get("rejected_why")}
                               for r in rejected],
        "pairs_unverifiable": sum(1 for p in live
                                  if p.get("pair_verified") is None),
        "quote_unreadable_pools": len(quote_unread),
        # ⚠️ A venue with fewer than two measured mint slots can only be
        # searched on the side it stores, so a pool where this mint sits on the
        # other side is invisible. Measured, per venue, in offsets.json.
        "venues_one_sided": sorted(v for v, x
                                   in (offsets().get("venues") or {}).items()
                                   if x.get("one_sided_lookup")),
        "rpc_calls": b.calls,
        "elapsed_s": round(time.time() - t0, 2),
        # ⛔ Restated on every row, because it is the thing most likely misread.
        "sellable": None,
        "sellable_note": ("NOT MEASURED HERE. A pool holding $41.07 of WSOL "
                          "returned NO_SELL_ROUTE from Jupiter, measured. "
                          "The exit is chainfields.round_trip() and only that."),
        "absence_is_a_floor": True,
        "floor_note": ("not_found means we could not derive or discover a pool. "
                       "It is OUR UNCERTAINTY, never a claim about the token. "
                       "Venues with no measured offset were not asked at all."),
    }


def main(argv):
    if len(argv) < 2:
        print(__doc__)
        print("queryable venues (MEASURED offsets):")
        for v, p, o in queryable_venues():
            print("   %-20s %-44s %s" % (v, p, o))
        print("⛔ NOT queryable, so never asked:")
        for v, p in unqueryable_venues():
            print("   %-20s %s" % (v, p))
        return 2
    px, src, ts = pd.sol_price()
    print("SOL $%s from %s at %d\n" % (px, src, ts))
    for mint in argv[1:]:
        d = state(mint, sol_usd=px)
        print("%s  %-13s quote_max $%.2f  pools %d (%d live)  %s  %d calls %.1fs"
              % (mint[:12], d["pool_state"], d["quote_usd_max"], d["pool_count"],
                 d["pools_existing"], d["how_found"], d["rpc_calls"],
                 d["elapsed_s"]))
        for p in d["pools"]:
            print("    %-18s %-44s exists=%s quote=%s  %s"
                  % (p["venue"], p["pool"], p.get("exists"),
                     p.get("quote_usd"), p["how"]))
        if d["errors"]:
            print("    errors:", d["errors"][:3])
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
