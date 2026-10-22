# greedy2 design notes

What greedy2 does, what was measured, what worked, and what was tried and
rejected. The code in `pack.py` and `geometry.py` only explains what it does;
the reasons and the numbers live here.

For a step-by-step walkthrough of the algorithm, see `README.md`. The benchmark
scripts named below (`bench/`) are maintained separately from this repository;
the tables here are their recorded results.

## 1. How to read the numbers

Every number below is a carton count (fewer is better) unless stated otherwise.

**Workloads.** W1 is 1000 items with distinct shapes, W2 is 1000 items from 40
SKUs, W3 is 40 small orders of 5 to 60 items, and W4 is the `bench/run.py`
cases. Run with `python bench/compare_algorithms.py`.

**Optimum fixtures.** 64 small orders whose true optimum was computed exactly
with Google's CP-SAT solver [4], [5] (section 5). "Small" is 5 to 12 items and
"large" is 14 to 20 items. Only S and M cartons are used, because with the full
catalogue one XL carton swallows any order this size. Run with
`python bench/compare_optimum.py`.

**Two regimes.** "Geometry-bound" means cartons have no mass limit, so space
decides the count. "Mass-limited" means realistic mass limits, so weight often
decides it. Every change was measured in both.

**The keep rule.** A behaviour change was kept only if it reduced cartons on at
least one workload or fixture set and made none worse, in both regimes.
Otherwise it was reverted and recorded in section 4.

Budget is 1200 ms and seed is 1 unless stated.

## 2. Results

### Against v1

| Workload | v1 geometry-bound | greedy2 geometry-bound | v1 mass-limited | greedy2 mass-limited |
|---|---:|---:|---:|---:|
| W1 | 36 | **20** | 54 | **53** |
| W2 | 32 | **20** | 56 | **54** |
| W3 | 60 | **46** | 87 | 87 |
| W4 | 28 | **25** | 32 | **31** |

greedy2 is fewer or equal on all eight rows, with zero unplaced items on
every workload. W1 fill rate rises from 0.489 to 0.832.

With mass limits the gain is small, because weight rather than space decides
the count, so there is much less for a packer to get wrong.

### Against the proven optimum

| Fixture set | v1 | greedy2 | Optimum | greedy2 above optimum |
|---|---:|---:|---:|---:|
| 5 to 12 items, geometry-bound | 36 | **31** | 28 | 10.7% |
| 5 to 12 items, mass-limited | 36 | **31** | 30 | 3.3% |
| 14 to 20 items, geometry-bound | 49 | **44** | 41 | 7.3% |
| 14 to 20 items, mass-limited | 50 | **47** | 46 | 2.2% |

Over all sets, greedy2 is 8.7% above optimum geometry-bound (v1: 23.2%) and
2.6% mass-limited (v1: 13.2%). 54 of the 62 proven orders are solved exactly,
and no order is more than one carton above its optimum.

How the gap closed over the later phases:

| After | Geometry-bound gap | Mass-limited gap |
|---|---:|---:|
| phase 9 (measured, no change) | 18.8% | 9.2% |
| phase 11 (rule fixes) | 17.4% | 7.9% |
| phase 12 (restarts and elimination) | **8.7%** | **2.6%** |

**Seed spread.** The restarts are seeded, so seed 1 is one draw. Over seeds 1
to 10 (min / median / max):

| Fixture set | Optimum | phase 11 | phase 12 |
|---|---:|---|---|
| 5 to 12, geometry-bound | 28 | 32 / 32 / 32 | 31 / 31 / 32 |
| 5 to 12, mass-limited | 30 | 32 / 32 / 32 | 31 / 31 / 32 |
| 14 to 20, geometry-bound | 41 | 49 / 49 / 49 | 44 / 44 / 44 |
| 14 to 20, mass-limited | 46 | 50 / 50 / 50 | 47 / 47 / 47 |

Every seed beats phase 11 on every set, and seed 1 equals the median.

## 3. What worked

### 3.1 Pruning dead corner points (phase 2) - the biggest single win

greedy2 places each item at a corner point: a position next to an item already
placed, tried lowest first. This is a simplified form of the corner-point and
extreme-point rules in the 3D bin packing literature [2], [3].

v1 kept corner points where nothing could ever go: points inside placed items,
and points on or past a carton wall. It then sorted the list lowest-first and
cut it to a fixed length, so those dead low points pushed out the live high
ones, and the solver stopped stacking. Measured on W1, half of every scan was
dead points, and the cut discarded live points in a quarter of all placement
attempts.

greedy2 drops dead points and keeps the live ones in a per-carton cache that is
updated after each placement instead of rebuilt. This is safe because free
space only ever shrinks, so a dead point stays dead. Together with the later
phases, W1 went from 36 cartons to 20.

With dead points gone, the candidate cap was re-swept. At the time,
`MAX_CANDIDATES` of 128 gave 25 cartons on W1 against 27 at 64, for about 9%
more time. The most live points ever seen in one carton is 118, so 128 is a
safety bound.

### 3.2 Exact pre-checks and a memo (phase 3) - speed only

An O(1) test rejects a point before trying any orientation: a box with sorted
sides a <= b <= c fits a space p <= q <= r in some orientation if and only if
a <= p, b <= q and c <= r. Points where a shape can never fit are remembered.
Layouts are identical; only time changed.

One rule matters here: a point that fails only on the 70% support rule is
never remembered, because a later item can become its floor.

### 3.3 Trying every carton type each round (kept from v1, re-measured)

Each round, every usable carton type is test-filled and the best is kept.
Against the obvious alternative, opening the smallest carton that fits the
next item (measured before phase 11):

| Workload | Every carton type | Smallest that fits |
|---|---:|---:|
| W4 | 28 | 143 |
| W3 | 47 | 513 |
| W2 | 21 | 505 |

Five to twenty times worse. This is the most important decision in the solver.

### 3.4 Multi-start with a lower-bound early stop (phase 4)

Several item orderings are tried and the best result kept, a standard
multi-start approach [8]. A pass that reaches the lower bound is provably
optimal on carton count, so the solve stops there.

The lower bound, per conflict group, is the larger of total volume over the
largest carton and total mass over the largest mass limit, in the spirit of
the simple bounds in [2].

### 3.5 Ordering by order size, and CHUNK (phase 5)

No single ordering wins everywhere. Single pass, mean cartons over 8 seeds,
geometry-bound:

| Items | Volume | Longest edge | Base area |
|---:|---:|---:|---:|
| 100 | 2.62 | 2.88 | 2.88 |
| 200 | 4.75 | 4.88 | 4.88 |
| 250 | 5.75 | 5.75 | 5.75 |
| 300 | 6.88 | 6.75 | 6.75 |
| 400 | 9.38 | 8.50 | 9.00 |
| 600 | 14.00 | 12.38 | 13.25 |

Volume wins up to 250 items and loses above, so `LARGE_ORDER_ITEMS = 250`
switches which ordering is tried first. That matters because a large order can
often afford only one pass.

`CHUNK` limits how many items are offered to each carton per round, which
bounds the cost of very large orders. Geometry-bound, cartons / time:

| CHUNK | W1 | W2 | W3 | W4 |
|---:|---|---|---|---|
| 120 | 21 / 3.66 s | 21 / 0.39 s | 46 / 1.32 s | 28 / 0.12 s |
| 240 | 20 / 7.06 s | 21 / 0.74 s | 46 / 1.33 s | 28 / 0.13 s |
| none | 20 / 17.04 s | 20 / 1.29 s | 46 / 1.35 s | 28 / 0.12 s |

240 matches no chunking on W1 for less than half the time. It has no effect on
orders under 240 items.

Conflict grouping was also made linear instead of quadratic, with identical
output.

### 3.6 Two rule fixes from code review (phase 11)

**Mass ordering replaces "tallest".** "Tallest" and "longest edge" both sorted
on the longest side first, so there were really three orderings, not four. A
mass-descending key replaced it: 33 to 32 cartons on each small fixture set,
both regimes, nothing worse. Mass is the weakest single ordering on large
orders, so it is tried last.

**Carton choice by packed volume, not item count.** Counting items let a big
carton win a round by filling up with small items, leaving the large ones to go
one per carton. Choosing by packed volume: 33 to 32 on each small set, both
regimes, nothing worse. The 10-item order `n10-0` went from 4 cartons to 3.

The two fixes overlap: each alone is worth one carton per small set, and both
together are still worth one.

### 3.7 Seeded restarts (phase 12)

Small orders used about 15 ms of their 1200 ms budget. After the four named
orderings, further passes now use seeded random orderings. They are not full
shuffles: each next item is picked at random from the first two items still
waiting in volume order (`RESTART_WINDOW = 2`), so big items still come first.
The random numbers come from Python's `random` module, seeded from the
request's `seed` and the pass number, so the same request always gives the
same layout [9].

The window width was compared over seeds 1 to 10 (median / worst):

| Window | 5 to 12 gb | 5 to 12 ml | 14 to 20 gb | 14 to 20 ml |
|---|---|---|---|---|
| 2 | 31.0 / 32 | 31.0 / 32 | 44.0 / 44 | 47.0 / 47 |
| 3 | 31.0 / 31 | 31.0 / 31 | 44.0 / 45 | 47.0 / 48 |
| 4 | 31.0 / 31 | 31.0 / 31 | 44.5 / 45 | 47.0 / 47 |
| 6 | 31.0 / 31 | 31.0 / 31 | 44.0 / 45 | 47.0 / 47 |
| uniform shuffle | 31.0 / 31 | 31.0 / 31 | 45.0 / 47 | 48.0 / 49 |

Widths 2 to 6 are within a carton of each other. The firm finding is that a
full shuffle is worst: the greedy needs big items first.

`MAX_PASSES = 64` is a safety ceiling, not a tuned value. More passes can never
make the result worse, because the best pass is kept. The budget divided by
`PASS_COST_MS` is the real limit, and by 64 every median and worst case over
seeds 1 to 10 has stopped improving.

### 3.8 Carton elimination (phase 12)

After each pass, two moves try to remove a carton. Each is taken only if it
removes a carton and places every item, so it can never make a result worse.

1. **Empty:** move every item of the emptiest carton into the others.
2. **Repack:** re-pack the last two cartons into one, then the last three into
   two.

The two halves earn different things (seed 1, on top of the restarts):

| | 5 to 12 gb | 5 to 12 ml | 14 to 20 gb | 14 to 20 ml | W2 gb | W2 ml |
|---|---:|---:|---:|---:|---:|---:|
| neither | 31 | 31 | 45 | 48 | 21 | 55 |
| empty only | 31 | 31 | 45 | 48 | 20 | 54 |
| repack only | 31 | 31 | 44 | 47 | 21 | 55 |
| both | 31 | 31 | 44 | 47 | 20 | 54 |

Phase 12 overall, geometry-bound, seed 1:

| | 5 to 12 | 14 to 20 | W1 | W2 | W3 | W4 |
|---|---:|---:|---:|---:|---:|---:|
| after phase 11 | 32 | 49 | 20 | 21 | 46 | 28 |
| + seeded restarts | 31 | 45 | 20 | 21 | 46 | 25 |
| + elimination | 31 | 44 | 20 | 20 | 46 | 25 |

**Timing.** Worst whole solve at the 1200 ms budget, both regimes: 5 items 1 ms,
20 items 16 ms, 60 items 250 ms, 250 items 644 ms. Nothing exceeds the budget.
Small-order totals (W3, W4) are now slower than v1 because small orders spend
their budget, and the test suite went from about 21 s to 81 s.

## 4. What did not work

Each of these was built, measured under the keep rule, and reverted. They are
recorded so nobody rebuilds them without new evidence.

### 4.1 Contact-area scoring (phase 6)

Instead of taking the first position that fits, score every position by how
much face area it shares with walls and neighbours. Cartons, off to on:

| Regime | W1 | W2 | W3 | W4 |
|---|---|---|---|---|
| geometry-bound | 20 to 21 | 21 to 25 | 46 to 48 | 28 to 28 |
| mass-limited | 53 to 53 | 55 to 54 | 87 to 87 | 32 to 33 |

Four workloads worse, one better by a carton, and 1.5 to 5 times slower.
Wedging each item into the tightest spot breaks the lowest-first order that
keeps the free space in one usable block. `CONTACT_SCORING` stays in the code,
switched off, so `bench/ablate_contact.py` can re-run this.

### 4.2 Other carton-choice rules (phase 11)

- **Minimise leftover carton volume:** 73, 75, 105 and 116 cartons against
  optima of 28, 30, 41 and 46. It opens the smallest carton anything fits in,
  every time.
- **Packed volume, then item count as a tie-break:** identical to packed volume
  everywhere. Volume ties between carton types almost never happen.
- **Packed volume, then packed mass:** identical everywhere. The carton packing
  the most volume nearly always packs the most mass too.

### 4.3 A combined volume and mass ordering (phase 11)

Sort by the larger of volume over the biggest carton and mass over the biggest
limit. Identical to the baseline on every set and workload, because on these
catalogues the volume term almost always wins, so it reproduces the volume
ordering.

### 4.4 Base area from the largest face (phase 11)

For freely rotatable items, `base_area` uses the first two dimensions as typed,
which is arbitrary. Using the largest face instead changed nothing on any set
or workload in either regime: base area runs last on small orders and not at
all on large ones. The dependence on typing is real but not reachable today.

### 4.5 A stronger lower bound (phase 11)

Items each larger than half the biggest carton can never share one, so their
count is a valid bound, a simplified form of the bounds in [2]. Correct, but it
was higher than the existing bound on 0 of 188 orders measured: no test item is
that large. Worth re-measuring if the client ships bulky goods.

### 4.6 Orientation trial order (phase 11)

`place()` tries orientations in the order the dimensions were typed. Three
shape-based trial orders were tested:

| Set / workload | As typed | Tallest first | Flattest first | Largest base first |
|---|---:|---:|---:|---:|
| 5 to 12, gb | 33 | 32 | 32 | 32 |
| 5 to 12, ml | 33 | 32 | 32 | 32 |
| 14 to 20, gb | 49 | 48 | 49 | 49 |
| 14 to 20, ml | 50 | 50 | 51 | 51 |
| W1 gb | 20 | 20 | 20 | 20 |
| W2 gb | 21 | 22 | 20 | 20 |
| W3 gb | 46 | 48 | 46 | 46 |
| W4 gb | 28 | 28 | 26 | 26 |
| W1 ml | 53 | 53 | 53 | 53 |
| W2 ml | 55 | 57 | 55 | 55 |
| W3 ml | 87 | 87 | 87 | 87 |
| W4 ml | 32 | 32 | 31 | 31 |

All three make something worse. Phase 10 had recommended tallest-first from
the four fixture rows alone; the workload rows reversed that. Flattest-first is
the near miss (one carton worse on one set) and the candidate if the keep rule
is ever relaxed.

### 4.7 Uncapped repacking (phase 12)

Without `REPACK_MAX_ITEMS`, repacking spent about 10 extra seconds on W1 and
found no carton anywhere:

| Cap | 5 to 12 gb | 5 to 12 ml | 14 to 20 gb | 14 to 20 ml | W1 gb time |
|---:|---:|---:|---:|---:|---:|
| 20 | 31 | 31 | 44 | 47 | 3.57 s |
| 40 | 31 | 31 | 44 | 47 | 3.55 s |
| 60 | 31 | 31 | 44 | 47 | 3.61 s |
| none | 31 | 31 | 44 | 47 | 13.81 s |

40 was chosen over 20 to avoid tuning to the benchmark; the result is flat.

### 4.8 Exhaustive search over which items go in which carton (phase 12)

For orders of 12 items or fewer, a depth-first search tried every assignment of
items to cartons, using the same placement code, pruned by the best known
result and the lower bound, and capped by node count. It found nothing:

| Search size limit | off | 8 | 10 | 12 | 14 | 16 |
|---|---:|---:|---:|---:|---:|---:|
| 5 to 12 gb | 31 | 31 | 31 | 31 | 31 | 31 |
| 5 to 12 ml | 31 | 31 | 31 | 31 | 31 | 31 |
| 14 to 20 gb | 44 | 44 | 44 | 44 | 44 | 44 |
| 14 to 20 ml | 47 | 47 | 47 | 47 | 47 | 47 |

W1 to W4 were unchanged too. Raising the node cap from 30,000 to 2,000,000
changed no answer, so the search was finishing, not running out. Measured at
seed 1 with the pass cap then at 16; the code was removed, so this table cannot
be re-run.

This is the most useful negative result. The remaining misses cannot be fixed
by choosing different items for a carton. They need an item in a position that
first-fit never offers. That points to smarter free-space tracking (section 6).

### 4.9 BoxPacker heuristics (earlier comparison)

The client's current library is BoxPacker [1]. Its "largest first" and "side by
side" ideas were already in greedy2. "Pack vertically up the side" (column-first
points) was worse: small orders went from 45 to 55 cartons. "Balance weight
across boxes" never reduces carton count; it is a client policy question.

## 5. How CP-SAT was used

Google's CP-SAT solver [4], [5], part of OR-Tools [6], was used only to measure
how far greedy2 is from the best possible answer. It is never part of the
solver and never a runtime dependency (OR-Tools 9.15, installed only where the
optima are regenerated).

`bench/compare_cpsat.py` asks CP-SAT a series of yes/no questions: can these
items fit in exactly these cartons? Carton combinations are tried cheapest
first, and the first "yes" is optimal only if every cheaper combination came
back as a proven "no" rather than a timeout. Rotation, containment, overlap,
mass limits, conflict rules and the 70% support rule are all modelled, and
every CP-SAT layout is re-checked with greedy2's own geometry functions.

The results are frozen in `tests/data/optima.json`: 64 orders, 62 proven (two
20-item orders timed out at 30 s per check and are excluded from totals).
Reading the file needs no OR-Tools, so the gap table runs in seconds.

Two lessons came out of this:

- **A volume lower bound is a poor stand-in for the optimum on small orders.**
  An earlier estimate used it and concluded greedy2 was nearly optimal; the
  proven optima showed an 18.5% gap.
- **The support rule must be in the model.** The first CP-SAT model left it
  out, 8 of 9 of its layouts floated items in mid-air, and that accounted for
  the whole apparent gap.

## 6. Limitations and next steps

**Limitations.**

- All test orders are synthetic. The real benefit depends on the client's
  order sizes and carton mix, which are not yet known.
- The optimum fixtures use S and M cartons only, which makes packing harder
  than it may be in practice.
- The phase 12 settings were chosen on the same fixtures they are scored on.
  The seed spread and the workload improvements (W2, W4) suggest the gain is
  real, but real orders would confirm it.
- Timings are from one development machine. Re-run
  `bench/calibrate_passes.py` on the deployment machine.

**Next steps.**

- **Smarter free-space tracking (phase 8).** Replace corner points with empty
  maximal spaces [7], which can offer the positions that section 4.8 shows are
  missing. The biggest remaining lever, and the biggest rewrite.
- **Client data.** Order-size distribution, carrier pricing, repeat orders and
  the real carton mix decide whether phases 7, 13 and 14 are worth doing.
- **Request size cap.** `io.parse_request` expands each line's `quantity` with
  no upper limit. This is shared parser code, so it is a team decision.

## 7. Reproducing

These scripts are maintained separately from this repository. Where they are
available, from `fitsolver/` with the venv active:

```
python bench/compare_algorithms.py --algorithms v1,greedy2 --with-bin4d
python bench/compare_optimum.py
python bench/ablate_contact.py
python bench/ablate_phase12.py            # --window --cap --halves --repack-cap --seeds --budget --workloads
python bench/calibrate_passes.py
pip install -e ".[bench]"                  # only to regenerate the optima
python bench/compare_cpsat.py --write-optima --time-limit 30
```

Sections 4.2 to 4.6 and 4.8 describe code that was removed; their tables are
the recorded measurements from the phase that built them.

## References

[1] D. Wright, "BoxPacker," GitHub repository. [Online]. Available:
https://github.com/dvdoug/BoxPacker

[2] S. Martello, D. Pisinger, and D. Vigo, "The three-dimensional bin packing
problem," *Oper. Res.*, vol. 48, no. 2, pp. 256-267, 2000.

[3] T. G. Crainic, G. Perboli, and R. Tadei, "Extreme point-based heuristics
for three-dimensional bin packing," *INFORMS J. Comput.*, vol. 20, no. 3,
pp. 368-384, 2008, doi: 10.1287/ijoc.1070.0250.

[4] L. Perron and F. Didier, "CP-SAT," Google OR-Tools, version 9.15.
[Software]. Available: https://developers.google.com/optimization/cp/cp_solver/

[5] L. Perron, F. Didier, and S. Gay, "The CP-SAT-LP solver," in *Proc. 29th
Int. Conf. Principles and Practice of Constraint Programming (CP 2023)*,
LIPIcs, vol. 280, 2023, doi: 10.4230/LIPIcs.CP.2023.3.

[6] L. Perron and V. Furnon, "OR-Tools," Google, version 9.15. [Software].
Available: https://developers.google.com/optimization/

[7] F. Parreño, R. Alvarez-Valdes, J. M. Tamarit, and J. F. Oliveira, "A
maximal-space algorithm for the container loading problem," *INFORMS J.
Comput.*, vol. 20, no. 3, pp. 412-422, 2008.

[8] R. Martí, M. G. C. Resende, and C. C. Ribeiro, "Multi-start methods for
combinatorial optimization," *Eur. J. Oper. Res.*, vol. 226, no. 1, pp. 1-8,
2013.

[9] M. Matsumoto and T. Nishimura, "Mersenne twister: A 623-dimensionally
equidistributed uniform pseudo-random number generator," *ACM Trans. Model.
Comput. Simul.*, vol. 8, no. 1, pp. 3-30, 1998.
