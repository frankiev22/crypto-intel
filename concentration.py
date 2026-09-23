"""⭐⭐ Sybil-adjusted holder concentration. Ten wallets, one funder, one buyer.

Frank, 2026-09-23, and it is the best idea in the conversation:

  *"nobody should ever be able to buy more than 1%-2% of a coin that early on...
  Not sure how we could police that."*

He is right about both halves. A per-wallet cap stops the lazy version and
nothing else: splitting one buy across twenty fresh wallets costs a few cents of
rent. **So the cap is not the measurement. The CLUSTERING is.**

⭐ **What this module reports: effective concentration after collapsing wallets
that share a funding source.** Ten wallets funded from one address minutes before
the pool opened are one buyer holding ten times what the raw table shows.

---

## ⛔ This is DESCRIPTION, not prediction, and the distinction is the whole
## reason it is allowed to exist

Marino applies to anything forward-looking: by the time a signal is readable it
is priced, and five ranking models have been built and retracted here. **This
predicts nothing.** It states a checkable fact about the present:

> *these six wallets hold 31.2% between them, and all six were funded by
> `7xKq…` within eleven minutes of each other, forty minutes before the first
> pool existed*

Every part of that sentence is verifiable by the reader against the chain, with
the signatures included. It needs no hit rate to defend, because it makes no
claim about what happens next. ⛔ **Do not attach an expected return to it, do
not rank tokens by it, and do not let it become a score.**

## ⛔ The two ways this measurement goes wrong, both handled

1. **A pool is not a whale.** The largest token accounts for almost any memecoin
   are the AMM pool vaults. Counting them as holders makes every healthy token
   look like it has a 60% whale. Accounts whose owner is a **program** rather
   than the System Program are excluded and counted separately.
2. ⛔⛔ **An exchange hot wallet funds everybody.** Two wallets both funded by
   Coinbase are not a cluster, and treating them as one would flag every real
   token on earth. So a funder's **outbound breadth** is measured, and a funder
   that pays many distinct wallets is labelled a hub and **never collapsed**.
   `devwallet.funding_chain()` names this problem in its docstring and declines
   to solve it; this module solves it by measuring rather than by keeping a list.

## ⚠️ What it cannot see, stated up front

- `getTokenLargestAccounts` returns **at most 20 accounts**. This is top-20
  concentration and never the full distribution. `is_partial` is always true.
- The funding walk pages back through a wallet's history. When it cannot reach
  the beginning, `exact` is false and the funder is **the earliest inbound
  transfer we saw**, not provably the one that created the wallet.
- A funder one hop back is the lazy construction. Two hops of separation defeat
  this module, and nothing here pretends otherwise.

⛔⛔ **And the third failure mode, found by running it rather than by thinking
about it: most top holders of an established token are not sybils at all.** On
Hypurr every one of the top 8 wallets carries **391 to 3,000+ signatures**. They
are traders and market makers. A funding walk on a wallet that busy cannot reach
its beginning, and collapsing two of them because some common ancestor turned up
would **manufacture** a cluster. So a wallet is only eligible to be collapsed
when its entire history was reached and it holds at most `FRESH_MAX_SIGNATURES`
signatures. ⭐ **"All top holders are established traders" is a real answer and
the module says it out loud**, rather than reporting a silent zero.
"""
import io
import json
import os
import time

import chainfields

SYSTEM = "11111111111111111111111111111111"
SPL = "TokenkegQfeZyiNwAJbNbGKPFXCWuBvf9Ss623VQ5DA"
TOKEN22 = "TokenzQdBNbLqP5VEhdkAS6EPFLC1PHnBqCXEpPxuEb"

# AMM authorities that own vaults directly rather than through a PDA whose owner
# is the program. Everything else is caught by the "owner is a program" test.
POOL_AUTHORITIES = {
    "5Q544fKrFoe6tsEbD7S8EmxGTJYAKtTVhAW5Q5pge4j1",   # Raydium AMM v4
    "GpMZbSM2GgvTKHJirzeGfMFoaZ8UR2X7F4v8vHTvxFbL",   # Raydium CPMM
    "7LNd3yGkqG1SNnKcWfVcnPz6Xi9WHeCnoH3uzE1AtVs4",   # Raydium stable
}

# ⛔ PRE-COMMITTED before this was run against any live token (standing rule 6).
LARGEST_N = 20            # the RPC ceiling, not a choice
HUB_BREADTH = 25          # a funder paying >= this many distinct wallets is a hub
CLUSTER_MIN = 2           # two wallets on one non-hub funder is the smallest cluster
CAP_PCTS = (1.0, 2.0)     # Frank's proposed caps, reported as counts
EARLY_WINDOW_S = 3600     # funded within this long before the first pool = "early"
WALK_PAGES = 3            # 3 x 1000 signatures before we admit the walk is a bound
FUND_SCAN = 25            # transactions scanned forward from the oldest
# ⛔ A wallet with more signatures than this is an ESTABLISHED trader, not a
# fresh per-launch wallet, and may never be collapsed into a sybil cluster.
# Measured on Hypurr: its top holders carry 391 to 3,000+ signatures each.
FRESH_MAX_SIGNATURES = 250


def _sig_pages(addr, pages=WALK_PAGES):
    """Signature history, oldest reachable last. Returns (sigs, reached_start)."""
    out, before = [], None
    for _ in range(pages):
        p = {"limit": 1000}
        if before:
            p["before"] = before
        res, _err = chainfields._rpc("getSignaturesForAddress", [addr, p])
        if not res:
            break
        out += res
        if len(res) < 1000:
            return out, True
        before = res[-1]["signature"]
    return out, False


def _net_gain(tx, wallet):
    """(gained_lamports, biggest_payer) for `wallet` in one transaction."""
    msg = tx["transaction"]["message"]
    keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
    pre = (tx.get("meta") or {}).get("preBalances") or []
    post = (tx.get("meta") or {}).get("postBalances") or []
    if wallet not in keys or len(pre) != len(keys):
        return None, None
    i = keys.index(wallet)
    gained = post[i] - pre[i]
    if gained <= 0:
        return gained, None
    losers = sorted(((pre[j] - post[j], keys[j]) for j in range(len(keys))
                     if j != i and (pre[j] - post[j]) > 0), reverse=True)
    return gained, (losers[0][1] if losers else None)


def funder(wallet, pages=WALK_PAGES, scan=FUND_SCAN):
    """⭐ Who put the first SOL into this wallet, keyless.

    Plain RPC rather than the Helius enhanced endpoint, so it works on a host
    with no `.env` - which is the runner, and would otherwise have been a silent
    capability gap.

    ⛔ **FIXED after running it: the OLDEST transaction is usually not the
    funding one.** A first pass looked only at the single oldest signature and
    failed on 6 of 8 real wallets with "the oldest transaction did not fund this
    wallet", because that transaction is typically one the wallet SIGNED, so it
    paid a fee and its balance went down. The funding transfer sits nearby but
    not exactly there. This now scans forward from the oldest signature until it
    finds the first transaction where the wallet's balance actually **increased**.

    ⚠️ `exact` is False when the history could not be walked to its beginning.
    The funder is then the earliest inbound transfer SEEN, which for a busy
    wallet is meaningless - so `analyse()` refuses to cluster on it.
    """
    sigs, reached = _sig_pages(wallet, pages)
    if not sigs:
        return {"funder": None, "exact": False, "n_signatures": 0,
                "error": "no signature history"}
    n = len(sigs)
    for s in reversed(sigs[-scan:]):          # oldest first
        tx, _err = chainfields._rpc(
            "getTransaction",
            [s["signature"], {"encoding": "jsonParsed",
                              "maxSupportedTransactionVersion": 1}])
        if not tx:
            continue
        gained, payer = _net_gain(tx, wallet)
        if gained and gained > 0 and payer:
            return {"funder": payer, "sol": round(gained / 1e9, 6),
                    "ts": s.get("blockTime"), "signature": s["signature"],
                    "exact": reached, "n_signatures": n, "error": None}
    return {"funder": None, "exact": reached, "n_signatures": n,
            "error": f"no inbound SOL transfer found in the oldest {scan} "
                     f"transactions of {n} seen"}


def breadth(addr, pages=1, sample=120):
    """⛔ How many DISTINCT wallets has this address paid? Hubs fund everyone.

    An exchange hot wallet or a router funds thousands of unrelated people, so a
    shared funder only means something when the funder is narrow. This is the
    measurement that replaces keeping a list of exchange addresses, which is a
    list this project does not have and should not have to maintain.

    ⚠️ Sampled, so the number is a FLOOR on breadth: seeing 25 distinct payees
    proves a hub, but seeing 3 does not prove it is not one.
    """
    sigs, _reached = _sig_pages(addr, pages)
    if not sigs:
        return {"distinct_payees": None, "sampled": 0,
                "error": "no signature history"}
    seen, looked = set(), 0
    for s in sigs[:sample]:
        tx, _e = chainfields._rpc(
            "getTransaction", [s["signature"],
                               {"encoding": "jsonParsed",
                                "maxSupportedTransactionVersion": 1}])
        looked += 1
        if not tx:
            continue
        msg = tx["transaction"]["message"]
        keys = [k["pubkey"] if isinstance(k, dict) else k for k in msg["accountKeys"]]
        pre = (tx.get("meta") or {}).get("preBalances") or []
        post = (tx.get("meta") or {}).get("postBalances") or []
        if len(pre) != len(keys) or addr not in keys:
            continue
        i = keys.index(addr)
        if post[i] - pre[i] >= 0:
            continue                       # this address did not pay here
        for j in range(len(keys)):
            if j != i and (post[j] - pre[j]) > 0 and keys[j] != SYSTEM:
                seen.add(keys[j])
        if len(seen) >= HUB_BREADTH:
            break
    return {"distinct_payees": len(seen), "sampled": looked, "error": None,
            "is_hub": len(seen) >= HUB_BREADTH,
            "note": f"a funder paying >= {HUB_BREADTH} distinct wallets is "
                    f"treated as an exchange or router and is NEVER collapsed"}


# --------------------------------------------------------------------------
# ⭐⭐ HOLDER RECURRENCE - the finding that came out of running the clustering
# --------------------------------------------------------------------------
# Measured 2026-09-23 over 60 consecutive graduations from our own ledger:
#
#   474 distinct top-10 wallets
#   ⭐ 43 of them (9.1% [6.8, 12.0]) are top-10 holders of MORE THAN ONE mint
#   ⭐ three wallets are top-10 holders of 10 of the 60 (17% of all launches)
#   ⭐ median 20% of any token's top 10 also top-hold another mint in the sample
#
# ⛔ That reframes Frank's question. The raw picture on a fresh graduate looks
# exactly like his worry - top-10 holds 54% to 64%, with 8 to 10 wallets over 2%
# - but those wallets are not one person splitting a buy across fresh addresses.
# They are industrial participants who are top holders of launch after launch,
# every one carrying 3,000+ signatures. "11.5% of supply" means something
# completely different when the holder also top-holds 200 other tokens.
#
# The registry is append-only and every analyse() call adds to it, so the
# measurement gets stronger at zero marginal cost. Standing rule 8.
REGISTRY_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "data", "holders")
_REG_CACHE = {"mtime": None, "index": None}


def _registry_path():
    return os.path.join(REGISTRY_DIR, time.strftime("%Y-%m") + ".jsonl")


def remember(mint, wallets):
    """Append this mint's top holders. Append-only; nothing is ever rewritten."""
    try:
        os.makedirs(REGISTRY_DIR, exist_ok=True)
        with io.open(_registry_path(), "a", encoding="utf-8") as f:
            f.write(json.dumps({"mint": mint, "top": list(wallets),
                                "ts": int(time.time())}) + "\n")
        return True
    except OSError:
        return False


def _index():
    """wallet -> set of mints, from every registry file. Cached per process."""
    try:
        files = sorted(os.path.join(REGISTRY_DIR, f)
                       for f in os.listdir(REGISTRY_DIR) if f.endswith(".jsonl"))
    except OSError:
        return {}, 0
    stamp = tuple((f, os.path.getmtime(f)) for f in files)
    if _REG_CACHE["mtime"] == stamp and _REG_CACHE["index"] is not None:
        return _REG_CACHE["index"]
    idx, mints = {}, set()
    for fp in files:
        try:
            for line in io.open(fp, encoding="utf-8"):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except ValueError:
                    continue
                m = row.get("mint")
                if not m:
                    continue
                mints.add(m)
                for w in (row.get("top") or []):
                    idx.setdefault(w, set()).add(m)
        except OSError:
            continue
    _REG_CACHE["mtime"] = stamp
    _REG_CACHE["index"] = (idx, len(mints))
    return idx, len(mints)


def recurrence(wallets):
    """⭐ For each wallet: how many OTHER mints is it also a top holder of?

    ⚠️ Always a FLOOR. It can only see mints this system has already looked at,
    so a wallet reported as appearing in 10 launches appears in at least 10, and
    very possibly in thousands. **It can prove presence, never absence.**
    """
    idx, n_mints = _index()
    out = {}
    for w in wallets:
        ms = idx.get(w) or set()
        out[w] = {"n_mints": len(ms), "mints": sorted(ms)[:25]}
    return out, n_mints


def holders(mint):
    """Top token accounts, with the pool vaults separated out. A pool is not a whale."""
    res, err = chainfields._rpc("getTokenLargestAccounts", [mint])
    vals = (res or {}).get("value") if res else None
    if not vals:
        return None, None, err or "getTokenLargestAccounts returned nothing"
    accts = [{"token_account": v["address"],
              "ui": float(v.get("uiAmountString") or 0)} for v in vals]
    r2, _ = chainfields._rpc("getMultipleAccounts",
                             [[a["token_account"] for a in accts],
                              {"encoding": "jsonParsed"}])
    owners = {}
    for a, v in zip(accts, ((r2 or {}).get("value") or [])):
        if v and isinstance(v.get("data"), dict):
            owners[a["token_account"]] = v["data"]["parsed"]["info"].get("owner")
    uniq = sorted({o for o in owners.values() if o})
    prog = {}
    if uniq:
        r3, _ = chainfields._rpc(
            "getMultipleAccounts",
            [uniq, {"encoding": "base64", "dataSlice": {"offset": 0, "length": 0}}])
        for o, v in zip(uniq, ((r3 or {}).get("value") or [])):
            prog[o] = (v or {}).get("owner")
    wallets, pools = [], []
    for a in accts:
        o = owners.get(a["token_account"])
        p = prog.get(o)
        is_pool = (o in POOL_AUTHORITIES) or (p is not None and p != SYSTEM)
        row = {**a, "owner": o, "owner_program": p}
        (pools if is_pool else wallets).append(row)
    return wallets, pools, None


def analyse(mint, supply=None, first_pool_ms=None, deep=True, max_walk=12):
    """⭐⭐ Raw concentration, then concentration after collapsing sybil clusters.

    `deep=False` skips the funding walk entirely and returns raw numbers only,
    with the sybil fields in `not_checked`. ⛔ It never returns a clean-looking
    zero for a check that did not run.
    """
    out = {"mint": mint, "ts": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
           "is_partial": True,
           "partial_why": f"getTokenLargestAccounts returns at most {LARGEST_N} "
                          f"accounts, so this is top-{LARGEST_N} concentration "
                          f"and never the full distribution",
           "not_checked": [], "warnings": []}

    wallets, pools, err = holders(mint)
    if err:
        out["error"] = err
        out["not_checked"].append({"field": "everything",
                                   "why": f"holder list unreadable ({err}). "
                                          f"⛔ Unknown, not 'no concentration'."})
        return out

    if not supply:
        res, _e = chainfields._rpc("getAccountInfo",
                                   [mint, {"encoding": "jsonParsed"}])
        v = (res or {}).get("value") if res else None
        if v:
            i = v["data"]["parsed"]["info"]
            d = i.get("decimals") or 0
            supply = float(i.get("supply") or 0) / (10 ** d)
    if not supply:
        out["not_checked"].append({"field": "percentages",
                                   "why": "token supply could not be read, so no "
                                          "percentage of supply can be computed"})
        return out

    def pct(x):
        return round(100.0 * x / supply, 4)

    out["supply"] = supply
    out["n_pool_vaults_excluded"] = len(pools)
    out["pool_vault_pct"] = pct(sum(p["ui"] for p in pools))
    out["n_wallets_seen"] = len(wallets)
    out["raw_top1_pct"] = pct(wallets[0]["ui"]) if wallets else 0.0
    out["raw_top10_pct"] = pct(sum(w["ui"] for w in wallets[:10]))
    out["raw_top20_pct"] = pct(sum(w["ui"] for w in wallets[:20]))
    for cap in CAP_PCTS:
        out[f"wallets_over_{cap:g}pct"] = sum(1 for w in wallets if pct(w["ui"]) > cap)
    out["wallets"] = [{"owner": w["owner"], "pct": pct(w["ui"]), "ui": w["ui"]}
                      for w in wallets]

    # ⭐⭐ RECURRENCE: is this "whale" a whale, or is it a wallet that top-holds
    # launch after launch? Free - a local read against the append-only registry.
    top_owners = [w["owner"] for w in wallets[:10] if w.get("owner")]
    rec, n_known = recurrence(top_owners)
    remember(mint, top_owners)
    seen_elsewhere = {w: r for w, r in rec.items()
                      if r["n_mints"] > 1 or (r["n_mints"] == 1 and mint not in r["mints"])}
    out["recurrence_registry_mints"] = n_known
    out["n_top10_seen_in_other_launches"] = len(seen_elsewhere)
    out["top10_recurring_share_pct"] = (round(100.0 * len(seen_elsewhere)
                                              / max(len(top_owners), 1), 1))
    out["recurring_holders"] = sorted(
        ({"owner": w, "also_top_holds_n_mints": r["n_mints"] - (1 if mint in r["mints"] else 0),
          "examples": [m for m in r["mints"] if m != mint][:5]}
         for w, r in seen_elsewhere.items()),
        key=lambda x: -x["also_top_holds_n_mints"])
    out["recurrence_note"] = (
        f"⚠️ a FLOOR: the registry holds {n_known} mints, so a wallet shown in N "
        f"launches appears in AT LEAST N. It can prove presence, never absence. "
        f"Base rate measured 2026-09-23 over 60 graduations: 9.1% [6.8, 12.0] of "
        f"474 top-10 wallets appear in more than one, and the median token has "
        f"20% of its top 10 recurring.")
    if out["recurring_holders"]:
        top = out["recurring_holders"][0]
        out["warnings"].append(
            f"⭐ {len(seen_elsewhere)} of the top {len(top_owners)} holders are "
            f"wallets we have already seen top-holding other launches; the worst "
            f"also top-holds {top['also_top_holds_n_mints']}. ⛔ A large position "
            f"held by a wallet that does this on launch after launch is an "
            f"industrial participant, not a single buyer cornering the supply.")

    if not deep:
        for f in ("clusters", "effective_top10_pct", "sybil_uplift_pct"):
            out["not_checked"].append(
                {"field": f, "why": "deep=False, so the funding walk did not run. "
                                    "⛔ This is NOT a finding of no clustering."})
        return out

    # ---- the funding walk -------------------------------------------------
    looked = wallets[:max_walk]
    if len(wallets) > max_walk:
        out["warnings"].append(
            f"only the top {max_walk} of {len(wallets)} wallets were walked for "
            f"funding. Clusters among the smaller holders are NOT ruled out.")
    by_funder, walk_fail, fresh_n, estab_n = {}, 0, 0, 0
    for w in looked:
        f = funder(w["owner"])
        nsig = f.get("n_signatures")
        # ⛔⛔ ONLY A FRESH WALLET CAN BE A SYBIL, and this is the check that
        # makes the whole metric honest. Measured on Hypurr: every one of its top
        # holders carries 391 to 3,000+ signatures. Those are traders and market
        # makers. Collapsing two of them because a walk found a common ancestor
        # somewhere in 3,000 transactions would manufacture a finding.
        is_fresh = bool(f.get("exact")) and (nsig or 0) <= FRESH_MAX_SIGNATURES
        w["funding"] = f
        w["n_signatures"] = nsig
        w["is_fresh"] = is_fresh
        if is_fresh:
            fresh_n += 1
        else:
            estab_n += 1
        if not f.get("funder"):
            walk_fail += 1
            continue
        if not is_fresh:
            continue
        by_funder.setdefault(f["funder"], []).append({
            "owner": w["owner"], "pct": pct(w["ui"]),
            "funded_ts": f.get("ts"), "sol": f.get("sol"),
            "signature": f.get("signature"), "exact": f.get("exact"),
            "n_signatures": nsig})
    out["n_fresh_wallets"] = fresh_n
    out["n_established_wallets"] = estab_n
    out["fresh_rule"] = (f"a wallet is FRESH when its whole history was reached "
                         f"and holds <= {FRESH_MAX_SIGNATURES} signatures. Only "
                         f"fresh wallets are eligible to be collapsed.")
    out["walked"] = [{"owner": w["owner"], "pct": pct(w["ui"]),
                      "n_signatures": w.get("n_signatures"),
                      "is_fresh": w.get("is_fresh"),
                      "funder": (w.get("funding") or {}).get("funder")}
                     for w in looked]
    if estab_n and not fresh_n:
        out["warnings"].append(
            f"⭐ NO SYBIL CLUSTERING IS POSSIBLE HERE: all {estab_n} walked "
            f"holders are established wallets with hundreds to thousands of "
            f"transactions each. They are traders, not per-launch wallets. "
            f"⚠️ That is a real negative result, not a failed check.")
    if walk_fail:
        out["not_checked"].append(
            {"field": "clusters",
             "why": f"{walk_fail} of {len(looked)} wallets could not be traced to "
                    f"a funder. Those wallets are counted individually, so the "
                    f"effective figure below is a FLOOR on concentration."})

    clusters = []
    for f, members in by_funder.items():
        if len(members) < CLUSTER_MIN:
            continue
        b = breadth(f)
        total = round(sum(m["pct"] for m in members), 4)
        tss = sorted(m["funded_ts"] for m in members if m["funded_ts"])
        row = {"funder": f, "n_wallets": len(members), "combined_pct": total,
               "members": members, "funder_breadth": b,
               "collapsed": not b.get("is_hub"),
               "funded_span_s": (tss[-1] - tss[0]) if len(tss) > 1 else 0,
               "first_funded": _iso(tss[0]) if tss else None}
        if b.get("is_hub"):
            row["why_not_collapsed"] = (
                f"the funder pays {b['distinct_payees']}+ distinct wallets, so it "
                f"is an exchange or router and shared funding means nothing")
        if first_pool_ms and tss:
            lead = (first_pool_ms / 1000.0) - tss[-1]
            row["funded_before_first_pool_s"] = round(lead, 1)
            row["funded_in_early_window"] = bool(0 < lead <= EARLY_WINDOW_S)
        clusters.append(row)
    clusters.sort(key=lambda c: -c["combined_pct"])
    out["clusters"] = clusters
    out["n_clusters"] = sum(1 for c in clusters if c["collapsed"])

    # ---- effective concentration -----------------------------------------
    # Collapse each non-hub cluster into ONE holder, then re-rank.
    member_of = {}
    for c in clusters:
        if not c["collapsed"]:
            continue
        for m in c["members"]:
            member_of[m["owner"]] = c["funder"]
    units, seen_cluster = [], {}
    for w in wallets:
        cid = member_of.get(w["owner"])
        if cid is None:
            units.append({"id": w["owner"], "pct": pct(w["ui"]), "kind": "wallet"})
        elif cid in seen_cluster:
            seen_cluster[cid]["pct"] = round(seen_cluster[cid]["pct"] + pct(w["ui"]), 4)
        else:
            u = {"id": "cluster:" + cid, "pct": pct(w["ui"]), "kind": "cluster"}
            seen_cluster[cid] = u
            units.append(u)
    units.sort(key=lambda u: -u["pct"])
    out["effective_holders"] = units
    out["effective_top1_pct"] = units[0]["pct"] if units else 0.0
    out["effective_top10_pct"] = round(sum(u["pct"] for u in units[:10]), 4)
    out["sybil_uplift_pct"] = round(out["effective_top1_pct"] - out["raw_top1_pct"], 4)
    out["effective_wallets_over_1pct"] = sum(1 for u in units if u["pct"] > 1.0)

    if out["sybil_uplift_pct"] > 0:
        big = clusters[0]
        out["warnings"].append(
            f"⭐ the largest holder is not a wallet, it is {big['n_wallets']} "
            f"wallets funded by {big['funder'][:12]}… holding "
            f"{big['combined_pct']:.2f}% between them. The raw table shows "
            f"{out['raw_top1_pct']:.2f}%; collapsed it is "
            f"{out['effective_top1_pct']:.2f}%.")
    return out


def _iso(ts):
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)) if ts else None


if __name__ == "__main__":
    import json
    import sys
    for m in sys.argv[1:]:
        print(json.dumps(analyse(m), indent=1, default=str))
