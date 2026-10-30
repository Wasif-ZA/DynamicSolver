# The packing contract

Our interface to the rest of the project. The Portal and visualiser teams build against **this
document** and the schemas in [`contract/`](../contract/) (`request.schema.json`,
`solution.schema.json`). We build the solver only
([ADR-0003](decisions/0003-solver-only-scope.md)), so a change here changes someone else's sprint.

## For the visualiser team, in short

1. `cartons[]` has one entry per physical box used, with its `inner_dims`, so you know how big to
   draw the box.
2. `cartons[].placements[]` is every item in that box: `position` is the corner it sits at and
   `dims` is its size **as placed**, rotation already applied. Draw a cuboid at `position` of size
   `dims`. That is the whole rendering job.
3. `placements[].sequence` is the packing order **within that carton**, starting at 0. Sort by it
   and reveal one item at a time for the step-by-step view.

You never do rotation maths. The [fixtures](#fixtures) are real solver output: point your renderer
at one and build against it.

## Units and axes

**Lengths are integer millimetres, masses are integer grams**
([ADR-0002](decisions/0002-units-and-coordinates.md)). **z is up**
([ADR-0006](decisions/0006-z-up-axes.md)).

```
        z (height, up)
        |
        |
        +--------- x (width)
       /
      y (depth)
```

- The origin `[0, 0, 0]` is the inside bottom corner of the carton (`"origin": "min_corner"`).
- A `position` is the item's corner nearest the origin, never its centre. An item at `[0, 0, 0]`
  with `dims` `[150, 100, 50]` fills x 0 to 150, y 0 to 100 and z 0 to 50.
- Every size is `[x, y, z]`, which is `[width, depth, height]`.
- Carton sizes are **inside** dimensions: the usable space.

## Request

```json
{
  "order_id": "ord-10432",
  "time_budget_ms": 1200,
  "items":   [ ... ],
  "cartons": [ ... ]
}
```

`order_id`, `items` (at least one) and `cartons` (at least one) are required. `time_budget_ms`
defaults to 1200.

### Item

`quantity: 3` means three identical items, and each is placed separately.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `item_ref` | string | required | The item's code, echoed in every placement |
| `label` | string | `item_ref` | Display name |
| `dims` | `[w, d, h]` mm | required | Three positive integers |
| `mass` | g | required | Per item, 0 or more |
| `quantity` | int | 1 | How many identical items |
| `allowed_rotations` | `any` / `upright` / `fixed` | `any` | `upright` keeps the height vertical; `fixed` allows no rotation |
| `dg_class` | string or null | null | Items with **different** classes never share a carton. Null conflicts with nothing |
| `incompatible_with` | list of `item_ref` | `[]` | Items that may never share a carton with this one |
| `tags` | list of strings | `[]` | Passed through to the output untouched |

### Carton

A carton is a **type**. The solver may use it several times, and each use is its own entry in
the response.

| Field | Type | Default | Meaning |
|---|---|---|---|
| `sku` | string | required | The carton type's code |
| `inner_dims` | `[w, d, h]` mm | required | Usable space inside |
| `tare_mass` | g | 0 | Weight of the empty carton. Counted in `total_mass` |
| `max_contents_mass` | g or null | null | Limit on the **contents**. Tare is not counted against it. Null means no limit |
| `maximum_boxes` | int or null | null | Most times this carton type may be used in one order (box stock). Null means unlimited; 0 means never use it ([ADR-0008](decisions/0008-enforce-maximum-boxes.md)) |

## Response

```json
{
  "schema_version": "1.0.0",
  "solution_id": "sol_...",
  "order_id": "ord-10432",
  "solver": { "version": "0.1.0", "seed": 1103..., "mode": "rigid",
              "time_budget_ms": 1200, "elapsed_ms": 1, "tier": 1 },
  "coordinate_system": { "up": "z", "handedness": "right", "origin": "min_corner" },
  "units": { "length": "mm", "mass": "g" },
  "metrics": { "carton_count": 1, "fill_rate": 0.3, "total_mass": 1400 },
  "cartons": [ ... ],
  "rejects": [ ... ]
}
```

| Field | Meaning |
|---|---|
| `solver.seed` | Derived from the request content. Same request, same seed, same layout |
| `solver.elapsed_ms` | Time inside the solver. The client's bar is 1000 to 2000 ms for one order |
| `solver.tier` | `1` greedy2. `2` an improved answer from Further Optimise ([ADR-0009](decisions/0009-further-optimise.md)). `0` is reserved for a future cache |
| `metrics.fill_rate` | Item volume over carton volume, 0 to 1. Reported, never optimised |
| `metrics.total_mass` | Every item plus every carton's tare, in grams |

### Carton

| Field | Meaning |
|---|---|
| `carton_id` | `c1`, `c2`, ... in the order the cartons were filled |
| `sku`, `inner_dims`, `tare_mass` | Copied from the carton type, so you never cross-reference the request |
| `contents_mass` | Items only, in grams |
| `fill_rate` | This carton's item volume over its own volume |
| `centre_of_mass` | `[x, y, z]` in mm, carton-local |
| `placements` | Everything in this carton |

### Placement

| Field | Meaning |
|---|---|
| `placement_id` | `p<carton number>_<sequence>`, for example `p1_0` |
| `item_ref`, `label`, `mass`, `tags` | Copied from the item |
| `position` | `[x, y, z]`, the corner nearest the origin |
| `dims` | `[x, y, z]` **as placed**, rotation already applied |
| `orientation` | 0 to 5: which of the item's `[w, d, h]` went to each axis. Informational; `dims` already reflects it |
| `sequence` | Physical packing order within the carton, from 0. Anything an item rests on has a lower number |

| `orientation` | Placed `dims` |
|---|---|
| 0 | `[w, d, h]`, as given |
| 1 | `[w, h, d]` |
| 2 | `[d, w, h]` |
| 3 | `[d, h, w]` |
| 4 | `[h, w, d]` |
| 5 | `[h, d, w]` |

### Rejects

One entry per item that could not be packed. A rejected item never stops the rest of the order
packing: the client said to reject what cannot be packed (R4), and per-item reasons let the
Portal tell the packer which item failed and why.

| `reason_code` | Meaning |
|---|---|
| `NO_FITTING_CARTON` | Too big for every carton type in every allowed orientation, or fits but is too heavy for every carton. The message says which |
| `UNPLACEABLE` | Fits a carton type, but every type it fits has reached its `maximum_boxes` limit |
| `INVALID_DIMENSIONS` | `dims` is not three positive integers |
| `MISSING_MASS` | `mass` is missing or negative |
| `UNKNOWN_DG_CLASS` | Reserved in the schema. Not produced today |

A request that is unusable as a whole (no cartons, invalid carton dimensions, an invalid
`maximum_boxes`) is refused with HTTP 422 instead.

## The API

| Route | Takes |
|---|---|
| `GET /v1/health` | Solver and schema versions |
| `POST /v1/solve` | A request in this contract's shape |
| `POST /v1/solve/portal` | A request in the Portal's own field names, translated by `portal.py` |

Both solve routes accept **`?optimise=true`**, the "Further Optimise" button. It is slower (up to
30 seconds) and may return a smaller carton with `solver.tier: 2`. See
[ADR-0009](decisions/0009-further-optimise.md).

The Portal backend in the monorepo calls `engine.solve` directly with a request it builds itself
(`solver_adapter.py`), so it does not use the `/v1/solve/portal` route.

## Worked examples

### 1. One carton, with a rotation

Two paperbacks and a boxed mug. This is real solver output.

**Request**

```json
{
  "order_id": "ord-10432",
  "items": [
    { "item_ref": "SKU-BOOK-01", "label": "Paperback", "dims": [150, 100, 50], "mass": 400, "quantity": 2 },
    { "item_ref": "SKU-MUG-01", "label": "Ceramic mug, boxed", "dims": [100, 120, 100], "mass": 350 }
  ],
  "cartons": [
    { "sku": "SMALL", "inner_dims": [300, 150, 200], "tare_mass": 250, "max_contents_mass": 15000 }
  ]
}
```

**Response** (the `solver`, `coordinate_system` and `units` blocks are as shown above)

```json
{
  "metrics": { "carton_count": 1, "fill_rate": 0.3, "total_mass": 1400 },
  "cartons": [
    {
      "carton_id": "c1", "sku": "SMALL", "inner_dims": [300, 150, 200],
      "tare_mass": 250, "contents_mass": 1150, "fill_rate": 0.3, "centre_of_mass": [171, 61, 41],
      "placements": [
        { "placement_id": "p1_0", "item_ref": "SKU-MUG-01", "label": "Ceramic mug, boxed",
          "position": [0, 0, 0], "dims": [100, 120, 100], "orientation": 0, "mass": 350, "sequence": 0, "tags": [] },
        { "placement_id": "p1_1", "item_ref": "SKU-BOOK-01", "label": "Paperback",
          "position": [100, 0, 0], "dims": [150, 100, 50], "orientation": 0, "mass": 400, "sequence": 1, "tags": [] },
        { "placement_id": "p1_2", "item_ref": "SKU-BOOK-01", "label": "Paperback",
          "position": [250, 0, 0], "dims": [50, 150, 100], "orientation": 4, "mass": 400, "sequence": 2, "tags": [] }
      ]
    }
  ],
  "rejects": []
}
```

Worth checking by hand. The mug and the first book sit side by side on the floor. The second book
would not fit flat in the 50 mm left on x, so it is turned on its side: `orientation` 4 maps its
`[150, 100, 50]` to `[50, 150, 100]`. Nothing overlaps, nothing pokes out, and `total_mass` is
400 + 400 + 350 + 250 tare = 1400 g.

### 2. Box stock runs out

Three totes, each needing its own SMALL carton, but only two SMALL cartons in stock
(`"maximum_boxes": 2`). The result is two cartons and one reject:

```json
"rejects": [
  { "item_ref": "SKU-TOTE", "reason_code": "UNPLACEABLE",
    "message": "Fits, but every carton type it fits has reached its maximum_boxes limit" }
]
```

### Fixtures

`contract/fixtures/` holds complete solution documents for the common cases, validated in CI:
a single item, a full carton, several cartons, a dangerous-goods split, incompatible items, partial
and total rejects, rotation-locked items, a large order, a mass-limited order and a 250-item bulk
order. `contract/fixtures_request_example.json` is an example request.

## Invariants

Any solution must satisfy all of these. They are the test list.

1. **In bounds.** For every placement, `position + dims` is within `inner_dims` on every axis.
2. **No overlaps.** No two placements in one carton share volume. Touching faces are fine.
3. **Supported.** Every item is on the floor or has at least 70% of its base resting on items
   below it.
4. **Conservation.** Every item in the request, after `quantity` is expanded, appears exactly once:
   in a placement or in `rejects`.
5. **Mass.** Every carton's `contents_mass` is within its `max_contents_mass`.
6. **Conflicts.** No carton holds two items with different `dg_class` values, or two items that
   name each other in `incompatible_with`.
7. **Box stock.** No carton type appears more times than its `maximum_boxes`.
8. **Sequence.** Within each carton, `sequence` runs 0 to n-1 with no gaps.
9. **Deterministic.** The same request gives the same layout, except with `?optimise=true`.

## Changing this document

1. **Additive changes are cheap.** A new optional field breaks nobody.
2. **Breaking changes need a heads-up.** Renaming or removing a field, or changing a meaning, goes
   to the Portal and visualiser teams **before** it is merged.
3. **Update the schemas and fixtures in the same commit.** An example that contradicts the spec is
   worse than none, because someone is building against it.
4. **Record the reasoning** in [`decisions/`](decisions/) when it settles a real question.
