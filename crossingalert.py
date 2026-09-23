"""⭐ The crossing lane: alert on a crossing that has a market, silence on one
that does not.

⛔ **THE SILENCE IS THE FEATURE.** Measured over the 24h to 2026-09-23: **61**
crossings of `mcap_1m` or `mcap_5m` on **34 distinct contracts**, and **45 of 60
(75.0%) had under $1,000 of exit depth at the crossing, median $0**. A detector
that fires on all 61 is worse than no detector, because standing rule 4 exists:
never fire on an unverified crossing, he will act on it.

⛔ **And zero pings fired, including on the 15 that DID clear the bar.** There
was no crossing lane at all - `outcome-win` fires on a multiple and nothing fired
on a market-cap crossing - so the 45 were correctly silent by accident and the 15
were incorrectly silent for exactly the same reason. That is the bug this closes.

⭐ **The rule was pre-committed to `PRECOMMIT_crossing_alert.md` before a single
crossing was evaluated against it**, including the bar, the lane budget, the
significance scale, and the two results that would make it wrong.

## Where it runs

`milestones.check_outcome()` claims a tier with `O_EXCL` and calls `on_milestone`
for each NEW claim; `journal.record_outcome()` forwards it; `track.py` supplies
`crossingalert.on_milestone`. So the decision happens inside the same call that
measured the depth, and the once-ever guarantee belongs to the filesystem rather
than to a convention someone has to remember.

## ⛔ What it does not claim

It never says the token will run further. Marino applies to anything
forward-looking. A crossing that has already happened, carrying the depth that
existed at the moment it happened, is description - the narrow exception CLAUDE.md
allows, and the only ground this lane stands on.
"""

# ⛔ PRE-COMMITTED in PRECOMMIT_crossing_alert.md before any crossing was scored.
# $1,000 is not a new dial: standing rule 18 already uses exactly this floor for
# "mcap > $1,000,000 on total liquidity < $1,000 is a ghost".
DEPTH_BAR_USD = 1_000.0

# Only these two tiers can alert. 100k and 200k are recorded and stay silent.
ALERTING_TIERS = ("mcap_1m", "mcap_5m")

# Significance is depth/1000, so a crossing on $3,000 of depth scores 3.0 - the
# same number a 3x outcome scores, which is what findings.SIGNIFICANCE_ALWAYS
# compares against. The two lanes therefore rank on a comparable scale.
SIG_PER_USD = 1_000.0

# ⛔⛔ AND IT IS CAPPED, which the first version of the pre-commit got
# WRONG. Replaying the rule over the 24h of real crossings before shipping it
# showed depths up to **$711,654** (VSOF), which on an uncapped depth/1000 scale
# is a significance of **711.7**. `findings._budget_spend` lets a finding through
# a spent budget whenever it is MORE significant than anything already sent that
# hour, so an unbounded scale means every next crossing with more depth than the
# last always breaks through and the 3-an-hour budget never binds at all.
# ⭐ The cap is where "definitely worth telling him" saturates: past $10,000 of
# quote-side depth, more depth is not more news at a $100 clip. Capping restores
# the budget's bite, because a second 10.0 cannot exceed the first.
# ⚠️ This is an amendment to a pre-committed number, made BEFORE the rule
# ever fired and recorded in PRECOMMIT_crossing_alert.md section 6 with the
# measurement that forced it. It is not a retune against outcomes.
SIG_CAP = 10.0

# ⛔ Text-direction overrides and homoglyphs. 112 contracts in our own corpus
# carry a bidi control in the symbol; one displays as "USDC" and claimed the
# highest liquidity of 2026-09-18 with zero sells. Caught in this lane by looking
# at a real replay: the top row of the 24h sample was symbolled with U+202E.
BIDI = {0x202A, 0x202B, 0x202C, 0x202D, 0x202E,
        0x2066, 0x2067, 0x2068, 0x2069, 0x200E, 0x200F, 0x061C}
CYRILLIC = set(range(0x0400, 0x0500))


def safe_symbol(sym):
    """A symbol safe to put in a message, with the deception NAMED, not hidden.

    ⛔ Never silently drops a control character: a removed character that
    leaves no trace is the same deception with our fingerprints on it. Plain
    text, not HTML - `dashboard.safe_sym()` returns HTML and an alert is not a
    web page.
    """
    raw = str(sym or "")
    if not raw:
        return "unknown"
    codes = [ord(c) for c in raw]
    stripped = "".join(c for c in raw if ord(c) not in BIDI)
    out = stripped[:22] or "unknown"
    if len(stripped) != len(raw):
        out += " [⛔ BIDI: this symbol renders as a DIFFERENT name]"
    if any(c in CYRILLIC for c in codes) and any(c < 0x0250 for c in codes):
        out += " [⛔ MIXED-SCRIPT: Cyrillic inside a Latin symbol]"
    return out


ALERT = "ALERT"
SILENT_THIN = "SILENT_THIN"
SILENT_UNMEASURED = "SILENT_UNMEASURED"
NOT_A_CROSSING = "NOT_A_CROSSING"

# Counters for the pass, so the lane can be audited on what it SUPPRESSED.
# ⛔ A lane that only records what it announced cannot be audited.
LAST = {"evaluated": 0, ALERT: 0, SILENT_THIN: 0, SILENT_UNMEASURED: 0,
        NOT_A_CROSSING: 0}


def reset():
    for k in LAST:
        LAST[k] = 0


def decide(milestone, meta):
    """(action, why, significance) for one newly claimed milestone.

    Pure. No network, no file, no import of `findings` - so the rule can be
    tested exhaustively without touching anything, which is the whole reason it
    is a separate function from the announcement.
    """
    if milestone not in ALERTING_TIERS:
        return NOT_A_CROSSING, "%s is not an alerting tier" % milestone, None

    meta = meta or {}
    depth = meta.get("exit_depth_at_crossing")

    # ⛔ RULE 5, and this is the whole of it. `depth_unmeasured` true, or depth
    # missing, means NOT CHECKED - which must never render as checked and fine.
    # It is the authority_live=None shape that put unverified wins on the record,
    # and the answer is silence plus a counted row, never a default.
    if meta.get("depth_unmeasured_at_crossing") or depth is None:
        return (SILENT_UNMEASURED,
                "exit depth was not measured at the crossing, and not measured "
                "is not the same as thin - silent, and counted", None)

    try:
        depth = float(depth)
    except (TypeError, ValueError):
        return (SILENT_UNMEASURED,
                "exit depth was not a number: %r" % (depth,), None)

    if depth < DEPTH_BAR_USD:
        return (SILENT_THIN,
                "${:,.2f} of quote-side depth at the crossing, under the "
                "${:,.0f} bar".format(depth, DEPTH_BAR_USD), None)

    return (ALERT,
            "${:,.0f} of quote-side depth measured at the crossing, clearing "
            "the ${:,.0f} bar".format(depth, DEPTH_BAR_USD),
            round(min(depth / SIG_PER_USD, SIG_CAP), 4))


def on_milestone(token, milestone, meta, record=None, verbose=False):
    """Called once per NEW milestone claim. Announces only an ALERT.

    ⛔ `token` is the CONTRACT ADDRESS and there is no ticker fallback anywhere
    in this function. Standing rule 2: six BASKET contracts collapsed into one
    findings class on 2026-09-20 and every one after the first went silent.
    """
    action, why, sig = decide(milestone, meta)
    LAST["evaluated"] += 1
    LAST[action] = LAST.get(action, 0) + 1
    if verbose and action != NOT_A_CROSSING:
        print("    [crossing] %-18s %s %s  %s"
              % (action, milestone, str(token or "?")[:12], why))
    if action != ALERT:
        return action

    meta = meta or {}
    # ⛔ The symbol is DISPLAY ONLY and it is sanitised. The key is the
    # address (below); this is the text a human reads, and a bidi override in it
    # would make the alert name a token it is not.
    sym = safe_symbol(meta.get("symbol"))
    depth = float(meta.get("exit_depth_at_crossing"))
    tier = "$5M" if milestone == "mcap_5m" else "$1M"
    try:
        mcap_txt = "$" + format(float(meta.get("value") or 0), ",.0f")
    except (TypeError, ValueError):
        mcap_txt = "unknown"

    if record is None:
        import findings
        record = findings.record
    try:
        record(
            "mcap-crossing",
            # ⛔ The address, with NO `or symbol` fallback. That fallback is the
            # exact shape test_tickerkey.py exists to catch.
            token or "no-address",
            "%s crossed %s market cap with $%s of quote-side depth at the "
            "crossing" % (sym, tier, format(depth, ",.0f")),
            detail=(
                "contract " + str(token) + chr(10)
                + "tier     " + str(milestone) + chr(10)
                + "mcap     " + mcap_txt + chr(10)
                + "depth    $" + format(depth, ",.0f")
                + " quote-side, measured in the same call as the crossing"
                + chr(10)
                + "pool     " + str(meta.get("exit_pair_at_crossing")) + chr(10)
                + chr(10)
                + "⛔ THIS IS DEXSCREENER'S QUOTE SIDE, NOT A SELL QUOTE. "
                  "Nothing here round-tripped $100. The field it comes from "
                  "overstates by a median 781x when it is wrong, and 85% of "
                  "$1M/$5M crossings fail realizability at the crossing."
                + chr(10)
                + "⚠️ 75% of crossings do not clear this bar and are "
                  "never announced. This one did. It describes what already "
                  "happened; it says nothing about what happens next."),
            significance=sig)
    except Exception as e:
        print("    crossing announcement failed (non-fatal): %s: %s"
              % (type(e).__name__, str(e)[:120]))
    return action


def beat(beat_fn=None):
    """Report the pass's crossing DECISIONS - not its alerts.

    ⛔ Beating on alerts would be the silent-failure shape all over again: a lane
    that legitimately has nothing to say would be indistinguishable from a lane
    that is broken. Counting decisions means the row moves whenever crossings
    happen at all, and 61 happened in the 24h before this was written.
    """
    detail = ("alert=%d thin=%d unmeasured=%d"
              % (LAST[ALERT], LAST[SILENT_THIN], LAST[SILENT_UNMEASURED]))
    n = LAST["evaluated"]
    # ⛔ The component name is a LITERAL in a call spelled `liveness.beat(...)`
    # and deliberately not factored into a variable. `test_stages.py` matches
    # declared liveness components against `beat("name")` literals at the AST
    # level, and a name reached through `beat_fn = liveness.beat` is invisible to
    # it - which would leave this lane passing its tests while nothing could ever
    # tell us it had stopped.
    try:
        if beat_fn is not None:
            beat_fn("crossing.decisions", n=n, detail=detail)
        else:
            import liveness
            liveness.beat("crossing.decisions", n=n, detail=detail)
    except Exception:
        pass


if __name__ == "__main__":
    import json
    print(json.dumps({"bar_usd": DEPTH_BAR_USD,
                      "alerting_tiers": list(ALERTING_TIERS),
                      "last_pass": LAST}, indent=1))
