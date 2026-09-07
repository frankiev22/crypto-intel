"""
The collection loop. Run this on a schedule; it is what actually accumulates
the dataset.

One pass does:
  1. scan new pools on each network
  2. journal EVERY result, passed and rejected
  3. score any older observations that have come due at their horizon
  4. push anything that cleared the bar to Discord

Safe to run repeatedly. Outcome scoring is idempotent, and observations are
append-only so a duplicate scan just adds another time-series point.

    python collect.py                    one pass, solana
    python collect.py solana,base        one pass, several networks
    python collect.py solana loop        keep going every 15 minutes

STAGES. Some runners cap a single command well below what a full pass needs -
the dispatch sandbox kills one at ~178s and a full pass takes ~5 minutes there.
A killed pass journals nothing and reports success, which is the worst failure
this system can have. --stage drives the pass in pieces that each fit:

    python collect.py solana --stage scan       scan, journal, alert
    python collect.py solana --stage outcomes   all four horizons
    python collect.py solana --stage 1          one horizon

The journal is append-only and outcome scoring is idempotent, so running the
stages separately is behaviour-identical to one full pass.
"""
import sys, time, traceback, datetime as dt
import scanner, journal, track, notify, macro, sources, findings, resolve
import watchlist
import news
import paper
import fieldguard

PASS_SCORE = 70
JOURNAL_BATCH = 10


def scan_stage(networks=("solana",), verbose=True):
    """Discovery, journalling and alerting. The half that cannot be redone
    later: an unobserved launch is gone permanently."""
    total_seen = total_passed = 0
    for net in networks:
        # Journal AS WE GO. Waiting for the loop to finish is what turned a
        # stalled Dexscreener lookup into three consecutive zero-observation
        # passes on 2026-08-30. A batch of 10 bounds the loss to 9 pools and
        # still keeps the Supabase push to one call per batch.
        buf, done = [], [0]

        def _flush(_net=net):
            if buf:
                done[0] += journal.record(list(buf), _net, pass_score=PASS_SCORE)
                buf.clear()

        def _on_row(r):
            buf.append(r)
            if len(buf) >= JOURNAL_BATCH:
                _flush()

        rows = []
        try:
            rows = scanner.scan(net, verbose=verbose, on_row=_on_row)
        except Exception as e:
            print(f"  [{net}] scan failed after {done[0]} journalled: {e}")
        _flush()          # keep the tail, and anything a raise left behind
        n = done[0]
        passed = [r for r in rows if r["score"] >= PASS_SCORE]
        # FIELD GUARD. Three silent-drop bugs in two days - vol_to_liq/vol_burst,
        # the news freshness check, and mint/freeze authority - all the same
        # shape: a field computed and never added to journal.record()'s
        # whitelist, so it was discarded without an error. Non-fatal here,
        # because losing a whole pass is worse than losing a column, but it
        # pings the health lane so it cannot go unnoticed the way those did.
        # `python fieldguard.py` exits non-zero, for CI.
        try:
            if rows:
                _w = max(rows, key=lambda r: sum(1 for v in r.values() if v is not None))
                _ok, _dropped = fieldguard.check(_w)
                if not _ok:
                    print(f"  !! FIELD GUARD: {_dropped} computed but not persisted")
                    findings.record(
                        "collector-error", "field-guard",
                        f"{len(_dropped)} computed field(s) are not persisted: "
                        f"{', '.join(_dropped)}",
                        detail=("A field computed and not persisted is a field that "
                                "does not exist. Add them to journal.record()'s "
                                "whitelist, or to fieldguard.TRANSIENT with a reason."))
        except Exception as e:
            print(f"  field guard failed (non-fatal): {e}")

        # What the discovery window actually covered. Recorded every pass,
        # because it cannot be reconstructed afterwards.
        cov = journal.record_coverage(net, sources.LAST_WINDOW, n,
                                      PASS_SCORE, len(passed))
        if verbose and cov.get("span_s") is not None:
            print(f"  [{net}] discovery window {cov['span_s']:.0f}s of launch "
                  f"stream from {cov['pools_returned']} pools")
        total_seen += n
        total_passed += len(passed)
        if verbose:
            print(f"  [{net}] {n} journalled, {len(passed)} cleared {PASS_SCORE}")
        if passed:
            # the same token often shows up as several pools; one line each
            seen, uniq = set(), []
            for r in passed:
                k = r.get("addr") or r.get("name")
                if k in seen:
                    continue
                seen.add(k)
                uniq.append(r)
            chain = net.replace("-", " ").title()
            noun = "token" if len(uniq) == 1 else "tokens"
            notify.send(
                content=(f"**{len(uniq)} new {chain} {noun}** passed the launch filter\n"
                         f"_Scored {PASS_SCORE}+ of 100 on liquidity, real turnover and "
                         f"buy/sell balance. This is a screen, not a recommendation._"),
                embeds=[notify.candidate_embed(r) for r in uniq[:8]])
    return total_seen, total_passed


def one_pass(networks=("solana",), verbose=True):
    total_seen, total_passed = scan_stage(networks, verbose=verbose)
    # APPROACH BAND, every pass. Tokens between $45k and $69k of FDV are the
    # only population where graduation is still ahead of them and observable;
    # the 1/6/24/168h outcome schedule cannot see a crossing that takes
    # minutes. Costs Dexscreener calls only - it spends none of the scarce
    # GeckoTerminal budget. Runs before outcome scoring so a graduation is
    # claimed on the freshest possible read.
    try:
        watchlist.sweep(sources.dexscreener_pair, verbose=verbose)
    except Exception as e:
        print(f"  watchlist sweep failed: {e}")
    # CLOSE THE PAPER LOG. A log of open positions is a wishlist; the losers
    # are what make it evidence. Every position that has met its declared exit
    # rule is closed here, whatever the number says, including to zero.
    try:
        paper.sweep(sources.dexscreener_pair, verbose=verbose)
    except Exception as e:
        print(f"  paper sweep failed: {e}")
    try:
        track.score_all(verbose=verbose)
    except Exception as e:
        print(f"  outcome scoring failed: {e}")
    return total_seen, total_passed


def main():
    argv = [a for a in sys.argv[1:]]
    stage = "full"
    if "--stage" in argv:
        i = argv.index("--stage")
        stage = argv[i + 1] if i + 1 < len(argv) else "full"
        del argv[i:i + 2]

    nets = ("solana",)
    loop = False
    if argv:
        nets = tuple(x.strip() for x in argv[0].split(","))
    if len(argv) > 1 and argv[1] == "loop":
        loop = True

    # Claim the pass before doing any work. If the previous one left its marker
    # behind it was killed, and that hour needs to be on the record as broken
    # rather than quiet.
    stale = journal.pass_begin(",".join(nets), stage)
    if stale:
        ab = journal.record_aborted(stale)
        print(f"  PREVIOUS PASS NEVER FINISHED: stage={ab['stage']} "
              f"ran {ab['ran_for_s']}s before dying. Recorded as an aborted pass.")

    rc = 0
    while True:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")
        print(f"\n=== pass {stamp} UTC · {','.join(nets)} · stage={stage} ===")
        try:
            if stage == "outcomes":
                track.score_all()
            elif stage.isdigit():
                track.score_horizon(int(stage))
            else:
                seen, passed = (scan_stage(nets) if stage == "scan" else one_pass(nets))
                s = journal.stats()
                print(f"  journal now: {s['observations']} obs · {s['unique_pairs']} pairs · "
                      f"{s['outcomes']} outcomes · {s['hours_covered']}h")
                # A pass that journalled NOTHING is not a quiet market, it is a
                # broken pass: scanner.scan swallows its own exception and
                # returns no rows, which is what an IP-level rate limit looks
                # like from a shared runner. Exit non-zero so the scheduler
                # reports a failure instead of a silent no-op hour.
                if seen == 0:
                    print("  NOTHING JOURNALLED - failed pass, not a quiet one")
                    rc = 1
                    # This must reach Frank, not a log file. It is the one
                    # condition that means the dataset stopped growing, and it
                    # went unnoticed six times because the error class had
                    # already pinged once and was suppressed thereafter.
                    _, _, pinged, why = findings.record(
                        "collector-zero", ",".join(nets),
                        "collector journalled ZERO observations while the host was up",
                        f"stage={stage}. Discovery returned "
                        f"{scanner.LAST_SCAN['pools']} pools, enriched "
                        f"{scanner.LAST_SCAN['enriched']}, failed "
                        f"{scanner.LAST_SCAN['failed']}, budget_hit="
                        f"{scanner.LAST_SCAN['budget_hit']}. This hour has no "
                        f"observations and cannot be recovered.")
                    print(f"  zero-result alert: {why}")
        except Exception:
            traceback.print_exc()
            rc = 1
        if not loop:
            break
        time.sleep(900)

    # Per-source reliability. If Dexscreener is a single point of failure it
    # should at least be a measured one.
    try:
        h = resolve.log_health()
        drops = h["dexscreener_dropped"]
        if drops:
            tot = drops + h["dexscreener_ok"]
            print(f"  source health: dexscreener dropped {drops}/{tot} lookups, "
                  f"geckoterminal recovered {h['geckoterminal_ok']}, "
                  f"{h['unresolved']} unresolved")
    except Exception as e:
        print(f"  source-health log failed (non-fatal): {e}")

    # PER-OUTLET NEWS FRESHNESS. A 6x drop in daily article count was spotted by
    # hand on 2026-09-06 and turned out to be ordinary weekend cadence - every
    # weekend in the record drops 4-5x and all four outlets drop together. A
    # volume alert would therefore fire two days in seven and be muted inside a
    # week. This checks staleness PER OUTLET instead, because a real failure is
    # one feed going quiet while the others keep publishing, which is visible on
    # a weekend too. Thresholds sit above every gap observed in 21 days.
    try:
        # NOTE: this block lives in main(), which has no `verbose` local.
        # Passing one here raised NameError on every pass from 2026-09-06
        # 17:11Z and silently killed the freshness check - the very class
        # of silent failure it exists to catch.
        news.check_freshness(record=findings.record, verbose=True)
    except Exception as e:
        print(f"  news-freshness check failed (non-fatal): {e}")

    # One line a day saying the collector is alive. Failures already page; a
    # week of silence from a runner nobody has seen working does not prove it
    # is running.
    try:
        hb = journal.daily_summary()
        if hb:
            msg = (f"**crypto-intel daily** {hb['hours_with_data']}/24 hours with data, "
                   f"{hb['observations']} observations, {hb['passed']} cleared the filter, "
                   f"{hb['stream_coverage_pct']}% of the launch stream seen")
            if hb["aborted"]:
                msg += f", {hb['aborted']} aborted passes"
            if hb["best_realizable_mult_24h"]:
                msg += f", best realizable {hb['best_realizable_mult_24h']}x"
            # Per-horizon lookup success on the line. A horizon failing at
            # 100% is what happened on 09-03 for four passes running, unseen.
            if hb.get("horizon_lookups"):
                msg += chr(10) + "horizon lookups resolved: " + ", ".join(
                    f"{k} {v}" for k, v in hb["horizon_lookups"].items())
            notify.send(content=msg)
    except Exception as e:
        print(f"  heartbeat failed (non-fatal): {e}")

    if rc == 0:
        journal.pass_end()      # only a clean finish clears the marker
    return rc


if __name__ == "__main__":
    sys.exit(main())
