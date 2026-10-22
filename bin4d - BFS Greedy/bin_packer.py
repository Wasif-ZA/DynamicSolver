"""
bin_packer.py

A from-scratch Python re-implementation of the packing STRATEGY popularised by
the PHP library dvdoug/BoxPacker (https://github.com/dvdoug/BoxPacker):

  1. Pack the largest (by volume) items first.
  2. Build each box up in horizontal "layers" stacked along the depth axis.
  3. Within a layer, place items in "rows": fill along the width, and when a
     row runs out of width, start a new row further along the length.
  4. Every item may be freely rotated (all 6 orientations are tried) and the
     orientation that best uses the available space is chosen.
  5. Respect a per-box weight limit as well as the 3 spatial dimensions
     (hence "4D" bin packing).
  6. When more than one box type is available, try every active box type for
     each new bin and keep whichever packs the most items (ties broken in
     favour of the smaller box) -- this mirrors BoxPacker's own "find best
     box of iteration" loop.

This is a heuristic, not an exact solver -- like BoxPacker itself, it does not
attempt to try every permutation (that's the NP-hard part), it simulates a
sensible, fast, human-style packing approach instead.

No code was copied from BoxPacker (which is PHP, GPL-incompatible concerns
aside) -- only the documented, high-level algorithm was translated into an
original Python implementation.
"""

from __future__ import annotations

import itertools
import json
import math
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional, Tuple


# --------------------------------------------------------------------------- #
# Data model
# --------------------------------------------------------------------------- #

@dataclass
class BoxType:
    reference: str
    width: float
    length: float
    depth: float
    max_weight: Optional[float]   # None => unlimited
    box_weight: float             # tare weight of the empty box itself
    active: bool
    maximum_boxes: Optional[int]  # None => unlimited instances of this box

    @property
    def volume(self) -> float:
        return self.width * self.length * self.depth


@dataclass
class Item:
    item_code: str
    item_reference: str
    width: float
    length: float
    depth: float
    weight: float
    box_group: Optional[str] = None

    @property
    def volume(self) -> float:
        return self.width * self.length * self.depth


@dataclass
class PlacedItem:
    item: Item
    x: float
    y: float
    z: float
    w: float  # dimensions AS PACKED (post-rotation)
    l: float
    d: float


# --------------------------------------------------------------------------- #
# Loading
# --------------------------------------------------------------------------- #

def load_boxes(raw: list) -> List[BoxType]:
    boxes = []
    for b in raw:
        boxes.append(
            BoxType(
                reference=b["Reference"],
                width=float(b["Width"]),
                length=float(b["Length"]),
                depth=float(b["Depth"]),
                max_weight=float(b["MaxWeight"]) if b.get("MaxWeight") is not None else None,
                box_weight=float(b.get("BoxWeight") or 0),
                active=bool(b.get("Active", True)),
                maximum_boxes=int(b["MaximumBoxes"]) if b.get("MaximumBoxes") is not None else None,
            )
        )
    return boxes


def load_items(raw: list) -> List[Item]:
    items = []
    for i in raw:
        items.append(
            Item(
                item_code=i["ItemCode"],
                item_reference=i.get("ItemReference", i["ItemCode"]),
                width=float(i["Width"]),
                length=float(i["Length"]),
                depth=float(i["Depth"]),
                weight=float(i.get("Weight") or 0),
                box_group=i.get("BoxGroup"),
            )
        )
    return items


# --------------------------------------------------------------------------- #
# Orientation helpers
# --------------------------------------------------------------------------- #

def orientations(item: Item):
    """All unique (w, l, d) rotations of an item's 3 dimensions."""
    dims = (item.width, item.length, item.depth)
    seen = set()
    for perm in itertools.permutations(dims):
        if perm not in seen:
            seen.add(perm)
            yield perm


def best_start_orientation(item: Item, avail_w: float, avail_l: float, avail_d: float):
    """Orientation used to START a new layer: prefer the shallowest (smallest
    depth) orientation that still fits, tie-broken by largest footprint --
    this tends to produce broad, shallow layers, echoing BoxPacker's
    "heavier/larger items at the bottom" behaviour."""
    best = None
    for w, l, d in orientations(item):
        if w <= avail_w and l <= avail_l and d <= avail_d:
            score = (d, -(w * l))
            if best is None or score < best[0]:
                best = (score, (w, l, d))
    return best[1] if best else None


def best_row_orientation(item: Item, avail_w: float, avail_l: float, max_d: float):
    """Orientation used to place an item WITHIN an existing layer/row: any
    orientation whose depth fits under the layer height, maximising the
    footprint used (best fill of the row)."""
    best = None
    for w, l, d in orientations(item):
        if w <= avail_w and l <= avail_l and d <= max_d:
            score = -(w * l)
            if best is None or score < best[0]:
                best = (score, (w, l, d))
    return best[1] if best else None


# --------------------------------------------------------------------------- #
# Layer / row packing (the geometric core)
# --------------------------------------------------------------------------- #

def pack_layer_shelves(
    box_width: float,
    box_length: float,
    layer_h: float,
    z: float,
    remaining: List[Item],
    weight_cap: float,
    weight_used: float,
) -> Tuple[List[PlacedItem], List[Item], float]:
    """Fill one horizontal layer (fixed height `layer_h`, positioned at
    depth `z`) using a row/shelf strategy: fill across width, then start a
    new row further along length. Items that don't fit are skipped over
    (not discarded) so later, smaller items still get a chance."""
    placed: List[PlacedItem] = []
    still_remaining = list(remaining)
    y = 0.0

    while y < box_length - 1e-9 and still_remaining:
        avail_l = box_length - y
        x = 0.0
        row_depth_used = 0.0
        row_had_item = False
        i = 0
        while i < len(still_remaining):
            it = still_remaining[i]
            if it.weight > weight_cap - weight_used + 1e-9:
                i += 1
                continue
            avail_w = box_width - x
            orient = best_row_orientation(it, avail_w, avail_l, layer_h)
            if orient is None:
                i += 1
                continue
            w, l, d = orient
            placed.append(PlacedItem(it, x, y, z, w, l, d))
            weight_used += it.weight
            x += w
            row_depth_used = max(row_depth_used, l)
            row_had_item = True
            still_remaining.pop(i)  # list shrank; keep i where it is

        if not row_had_item:
            break
        y += row_depth_used

    return placed, still_remaining, weight_used


def pack_box_instance(box: BoxType, items_sorted: List[Item]) -> Tuple[List[PlacedItem], List[Item]]:
    """Greedily pack as many items as possible (already sorted largest-first)
    into ONE fresh instance of `box`. Returns (placed_items, leftover_items)."""
    placed: List[PlacedItem] = []
    remaining = list(items_sorted)
    weight_cap = (box.max_weight - box.box_weight) if box.max_weight is not None else math.inf
    weight_used = 0.0
    z = 0.0

    while remaining and z < box.depth - 1e-9:
        avail_d = box.depth - z

        # Find the first (largest, since list is sorted) item that can start
        # a new layer here -- skipping over ones that can't, same as
        # BoxPacker's documented "skip and try the next item" behaviour.
        start_idx = None
        for idx, it in enumerate(remaining):
            if it.weight > weight_cap - weight_used + 1e-9:
                continue
            if best_start_orientation(it, box.width, box.length, avail_d):
                start_idx = idx
                break

        if start_idx is None:
            break  # nothing left can start another layer -> box is done

        layer_h = best_start_orientation(remaining[start_idx], box.width, box.length, avail_d)[2]

        layer_items, remaining, weight_used = pack_layer_shelves(
            box.width, box.length, layer_h, z, remaining, weight_cap, weight_used
        )
        placed.extend(layer_items)
        z += layer_h

    return placed, remaining


# --------------------------------------------------------------------------- #
# Top-level multi-box packer
# --------------------------------------------------------------------------- #

def pack_all(boxes: List[BoxType], items: List[Item]) -> dict:
    active_boxes = sorted((b for b in boxes if b.active), key=lambda b: b.volume)

    if not active_boxes:
        return {
            "success": False,
            "bins_used": 0,
            "bins": [],
            "unpacked_items": [{"item_code": i.item_code, "item_reference": i.item_reference} for i in items],
            "error": "No active box types were provided.",
        }

    # Largest-first (by volume, weight as tiebreak) -- the core BoxPacker heuristic.
    remaining_items = sorted(items, key=lambda i: (i.volume, i.weight), reverse=True)

    instance_counts = {b.reference: 0 for b in active_boxes}
    bins_result = []

    while remaining_items:
        best = None  # (score_tuple, placed, leftover, box)

        for box in active_boxes:
            if box.maximum_boxes is not None and instance_counts[box.reference] >= box.maximum_boxes:
                continue

            placed, leftover = pack_box_instance(box, remaining_items)
            if not placed:
                continue

            packed_volume = sum(p.w * p.l * p.d for p in placed)
            score = (len(placed), packed_volume)  # more items first, then more volume
            if best is None or score > best[0]:
                best = (score, placed, leftover, box)

        if best is None:
            break  # remaining items can't fit in any available box/instance

        _, placed, leftover, box = best
        instance_counts[box.reference] += 1
        bin_id = f"{box.reference}-{instance_counts[box.reference]}"

        bins_result.append(
            {
                "bin_id": bin_id,
                "box_reference": box.reference,
                "box_dimensions": {"width": box.width, "length": box.length, "depth": box.depth},
                "items_packed": len(placed),
                "weight_used": round(sum(p.item.weight for p in placed) + box.box_weight, 6),
                "max_weight": box.max_weight,
                "items": [
                    {
                        "item_code": p.item.item_code,
                        "item_reference": p.item.item_reference,
                        "position": {"x": p.x, "y": p.y, "z": p.z},
                        "packed_dimensions": {"width": p.w, "length": p.l, "depth": p.d},
                    }
                    for p in placed
                ],
            }
        )
        remaining_items = leftover

    success = len(remaining_items) == 0
    return {
        "success": success,
        "bins_used": len(bins_result),
        "bins": bins_result,
        "unpacked_items": [
            {"item_code": i.item_code, "item_reference": i.item_reference} for i in remaining_items
        ],
    }


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #

def _load_json(path: str):
    return json.loads(Path(path).read_text())


def _first_present(data: dict, keys: List[str]):
    return next((data[k] for k in keys if k in data), None)


def main(argv: List[str]) -> int:
    if len(argv) == 2:
        data = _load_json(argv[1])
        if not isinstance(data, dict):
            print(
                "Combined JSON file must be an object with 'boxes' and 'items' keys, "
                f"not a {type(data).__name__}.",
                file=sys.stderr,
            )
            return 2
        boxes_raw = _first_present(data, ["boxes", "Boxes", "box", "Box"])
        items_raw = _first_present(data, ["items", "Items", "item", "Item"])
        if boxes_raw is None or items_raw is None:
            print(
                "Combined JSON file must contain both a 'boxes' and an 'items' key.",
                file=sys.stderr,
            )
            return 2
    elif len(argv) == 3:
        boxes_raw = _load_json(argv[1])
        items_raw = _load_json(argv[2])
    else:
        print(
            "Usage:\n"
            "  python bin_packer.py <combined.json>\n"
            "  python bin_packer.py <boxes.json> <items.json>",
            file=sys.stderr,
        )
        return 2

    boxes = load_boxes(boxes_raw)
    items = load_items(items_raw)
    result = pack_all(boxes, items)

    print(json.dumps(result, indent=2))
    return 0 if result["success"] else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
