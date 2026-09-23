"""⭐⭐ THE QUOTE-ASSET REGISTRY: what the issuer of the thing you are PAID in can do.

Frank, 2026-09-23: *"for the xStocks and PreStocks quote assets used as pairs on
Stonk Fun, does the issuer retain freeze authority on chain? If yes, then a token
whose yield is paid in a freezable, US-person-restricted instrument is not clean,
and our detector should run on BOTH legs of every pair. That would be a genuinely
novel check."*

**It does. Measured on chain 2026-09-23: 14 of 14 of those quote mints carry a
LIVE freeze authority, 14 of 14 carry a `permanentDelegate`, and 14 of 14 carry
`pausableConfig`.** A `permanentDelegate` lets the issuer move a holder's tokens
with **no signature from the holder**.

⛔⛔ **AND THAT IS A DISCLOSURE, NOT A DANGER FINDING. Corrected the same day,
because Frank pushed back and was right:** *"rwa stonk pairs seem to be safe. I
understand they have alarming readings but I think you need to research more into
those. There may be a reason nobody checks the other leg."*

⭐ **The reason nobody checks it is that the answer is expected.** A freeze
authority and a permanentDelegate are what a regulated tokenised security is
REQUIRED to carry, so the issuer can comply with court orders, sanctions and
securities law. **A tokenised equity WITHOUT them would be the anomaly.**
Publishing the fact is useful. Publishing it as a red flag is wrong and would cost
us credibility with anyone who knows this space.

⭐ **What stays a genuine cost, and it is the one to lead with: the TRANSFER
TAX.** Measured here: VCF **800 bps**, Circuit **400**, and ZCAT, RAYCAT,
PURR-sol, LOOP and KNOTS at **300**. That is charged on the way in and again on
the way out, so it is a round-trip cost and not a yield. ⛔ **We have not read
any issuer's terms**, so which holders may actually redeem is unknown and is
labelled unknown.

⚠️ Stated precisely, because the stronger reading is the tempting one:
`defaultAccountState` on those mints reads `initialized`, **not** `frozen`, so
they are not whitelist-only today. The extension being present means the state
**can** be changed; it does not mean it has been. And presence of an authority is
**capability, not an event** - proving use needs the authority's own signature
history, which this module does not claim.

## Why a published registry and not a live call

`intel.pair_legs(mint)` answers on demand and is the thing a site or a bot calls.
But the set of quote assets is **small and slow-moving** - dozens of mints, whose
authorities change rarely - while the set of tokens quoted in them is large. So
the registry is the cheap half: **one RPC per quote mint, once**, published as a
file the site already knows how to read from git, with no new runtime and nothing
to sign up for.

## Where its input comes from

⛔ **Not from a literal list of mints I typed.** `journal.record_outcome()` now
persists `quote_mints` on every row that had an all-pairs read (BACKLOG A55 - the
09-21 "copper narrative" was a venue adding a pairable quote asset, and it was
invisible because nothing stored the quote mint), and this module harvests that.

⚠️ **It is therefore FORWARD-ONLY and incomplete by construction.** It knows the
quote assets of the tokens the pipeline happened to read all pairs for, which is
rows claiming >= 2x. The registry says how many mints it has seen and when; it
never implies it has seen them all.

⚠️ **Two mints are seeded, not fourteen**, and the difference matters: the
seed exists only to give the registry a non-empty first pass, so it holds the two
addresses that matter most (SPYx, the leg behind Frank's own STONK position, and
COPX, the leg behind the retracted copper finding). **The seed supplies addresses
to LOOK AT, never answers** - every seeded mint is read from chain like any other,
and every row carries `source` so a seeded entry is never mistaken for a
harvested one.

⭐ `seed_from_tokens(mints)` is the other way in: it reads all pairs for named
mints and folds their quote mints in. That is a measurement, not a typed list.
"""
import glob
import io
import json
import os
import time

import chainfields

BASE = os.path.dirname(os.path.abspath(__file__))
DIR = os.path.join(BASE, "data", "legs")
REGISTRY = os.path.join(DIR, "quote_assets.json")
OUTCOMES = os.path.join(BASE, "data", "outcomes")

SPL = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# How stale an entry may be before it is re-read. Mint authorities change rarely,
# but "rarely" is not "never" and a revocation is exactly the news worth having.
REFRESH_AFTER_S = 24 * 3600

# ⛔ A budget, because this runs inside a pass with a clock. One RPC per mint.
MAX_READS_PER_PASS = 40

# Extensions that hand the issuer power over a holder's balance, worst first.
# ⚠️ The NAME list only. The sentence comes from `power_sentence()`, which reads
# the extension's STATE, because two of these were saying something false.
POWERS = (
    "permanentDelegate",
    "pausableConfig",
    "defaultAccountState",
    "transferHook",
    "confidentialTransferMint",
    "scaledUiAmountConfig",
)

# ⛔⛔ A PRESENT EXTENSION IS NOT AN ACTIVE ONE, and two of the old sentences
# were wrong about exactly that. Read from chain 2026-09-23 on SPYx and COPX:
#
#   transferHook        {"authority": "5aMNNLQJ...", "programId": null}
#   defaultAccountState {"accountState": "initialized"}
#
# So "every transfer runs issuer code that can reject it" was FALSE on both: the
# hook slot is EMPTY, and no issuer code runs on any transfer today. What is true
# is that the authority can install one later. That is the `authority_live=None`
# error pointed the other way - **not happening, rendered as happening** - and it
# is the more damaging direction for us, because it is the one that cries wolf.
#
# ⚠️ `state=None` means the caller knows only that the extension is PRESENT. The
# sentence is then the capability, hedged in words, never the active claim.
ZERO_ADDRESS = "11111111111111111111111111111111"


def power_sentence(ext, state=None):
    """The plain sentence for one extension given its state. None = say nothing."""
    st = state or {}
    if ext == "permanentDelegate":
        who = st.get("delegate")
        # ⛔⛔ CORRECTED while writing this: the first version returned None when
        # the delegate field was absent, which made the extension being present
        # with an UNREADABLE delegate look like no power at all. That is
        # not-checked rendering as clean - the one failure this repo keeps making.
        # Silence is only correct when the delegate is explicitly the zero
        # address, which is what a revoked delegate looks like.
        if who == ZERO_ADDRESS:
            return None
        if not who:
            return ("the issuer can MOVE your tokens without your signature "
                    "(the delegate address could not be read, so WHO holds that "
                    "power is unknown)")
        return ("the issuer can MOVE your tokens without your signature "
                "(delegate %s)" % who)
    if ext == "pausableConfig":
        if st.get("paused"):
            return "⛔ THIS ASSET IS PAUSED RIGHT NOW: transfers are halted"
        return "the issuer can halt every transfer of this asset"
    if ext == "defaultAccountState":
        s2 = st.get("accountState")
        if s2 == "frozen":
            return "⛔ new accounts START FROZEN: the state is `frozen` right now"
        return ("new accounts can be forced to start frozen"
                + (" (it is `%s` today, so they are not)" % s2 if s2 else ""))
    if ext == "transferHook":
        prog = st.get("programId")
        # ⚠️ Only an EXPLICIT null programId means no hook. A missing key means we
        # did not read it, and that is not the same answer.
        if state is not None and "programId" in st and not prog:
            return ("a transfer hook CAN be installed, but the slot is empty, so "
                    "no issuer code runs on a transfer today")
        return ("every transfer runs issuer code that can reject it"
                + (" (program %s)" % prog if prog else ""))
    if ext == "confidentialTransferMint":
        return "balances can be confidential, so holdings are not fully auditable"
    if ext == "scaledUiAmountConfig":
        # ⭐⭐ THE DIVIDEND MECHANISM, VISIBLE ON CHAIN. An xStock pays no cash
        # dividend; it raises this multiplier, so a holder's DISPLAYED balance
        # grows without any transfer. Measured on SPYx 2026-09-23: multiplier
        # 1.003909240011759, newMultiplier 1.005714560286254 effective
        # 1781755200. COPX's multiplier is exactly 1, which is consistent with
        # Backpack paying cash dividends instead. ⭐ So the two instruments are
        # distinguishable from the mint account alone.
        m, nm = st.get("multiplier"), st.get("newMultiplier")
        if m in (None, "1", 1) and nm in (None, "1", 1):
            return None
        return ("your DISPLAYED balance is scaled by a multiplier the issuer "
                "sets (now %s, next %s): this is how a rebasing token pays a "
                "dividend without a transfer, and the raw token amount does not "
                "change" % (m, nm))
    return None


# ⭐⭐ THE ISSUER REGISTRY. Frank, 2026-09-23: *"Research the actual issuer terms
# before we publish anything either way."*
#
# ⛔ KEYED ON THE MINT, never the symbol (standing rule 2). Six different mints
# answer to COPX.
#
# ⚠️ PROVENANCE IS PART OF THE RECORD. `from_chain` was read by us from the mint
# account. `from_issuer` came from the issuer's own file or site, with the URL.
# `from_press` is secondary reporting and is labelled as such, never as ours.
# A mint absent from here has NO issuer research, which the endpoint says out
# loud rather than implying the absence means nothing to report.
ISSUERS = {
    "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W": {
        "symbol": "SPYx",
        "name_on_chain": "SP500 xStock",
        "issuer": "Backed Assets (JE) Limited (xStocks)",
        "metadata_uri":
            "https://xstocks-metadata.backed.fi/tokens/Solana/SPYx/metadata.json",
        "terms_url": "https://www.backedassets.fi/legal-documentation",
        "instrument": "a tracker certificate, NOT the share. Holders get price "
                      "and dividend economics, not ownership on the register",
        "voting_rights": False,
        "dividends": "reinvested by RAISING an on-chain multiplier "
                     "(scaledUiAmountConfig), not paid as cash",
        "redeemable_for_the_real_share": False,
        "us_persons": "⛔ EXCLUDED. Backed's own geoblock page says its products "
                      "are prohibited for US citizens, US residents or anyone "
                      "otherwise taxable in the United States, and that the "
                      "securities are not registered under US law",
        "why_the_issuer_powers_exist":
            "a regulated tokenised security must be able to freeze and move a "
            "holder's balance to comply with court orders, sanctions and "
            "securities law. ⭐ An equity token WITHOUT these would be the anomaly",
        "from_chain": ["name_on_chain", "metadata_uri", "dividends",
                       "the authorities and extensions on this page"],
        "from_issuer": ["terms_url", "us_persons",
                        "docs.xstocks.fi: 'xStocks are not intended for "
                        "distribution in the United States, to any US person, "
                        "or in any other prohibited jurisdiction.'"],
        "from_press": ["instrument", "voting_rights",
                       "redeemable_for_the_real_share",
                       "Kraken's xStocks FAQ: 'xStocks do not confer shareholder "
                       "rights like voting or dividends paid as cash' and "
                       "'xStocks are onchain tokens - they cannot be transferred "
                       "to a traditional brokerage account'"],
        "read_at": "2026-09-23",
    },
    "CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5": {
        "symbol": "COPX",
        "name_on_chain": "Global X Copper Miners ETF - Backpack Securities",
        "issuer": "Backpack Securities",
        "metadata_uri": "https://metadata.backpack.exchange/stocks/copx.us.json",
        "terms_url": "https://support.backpack.exchange/legal/general-legal/"
                     "user-agreement",
        "instrument": "a tokenised share held by a broker-dealer, redeemable 1:1 "
                      "for the real underlying share",
        "voting_rights": None,   # not established either way - not published
        "dividends": "cash dividends and corporate actions, per Backpack's own "
                     "page. ⭐ Consistent with the chain: its scaled-UI "
                     "multiplier is exactly 1, so it does NOT rebase",
        "redeemable_for_the_real_share": True,
        "us_persons": "⚠️ NOT ESTABLISHED by this research. Backpack Securities is "
                      "a US broker-dealer and its own page describes ACATS "
                      "transfers to other brokerages, but the user agreement is "
                      "distributed as PDFs that were not read",
        "why_the_issuer_powers_exist":
            "same reason as any tokenised security, and here every power sits on "
            "ONE key (2cVYpagTt7ZG...): freeze, permanent delegate, pause, "
            "confidential transfers and the transfer-hook authority",
        "from_chain": ["name_on_chain", "metadata_uri",
                       "the multiplier of exactly 1",
                       "the authorities and extensions on this page"],
        "from_issuer": ["terms_url", "instrument", "dividends",
                        "learn.backpack.exchange: 'each Backpack tokenized "
                        "security is redeemable 1:1 for the real underlying "
                        "share through Backpack Securities' brokerage'"],
        "from_press": ["that the issuer retains mint, burn, freeze and forced "
                       "transfer as tools to meet securities-law obligations"],
        "read_at": "2026-09-23",
    },
}


def issuer(mint):
    """What we have RESEARCHED about a quote asset's issuer, or None.

    ⛔ None means NOT RESEARCHED, which is not the same as nothing to report.
    """
    return ISSUERS.get(mint)

# ⭐ Seeded from the reads I made on chain 2026-09-23, so the registry is useful
# on its first pass instead of empty. Each seeded mint is still RE-READ like any
# other; the seed only supplies the addresses to look at, never the answers.
SEED = {
    # xStocks (Backed Finance), the tokenised-equity quote assets Stonk Fun uses
    "XsoCS1TfEyfFhfvj8EtZ528L3CaKBDBRqRapnBbDF2W": "SPYx",
    # the copper ETF quote asset behind the retracted "copper narrative"
    "CzLTZppPdZtTjyq3WGpHLstoc3GLhu7zH5Zg6xUa6Gv5": "COPX",
}


def seed_from_tokens(mints, verbose=True):
    """Read all pairs for these mints and fold their QUOTE mints into the registry.

    ⭐ One Dexscreener call per mint (never batched - 3 mints in one call
    returned 30 pairs TOTAL, split 15/14/1, which is the original one-pool bug
    reproduced silently; standing rule 18).

    This exists because the harvest is forward-only: `quote_mints` landed on
    outcome rows on 2026-09-23, so nothing older carries it. Pointing this at a
    named set of mints is a real measurement of what those tokens are quoted in,
    not a list of answers typed by hand.
    """
    import allpairs
    d = _load()
    seen = d.setdefault("harvested_from", {})
    added = {}
    for mint in mints:
        try:
            t = allpairs.token(mint)
        except Exception as e:
            if verbose:
                print("  [legs] all-pairs failed for %s: %s" % (mint[:12], e))
            continue
        if not t.get("ok"):
            if verbose:
                print("  [legs] all-pairs not ok for %s: %s"
                      % (mint[:12], t.get("error")))
            continue
        quotes = {}
        for sym, meta in (t.get("quote_assets") or {}).items():
            qm = meta.get("mint") if isinstance(meta, dict) else None
            if isinstance(qm, str) and 32 <= len(qm) <= 44:
                quotes[qm] = sym
                added[qm] = sym
        seen[mint] = {
            "symbol": t.get("symbol_display"),
            "pair_count": t.get("pair_count"),
            # ⚠️ At 30 pairs Dexscreener has truncated and the 30 are not
            # the biggest 30, so the quote-asset set for this token is a FLOOR.
            "quote_set_is_floor": t.get("pair_count") == 30,
            "quote_mints": sorted(quotes),
            "read_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        }
        if verbose:
            print("  [legs] %-12s %2s pairs -> %d quote mints%s"
                  % (str(t.get("symbol_display"))[:12], t.get("pair_count"),
                     len(quotes), " (FLOOR)" if t.get("pair_count") == 30 else ""))
    d["harvested_from"] = seen
    _save(d)
    # Fold them in as things to read, then let build() do the chain reads.
    SEED.update(added)
    return added


def _load():
    try:
        with io.open(REGISTRY, encoding="utf-8") as f:
            d = json.load(f)
        if isinstance(d, dict) and isinstance(d.get("assets"), dict):
            return d
    except (OSError, json.JSONDecodeError):
        pass
    return {"built_at": None, "assets": {}}


def _save(d):
    os.makedirs(DIR, exist_ok=True)
    tmp = REGISTRY + ".tmp"
    with io.open(tmp, "w", encoding="utf-8") as f:
        json.dump(d, f, indent=1, sort_keys=True)
    os.replace(tmp, REGISTRY)


def harvest(days=2):
    """{mint: symbol} for every quote asset on recent outcome rows, plus the seed.

    ⛔ Keyed on the MINT. Two mints answering to the same symbol are two entries,
    because a symbol is not an identity (standing rule 2).
    """
    found = dict(SEED)
    cutoff = time.time() - days * 86400
    for path in sorted(glob.glob(os.path.join(OUTCOMES, "*.jsonl")))[-(days + 1):]:
        try:
            if os.path.getmtime(path) < cutoff - 86400:
                continue
            for ln in io.open(path, encoding="utf-8"):
                ln = ln.strip()
                if not ln or '"quote_mints"' not in ln:
                    continue
                try:
                    row = json.loads(ln)
                except ValueError:
                    continue
                for q in (row.get("quote_mints") or []):
                    m = q.get("mint")
                    if isinstance(m, str) and 32 <= len(m) <= 44:
                        found.setdefault(m, q.get("symbol") or "unknown")
        except OSError:
            continue
    return found


def read_mint(mint, rpc=None):
    """One quote mint's authorities from chain. ⛔ Unknown stays unknown."""
    rpc = rpc or chainfields._rpc
    try:
        res, err = rpc("getAccountInfo", [mint, {"encoding": "jsonParsed"}])
    except Exception as e:
        return {"ok": False, "why": "%s: %s" % (type(e).__name__, str(e)[:120])}
    if err:
        return {"ok": False, "why": str(err)[:160]}
    val = (res or {}).get("value")
    if not val:
        return {"ok": False, "why": "no account returned for this mint"}
    info = (((val.get("data") or {}).get("parsed")) or {}).get("info") or {}
    exts = info.get("extensions") or []
    names = [e.get("extension") for e in exts]

    # ⭐ Keep every extension's STATE, not just its name. The old reader threw
    # the state away and then generated sentences from presence alone, which is
    # how "every transfer runs issuer code" came to be said about a mint whose
    # hook slot is empty.
    state_by_ext = {}
    for e in exts:
        state_by_ext[e.get("extension")] = e.get("state") or {}
    fee_bps = ((state_by_ext.get("transferFeeConfig", {})
                .get("newerTransferFee") or {}).get("transferFeeBasisPoints"))
    default_state = state_by_ext.get("defaultAccountState", {}).get("accountState")
    scaled = state_by_ext.get("scaledUiAmountConfig", {}).get("multiplier")

    powers = []
    if info.get("freezeAuthority"):
        powers.append("the issuer can FREEZE your account")
    for ext in POWERS:
        if ext in names:
            sentence = power_sentence(ext, state_by_ext.get(ext))
            if sentence:
                powers.append(sentence)
    if fee_bps:
        powers.append("every transfer is taxed %s bps" % fee_bps)

    return {
        "ok": True,
        "freeze_authority": info.get("freezeAuthority"),
        "mint_authority": info.get("mintAuthority"),
        "is_token_2022": val.get("owner") == TOKEN22,
        "extensions": names,
        # ⚠️ `initialized` is NOT `frozen`. The extension being present means the
        # state can be changed, not that it has been.
        "default_account_state": default_state,
        "transfer_fee_bps": fee_bps,
        # ⭐ The dividend multiplier, so a rebasing instrument is distinguishable
        # from a cash-dividend one without asking the issuer.
        "scaled_ui_multiplier": scaled,
        "extension_state": state_by_ext,
        "powers": powers,
        # ⛔ What we have RESEARCHED about the issuer, or None for NOT RESEARCHED.
        "issuer_research": ISSUERS.get(mint),
        # ⭐ The loud one: the issuer can move a holder's balance unsigned.
        # ⚠️ The field name says CONTROL, not danger. On a regulated
        # tokenised security this is expected and required; on a memecoin quote
        # asset it is unusual. The fact is the same, the meaning is not, and this
        # module does not decide which it is.
        "issuer_controlled": "permanentDelegate" in names,
        "issuer_control_is_expected_for": ("a regulated tokenised security, "
                                           "which must be able to comply with "
                                           "court orders and sanctions"),
    }


def build(verbose=True, max_reads=None, rpc=None, days=2):
    """Refresh the registry and publish it. Returns the summary."""
    max_reads = MAX_READS_PER_PASS if max_reads is None else max_reads
    d = _load()
    assets = d["assets"]
    want = harvest(days=days)
    now = time.time()

    stale = []
    for mint, sym in want.items():
        cur = assets.get(mint)
        if (not cur or not cur.get("ok")
                or (now - (cur.get("checked_ts") or 0)) > REFRESH_AFTER_S):
            stale.append((mint, sym))
    # Never-read first, then oldest, so a budget cut never starves new mints.
    stale.sort(key=lambda ms: (assets.get(ms[0], {}).get("checked_ts") or 0))

    read = 0
    for mint, sym in stale[:max_reads]:
        a = read_mint(mint, rpc=rpc)
        read += 1
        prev = assets.get(mint) or {}
        row = dict(a)
        row["symbol"] = sym
        row["mint"] = mint
        row["checked_ts"] = now
        row["checked_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
        row["first_seen_at"] = prev.get("first_seen_at") or row["checked_at"]
        row["source"] = "seed" if mint in SEED else "harvested_from_outcome_rows"
        # ⛔ Nothing is ever overwritten with LESS than we had. A failed read must
        # not erase a good answer, or one RPC blip turns a known issuer-controlled
        # asset into an unknown one - the same shape as journal.py:974 writing
        # `gone` on a single failed lookup.
        if not a.get("ok") and prev.get("ok"):
            row = dict(prev)
            row["last_read_failed_at"] = row["checked_at"] = time.strftime(
                "%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
            row["last_read_failed_why"] = a.get("why")
        assets[mint] = row
        if verbose:
            flag = (" [issuer retains control - expected on an RWA]"
                    if row.get("issuer_controlled") else "")
            print("  [legs] %-10s %-44s ok=%s%s"
                  % (str(sym)[:10], mint, row.get("ok"), flag))

    ok = [a for a in assets.values() if a.get("ok")]
    controlled = sorted(a["symbol"] for a in ok if a.get("issuer_controlled"))
    d["assets"] = assets
    d["built_at"] = time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(now))
    d["summary"] = {
        "known": len(assets),
        "read_ok": len(ok),
        "issuer_controlled": len(controlled),
        "issuer_controlled_symbols": controlled,
        "freezable": sum(1 for a in ok if a.get("freeze_authority")),
        "taxed": sum(1 for a in ok if a.get("transfer_fee_bps")),
        "read_this_pass": read,
        "stale_remaining": max(0, len(stale) - read),
    }
    # ⚠️ Said in the file itself, because a reader of the JSON will not have read
    # this docstring.
    d["not_checked"] = [
        "authority_ever_used: presence of an authority is capability, not an "
        "event. Proving use needs the authority's own signature history.",
        "completeness: this registry holds the quote assets of the tokens the "
        "pipeline read all pairs for (rows claiming >= 2x), plus a seed. It is "
        "forward-only and does not claim to be every quote asset on Solana.",
        "defaultAccountState `initialized` is NOT `frozen`: the extension being "
        "present means the state can be changed, not that it has been.",
    ]
    _save(d)

    try:
        import liveness
        liveness.beat("legs.registry", n=len(assets),
                      detail="read=%d controlled=%d stale=%d"
                             % (read, len(controlled),
                                d["summary"]["stale_remaining"]))
    except Exception:
        pass

    if verbose:
        sm = d["summary"]
        print("  legs: %d quote assets known, %d read ok, %d issuer-controlled%s"
              % (sm["known"], sm["read_ok"], sm["issuer_controlled"],
                 (" (" + ", ".join(controlled[:8]) + ")") if controlled else ""))
    return d["summary"]


def lookup(mint):
    """What is published about one quote mint, or None. No network."""
    return _load()["assets"].get(mint)


if __name__ == "__main__":
    import sys
    if "--from" in sys.argv:
        i = sys.argv.index("--from")
        mints = [a for a in sys.argv[i + 1:] if not a.startswith("-")]
        print(json.dumps(seed_from_tokens(mints), indent=1))
        print(json.dumps(build(max_reads=200), indent=1))
    elif "--show" in sys.argv:
        d = _load()
        print(json.dumps(d.get("summary") or {}, indent=1))
        for m, a in sorted(d["assets"].items(),
                           key=lambda kv: (not kv[1].get("issuer_controlled"),
                                           kv[1].get("symbol") or "")):
            print("%-10s %-44s %s" % (str(a.get("symbol"))[:10], m,
                                      "; ".join(a.get("powers") or []) or "no powers"))
    else:
        print(json.dumps(build(), indent=1))
