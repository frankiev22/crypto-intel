# "Bouncer": domain availability and the ticker collision, measured

**2026-09-23.** Frank asked for a Namecheap `domains.check` on five domains plus
a check that no Solana token would collide with the name.

⛔ **Nothing was purchased and no account setting was changed.**

---

## 1. ⛔ Two corrections to the brief, before the answers

**(a) The Namecheap key is NOT in `C:\Users\Frankie\.openclaw\openclaw.json`.**
That file holds 111 keys and none of them mentions Namecheap; there is no
`gateway.cmd` in that directory either, only a `.deprecated-2026-05-06` copy that
sets no environment variables. The credentials are `NAMECHEAP_API_KEY` (32 chars)
and `NAMECHEAP_USERNAME`, and they live in **three** places:

- `Desktop\Projects\dispatch-workspace\.env`
- `Documents\openclaw-review\gateway.cmd`
- `OLD-OC-old\gateway.cmd`

⛔ **Values are never printed, logged or committed.** A disk sweep of 62,154 files
found the word "Namecheap" in 40 documents, all prose except those three.

**(b) The Namecheap API call is BLOCKED, and not by the key.** The call reached
Namecheap and came back:

```
API Status: ERROR
  ERROR 1011150: Invalid request IP: 184.152.217.111
```

That is the IP whitelist on Frank's Namecheap account, not an auth failure. ⛔ **I
did not add the IP**: changing an account setting is his call, and the address is
a home IP that will rotate. **So `domains.check` produced no availability and no
price**, and the prices below are therefore **NOT ESTABLISHED**.

---

## 2. Availability, from each registry's own RDAP or whois

⭐ Free, keyless, and authoritative for existence because it is the registry's own
database. The endpoint for each TLD comes from **IANA's own bootstrap file**
(`data.iana.org/rdap/dns.json`), not guessed, and **every TLD has a control that
must read REGISTERED** or that TLD's answer is void.

| priority | domain | answer | evidence |
|---|---|---|---|
| 1 | **`bouncer.fun`** | ⭐ **AVAILABLE** | registry has no record (404), control `pump.fun` reads REGISTERED |
| 2 | `bouncer.xyz` | ⛔ **TAKEN** | registered **2014-10-31**, expires 2026-10-31, four client-side locks |
| 3 | **`thebouncer.fun`** | ⭐ **AVAILABLE** | 404, same working endpoint |
| 4 | `bouncer.so` | ⛔ **TAKEN** | `whois.nic.so` returns a record; control `nic.so` reads REGISTERED |
| 5 | `bouncer.app` | ⛔ **TAKEN** | registered **2018-05-09**, expires 2027-05-09 |

⚠️ **`bouncer.app` was the control catching a mistake of mine.** My first pass
used `www.registry.google/rdap/` and got a 404, which read as *available*. The
IANA bootstrap gives `pubapi.registry.google/rdap/`, and the same domain is
**registered since 2018**. ⛔ **A wrong endpoint returning 404 is indistinguishable
from an available domain** unless a control proves the endpoint works. Same bug
class as everything else in this repo: not-checked reading as clean.

⚠️ **`.so` publishes no RDAP endpoint at all** in IANA's bootstrap, so that answer
comes from port-43 whois instead.

### ⛔ What is NOT established

- **No price, for any of them.** First-year and renewal both need
  `namecheap.users.getPricing`, which is behind the same IP whitelist.
- **Whether `bouncer.fun` is a PREMIUM name.** `.fun` premiums are common and can
  be hundreds of dollars a year. RDAP says nothing about price; only
  `domains.check` returns `IsPremiumName` and `PremiumRegistrationPrice`.
- ⚠️ Frank's instinct that renewal on `.fun` and `.xyz` is often far above the
  first year is correct as a pattern, but **I have no figure for it and am not
  guessing one.**

⭐ **Two ways to get the price without me touching his account:** whitelist the
current IP under Namecheap's API settings and I can run the call, or put the
domain in the cart, where the renewal price is shown before payment.

---

## 3. The ticker collision, and it is not clean

Jupiter's token search returns **20 Solana mints** whose symbol or name contains
"bouncer". Of those:

- ⛔ **7 carry the exact symbol `BOUNCER`.**
- ⛔ **2 carry the exact name `Bouncer`**: `C1tGGgNA8GutDrehkmeVpRC6M1yaVdzuoxkMhASBBoY1`
  (symbol BOUNCER, pump.fun, **first pool 2026-09-21**, two days ago) and
  `A5kfREcZ4L11FnAYhsNPJEy6wZmnrdLEPR1D68hGpump` (symbol BNCR, 2026-08-26).
- One is on **bags.fun**, not pump.fun: `E3XfEaLR3RbzCPvQgMhDLjS9AzFicXPVxMpusPmmBAGS`,
  "Persuadable Bouncer", first pool 2025-08-14.
- The oldest are from **2024-06-10** ("BILLY THE BOUNCER", 78 holders, and an
  "OFFICIAL" duplicate with 59).

⭐ **None of them is a real market.** Every one of the 7 exact-symbol mints returns
**0 pairs** from the indexer. Measured from chain with the derived-pool path:

| mint | state | reserves | $100 round trip |
|---|---|---|---|
| `C1tGGgNA8Gut…` | curve_died | **$0.00** | TRADEABLE, $92.22 back |
| `FsQ75AkBjNDK…` | curve_died | $0.04 | TRADEABLE, $92.22 |
| `3Jao55pMF3VB…` | curve_died | $0.04 | TRADEABLE, $92.22 |
| `98CbJFdpx663…` | curve_died | $0.59 | NO_BUY_ROUTE |
| `E3XfEaLR3Rbz…` | **pool_live** | **$23.27** (Meteora DBC) | NO_BUY_ROUTE |
| `5YoR2J9dLA2h…` | curve_died | $0.08 | NO_BUY_ROUTE |
| `13hivKpUS961…` | curve_died | $0.06 | NO_BUY_ROUTE |

Holder counts are **1 to 8**. Market caps, where Jupiter reports one at all, are
**$869 to $3,350**.

### ⭐⭐ And that first row is a free control worth keeping

`C1tGGgNA8Gut…` holds **$0.00** of quote side and still quotes **$92.22 back on a
$100 round trip**, because a bonding-curve round trip is paid for by its own buy
leg. ⛔ **That corrects a claim I published an hour earlier in this session**: of
the four `gone` contracts I called verified sellable, only **APEZCAT ($1,238.65)
and TRADER ($225.80)** hold more than the $100 probe. **CATP ($11.45) and PERPY
($11.04) are round-trippable but self-financed.**

---

## 4. The read for the brand

- ⭐ **`bouncer.fun` is available and it is the one that matches the product**, if
  it is not priced as a premium.
- ⛔ **`.xyz`, `.so` and `.app` are all gone**, so the choice is `.fun`, a prefix
  like `thebouncer.fun`, or another word.
- ⚠️ **The ticker is contested but not occupied.** 7 mints wear BOUNCER and 2 are
  named Bouncer, with no liquidity between them - but one was minted **two days
  ago**, which is what happens to any name that gets said out loud near a
  launchpad. ⭐ **Our own `resolve('BOUNCER')` returns no winner**, which is the
  product working on us: a ticker is not an identifier, the contract is.
