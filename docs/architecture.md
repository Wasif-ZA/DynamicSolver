# Architecture

How the solver is put together, and why. Read
[`client-requirements.md`](client-requirements.md) first, then [`contract.md`](contract.md).

The solver is the Python package `fitsolver`
([ADR-0005](decisions/0005-python-implementation.md)). The algorithm that runs is **greedy2**
([ADR-0007](decisions/0007-greedy2-is-the-solver.md)).

## The pipeline

```
request -> io.parse_request -> engine.solve -> greedy2.pack -> io.emit_document -> response
           validate, expand                  choose cartons,   self-contained
           quantities                        place items       solution document
```

| Step | File | Does what |
|---|---|---|
| Parse | `io.py` | Reads the JSON request into plain data types. Bad items become per-item rejects; a request that is unusable as a whole raises `RequestError` (a 422). `quantity: 3` becomes three items. |
| Solve | `engine.py` | One function, `solve(payload, optimise=False)`. Every caller uses it: the API, the Portal and the tests. |
| Pack | `greedy2/pack.py` | Decides which cartons to use and where each item goes. |
| Further Optimise | `greedy2/optimise.py` | Only when `optimise=True`. See [Further Optimise](#further-optimise). |
| Emit | `io.py` | Builds the solution document. Labels, sizes and masses are repeated in every placement so the visualiser needs no second request. |

**JSON stops at `io.py`.** Nothing past it knows JSON exists, so the geometry is tested without
parsing anything, and a contract change touches one file.

**Portal requests** come in through `portal.py`, which translates the Portal's field names
(PascalCase, kilograms) into the contract (snake_case, grams). In the monorepo, the Portal backend
does the same translation in its own `solver_adapter.py` and calls `engine.solve` directly.

## Package layout

```
fitsolver/src/fitsolver/
  domain.py          Item, Carton, Placement, PackedCarton, Reject, Solution. Plain data.
  io.py              JSON in, JSON out. Validation and reject codes live here.
  engine.py          solve(payload, optimise=False). The one entry point.
  api.py             FastAPI: /v1/health, /v1/solve, /v1/solve/portal
  portal.py          Portal field names -> contract field names
  greedy2/
    pack.py          the solver
    geometry.py      integer geometry: fits, overlaps, support, corner points
    optimise.py      Further Optimise (CP-SAT, opt-in)
    README.md        how greedy2 works, step by step
    DESIGN_NOTES.md  what was measured, kept and rejected, with numbers
  pack.py, geometry.py   v1, frozen as a baseline. Not used by the engine.
```

## How greedy2 packs an order

The short version. [`greedy2/README.md`](../fitsolver/src/fitsolver/greedy2/README.md) has the full
walkthrough and `DESIGN_NOTES.md` has the measurements.

1. **Reject what can never fit.** An item no carton type can hold, by size or by mass, is rejected
   up front with the reason.
2. **Canonical order.** Items are sorted by content, so the same goods in a different order give
   the same layout.
3. **Conflict groups.** Items that may not share a carton (different dangerous-goods classes, or an
   explicit `incompatible_with`) go into separate groups that pack independently.
4. **Lower bound.** The fewest cartons any answer could use. A pass that reaches it stops the solve.
5. **Several orderings, best kept.** Four named orderings, then seeded random restarts. The number
   of passes comes from the time budget and a fixed cost table, never from a clock.
6. **Fill one carton at a time.** Each round, every carton type with uses left is test-filled and
   the one packing the most volume wins.
7. **Place at the lowest live corner point** where the item fits inside the walls, overlaps
   nothing, and has at least 70% of its base supported.
8. **Try to remove a carton** by emptying the emptiest one into the others, or repacking the last
   two or three into one fewer. Only taken if it removes a carton.

**The objective**, in order: fewest unplaced items, then fewest cartons, then least total carton
volume. Fill rate is reported but never optimised, because it rewards many small tight cartons.

## Constraints the solver enforces

| Constraint | Where | Notes |
|---|---|---|
| Fits inside the carton, no overlaps | `geometry.py` | Exact integer checks. Touching faces are fine. |
| 70% of each item's base supported | `geometry.supported` | Nothing floats. |
| Rotation rules | `geometry.orientations` | `any`, `upright` (height stays vertical) or `fixed`. |
| Mass limit | `pack.place` | `max_contents_mass` limits the contents. Tare is not counted against it. |
| Dangerous goods and incompatibility | `pack.split_compatible` | Different DG classes, or items naming each other in `incompatible_with`, never share a carton. |
| Box stock (`maximum_boxes`) | `pack.pack_one` | A carton type is used at most this many times per order ([ADR-0008](decisions/0008-enforce-maximum-boxes.md)). |

## Further Optimise

An opt-in second step behind the Portal's "Further Optimise" button
([ADR-0009](decisions/0009-further-optimise.md)). Normal solving never runs it.

1. greedy2 answers first. Its answer is always the fallback.
2. Only orders of **30 items or fewer**, with no rejects and one conflict group, go further.
3. It tries to fit the **whole order in one smaller carton**, starting with the next size down from
   greedy2's carton, and **stops at the first one that fits**.
4. Google's CP-SAT solver searches for that layout under greedy2's own rules (rotations, inside
   the carton, no overlaps, 70% support, mass limit, `maximum_boxes`). The layout is re-checked
   with greedy2's geometry before it is used.
5. **Hard limit of 30 seconds.** If nothing is found in time, greedy2's answer is returned.

The response marks an improved answer with `solver.tier: 2`. OR-Tools is an optional install
(`pip install -e ".[optimise]"`); without it the button returns greedy2's answer.

## Rules that shaped this

**Integer millimetres and grams.** No floats in geometry, so overlap checks are exact
([ADR-0002](decisions/0002-units-and-coordinates.md)).

**z is up** ([ADR-0006](decisions/0006-z-up-axes.md)). The origin is the inside minimum corner of
the carton, and a position is the item's corner nearest the origin, never its centre.

**Sizes are as placed.** The response carries dimensions after rotation, so the visualiser never
does rotation maths.

**Deterministic.** The same request gives the same layout on any machine: the only randomness is
seeded from the request, and no clock is read during a solve. Further Optimise is the one
exception, because it runs only when asked for.

## Performance

The bar is 1 to 2 seconds for **one order** (R2). It is a latency target, not a throughput one.

3D bin packing is NP-hard, so greedy2 is a heuristic: it finds a good answer fast, and never
claims optimality. Measured against proven optima on 62 small orders, it is 8.7% above optimum
with no mass limits and 2.6% above with realistic mass limits, and never more than one carton over.

Small orders finish in milliseconds and spend the rest of the budget on extra orderings. One pass
over about 300 items costs roughly the whole budget, so very large orders run a single pass and
can overrun. `solver.elapsed_ms` is in every response.

## Testing

The [contract invariants](contract.md#invariants) are the test list.

| Tests | Check |
|---|---|
| `test_properties.py` (Hypothesis) | In bounds, no overlaps, support, mass, conflict groups, conservation, determinism, on random orders |
| `test_greedy2_layouts.py` | Layouts match a recorded baseline placement by placement, so any behaviour change is visible |
| `test_greedy2_max_boxes.py` | `maximum_boxes` is never exceeded, including across groups and in the repack move |
| `test_greedy2_optimise.py` | Further Optimise finds the one smaller carton, respects the limits, falls back cleanly. Skipped when OR-Tools is not installed. |
| `test_contract.py`, `test_portal.py` | The request and response shapes, and the Portal translation |

CI runs ruff and the full suite on Python 3.11 to 3.14, plus a contract job that validates every
fixture against the published schema.

**Whoever writes an implementation should not also write its tests.** The author shares the code's
blind spots, and their tests confirm what it does rather than what it should do. This applies to
AI-generated code too.

## Extending it

The client asked for this to be **extensible**, naming **modes** (fluid, own packaging) as the
example. Every packer shares one signature, `pack(items, cartons, time_budget_ms, seed) ->
Solution`, and `Solution` already carries a `mode` field (`rigid` today). A new mode is a new
module with that signature, selected in `engine.solve`. Nothing in `io.py` or the contract has to
change.
