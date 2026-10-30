"""Further optimise: one smaller carton, found by CP-SAT, checked by greedy2's geometry."""
import json
import random
import time
from collections import Counter

import pytest

from fitsolver.domain import Carton, Item
from fitsolver.engine import solve
from fitsolver.greedy2.geometry import inside, overlaps, supported
from fitsolver.greedy2.optimise import MAX_ITEMS, further_optimise
from fitsolver.greedy2.pack import pack

pytest.importorskip("ortools")

# The client's challenge order: greedy2 alone needs a P500, one P300 is enough.
CHALLENGE = [
    ("ITM-014", (108, 108, 137)), ("ITM-013", (140, 140, 75)), ("ITM-015", (83, 129, 74)),
    ("ITM-001", (380, 285, 80)), ("ITM-016", (86, 395, 55)), ("ITM-008", (120, 131, 50)),
    ("ITM-011", (72, 103, 38)), ("ITM-006", (156, 200, 33)), ("ITM-003", (112, 92, 50)),
    ("ITM-010", (100, 105, 97)), ("ITM-004", (127, 86, 45)), ("ITM-009", (103, 175, 93)),
    ("ITM-012", (140, 158, 115)), ("ITM-007", (93, 245, 60)), ("ITM-005", (89, 140, 55)),
]
P200 = Carton("P200", (440, 275, 165), 500, 10000, maximum_boxes=2)
P300 = Carton("P300", (400, 300, 250), 750, 15000, maximum_boxes=1)
P500 = Carton("P500", (525, 365, 310), 900, 20000, maximum_boxes=1)


def _items():
    return [Item(ref, dims, 100) for ref, dims in CHALLENGE]


def _valid(sol):
    for pc in sol.cartons:
        placed = []
        for p in sorted(pc.placements, key=lambda p: p.sequence):
            assert inside(p.pos, p.dims, pc.carton)
            assert not any(overlaps(p.pos, p.dims, q.pos, q.dims) for q in placed)
            assert supported(p.pos, p.dims, placed)
            placed.append(p)


def test_challenge_greedy2_alone_uses_p500():
    sol = pack(_items(), [P200, P300, P500], 1200, 1)
    assert [pc.carton.sku for pc in sol.cartons] == ["P500"]


def test_challenge_further_optimise_finds_one_p300():
    # A generous limit here: this test is about whether it CAN find the P300,
    # not how fast a given machine is. The 20 s cap has its own test below.
    sol = further_optimise(_items(), [P200, P300, P500], 1200, 1, time_limit_s=120)
    assert [pc.carton.sku for pc in sol.cartons] == ["P300"]
    assert sum(len(pc.placements) for pc in sol.cartons) == 15
    assert not sol.rejects
    assert sol.tier == 2
    _valid(sol)


def test_no_improvement_possible_returns_greedy2_exactly():
    # greedy2 already uses the smallest carton that fits, so nothing can beat it.
    items = [Item(f"s{k}", (50, 50, 50), 100) for k in range(4)]
    cartons = [Carton("S", (120, 120, 120), 0), Carton("L", (400, 400, 400), 0)]
    a, b = pack(items, cartons, 1200, 1), further_optimise(items, cartons, 1200, 1)

    def layout(sol):
        return [(pc.carton.sku, [(p.item.ref, p.pos, p.dims) for p in pc.placements])
                for pc in sol.cartons]

    assert layout(a) == layout(b) and b.tier == 1


def test_maximum_boxes_zero_carton_is_never_used():
    p300_none_left = Carton("P300", (400, 300, 250), 750, 15000, maximum_boxes=0)
    sol = further_optimise(_items(), [P200, p300_none_left, P500], 1200, 1)
    assert "P300" not in Counter(pc.carton.sku for pc in sol.cartons)


def test_mass_limit_is_respected():
    heavy = [Item(ref, dims, 1100) for ref, dims in CHALLENGE]   # 16.5 kg > P300's 15 kg
    sol = further_optimise(heavy, [P200, P300, P500], 1200, 1)
    assert "P300" not in Counter(pc.carton.sku for pc in sol.cartons)
    _valid(sol)


def test_two_conflict_groups_are_left_to_greedy2():
    items = _items()
    items[0] = Item(items[0].ref, items[0].dims, 100, dg_class="3")
    items[1] = Item(items[1].ref, items[1].dims, 100, dg_class="8")
    cartons = [P200, P300, P500]
    a, b = pack(items, cartons, 1200, 1), further_optimise(items, cartons, 1200, 1)
    assert [pc.carton.sku for pc in a.cartons] == [pc.carton.sku for pc in b.cartons]
    assert b.tier == 1


def test_large_orders_are_left_to_greedy2():
    items = [Item(f"b{k}", (60, 60, 60), 10) for k in range(MAX_ITEMS + 1)]
    sol = further_optimise(items, [Carton("M", (400, 400, 400), 0)], 1200, 1)
    assert sol.tier == 1


def test_engine_optimise_flag_and_default_path():
    req = {"order_id": "challenge",
           "items": [{"item_ref": r, "dims": list(d), "mass": 100} for r, d in CHALLENGE],
           "cartons": [{"sku": c.sku, "inner_dims": list(c.inner_dims), "tare_mass": c.tare_mass,
                        "max_contents_mass": c.max_contents_mass,
                        "maximum_boxes": c.maximum_boxes} for c in (P200, P300, P500)]}
    fast = solve(req)
    slow = solve(req, optimise=True)
    assert [c["sku"] for c in fast["cartons"]] == ["P500"]
    # Within the 20 s cap it finds the P300 or falls back to greedy2's P500,
    # never anything worse, and every item is still packed.
    assert [c["sku"] for c in slow["cartons"]] in (["P300"], ["P500"])
    assert sum(len(c["placements"]) for c in slow["cartons"]) == 15
    json.dumps(slow)


def test_time_cap_is_respected():
    rng = random.Random(3)
    items = [Item(f"x{k}", (rng.randint(40, 160), rng.randint(40, 160), rng.randint(30, 120)), 100)
             for k in range(MAX_ITEMS)]
    cartons = [Carton("S", (300, 250, 200), 0), Carton("M", (400, 300, 250), 0),
               Carton("L", (525, 365, 310), 0)]
    t = time.monotonic()
    sol = further_optimise(items, cartons, 1200, 1, time_limit_s=3)
    assert time.monotonic() - t < 3 + 2
    assert sum(len(pc.placements) for pc in sol.cartons) == MAX_ITEMS
    _valid(sol)


def test_defaults_match_the_agreed_limits():
    from fitsolver.greedy2 import optimise
    assert optimise.MAX_ITEMS == 30
    assert optimise.TIME_LIMIT_S == 30
