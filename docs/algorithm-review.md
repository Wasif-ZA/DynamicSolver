# GitHub Issues - bin4d (BFS Greedy)

Three confirmed, small-scope bugs. Each section below is ready to paste into a GitHub issue. All reproductions were run against the current `bin_packer.py`.

---

## Issue 1 - `BoxGroup` is parsed but never enforced (items from different groups share a bin)

**Labels:** `bug`, `good first issue`

### Description
`Item` has a `box_group` field, `load_items()` reads `BoxGroup` from the input JSON (line 119), and the shipped `items.json` even ships with `GROUP-A` and `GROUP-B` items but `pack_all()` never looks at the field. Items from different groups are silently packed into the same bin.

This is worse than the feature simply not existing: the input schema *advertises* the constraint and accepts it without warning, so a caller reasonably believes it's being honoured.

### Steps to reproduce
Run the packer on the bundled sample data:

```
python bin_packer.py boxes.json items.json
```

### Actual behaviour
`ITM-001` (`GROUP-A`) and `ITM-003` (`GROUP-B`) are both placed in bin `MED-1`.

### Expected behaviour
One of:
1. Items with different `BoxGroup` values are never mixed in the same bin (grouped packing), or
2. The field is rejected/warned about as unsupported.

### Suggested fix (option 1, small)
In `pack_all()`, partition `remaining_items` by `box_group` (treating `None` as its own bucket, or as "compatible with anything", decide and document) and run the existing packing loop once per group. This reuses all existing code; only the top-level loop changes. Add a sample-data regression test asserting no bin contains two distinct non-None groups.

---

## Issue 2 - Items can be placed floating in mid-air (no support check between layers)

**Labels:** `bug`, `geometry`

### Description
`pack_box_instance()` advances the layer cursor by the *tallest* item's height (`z += layer_h`, line 250), but `pack_layer_shelves()` happily fills a layer with items shorter than `layer_h`. The next layer is then placed at the uniform height `z`, so anything positioned above a shorter item in the previous layer hangs over an air gap. There is no support/gravity check anywhere in the placement path.

For a physical packing solver this produces instructions a human packer cannot follow, the item would fall.

### Steps to reproduce
```python
import bin_packer as bp
boxes = [bp.BoxType("BOX", 400, 400, 400, None, 0, True, None)]
items = [
    bp.Item("BIG",  "BIG",  400, 200, 100, 1),
    bp.Item("TOP1", "TOP1", 400, 200, 50,  1),
    bp.Item("TOP2", "TOP2", 400, 150, 50,  1),
    bp.Item("LOW",  "LOW",  400, 150, 30,  1),
]
print(bp.pack_all(boxes, items))
```

### Actual behaviour
`LOW` is placed at `z=100`, spanning `y=150–300`. Beneath it, `TOP1` (which occupies `y=200–400` in layer 1) only reaches `z=50`. Measured support: **33.3% of `LOW`'s footprint** The other two-thirds sits over a 50 mm air gap.

```
BIG   z=0     support=100.0%
TOP1  z=0     support=100.0%
TOP2  z=100   support=100.0%
LOW   z=100   support= 33.3%   <-- floating
```

### Expected behaviour
Every item's underside should rest on the floor or on the top surface of items beneath it (ideally with a configurable minimum support percentage, e.g. ≥ 60% of footprint area).

### Suggested fix (minimal)
A cheap "gravity settle" pass after placement inside `pack_layer_shelves`: for each placed item, compute the maximum top-surface height of already-placed items overlapping its (x, y) footprint and lower its `z` to that height. This eliminates the air gap without restructuring the layer algorithm. A stricter fix (reject placements below a minimum support fraction) can follow later. Add a property test: for every placed item with `z > 0`, supported footprint fraction ≥ threshold.

---

## Issue 3 - CLI combined-file mode: crashes on top-level JSON arrays and mis-reports empty `"boxes"` key

**Labels:** `bug`, `cli`, `good first issue`

### Description
Two related problems in `main()` (lines 342–350):

**(a)** Single-file mode assumes the JSON root is an object. Passing a file whose root is an array (e.g. accidentally passing `items.json` alone) raises an unhandled traceback instead of the usage message:

```
$ python bin_packer.py items.json
...
AttributeError: 'list' object has no attribute 'get'
```

**(b)** The key lookup uses an `or` chain:

```python
boxes_raw = data.get("boxes") or data.get("Boxes") or data.get("box") or data.get("Box")
```

`or` treats an empty list the same as a missing key. A combined file containing `{"boxes": [], "items": [...]}` - where the key **is** present, exits with the misleading error *"Combined JSON file must contain both a 'boxes' and an 'items' key"* instead of the accurate `"No active box types were provided."` path already implemented in `pack_all()`.

### Expected behaviour
- (a) A friendly error explaining the file must be a JSON object with `boxes`/`items` keys (exit code 2, no traceback).
- (b) A present-but-empty `boxes` key should flow through to `pack_all()` and produce its existing "No active box types" error.

### Suggested fix
```python
if not isinstance(data, dict):
    print("Combined JSON file must be an object with 'boxes' and 'items' keys.", file=sys.stderr)
    return 2

def _first_key(d, *keys):
    for k in keys:
        if k in d:          # presence check, not truthiness
            return d[k]
    return None

boxes_raw = _first_key(data, "boxes", "Boxes", "box", "Box")
items_raw = _first_key(data, "items", "Items", "item", "Item")
```
