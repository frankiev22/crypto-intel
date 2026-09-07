# X/Twitter API: priced, not signed up for

2026-09-07. Nothing has been signed up for. Prices below are from public
documentation and vendor write-ups, read today.

## What it costs now

**The free tier is gone, and the flat tiers are closed to new developers.**

| tier | price | status for us |
|---|---|---|
| Free | — | **discontinued entirely** |
| Basic | $200/mo | existing subscribers only, **closed to new signups** |
| Pro | $5,000/mo | closed; remaining subscriptions end after 2026-09-01 |
| **Pay-per-use** (the only route open) | **$0.005 per post read** | hard cap 2,000,000 reads/month |
| | $0.015 per post created ($0.20 with a link) | |
| Enterprise | ~$42,000+/mo | required above the 2M cap; sales conversation |

Hitting the 2M read cap costs about **$10,000**.

## What real-time narrative detection would actually consume

A narrative breaks and the coins appear within the hour. To see the *tweet*
rather than the *launches*, you need broad, continuous coverage — keyword
searches plus a few hundred accounts, polled at minutes-level.

| polling shape | posts/day | monthly cost at $0.005 |
|---|---:|---:|
| 100 posts every 5 min | 28,800 | **$4,320** |
| 10 posts/min | 14,400 | **$2,160** |
| 1 post/min (uselessly sparse) | 1,440 | $216 |
| budget-capped at $50/mo | ~333 | ~14 posts/hour — cannot see a wave forming |

**Against a $1,000 bankroll, the cheapest genuinely useful configuration costs
roughly 2x his entire capital every month.** There is no tier, no discount and
no clever query shape that changes that. The answer is no.

A third-party reseller advertises $0.00015/read, about 33x cheaper — ~$130/month
at the 28,800/day shape. Still 13% of the bankroll monthly, still requires
creating an account, and it puts a resale intermediary between us and the data.
**Priced, not recommended, not signed up for.**

## The caveat that decides it

**The best narrative in our entire record would have been missed by an English
crypto-Twitter feed anyway.** The 2026-08-27 wave was Justin Sun's Chinese-
language essay, partly Weibo-origin. Our scanner logged 我的女友景甜 — the post's
own title — at 12:05 the same day, and then 我的男友孙宇晨, 孙宇晨VS景甜,
景甜孩子的妈妈, 景甜妈妈, 女友景甜, 景甜, 孙宇晨 over the following day.

We did not need Twitter to see that. **The launches were the signal**, and they
were already in the journal. Nothing grouped them, which is what `clusters.py`
now fixes, for free.

## The honest conclusion, including the part that is not flattering

**The free cluster detector is most of the value.** But the lead time X would
buy is real and I will not pretend otherwise — a tweet precedes its coins by
some minutes, and being first matters in this market.

What I can say precisely is that **X is not our binding constraint, our own
polling cadence is.** Measured over the 7 days to 2026-09-07: the hosted
collector fires about **7 times a day, median gap 3.4h, worst 5.5h** against a
cron that asks for hourly. A narrative that breaks at 13:10 is not seen until
the next pass, which on average is ~2 hours later and can be 5.

So the lead time available for **$0** — by fixing our own scheduling — is larger
than the lead time available for **$2,160/month** from X on top of a collector
that only wakes up every 3.4 hours. **Fix the cadence first. Revisit X only if
cadence is solved and lead time is still the thing losing money.**

## Sources

- <https://twitterapi.io/blog/x-api-cost-breakdown-2026>
- <https://postproxy.dev/blog/x-api-pricing-2026/>
- <https://www.xpoz.ai/blog/guides/understanding-twitter-api-pricing-tiers-and-alternatives/>
