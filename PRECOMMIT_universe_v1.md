# Universe definition v1 — PRE-COMMITTED 2026-09-10, before measuring size

Written BEFORE looking at how many tokens each band contains. The low-score
inversion died of exactly this: a band chosen after seeing which tokens it
would have caught. If these numbers turn out inconvenient they stay as they
are, and the inconvenience is the finding.

## The two bands

**GRADUATED** — `venue_type == "amm"` AND `is_graduated is True`.
  A real two-sided pool exists. This is an observable event, not an opinion.

**APPROACHING** — `venue_type == "bonding_curve"` AND
  `fdv >= 0.75 * GRADUATION_MCAP_USD` (>= $51,750) AND `fdv < $69,000`.
  75% of the way up the curve. Chosen because it is a round three-quarters,
  not because of anything observed about which tokens sit there.

## What does NOT change

The fraud gate is untouched: exit depth >= $1,000, mint/freeze authority known
AND revoked, sell side ever tested, pair identity verified, D1, the sticky
quarantine. Removing the score does not loosen one of them. A token in the
universe still has to clear the gate before it is entered or announced.

## What this is NOT

Graduation predicts LEGITIMACY, not appreciation. A graduated token is real
enough to have cleared ~$69k of market cap and to have a pool that can be sold
into. It says nothing whatsoever about whether it goes up. This is a universe
definition. It is not a signal and must never be reported as one.

## Pre-committed success criterion for size

Tractable if the daily universe is <= 150 new contracts. Useless as a dashboard
above ~500. Between 150 and 500, it needs a second cut before Frank looks at it.
