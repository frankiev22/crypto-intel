# Late closes — pre-committed 2026-09-14, before any gap position is priced

## What happened

The host was off from 9/11 ~16:06Z. The GitHub runner covered until 9/12 19:42Z,
then stopped: GitHub declined to start the job over an account billing hold. From
9/12 19:44Z to 9/14 19:43Z nothing ran, **the sweep included.** `paper.sweep`
last ran 2026-09-12 19:44Z.

So at 19:51Z today, **15 v1 and 64 v2 positions sit past their 24h hold**, aged
48–79h. The exit rule both ledgers pinned is "first of 2.0x on quote-side depth,
or 24h elapsed". When the sweep next runs it will price them at 48–79h, and
record the reason as an ordinary expiry.

## The definition, fixed now

A close is **late** when elapsed hold exceeds **24h × journal.DRIFT_TOLERANCE**:

    late  ⇔  elapsed_h > 36.0

The multiplier is the project's existing horizon-drift tolerance (1.5), not a
number chosen here. It is written down before a single gap position has been
priced, so no outcome could have informed it.

Both ledgers already record elapsed time on every exit — `actual_elapsed_h` in
v1, `elapsed_h` in v2 — so every late close stays identifiable forever and
nothing needs rewriting.

## What does NOT happen

- No late close is voided, deleted or re-priced. The price at 60h is a real
  price; it is simply not the outcome of a 24h rule.
- No price is invented for the 24h mark. None was observed, so none exists.
- The sweep is not held back. A position left open indefinitely is worse than a
  late close that is labelled as one.

## How the n=200 number is reported

**Every figure is given with late closes included AND excluded**, alongside the
existing measured-only / measured-plus-inferred split, with n and Wilson
intervals on each. If the two differ materially, that gap is the finding. No
headline picks one.

Before this, v1 held 125 closes with a median hold of 25.7h and a maximum of
36.1h: the rule was being honoured to within about an hour. The gap is the first
event that breaks it at scale.
