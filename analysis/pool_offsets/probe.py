"""MEASURE where each AMM stores the mint inside its pool account.

Rule: ../../PRECOMMIT_pool_state.md section 2. ⛔⛔ NO STRUCT OFFSET IS ASSUMED.

Why this file exists. To find a mint's pools by `getProgramAccounts` you need a
memcmp filter, and a memcmp needs a byte offset into an account layout you do not
control. Guessing that offset returns ZERO ROWS, and zero rows reads as "this
token has no pool" - the `authority_live=None` bug for the seventh time in this
repo. So the offset is measured: take a pool we already know belongs to a mint,
fetch its raw account, and find where those 32 bytes actually sit.

Output: data/pools/offsets.json, with the pool each offset was measured on.
⛔ A venue whose offset could not be measured is NOT QUERIED AT ALL.

Run: python analysis/pool_offsets/probe.py
"""
import base64
import io
import json
import os
import sys
import time

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))
sys.path.insert(0, ROOT)

import allpairs  # noqa: E402
import pooldiscovery as pd  # noqa: E402
import solpda  # noqa: E402

# Liquid mints spanning many venues. Their pools are the measurement fixtures.
SEED_MINTS = [
    "So11111111111111111111111111111111111111112",   # SOL
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",  # USDC
    "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263",  # BONK
    "5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6",  # EMBER
    "EKShF2iKiGZNLh9QjXF7tu822AapGh4rNj9h6y8upump",  # NOOS (pumpswap)
    "3ZvY6acjpewyFphnwQrpF89YmoMqjdC3QqHALvgbpump",  # JEANB (pumpswap)
]

QUOTE_MINTS = {
    "So11111111111111111111111111111111111111112",
    "EPjFWdd5AufqSSqeM2qN1xzybapC8G4wEGGkZwyTDt1v",
    "Es9vMFrzaCERmJfrF4H2FYD4KCoNkY11McCe8BenwNYB",
}


# ⛔ The indexer returns ZERO pairs for exactly the tokens this project cares
# about, so the seed list above can only measure a venue's QUOTE slot: the seeds
# are SOL/USDC/BONK and they sit on the quote side. These fixtures are pools found
# ON CHAIN by pooldiscovery, where OUR mint is the BASE, which is the only way to
# measure the base slot. Without them PumpSwap measured at offset 75 only, and 25
# of the 120 `gone` contracts are PumpSwap.
#
# ⚠️ Every address here was READ OUT OF `analysis/gone_pools/result.json`, not
# typed. I twice completed a 16-character prefix from memory in this session and
# twice produced an address that does not exist. A truncated identifier is not an
# identifier.
KNOWN_FIXTURES = [
    ("9Vtqt6UruSVL8otRwYHughNLszXTE7E2hga2Z9AyYw6B",
     "3ZvY6acjpewyFphnwQrpF89YmoMqjdC3QqHALvgbpump"),   # pumpswap, JEANB
    ("BiWTskxEzfMK1EeXdD2o7e8cP2iCNgZf7utwxcaHfYSE",
     "EKShF2iKiGZNLh9QjXF7tu822AapGh4rNj9h6y8upump"),   # pumpswap, NOOS
    ("7FfGFgaGobmcZNnmnC6kYTxwVTX2HQvGYAuWV5bYawN1",
     "9VwDGtyezNwrTQTLobyczWKbNje45zyXgBkZpKMnpump"),   # pumpswap, LOOONGJAK
    # ⭐ ADDED 2026-09-23 after measuring the backfill sample's recorded
    # pairs: 12 of 120 are Meteora DBC and 1 is FluxBeam, and NEITHER had a
    # measured offset, so neither was ever queried. Addresses read out of
    # analysis/pool_offsets/recorded_pair_owners.json, not typed.
    ("3Di6VyFDLYH3kiRBDQMmQj4zU1hZmHCck1xhVhnpfw6i",
     "DqD7kkcbmaEoVZwoHs6E5bhDzwDrYkC9WaXNa4Fffinb"),   # meteora_dbc, Ponk
    ("3UkzaTg8ayPXoLu2hG7noBzwDNpjJo6LcnbehCrpvHcL",
     "Hc7yz6XJA4uuUYFCkbGtjEebMFk5r1K6SjqwXk1m2nah"),   # meteora_dbc, business
    ("46ZbiZ22yNK9hZYDZgfsmkCxA1UJTSwptMUAKZHSf7or",
     "ArkYeLVSQe9RqQguuLaPn6rimzqGNk3ut3tEahGERjRw"),   # meteora_dbc, TIP
    ("4n7mmAdTUzRZ72DyJboyofGbRe476LN1peRr6YexsSuP",
     "GtHLW4mK5Xsc5qKc6zevooZqMvUgT5huvNt1sgv36kZ6"),   # meteora_dbc, SEX
    ("CYeGw7hSNLjwpEKFevawzZPHbxEDctpCdVsDSHFVzX1h",
     "BsskZM8NNi6ayj3h9KUwawMuuY8hU4iB1QYxEaSuJAfh"),   # fluxbeam, business

    # ⭐ ADDED 2026-09-23: `raydium_cpmm` is in Frank's spec list and had NO
    # measured offset, so it was never queried. It did not appear in the first
    # 12 indexer pairs of any seed mint. These pools were FOUND by resolving
    # every seed pair's owner on chain, not typed.
    ("5hinZuqbN8Va93CMWSHZJBAUKdgN99FXAD2g3spnHy7N",
     "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),   # raydium_cpmm
    ("DTPk5qoWmAsDnoRtRejaj7p5ZHUf7JP4JdvXNwTbdP2B",
     "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"),   # raydium_cpmm
    ("54x5AxRsqdZc4cxKu6XmNFUZSMFVZ43CDXyrpXA9K2ht",
     "5dvXTZ5qwgafnHtwu3Ls3QrWx1U4LQsFeCuJgkk4QEC6"),   # raydium_cpmm

    # RAYDIUM LAUNCHLAB, 2026-09-24. Three earlier fixture routes came back
    # empty for this venue, and the reason was in the routes, not the venue: a
    # LaunchLab token MIGRATES, so a mature mint's pair list only ever shows
    # where it went. USELESS (64,262 holders, letsbonk.fun) resolves 30 pairs
    # and not one of them is LaunchLab.
    # The route that works is the LAUNCH feed: GeckoTerminal labels new pools
    # with dexId `raydium-launchlab`, 5 of 53 in one sample, and a pool minutes
    # old has not migrated yet. Addresses read out of the feed's own rows.
    ("AEMbbqb5XCP9xvVTy7pwm489mvEzKTtJDpTCsWdJb12S",
     "3h7doGcoK47y8JqP4Kd2ESJZfsLZBJj5ojaP1HnDrBTJ"),   # launchlab, 1GORIL/SOL
    ("6iqVFWeyTBpgfAkv1KP82BTT9hvL6n9HedHTmXTQTw2C",
     "33iJTEFmyppgXEUHn1EBMcotKNncxzJiD2w5fNb4cLK1"),   # launchlab, VIBE/HOODx
    ("H6uuPrnGi3XHaPCpAtDGeHMBC4xbAhb1bFcMgvX4rTzp",
     "3B3DQkbDA3xns2JjteSafMmT3xtRoS1wqg5cNoi2WsuF"),   # launchlab, SINK/METAx
    ("7sLuPhWMm6savSgkmNkbutYL1onGQ6Xr5gmW3xvo4BHV",
     "DCJrT1HErcsnyVdDLJbUxNFh83pxGWsfWh8Vgj2KMidK"),   # launchlab, LTSI/METAx
    # MOONSHOT, 2026-09-24, and the route generalised. GeckoTerminal serves
    # pools BY dexId at /networks/solana/dexes/<dexId>/pools, which does not
    # depend on a pool being new, so it is a better fixture route than watching
    # the launch feed for a venue to appear (moonshot showed up in 0 of 113 new
    # pools across two samples).
    # Two things fell out of it. Its `moonshot` dexId returns 20 pools that are
    # all METEORA DBC accounts (424 B, owner dbcij3LW...), a venue we already
    # measure, so that dexId is not this program. Its `moonit` dexId returns 20
    # pools owned by MoonCVVNZ..., which is the id our own map already carried,
    # so unlike LaunchLab this id was right. Addresses read out of
    # scratchpad moonshot_measured.json, not typed.
    ("H34oXzgqFQo7jSuEnSYi9qTK6gVBr7zbzxaorEbSoWZm",
     "EuhYh1mTCtaCGBv6NuWz3VC5AcMmTYxxDGJFLkdjkCGu"),   # moonshot, Find
    ("BiZAoicujGyhvWNmriDnGsNHqBtrkd4jRKikdD1Fi1e6",
     "5PMWr2Fajj9u4bsohGRdZvTSqKw5JJT6V828U59Fmoon"),   # moonshot, JMP
    ("83vkfAYU5KksrzrLgpXp1yWmee355ossXbtsbzAGNLgD",
     "577UwRNyXCiPEZtujjnyAZJGv8DrnTKC3dRR2rxLmoon"),   # moonshot, $SVB
    ("3tmfCM3FzgPB37oB85zAQmoEu5Yj89ZtYxNh1ECZQZLs",
     "B9uCnVsbgEdwC1fqucTeM4uGuice9iXAsoc5UfB1moon"),   # moonshot, MHOG
]


def find_offsets(data, needle):
    """Every byte offset where these 32 bytes appear."""
    out, i = [], 0
    while True:
        j = data.find(needle, i)
        if j < 0:
            return out
        out.append(j)
        i = j + 1


def main():
    samples = []
    print("collecting pool fixtures from the indexer (fixtures only, not a "
          "measurement of any token)\n")
    for mint in SEED_MINTS:
        t = allpairs.token(mint)
        if not t.get("ok"):
            print("  %s lookup failed" % mint[:10])
            continue
        for p in (t.get("pairs") or [])[:12]:
            samples.append({"pool": p["pair"], "dex": p.get("dex"),
                            "mint": mint})
        print("  %-12s %2d pairs" % (mint[:10], len(t.get("pairs") or [])))

    for pool, mint in KNOWN_FIXTURES:
        samples.append({"pool": pool, "dex": "from_chain_fixture", "mint": mint})
    print("  + %d on-chain fixtures where OUR mint is the BASE"
          % len(KNOWN_FIXTURES))

    print("\nreading %d pool accounts from chain\n" % len(samples))
    by_program = {}
    for s in samples:
        res, err = pd.rpc("getAccountInfo",
                          [s["pool"], {"encoding": "base64"}])
        val = (res or {}).get("value")
        if err or not val:
            s["error"] = err or "absent"
            continue
        owner = val.get("owner")
        try:
            raw = base64.b64decode(val["data"][0])
        except Exception as e:
            s["error"] = str(e)[:60]
            continue
        s["owner_program"] = owner
        s["venue"] = pd.AMM_OWNERS.get(owner) or "unknown"
        s["account_len"] = len(raw)
        s["offsets"] = find_offsets(raw, solpda.b58decode(s["mint"]))
        s["is_quote_side"] = s["mint"] in QUOTE_MINTS

        # ⭐ BOTH SLOTS, measured. Searching only for the mint we asked about
        # finds one side, so raydium_v4 measured at [400] and meteora_dynamic at
        # [40] - a token on the OTHER side of those pools would have been missed
        # entirely. The pool's own vaults name both assets, so ask the pool.
        vaults, _verr = pd._vaults(s["pool"])
        if not vaults:
            # ⭐ The venue keeps its vaults under a separate authority, so ask the
            # struct itself. Without this, DBC and FluxBeam measure ONE slot.
            vaults, _verr2, _nc = pd.vaults_from_struct(s["pool"])
            s["vaults_via"] = "struct-scan"
        both = {}
        for v in vaults:
            try:
                for off in find_offsets(raw, solpda.b58decode(v["mint"])):
                    both.setdefault(off, []).append(v["mint"])
            except Exception:
                continue
        s["vault_mints"] = sorted({v["mint"] for v in vaults})
        s["offsets_from_vault_mints"] = sorted(both)
        # ⛔ A MEASURED COVERAGE LIMIT, not a guess. Meteora DBC holds a WSOL
        # vault but the WSOL mint's bytes are NOWHERE in its 424-byte struct, so
        # a memcmp can only find DBC pools where the searched mint is the BASE.
        # Recording which held mints are absent from the struct is the only way
        # that limit shows up anywhere.
        s["held_mints_not_in_struct"] = sorted(
            m for m in s["vault_mints"] if not find_offsets(
                raw, solpda.b58decode(m)))
        for off in both:
            if off not in s["offsets"]:
                s["offsets"].append(off)
        s["offsets"] = sorted(s["offsets"])
        by_program.setdefault(owner, []).append(s)

    # ---- a program's mint slots are the offsets that recur across samples
    out = {"measured_at_utc": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "rule": "PRECOMMIT_pool_state.md section 2",
           "note": ("offsets are MEASURED by finding the mint's 32 raw bytes "
                    "inside a pool account we already know belongs to it. "
                    "A venue absent here is NOT queried."),
           "venues": {}}
    for owner, rows in sorted(by_program.items()):
        venue = pd.AMM_OWNERS.get(owner) or "unknown"
        counts = {}
        for r in rows:
            for off in r.get("offsets") or []:
                counts[off] = counts.get(off, 0) + 1
        usable = [r for r in rows if r.get("offsets")]
        # keep offsets seen on at least 2 distinct pools, or on the only pool
        keep = sorted(o for o, c in counts.items()
                      if c >= (2 if len(usable) > 1 else 1))
        out["venues"][venue] = {
            "program": owner,
            "samples": len(rows),
            "samples_with_a_hit": len(usable),
            "mint_offsets": keep,
            "offset_counts": {str(k): v for k, v in sorted(counts.items())},
            "account_lens": sorted({r.get("account_len") for r in rows
                                    if r.get("account_len")}),
            "measured_on": [{"pool": r["pool"], "mint": r["mint"],
                             "offsets": r["offsets"]}
                            for r in usable[:4]],
            "verified": bool(keep),
            # ⚠️ A MEASURED COVERAGE LIMIT. Meteora DBC stores ONE mint slot
            # (136) and holds a WSOL vault whose mint is nowhere in its 424-byte
            # struct, verified on 4 of 4 samples. So a memcmp finds DBC pools
            # where the searched mint is the BASE and can never find one where it
            # is the quote. Derived from the offsets themselves: fewer than two
            # recurring slots means one-sided.
            #
            # ⛔ `mints_held_but_not_stored_sample` is a DIAGNOSTIC ONLY and it
            # OVER-REPORTS on pools with many vaults, so no claim is built on it.
            "one_sided_lookup": len(keep) < 2,
            "one_sided_note": ("fewer than two recurring mint slots: this venue "
                               "can only be searched on the side it stores"),
            "mints_held_but_not_stored_sample": sorted(
                {m for r in rows if len(r.get("vault_mints") or []) <= 4
                 for m in (r.get("held_mints_not_in_struct") or [])})[:8],
        }
        print("%-18s %-44s samples %2d  hits %2d  offsets %s"
              % (venue, owner, len(rows), len(usable), keep))

    d = os.path.join(ROOT, "data", "pools")
    if not os.path.isdir(d):
        os.makedirs(d)
    path = os.path.join(d, "offsets.json")
    io.open(path, "w", encoding="utf-8").write(
        json.dumps(out, indent=1, sort_keys=True))
    print("\nwrote", path)
    unver = [v for v, x in out["venues"].items() if not x["verified"]]
    if unver:
        print("⛔ NOT verified, so NOT queried:", unver)
    return 0


if __name__ == "__main__":
    sys.exit(main())
