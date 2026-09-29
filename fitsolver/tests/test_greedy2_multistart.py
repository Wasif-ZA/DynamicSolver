"""Phase 4: canonical input order, multi-start, and the lower-bound early stop.

Three separable claims, tested separately:

  1. the layout depends on WHAT was ordered, never on the sequence it arrived
     in, so re-keying an order does not redraw the picture;
  2. multi-start keeps the lexicographically best pass and never a worse one;
  3. the early stop only fires on a bound that is genuinely a lower bound, so
     stopping cannot skip a better answer.

The third is the one that fails silently if it is wrong. A bound that is too
high stops a pass that was not optimal and calls it done.
"""
from __future__ import annotations

import math
import random

import pytest

from fitsolver.domain import Carton, Item
from fitsolver.greedy2.pack import (
    PASS_COST_MS,
    SORT_KEYS,
    canonical_key,
    estimated_pass_ms,
    lower_bound,
    passes_for,
    result_key,
    split_compatible,
)
from fitsolver.greedy2.pack import pack as greedy2_pack

CARTONS = [
    Carton("S", (220, 160, 120), 120, 5000),
    Carton("M", (320, 240, 180), 210, 12000),
    Carton("L", (450, 350, 300), 380, 20000),
    Carton("XL", (600, 400, 400), 520, 30000),
]
NO_LIMITS = [Carton(c.sku, c.inner_dims, c.tare_mass) for c in CARTONS]


def make_items(n: int, seed: int = 1, **kw) -> list[Item]:
    r = random.Random(seed)
    return [Item(f"S{i}", (r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                           r.randrange(30, 160, 5)), r.randrange(50, 3000, 10),
                 **kw)
            for i in range(n)]


def layout(sol) -> list:
    return [(pc.carton.sku, [(p.item.ref, p.pos, p.dims, p.orientation)
                             for p in pc.placements])
            for pc in sol.cartons]


# --------------------------------------------------------------------------- #
# 1. The same goods in a different sequence give the same layout.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [1, 5, 40, 150])
@pytest.mark.parametrize("boxes", [CARTONS, NO_LIMITS],
                         ids=["mass_limited", "geometry_bound"])
def test_input_order_does_not_change_the_layout(n, boxes):
    items = make_items(n, seed=5)
    reference = greedy2_pack(items, boxes, time_budget_ms=1200, seed=1)
    for shuffle_seed in range(4):
        shuffled = list(items)
        random.Random(shuffle_seed).shuffle(shuffled)
        got = greedy2_pack(shuffled, boxes, time_budget_ms=1200, seed=1)
        assert layout(got) == layout(reference), (
            f"shuffle {shuffle_seed} produced a different layout")


def test_reversed_input_gives_the_same_layout():
    items = make_items(80, seed=6)
    a = greedy2_pack(items, CARTONS, time_budget_ms=1200, seed=1)
    b = greedy2_pack(list(reversed(items)), CARTONS, time_budget_ms=1200, seed=1)
    assert layout(a) == layout(b)


def test_canonical_key_separates_items_that_pack_differently():
    """Anything that can change packing has to be in the key, or two different
    orders canonicalise to the same sequence and one of them gets the other's
    layout."""
    base = Item("A", (100, 90, 80), 500)
    variants = [
        base,
        Item("A", (100, 90, 81), 500),                       # dims
        Item("A", (100, 90, 80), 501),                       # mass
        Item("A", (100, 90, 80), 500, allowed_rotations="fixed"),
        Item("A", (100, 90, 80), 500, dg_class="3"),
        Item("A", (100, 90, 80), 500, incompatible_with=frozenset({"B"})),
        Item("B", (100, 90, 80), 500),                       # ref
    ]
    keys = [canonical_key(v) for v in variants]
    assert len(set(keys)) == len(keys)


def test_canonical_key_orders_set_and_unset_dg_class():
    """None cannot be compared to a string, so the key splits the question in
    two. Without that this raises TypeError on any mixed order."""
    items = [Item("A", (10, 10, 10), 1, dg_class=None),
             Item("B", (10, 10, 10), 1, dg_class="3")]
    assert sorted(items, key=canonical_key)  # must not raise


def test_identical_items_are_interchangeable():
    """quantity expansion puts the SAME item in the list repeatedly, so ties
    under the canonical key are normal and must not be resolved by identity."""
    item = Item("Q", (100, 100, 100), 500)
    a = greedy2_pack([item] * 12, CARTONS, time_budget_ms=1200, seed=1)
    b = greedy2_pack([item] * 12, CARTONS, time_budget_ms=1200, seed=1)
    assert layout(a) == layout(b)


# --------------------------------------------------------------------------- #
# 2. Multi-start keeps the best pass.
# --------------------------------------------------------------------------- #

def test_result_key_is_unplaced_then_cartons_then_volume():
    small = Carton("S", (100, 100, 100), 0)
    big = Carton("B", (200, 200, 200), 0)
    from fitsolver.domain import PackedCarton
    one_small = [PackedCarton(carton=small)]
    one_big = [PackedCarton(carton=big)]
    two_small = [PackedCarton(carton=small), PackedCarton(carton=small)]
    item = Item("X", (10, 10, 10), 1)

    # fewer unplaced wins, whatever the carton count
    assert result_key(two_small, []) < result_key(one_small, [item])
    # then fewer cartons
    assert result_key(one_big, []) < result_key(two_small, [])
    # then less volume
    assert result_key(one_small, []) < result_key(one_big, [])


@pytest.mark.parametrize("n", [30, 120])
def test_multistart_is_never_worse_than_any_single_ordering(n):
    """The whole justification for spending the passes."""
    items = make_items(n, seed=8)
    best = greedy2_pack(items, NO_LIMITS, time_budget_ms=60_000, seed=1)
    got = result_key(best.cartons, best.rejects)

    from fitsolver.greedy2.pack import _run_pass, carton_fit_table
    table = carton_fit_table(items, NO_LIMITS)
    groups = split_compatible(sorted(items, key=canonical_key))
    for name, sort_key in SORT_KEYS:
        packed, unplaced = _run_pass(groups, NO_LIMITS, table, sort_key)
        assert got <= result_key(packed, unplaced), f"{name} beat multi-start"


def test_more_budget_is_never_worse():
    """A bigger budget buys more orderings, and keeping the best of more
    cannot be worse than keeping the best of fewer."""
    items = make_items(200, seed=9)
    small = greedy2_pack(items, NO_LIMITS, time_budget_ms=200, seed=1)
    large = greedy2_pack(items, NO_LIMITS, time_budget_ms=60_000, seed=1)
    assert large.carton_count <= small.carton_count


# --------------------------------------------------------------------------- #
# 3. The early stop, and the bound it trusts.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n", [1, 7, 30, 90, 200])
@pytest.mark.parametrize("boxes", [CARTONS, NO_LIMITS],
                         ids=["mass_limited", "geometry_bound"])
def test_the_bound_is_never_above_what_is_achievable(n, boxes):
    """THE dangerous direction. A bound higher than the true optimum makes the
    early stop declare a suboptimal pass finished."""
    items = make_items(n, seed=10)
    sol = greedy2_pack(items, boxes, time_budget_ms=60_000, seed=1)
    groups = split_compatible(sorted(items, key=canonical_key))
    assert lower_bound(groups, boxes) <= sol.carton_count


def test_the_volume_bound_is_the_obvious_division():
    box = [Carton("B", (100, 100, 100), 0)]           # 1e6 mm3
    items = [Item(f"X{i}", (50, 50, 50), 1) for i in range(20)]   # 125000 each
    groups = split_compatible(items)
    assert lower_bound(groups, box) == math.ceil(20 * 125_000 / 1_000_000)


def test_the_mass_bound_applies_when_every_carton_is_limited():
    box = [Carton("B", (1000, 1000, 1000), 0, max_contents_mass=1000)]
    items = [Item(f"X{i}", (10, 10, 10), 400) for i in range(10)]  # 4000 g
    assert lower_bound(split_compatible(items), box) == 4


def test_one_unlimited_carton_disables_the_mass_bound():
    """A carton with no limit could in principle hold everything, so the mass
    bound is not a bound at all. Trusting it would stop early on a layout that
    is not optimal."""
    boxes = [Carton("L", (1000, 1000, 1000), 0, max_contents_mass=1000),
             Carton("U", (1000, 1000, 1000), 0)]
    items = [Item(f"X{i}", (10, 10, 10), 400) for i in range(10)]
    assert lower_bound(split_compatible(items), boxes) == 1


def test_the_bound_sums_over_conflict_groups():
    """Groups cannot share a carton, so each needs its own. A bound taken over
    the whole order would be weaker, and the early stop would rarely fire."""
    box = [Carton("B", (1000, 1000, 1000), 0)]
    items = [Item("A", (10, 10, 10), 1, dg_class="3"),
             Item("B", (10, 10, 10), 1, dg_class="8"),
             Item("C", (10, 10, 10), 1, dg_class="9")]
    assert lower_bound(split_compatible(items), box) == 3


def test_the_early_stop_fires_when_one_carton_is_provably_enough():
    """Everything fits one carton, so the bound is 1, the first pass reaches
    it, and no further ordering is tried."""
    calls = []
    import fitsolver.greedy2.pack as mod
    real = mod._run_pass

    def counting(*a, **k):
        calls.append(1)
        return real(*a, **k)

    mod._run_pass = counting
    try:
        greedy2_pack([Item(f"T{i}", (40, 40, 40), 10) for i in range(8)],
                     NO_LIMITS, time_budget_ms=60_000, seed=1)
    finally:
        mod._run_pass = real
    assert len(calls) == 1, "the bound was reached but more passes still ran"


def test_an_empty_order_has_a_zero_bound():
    assert lower_bound([], CARTONS) == 0
    assert lower_bound([[]], CARTONS) == 0
    sol = greedy2_pack([], CARTONS, time_budget_ms=1200, seed=1)
    assert sol.carton_count == 0 and not sol.rejects


# --------------------------------------------------------------------------- #
# The work cap: a table, never a clock.
# --------------------------------------------------------------------------- #

def test_passes_for_is_between_one_and_the_number_of_keys():
    for n in (0, 1, 10, 500, 100_000):
        for budget in (1, 50, 1200, 60_000, 10 ** 9):
            assert 1 <= passes_for(n, budget) <= len(SORT_KEYS)


def test_passes_for_never_decreases_with_budget():
    for n in (10, 100, 300, 1000):
        counts = [passes_for(n, b) for b in (100, 500, 1200, 5000, 60_000)]
        assert counts == sorted(counts)


def test_passes_for_never_increases_with_order_size():
    for budget in (1200, 5000, 60_000):
        counts = [passes_for(n, budget) for n in (10, 50, 100, 300, 1000, 5000)]
        assert counts == sorted(counts, reverse=True)


def test_a_tiny_budget_still_runs_one_pass():
    """An answer is not optional. Returning nothing because the budget was
    small would be a false rejection of goods that fit."""
    assert passes_for(10_000, 1) == 1
    sol = greedy2_pack(make_items(20, seed=11), CARTONS,
                       time_budget_ms=1, seed=1)
    assert sum(len(c.placements) for c in sol.cartons) == 20


def test_pass_cost_table_is_sorted_and_increasing():
    sizes = [n for n, _ in PASS_COST_MS]
    costs = [ms for _, ms in PASS_COST_MS]
    assert sizes == sorted(sizes)
    assert costs == sorted(costs)


def test_cost_beyond_the_table_is_extrapolated_not_flat():
    """Cost grows faster than linearly, so treating anything past the last row
    as costing the same would let a huge order try four passes."""
    last_n, last_ms = PASS_COST_MS[-1]
    assert estimated_pass_ms(last_n * 4) > last_ms
    assert estimated_pass_ms(last_n) == last_ms


def test_the_pass_count_does_not_depend_on_the_clock():
    """Same arguments, same answer, whatever the machine is doing."""
    assert len({passes_for(250, 1200) for _ in range(50)}) == 1
