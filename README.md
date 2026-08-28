# crypto-intel

On-chain scanner and regime dashboard. Built 2026-08-20. Every endpoint here was
probed live before being written in.

**This produces data, not recommendations.** No trade execution anywhere in it.

## Run it
```
python config.py     # what keys are set, what each missing one costs you
python macro.py      # regime: prices, dominance, stablecoin flow, fear/greed
python scanner.py    # new-pair scan, scored and filtered  (arg: solana | ethereum | base)
```

## Files
| file | does |
|---|---|
| `sources.py` | every free endpoint, with retry/backoff. No keys needed. |
| `config.py` | key handling. Everything degrades gracefully and says what it lost. |
| `scanner.py` | new-pair scoring. **The thresholds in `CFG` are the product.** |
| `macro.py` | regime read. Run before looking at any single token. |
| `wallets.py` | early-buyer backfill + watchlist. Highest-value piece once keyed. |
| `pumpfun.py` | pre-bonding launch feed off the program account. |
| `notify.py` | Discord out. No-ops loudly without a webhook. |

## Design notes

**The scanner rejects.** 40 pools in, 3 out on the first live run. A scanner that
surfaces 200 candidates is noise. Every rejection prints its reason so the
thresholds can be argued with.

**Two wash-trading checks.** vol/liq above 40 is implausible. A buy/sell ratio
that is *too* clean reads as bots, not people.

**pump.fun fails ~90% of the time.** Failed buys, slippage, lost races. Query a
high limit or you will get an empty list and assume it is broken. The failure
rate is a congestion signal worth charting on its own.

**Macro before micro.** A good filter in a risk-off tape still loses. As of the
first run BTC dominance was 59%, meaning money was in majors and not rotating
into small caps, regardless of how green the majors looked.

## Keys (all free tiers, none need payment details)
| env var | unlocks |
|---|---|
| `HELIUS_API_KEY` | Solana websockets. Polling becomes real-time. |
| `BIRDEYE_API_KEY` | Holder distribution. **No free substitute exists.** |
| `ETHERSCAN_API_KEY` | ETH contract verification, holder counts. |
| `ALCHEMY_API_KEY` | ETH RPC. |
| `CRYPTO_DISCORD_WEBHOOK` | alert output |

Works without all of them, on the public Solana RPC.

## Known dead ends
- Binance API: HTTP 451 from US infrastructure.
- Jupiter, Reservoir: DNS-blocked in the build sandbox. May work locally.
- Magic Eden: 400 on the collections endpoint, needs different params.

## Next
1. Wallet tracker live via Helius websockets
2. Scanner + macro posting to Discord on a schedule
3. pump.fun subscription instead of polling
4. NFT module once the chain priority is decided

## Scheduling

The hourly collector runs as a GitHub Actions workflow
(`.github/workflows/collect.yml`), not as a Claude scheduled task. It is
stdlib-only Python on a timer — no model session is involved, and no reasoning
happens in a collection pass.

```
schedule: 0 * * * *      hourly, UTC. Best-effort: GitHub may run late.
                         journal.pending() looks back 6h, so a late or
                         missed hour is picked up by the next run.
```

**State lives in git.** `data/` is committed back after every run.
`journal.pending()` and `journal.scored_pairs()` need the whole history to know
what is due and what has already been scored, and the runner is stateless. The
Supabase mirror cannot serve that role: `crypto_observations` and
`crypto_outcomes` are write-only to the anon key — a secret-gated RPC goes in,
and there is no SELECT grant coming out.

Secrets are repo secrets, never files:

```
gh secret set SUPABASE_URL             --repo frankiev22/crypto-intel
gh secret set SUPABASE_PUBLISHABLE_KEY --repo frankiev22/crypto-intel
gh secret set CRYPTO_JOURNAL_SECRET    --repo frankiev22/crypto-intel
gh secret set CRYPTO_DISCORD_WEBHOOK   --repo frankiev22/crypto-intel   # optional
```

Discord is deliberately unset. Without it `notify.send` prints instead of
posting, which is its documented no-op. Set it to turn alerting back on.

A pass that journals zero rows exits non-zero. That is what an IP-level rate
limit looks like from a shared runner, and it must not read as a quiet hour —
a red run emails the repo owner, which is the alert path that works when
nobody is at the machine.
