"""The golden-layout fixture: exactly what greedy2 currently lays out.

Some phases are speed work and must leave every layout untouched. "Untouched"
is not something a carton count can check: two runs can agree on how many
cartons they used and disagree about where every item went. So the layouts are
recorded and compared placement by placement.

tests/data/greedy2_layouts.json holds them. This module owns the workloads,
the encoding and the regenerate entry point, so the test file only compares.

Re-recorded when behaviour changes ON PURPOSE, and only then. The history so
far:
    phase 2  first recorded, at MAX_CANDIDATES 128
    phase 3  reproduced exactly; pre-checks and the memo are speed only
    phase 4  re-recorded; multi-start and canonical input ordering change
             layouts by design
    phase 5  re-recorded; the size-dependent ordering and CHUNK 240 change
             layouts by design. Two fixtures improved by a carton, none got
             worse

To re-record, deliberately, after an approved change of behaviour:

    python tests/golden_layouts.py --write

Never run that to make a red test go green. A diff here means either a real
regression or an intended change, and the two are told apart by reading the
diff, not by overwriting it.
"""
from __future__ import annotations

import argparse
import json
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fitsolver.domain import Carton, Item  # noqa: E402

DATA = Path(__file__).resolve().parent / "data" / "greedy2_layouts.json"

# The four bench cartons, with and without mass limits, so both regimes are
# covered: with limits, mass rather than geometry is what runs out.
_SPEC = [("S", (220, 160, 120), 120, 5000), ("M", (320, 240, 180), 210, 12000),
         ("L", (450, 350, 300), 380, 20000), ("XL", (600, 400, 400), 520, 30000)]


def cartons(mass_limited: bool) -> list[Carton]:
    return [Carton(sku, dims, tare, limit if mass_limited else None)
            for sku, dims, tare, limit in _SPEC]


def workloads() -> dict[str, list[Item]]:
    """Deterministic orders, sized to run in about a second in total.

    Every item here fits some carton. Orders containing items no carton can
    hold are deliberately excluded: Phase 3 adds an up-front filter for those,
    which changes their rejects on purpose, and mixing an intended change into
    the fixture that guards against unintended ones would defeat the fixture.
    """
    out: dict[str, list[Item]] = {}

    r = random.Random(11)
    out["random_300"] = [
        Item(f"R{i}", (r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                       r.randrange(30, 160, 5)), r.randrange(50, 3000, 10))
        for i in range(300)]

    r = random.Random(12)
    catalogue = [((r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                   r.randrange(30, 160, 5)), r.randrange(50, 3000, 10))
                 for _ in range(20)]
    out["catalogue_300"] = [
        Item(f"C{i}", *catalogue[r.randrange(20)]) for i in range(300)]

    # Identical items, the case that stacks deepest and so exercises the most
    # candidate points per carton.
    out["uniform_250"] = [Item(f"U{i}", (70, 60, 50), 400) for i in range(250)]

    # Mixed rotation rules, so the orientation paths are all covered.
    r = random.Random(13)
    out["rotation_mixed_200"] = [
        Item(f"O{i}", (r.randrange(30, 240, 10), r.randrange(30, 200, 10),
                       r.randrange(30, 150, 10)), r.randrange(50, 2500, 10),
             allowed_rotations=("any", "upright", "fixed")[i % 3])
        for i in range(200)]

    # Segregation, so split_compatible's grouping is covered too. Phase 5
    # rewrites that function and must not move an item between groups.
    r = random.Random(14)
    out["dg_mixed_200"] = [
        Item(f"D{i}", (r.randrange(30, 200, 10), r.randrange(30, 180, 10),
                       r.randrange(30, 140, 10)), r.randrange(50, 2000, 10),
             dg_class=(None, None, "3", "8")[i % 4])
        for i in range(200)]

    return out


def encode(sol) -> dict:
    """Everything observable about a Solution except the wall clock."""
    return {
        "cartons": [
            {"sku": pc.carton.sku,
             "placements": [[p.item.ref, list(p.pos), list(p.dims),
                             p.orientation, p.sequence]
                            for p in pc.placements]}
            for pc in sol.cartons],
        "rejects": [[r.item_ref, r.reason_code] for r in sol.rejects],
        "carton_count": sol.carton_count,
    }


def produce() -> dict:
    from fitsolver.greedy2.pack import pack

    out: dict[str, dict] = {}
    for name, items in workloads().items():
        for mass_limited in (False, True):
            regime = "mass_limited" if mass_limited else "geometry_bound"
            sol = pack(items, cartons(mass_limited), time_budget_ms=1200, seed=1)
            out[f"{name}.{regime}"] = encode(sol)
    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true",
                    help="overwrite the recorded layouts; read the docstring first")
    args = ap.parse_args()
    produced = produce()
    if not args.write:
        print("dry run; pass --write to overwrite", file=sys.stderr)
    else:
        DATA.parent.mkdir(parents=True, exist_ok=True)
        # Compact: one line per workload. 2500 placements pretty-printed is a
        # 370 KB diff nobody reads; this is a tenth of that and still greppable.
        body = ",\n".join(f' {json.dumps(k)}: {json.dumps(v)}'
                          for k, v in sorted(produced.items()))
        DATA.write_text("{\n" + body + "\n}\n")
    for key, enc in sorted(produced.items()):
        n = sum(len(c["placements"]) for c in enc["cartons"])
        print(f"{key}: {enc['carton_count']} cartons, {n} placements, "
              f"{len(enc['rejects'])} rejects")


if __name__ == "__main__":
    main()
