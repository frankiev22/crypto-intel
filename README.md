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
