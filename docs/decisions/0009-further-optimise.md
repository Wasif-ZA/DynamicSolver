# ADR-0009: "Further Optimise": an opt-in exact search for one smaller carton

- **Status:** accepted
- **Date:** 2026-10-30

## Context

The client's challenge order has 15 items and three box types, priced at 300 pesos (P200), 500
(P300) and 750 (P500), plus 1 peso for every second of packing time.

- **greedy2** packs it into one P500 in a few milliseconds: **about 750 pesos**.
- **One P300** can hold every item. An exact solver (Google's CP-SAT) found and verified that
  layout: **about 505 to 525 pesos**, including the search time.
- greedy2 cannot reach that layout. Nine cheap changes were tried (more orderings, contact
  scoring, rotation orders, extra candidate positions, randomised placement, a capped search) and
  none got past 14 of 15 items.
- CP-SAT takes several seconds, too slow for the 1 to 2 second bar on every order.

## Decision

**Add an opt-in "Further Optimise" step. Normal solving is unchanged.**

1. greedy2 answers first. Its answer is always the fallback.
2. Only orders of **30 items or fewer**, with no rejects and one conflict group, go further.
3. It tries to fit the **whole order in one carton smaller than greedy2's**, starting with the
   next size down, and **stops at the first one that fits**.
4. CP-SAT searches for that layout under greedy2's own rules: allowed rotations, inside the
   carton, no overlaps, 70% support, the mass limit and `maximum_boxes`. Every layout is
   re-checked with greedy2's geometry before it is used.
5. **Hard limit: 30 seconds.** If nothing is found in time, greedy2's answer is returned.

It is reached with `engine.solve(payload, optimise=True)`, or `?optimise=true` on the API. An
improved answer has `solver.tier: 2`. OR-Tools is an optional install
(`pip install -e ".[optimise]"`); without it, the button returns greedy2's answer.

## Why

- **The saving outweighs the time.** One P300 saves 250 pesos, and a second costs 1 peso. Even a
  miss costs at most 30 pesos of waiting.
- **30 seconds, not 25.** Measured on the challenge on a 2-core machine, the P300 was found in
  about 90% of runs within 30 seconds, against about 85% within 25. Each extra second costs 1 peso
  against a 250 peso saving. A machine with more cores does better.
- **Next size down, then stop.** A slightly smaller carton is far easier to prove than the
  smallest, so trying it first finds a saving more often within the limit.
- **Small and contained.** One new module, one engine flag, an optional dependency. greedy2 is not
  touched.

## Consequences

- It only ever tries **one** smaller carton. It will not find "3 cartons instead of 4", and it uses
  carton volume as a stand-in for price, which matches the client's price list.
- Its timing varies between runs, and so can the layout it returns. That is accepted because it
  runs only when asked for.
- The Portal needs the button, a loading state, and a way to show the improved answer.
