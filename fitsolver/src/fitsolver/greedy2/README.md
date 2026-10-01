# greedy2

A greedy 3D carton packer. It replaces `fitsolver.pack` (v1) and was developed
beside it rather than on top of it, so v1 stays unchanged and the two can be
compared on identical input.

What worked, what did not, the measurements behind every constant, and
references are in [`DESIGN_NOTES.md`](DESIGN_NOTES.md).

## Usage

```python
from fitsolver.greedy2.pack import pack
solution = pack(items, cartons, time_budget_ms=1200, seed=1)
```

Same signature as v1, so `engine.py` calls it in place of v1.

Integer millimetres and grams throughout. No floats, no epsilons, and no
wall-clock reads during a solve. The only randomness is seeded from the
request's `seed`, so the same request and seed always give the same layout on
any machine.

## Results in brief

Cartons used, fewer is better (geometry-bound, 1200 ms budget):

| Workload | v1 | greedy2 |
|---|---:|---:|
| 1000 items, all-distinct shapes | 36 | **20** |
| 1000 items from 40 SKUs | 32 | **20** |
| 40 small orders of 5 to 60 items | 60 | **46** |
| mixed test cases | 28 | **25** |

Against exact optima computed with Google's CP-SAT solver on 64 small orders,
greedy2 is 8.7% above optimum geometry-bound (v1: 23.2%) and 2.6% above with
realistic mass limits (v1: 13.2%). Full tables are in `DESIGN_NOTES.md`.

## How it works

1. **Reject what can never fit.** A table records which carton types could hold
   each item shape. Items no carton can hold, by size or by mass, are rejected
   up front with a message naming the real cause.
2. **Put the order in canonical form.** Items are sorted by content, not request
   order, so the same goods in a different sequence give the same layout.
3. **Split into conflict groups.** Items that can never share a carton
   (different dangerous-goods classes, or an explicit incompatibility) go into
   separate groups that pack independently.
4. **Compute a lower bound.** The fewest cartons any solution could use, from
   total volume and total mass. A pass that reaches it is optimal, so the solve
   stops early.
5. **Try several item orderings, keep the best.** Four named orderings (volume,
   longest edge, base area, mass), then seeded restarts: random orderings that
   stay close to largest-first. How many passes run is the budget divided by a
   fixed per-pass cost table, never a clock. The best result is the one with
   fewest unplaced items, then fewest cartons, then least carton volume. Fill
   rate is never optimised.
6. **Fill cartons one at a time.** Each round, every usable carton type is
   test-filled and the one packing the most volume is kept. This is the most
   important decision in the solver: opening the smallest carton that fits is
   5 to 20 times worse.
7. **Place items at live corner points.** Inside a carton, each item goes at the
   lowest corner point where it fits inside the walls, overlaps nothing, and has
   at least 70% of its base supported.
8. **Try to remove a carton.** After each pass, try to move every item out of
   the emptiest carton, then try to repack the last two or three cartons into
   one fewer. A move is only taken if it removes a carton, so this can never
   make a result worse.

## Things that look like bugs and are not

**`candidates()` in `geometry.py` is never called by the solver.** It rebuilds
the live point set from scratch and is the obviously correct reference. The
tests compare the fast cache against it after every placement.

**Support failures are never memoised.** Bounds and overlap failures are
permanent, so they are remembered. A support failure is not: a later item can
become this one's floor. Memoising it would quietly refuse legal placements.

**Containment is half-open, `pos <= q < pos + dims`.** The point on top of a box
is where the next box starts. Treating it as covered would stop all stacking.

**Wall tests use `q >= wall`, not `>`.** `x == W` is outside the carton. Flush
against a wall means `x + w == W`, a different point.

**`sorted(item.dims) <= sorted(room)` is exact, not a heuristic.** A box
`a <= b <= c` fits a space `p <= q <= r` in some orientation if and only if
`a <= p`, `b <= q` and `c <= r`.

**Dead points are deleted for good.** Free space only shrinks, so a point where
nothing can be placed stays that way. That is what makes the incremental point
cache and the memo safe.

**Contact-area scoring exists and is switched off.** `CONTACT_SCORING` in
`pack.py`. It was measured and made results worse; see `DESIGN_NOTES.md`.

## Tuning constants

All at the top of `pack.py`. Why each value was chosen is in `DESIGN_NOTES.md`.

| Constant | Value | Meaning |
|---|---:|---|
| `MAX_CANDIDATES` | 128 | corner points considered per placement |
| `CHUNK` | 240 | items offered to each carton per round |
| `LARGE_ORDER_ITEMS` | 250 | above this, a different ordering is tried first |
| `RESTART_WINDOW` | 2 | how far a seeded restart may stray from volume order |
| `MAX_PASSES` | 64 | safety ceiling on passes per solve |
| `PASS_COST_MS` | table | measured cost of one pass, per order size |
| `ELIMINATE_VICTIMS`, `ELIMINATE_ATTEMPTS` | 3, 8 | limits on the emptying move |
| `REPACK_SPANS`, `REPACK_MAX_ITEMS` | (2, 3), 40 | limits on the repacking move |
| `CONTACT_SCORING` | False | score positions instead of taking the first fit |

`PASS_COST_MS` was measured on one development machine and may need
re-measuring on the deployment machine.

## Tests

| File | Covers |
|---|---|
| `test_properties.py` | every packing invariant |
| `test_scaling.py` | correctness and timing by order size, both mass regimes |
| `test_greedy2_layouts.py` | layouts match the recorded baseline, placement by placement |
| `test_greedy2_candidates.py` | point pruning, and the cache against the slow reference |
| `test_greedy2_phase3.py` | the O(1) room test, the memo, the fit table |
| `test_greedy2_multistart.py` | canonical order, the lower bound, the pass cap |
| `test_greedy2_grouping.py` | conflict grouping matches the pairwise definition |
| `test_greedy2_contact.py` | the contact score arithmetic, and that it is off |
| `test_greedy2_phase11.py` | the mass ordering and the packed-volume carton choice |
| `test_greedy2_phase12.py` | restarts are deterministic, elimination never makes things worse |

`tests/data/greedy2_layouts.json` records about 2500 placements. Re-record with
`python tests/golden_layouts.py --write`, and only after checking the change is
intended. A carton count alone will not catch a regression: two runs can use
the same number of cartons and put every item somewhere different.
