"""Phase 11: the two behaviour changes that were kept, as properties.

Item 2 replaced the "tallest" ordering with a mass ordering, and item 3
changed pack_one's carton choice from most items packed to most volume
packed. Both are measured decisions, and the measurements are in
src/fitsolver/greedy2/DESIGN_NOTES.md. What is tested here is the thing a measurement cannot pin
down: that the change is the change it claims to be, and that it did not
break an invariant on the way.

The rejected items, 1, 4 and 7, are not tested. There is nothing to test: the
code they would have changed is unchanged, and the reason is recorded in
DESIGN_NOTES.md.
"""
from __future__ import annotations

import random

import pytest

from fitsolver.domain import Carton, Item
from fitsolver.greedy2.pack import (
    SORT_KEYS,
    canonical_key,
    carton_fit_table,
    fill_carton,
    pack_one,
)
from fitsolver.greedy2.pack import pack as greedy2_pack

CARTONS = [
    Carton("S", (220, 160, 120), 120, 5000),
    Carton("M", (320, 240, 180), 210, 12000),
    Carton("L", (450, 350, 300), 380, 20000),
    Carton("XL", (600, 400, 400), 520, 30000),
]
NO_LIMITS = [Carton(c.sku, c.inner_dims, c.tare_mass) for c in CARTONS]


def make_items(n: int, seed: int = 1) -> list[Item]:
    r = random.Random(seed)
    return [Item(f"S{i}", (r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                           r.randrange(30, 160, 5)), r.randrange(50, 3000, 10))
            for i in range(n)]


# --------------------------------------------------------------------------- #
# Item 2: four orderings, four DISTINCT orderings.
# --------------------------------------------------------------------------- #

def test_there_are_four_sort_keys_and_the_names_are_unique():
    names = [n for n, _ in SORT_KEYS]
    assert len(names) == len(set(names)) == 4


def test_no_two_sort_keys_agree_on_every_order():
    """What went wrong before, as a test.

    "tallest" was (-max(dims), -volume) and "longest_edge" is
    (-max(dims), -min(dims)). Both lead on the longest edge, so on many orders
    they produced the identical sequence and one of the four passes was spent
    re-deriving another pass's answer. bench/NOTES_order_diagnosis.md caught
    it on n10-0, where all ten items come out in the same order under both.

    A pair that merely CAN agree is fine: two keys will coincide on some
    order, and on a one-item order every key agrees. The defect is a pair that
    agrees on everything, so each pair has to be separated by at least one of
    several orders, not by all of them.
    """
    orders = [sorted(make_items(n, seed=s), key=canonical_key)
              for n in (10, 40, 120) for s in range(4)]
    for i, (name_a, key_a) in enumerate(SORT_KEYS):
        for name_b, key_b in SORT_KEYS[i + 1:]:
            assert any(sorted(o, key=key_a) != sorted(o, key=key_b)
                       for o in orders), (
                f"{name_a} and {name_b} agree on every order tried")


def test_the_mass_ordering_is_descending_in_mass():
    """The key is negated, so a plain ascending sort is heaviest first."""
    key = dict(SORT_KEYS)["mass"]
    items = make_items(60, seed=3)
    masses = [i.mass for i in sorted(items, key=key)]
    assert masses == sorted(masses, reverse=True)


def test_the_mass_ordering_breaks_ties_by_volume_then_canonically():
    """Two items of equal mass sort by volume descending, and two equal in
    both keep canonical order, because Python's sort is stable and the input
    is canonical. Determinism depends on this."""
    key = dict(SORT_KEYS)["mass"]
    twins = [Item("A", (100, 100, 100), 500), Item("B", (100, 100, 100), 500),
             Item("C", (200, 100, 100), 500)]
    ordered = sorted(sorted(twins, key=canonical_key), key=key)
    assert [i.ref for i in ordered] == ["C", "A", "B"]


# --------------------------------------------------------------------------- #
# Item 3: the carton chosen is the one packing the most volume.
# --------------------------------------------------------------------------- #

def _packed_volume(pc) -> int:
    return sum(p.dims[0] * p.dims[1] * p.dims[2] for p in pc.placements)


@pytest.mark.parametrize("boxes", [CARTONS, NO_LIMITS],
                         ids=["mass_limited", "geometry_bound"])
@pytest.mark.parametrize("seed", [0, 1, 2, 3])
def test_the_first_carton_opened_packs_the_most_volume(boxes, seed):
    """pack_one's choice, checked against every carton type by hand.

    Only the FIRST carton is checked, because after that the remaining items
    differ and there is nothing to compare against.
    """
    items = sorted(make_items(25, seed=seed), key=canonical_key)
    table = carton_fit_table(items, boxes)
    ordering = sorted(items, key=dict(SORT_KEYS)["volume"])

    out, _left = pack_one(ordering, boxes, table)
    chosen = out[0]

    best = max(_packed_volume(fill_carton(c, ordering)[0]) for c in boxes)
    assert _packed_volume(chosen) == best


@pytest.mark.parametrize("boxes", [CARTONS, NO_LIMITS],
                         ids=["mass_limited", "geometry_bound"])
def test_a_volume_tie_goes_to_the_smaller_carton(boxes):
    """The second half of the key. One item that fits every carton: all four
    pack the same volume, so the smallest must win."""
    item = [Item("only", (100, 100, 100), 100)]
    table = carton_fit_table(item, boxes)
    out, left = pack_one(item, boxes, table)
    assert left == []
    assert out[0].carton.sku == "S"


@pytest.mark.parametrize("boxes", [CARTONS, NO_LIMITS],
                         ids=["mass_limited", "geometry_bound"])
@pytest.mark.parametrize("n", [1, 5, 25, 120])
def test_every_item_is_still_placed_exactly_once(boxes, n):
    """The invariant the carton-choice key must not break. A key that picks a
    carton whose `left` list has lost an item would pass every count-based
    check above and silently drop goods."""
    items = make_items(n, seed=6)
    sol = greedy2_pack(items, boxes, time_budget_ms=1200, seed=1)
    placed = [p.item.ref for c in sol.cartons for p in c.placements]
    assert sorted(placed) == sorted(i.ref for i in items)
    assert sol.rejects == []


def test_single_item_cartons_are_not_the_default_outcome():
    """Guards the failure mode the volume key exists to avoid, and the one
    the rejected leftover-volume key falls into: opening a small carton per
    item. 60 mixed items must not come back as 60 cartons."""
    items = make_items(60, seed=7)
    sol = greedy2_pack(items, NO_LIMITS, time_budget_ms=1200, seed=1)
    singles = sum(1 for c in sol.cartons if len(c.placements) == 1)
    assert singles <= 1, f"{singles} single-item cartons of {sol.carton_count}"
