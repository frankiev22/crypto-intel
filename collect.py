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

    python collect.py              one pass, solana
    python collect.py solana,base  one pass, several networks
    python collect.py solana loop  keep going every 15 minutes
"""
import sys, time, traceback, datetime as dt
import scanner, journal, track, notify, macro, sources

PASS_SCORE = 70


def one_pass(networks=("solana",), verbose=True):
    total_seen = total_passed = 0
    for net in networks:
        try:
            rows = scanner.scan(net, pages=2, verbose=verbose)
        except Exception as e:
            print(f"  [{net}] scan failed: {e}")
            continue
        n = journal.record(rows, net, pass_score=PASS_SCORE)
        passed = [r for r in rows if r["score"] >= PASS_SCORE]
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

    # score whatever has come due
    try:
        track.score_all(verbose=verbose)
    except Exception as e:
        print(f"  outcome scoring failed: {e}")

    return total_seen, total_passed


def main():
    nets = ("solana",)
    loop = False
    if len(sys.argv) > 1:
        nets = tuple(x.strip() for x in sys.argv[1].split(","))
    if len(sys.argv) > 2 and sys.argv[2] == "loop":
        loop = True

    rc = 0
    while True:
        stamp = dt.datetime.now(dt.timezone.utc).strftime("%H:%M:%S")
        print(f"\n=== pass {stamp} UTC · {','.join(nets)} ===")
        try:
            seen, passed = one_pass(nets)
            s = journal.stats()
            print(f"  journal now: {s['observations']} obs · {s['unique_pairs']} pairs · "
                  f"{s['outcomes']} outcomes · {s['hours_covered']}h")
            # A pass that journalled NOTHING is not a quiet market, it is a
            # broken pass: scanner.scan swallows its own exception and returns
            # no rows, which is exactly what an IP-level rate limit looks like
            # from a shared datacenter runner. Exit non-zero so the scheduler
            # reports a failure instead of a silent no-op hour.
            if seen == 0:
                print("  NOTHING JOURNALLED - failed pass, not a quiet one")
                rc = 1
        except Exception:
            traceback.print_exc()
            rc = 1
        if not loop:
            break
        time.sleep(900)
    return rc


if __name__ == "__main__":
    sys.exit(main())
