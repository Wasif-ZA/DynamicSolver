# greedy2

A greedy 3D carton packer. Replacement for `fitsolver.pack` (v1), developed
beside it rather than on top of it, so v1 stays byte-for-byte frozen and the two
can be benchmarked on identical input.

```python
from fitsolver.greedy2.pack import pack
solution = pack(items, cartons, time_budget_ms=1200, seed=1)
```

Same signature as v1. Selected through `engine.solve(payload,
algorithm="greedy2")` or `FITSOLVER_ALGORITHM=greedy2`. The default stays `v1`.

Integer millimetres and grams throughout. No floats, no epsilons, no randomness,
and no wall-clock reads during a solve: the same request always returns the same
layout.

## Results

Geometry-bound, 1200 ms budget, cartons (fewer is better). Full tables, both
mass regimes, and the bin4d caveat are in `BENCHMARK.md`.

| Workload | v1 | greedy2 |
|---|---:|---:|
| W1, 1000 items, all-distinct shapes | 36 | **20** |
| W2, 1000 items from 40 SKUs | 32 | **21** |
| W3, 40 small orders of 5 to 60 | 60 | **46** |
| W4, the `bench/run.py` cases | 28 | 28 |

Fill rate on W1 rises from 0.489 to 0.832, and the pass is faster: 12.3 s to
7.3 s.

With realistic carton mass limits the gain is much smaller (W1 54 to 53), because
mass rather than geometry then decides the carton count. Read both regimes.

## How it works, step by step

**1. Reject what can never fit.** A table keyed on `(dims, allowed_rotations)`
records which carton types could hold each item shape if the carton were empty.
A 1000-item order over 40 SKUs costs 40 tests, not 1000. Items that fit no
carton on geometry or mass are rejected here, before any geometry runs, and the
message names the real cause so an item that fits but is too heavy is not told
it is too big.

**2. Put the order in canonical form.** Items are sorted by content: dims, mass,
rotation rule, dg class, incompatibility set, then ref. The same goods submitted
in a different sequence give the same layout, so a packer who re-keys an order
sees the same picture.

**3. Split into conflict groups.** Items that can never share a carton, on
differing dangerous-goods class or an explicit incompatibility, are coloured
into separate groups that pack independently. Geometry never sees a constraint.
Each group carries three summaries (its one regulated class, the refs it holds,
the refs its members refuse) so admission is a set lookup rather than a scan of
every member. Linear, not quadratic.

**4. Compute a lower bound.** Per group, the larger of total item volume over
the largest carton's volume and total mass over the largest mass limit, as
integer ceilings, summed across groups because groups cannot share a carton. The
mass bound counts only if every carton has a limit; one unlimited carton and it
is not a bound at all.

**5. Try several item orderings and keep the best.** Volume descending, longest
edge, longest dimension, base area. Which is tried first depends on the order
size: volume descending wins up to 250 items and loses above it, measured. How
many are tried comes from `passes_for`, which divides the budget by a measured
per-pass cost table. If a pass reaches the lower bound with nothing unplaced it
is optimal on carton count and the rest are skipped.

The winner is chosen lexicographically: fewest unplaced, then fewest cartons,
then least total carton volume. **Fill rate is never optimised.** Maximising
fill rewards many small tight cartons, the opposite of "reduce the number of
boxes required".

**6. For each ordering, fill cartons one at a time.** Offer the first `CHUNK`
remaining items to every carton type that could hold at least one of them, and
open whichever packs the most items, tie-breaking on the smallest carton.
Evaluating every carton type is the single most important decision in the whole
solver. Measured against the naive alternative, opening the smallest carton
that fits the next item, on the same inputs and with everything else in greedy2
unchanged:

| Workload | every carton type | first-fit-smallest |
|---|---:|---:|
| W4 | 28 | 143 |
| W3 | 47 | 513 |
| W2 | 21 | 505 |

Five to twenty times worse. Nothing else in this file comes close to mattering
that much.

**7. Inside one carton, place items at live corner points.** Each carton has a
`CartonState` holding its placements, its contents mass, and its live candidate
points, kept sorted bottom-first. For each item, walk the first
`MAX_CANDIDATES` points and take the first position and orientation that is
inside the carton, clear of everything placed, and has at least 70 percent of
its base supported.

## The two ideas that made the difference

**Dead candidate points.** v1 keeps corner points that lie inside placed items,
and points on or beyond the carton walls. Nothing can ever be placed at either.
Sorted bottom-first and then cut at `MAX_CANDIDATES`, those dead low points
crowd out the live high ones, so the solver stops stacking. Measured on W1: half
of every scan was dead points, and the cut discarded live points in a quarter of
all placement attempts. Pruning them is most of greedy2's advantage.

**Deadness is permanent.** Free space only shrinks: the carton never grows and
placed items are never removed. So a point that nothing can start at stays that
way forever, which is what makes it safe to delete it and never look again. That
one fact licenses the incremental cache, the infeasibility memo and the
size-based point removal. After each placement the state drops the points the
new item covers and offers the item's three exposed corners, keeping only the
live ones, instead of rebuilding the list inside every placement attempt.

## Things that look like bugs and are not

**`candidates()` in `geometry.py` is never called by the solver.** It rebuilds
the live set from scratch and is kept as an obviously correct definition of what
`CartonState` should contain. The tests compare the cache against it after every
single placement, which is how an incremental update that only goes wrong deep
into a long run gets caught.

**Support failures are never memoised.** Bounds and overlap failures are
permanent, so they are remembered. A support failure is not: a later item can
become this one's floor. Memoising it would refuse placements that become legal
moments later, and that loses cartons without failing any test.

**Containment is half-open, `pos <= q < pos + dims`.** The point on top of a box
is where the next box starts. Treating it as covered would stop all stacking.

**Wall tests use `q >= wall`, not `>`.** `x == W` is outside the carton. Flush
against a wall means `x + w == W`, a different point.

**`sorted(item.dims) <= sorted(room)` is exact, not a heuristic.** A box
`a <= b <= c` fits a room `p <= q <= r` in some axis-aligned orientation if and
only if `a <= p`, `b <= q` and `c <= r`. That is why the O(1) pre-check can
replace six orientation trials without ever skipping a placement that would
have worked.

**Contact-area scoring exists and is switched off.** `CONTACT_SCORING` in
`pack.py`. v1's docstring said an ablation found it worthless, but that ablation
ran while the candidate cap bug was active, so it was re-tested properly in
phase 6. It is worse, not neutral: one workload improves by a carton, four get
worse, and every pass costs 1.5x to 5x more. `bench/ablate_contact.py` re-runs
the comparison and prints the verdict.

## Tuning constants

All in `pack.py`, each with its measurement recorded beside it.

| Constant | Value | Meaning |
|---|---:|---|
| `MAX_CANDIDATES` | 128 | corner points considered per placement |
| `CHUNK` | 240 | items offered to each carton per round |
| `LARGE_ORDER_ITEMS` | 250 | above this, a different ordering is tried first |
| `PASS_COST_MS` | table | measured cost of one pass, per order size |
| `CONTACT_SCORING` | False | score positions instead of taking the first fit |

Re-derive `PASS_COST_MS` on a different machine with
`python bench/calibrate_passes.py`.

## Tests

| File | Covers |
|---|---|
| `test_properties.py` | every invariant, against every registered algorithm |
| `test_scaling.py` | correctness and timing by order size, both regimes |
| `test_greedy2_layouts.py` | layouts match the recorded baseline, placement by placement |
| `test_greedy2_candidates.py` | pruning, and the cache against the slow reference |
| `test_greedy2_phase3.py` | the O(1) room test, the memo, the fit table |
| `test_greedy2_multistart.py` | canonical order, the lower bound, the work cap |
| `test_greedy2_grouping.py` | colouring identical to the pairwise original |
| `test_greedy2_contact.py` | the contact score arithmetic, and its default |
| `test_greedy2_scaffold.py` | algorithm selection and the env var |

`tests/data/greedy2_layouts.json` records about 2500 placements. Re-record with
`python tests/golden_layouts.py --write`, and only after checking the diff is
an intended change. A carton count alone will not catch a regression here: two
runs can agree on how many cartons they used and disagree about where every
item went.
