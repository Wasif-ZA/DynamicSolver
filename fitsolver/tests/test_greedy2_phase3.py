"""Phase 3: pre-checks and the infeasibility memo, unit by unit.

Phase 3 adds no heuristic: each pre-check is exact, so it may only ever skip
work that was provably going to fail. That the layouts did not move is checked
in test_greedy2_layouts.py, against the recorded baseline.

The one deliberate behaviour change is the up-front rejection of items no
carton can hold, covered at the bottom. It fixes a false-rejection bug, so it
is tested for what it now does rather than for staying the same.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fitsolver.domain import Carton, Item
from fitsolver.greedy2.geometry import (
    fits_empty_carton,
    inside,
    orientations,
    room_admits,
    room_at,
)
from fitsolver.greedy2.pack import (
    CHUNK,
    CartonState,
    carton_fit_table,
    fill_carton,
    place,
    smallest_dim_suffixes,
)
from fitsolver.greedy2.pack import pack as greedy2_pack

CARTONS = [
    Carton("S", (220, 160, 120), 120, 5000),
    Carton("M", (320, 240, 180), 210, 12000),
    Carton("L", (450, 350, 300), 380, 20000),
    Carton("XL", (600, 400, 400), 520, 30000),
]

dims_st = st.tuples(st.integers(10, 400), st.integers(10, 400),
                    st.integers(10, 400))
rot_st = st.sampled_from(["any", "upright", "fixed"])
item_st = st.builds(Item, ref=st.just("X"), dims=dims_st, mass=st.just(1),
                    allowed_rotations=rot_st)


# --------------------------------------------------------------------------- #
# The layout must not move. This is the phase's acceptance criterion.
# --------------------------------------------------------------------------- #

# --------------------------------------------------------------------------- #
# The O(1) room test has to be exact, not merely conservative.
# --------------------------------------------------------------------------- #

@given(item=item_st, room=dims_st)
@settings(max_examples=800, deadline=None)
def test_room_admits_agrees_with_trying_every_orientation(item, room):
    """The whole point of the sorted comparison is that it is exact. If it
    ever says no where an orientation would have fitted, the solver silently
    loses positions and no invariant fails."""
    brute = any(all(dims[a] <= room[a] for a in range(3))
                for _, dims in orientations(item))
    assert room_admits(item, room) == brute


@pytest.mark.parametrize("rotations", ["any", "upright", "fixed"])
def test_an_item_may_sit_exactly_flush(rotations):
    """<= not <. An item exactly filling the room fits, in every rotation
    mode. This is the off-by-one that would reject every perfect fit."""
    item = Item("E", (100, 80, 60), 1, allowed_rotations=rotations)
    assert room_admits(item, (100, 80, 60))
    assert not room_admits(item, (99, 80, 60))


def test_room_admits_uses_rotation_to_fit_a_long_item_flat():
    tall = Item("T", (10, 10, 190), 1)
    flat_room = (200, 200, 50)
    assert room_admits(tall, flat_room)
    assert not room_admits(
        Item("T", (10, 10, 190), 1, allowed_rotations="fixed"), flat_room)


def test_upright_may_yaw_but_not_tip():
    item = Item("U", (200, 50, 100), 1, allowed_rotations="upright")
    assert room_admits(item, (60, 210, 100))     # yawed 90 degrees
    assert not room_admits(item, (200, 50, 99))  # would have to tip over


def test_room_at_measures_to_the_far_wall():
    carton = Carton("T", (100, 200, 300), 0)
    assert room_at((0, 0, 0), carton) == (100, 200, 300)
    assert room_at((10, 20, 30), carton) == (90, 180, 270)


# --------------------------------------------------------------------------- #
# The memo. Getting this wrong loses cartons without failing an invariant.
# --------------------------------------------------------------------------- #

def test_a_support_failure_is_never_memoised():
    """THE dangerous case. A point unsupported now can be supported later,
    once something becomes its floor. Memoising that refuses a placement that
    is legal a moment afterwards.

    Here a narrow shelf leaves a point that fails support, then a second item
    fills in beneath it and the same point must be reconsidered.
    """
    carton = Carton("T", (300, 300, 300), 0)
    state = CartonState(carton)
    base = place(Item("BASE", (100, 300, 100), 1), state)
    assert base is not None
    state.add(base)

    # A wide item at the top of the base overhangs: 100 of its 300 width is
    # supported, which is under the 70% rule, so it cannot go there yet.
    wide = Item("WIDE", (300, 300, 100), 1, allowed_rotations="fixed")
    assert place(wide, state) is None
    assert ((0, 0, 100), wide.dims, "fixed") not in state.infeasible, (
        "a support failure was memoised; the point can become supported later")

    # Fill in the rest of the floor, and now the same position is legal.
    filler = place(Item("FILL", (200, 300, 100), 1), state)
    assert filler is not None
    state.add(filler)
    again = place(wide, state)
    assert again is not None and again.pos == (0, 0, 100), (
        "the position became supported but was refused")


def test_an_out_of_bounds_failure_is_memoised():
    carton = Carton("T", (300, 300, 300), 0)
    state = CartonState(carton)
    huge = Item("H", (290, 290, 290), 1)
    state.add(place(Item("A", (100, 100, 100), 1), state))
    assert place(huge, state) is None
    assert any(k[1] == huge.dims for k in state.infeasible), (
        "a permanent bounds failure was not memoised, so it will be retried")


def test_the_memo_never_changes_what_gets_placed():
    """Same fill, with the memo disabled by clearing it before every attempt.
    Identical placements, or the memo is refusing something it should not."""
    items = [Item(f"S{i}", (40 + (i % 7) * 20, 30 + (i % 5) * 25,
                            20 + (i % 3) * 30), 10) for i in range(120)]
    carton = CARTONS[3]

    with_memo, _ = fill_carton(carton, items)

    state = CartonState(carton)
    for item in items:
        state.infeasible.clear()
        p = place(item, state)
        if p is not None:
            state.add(p)
    assert [(p.item.ref, p.pos, p.dims) for p in with_memo.placements] == \
           [(p.item.ref, p.pos, p.dims) for p in state.placements]


# --------------------------------------------------------------------------- #
# Size-based point removal must only drop points nothing could use.
# --------------------------------------------------------------------------- #

def test_smallest_dim_suffixes_is_the_running_minimum_from_the_right():
    items = [Item("A", (90, 80, 70), 1), Item("B", (50, 60, 55), 1),
             Item("C", (200, 30, 120), 1)]
    assert smallest_dim_suffixes(items) == [30, 30, 30, 0]
    assert smallest_dim_suffixes([]) == [0]


def test_dropping_small_points_keeps_every_point_an_item_could_use():
    carton = Carton("T", (200, 200, 200), 0)
    state = CartonState(carton)
    state.add(place(Item("A", (150, 150, 150), 1), state))
    kept_before = set(state.points)
    state.drop_points_too_small_for(40)
    for q in kept_before - set(state.points):
        assert min(room_at(q, carton)) < 40, f"{q} was usable and was dropped"
    for q in state.points:
        assert min(room_at(q, carton)) >= 40


@settings(max_examples=60, deadline=None)
@given(items=st.lists(
    st.builds(Item, ref=st.uuids().map(lambda u: u.hex[:6]), dims=dims_st,
              mass=st.integers(1, 4000), allowed_rotations=rot_st),
    min_size=1, max_size=30))
def test_point_removal_does_not_change_the_fill(items):
    """fill_carton prunes by size; driving CartonState directly does not.
    The placements must match, or the pruning is dropping usable points."""
    carton = CARTONS[2]
    pruned, _ = fill_carton(carton, items)

    state = CartonState(carton)
    for item in items:
        p = place(item, state)
        if p is not None:
            state.add(p)
    assert [(p.item.ref, p.pos, p.dims) for p in pruned.placements] == \
           [(p.item.ref, p.pos, p.dims) for p in state.placements]


# --------------------------------------------------------------------------- #
# The carton fit table.
# --------------------------------------------------------------------------- #

def test_fit_table_keys_on_shape_not_on_item():
    """A 1000-item order over 40 SKUs must cost 40 tests, not 1000."""
    items = [Item(f"S{i}", (100, 100, 100), i) for i in range(50)]
    assert len(carton_fit_table(items, CARTONS)) == 1


def test_fit_table_lists_exactly_the_cartons_that_could_hold_the_shape():
    item = Item("M", (300, 200, 150), 1)
    table = carton_fit_table([item], CARTONS)
    expected = tuple(i for i, c in enumerate(CARTONS)
                     if fits_empty_carton(item, c))
    assert table[(item.dims, "any")] == expected
    # Sanity: this one is too big for S but fits M, L and XL.
    assert expected == (1, 2, 3)


@given(item=item_st)
@settings(max_examples=300, deadline=None)
def test_fits_empty_carton_agrees_with_the_geometry(item):
    for carton in CARTONS:
        brute = any(inside((0, 0, 0), dims, carton)
                    for _, dims in orientations(item))
        assert fits_empty_carton(item, carton) == brute


# --------------------------------------------------------------------------- #
# The one intended behaviour change: rejecting unplaceable items up front.
# --------------------------------------------------------------------------- #

@pytest.mark.parametrize("n_giants", [CHUNK - 1, CHUNK, CHUNK + 50])
def test_unplaceable_items_never_starve_placeable_ones(n_giants):
    """Before this phase, a CHUNK-sized run of items no carton can hold filled
    the window, packed nothing, and abandoned every item behind it. The five
    smalls also have to land in ONE carton, not five."""
    small = [Carton("S", (200, 200, 200), 0)]
    giants = [Item(f"G{i}", (500, 500, 500), 100) for i in range(n_giants)]
    smalls = [Item(f"S{i}", (50, 50, 50), 10) for i in range(5)]

    sol = greedy2_pack(giants + smalls, small, time_budget_ms=1200, seed=1)

    placed = [p.item.ref for c in sol.cartons for p in c.placements]
    assert sorted(placed) == sorted(f"S{i}" for i in range(5))
    assert sorted(r.item_ref for r in sol.rejects) == sorted(
        f"G{i}" for i in range(n_giants))
    assert sol.carton_count == 1, "the five smalls all fit in one carton"


def test_an_overweight_item_is_told_about_mass_not_size():
    """An item that fits but is too heavy, told it exceeds every carton's
    dimensions, sends a packer looking for a bigger box."""
    carton = [Carton("B", (200, 200, 200), 0, max_contents_mass=100)]
    sol = greedy2_pack([Item("HEAVY", (50, 50, 50), 9999)], carton,
                       time_budget_ms=100, seed=1)
    assert len(sol.rejects) == 1
    assert "mass" in sol.rejects[0].message.lower()


def test_an_oversized_item_is_told_about_size():
    carton = [Carton("B", (200, 200, 200), 0)]
    sol = greedy2_pack([Item("BIG", (500, 500, 500), 1)], carton,
                       time_budget_ms=100, seed=1)
    assert len(sol.rejects) == 1
    assert "Exceeds every carton" in sol.rejects[0].message


def test_conservation_holds_with_a_mix_of_causes():
    carton = [Carton("B", (200, 200, 200), 0, max_contents_mass=1000)]
    items = [Item("OK", (50, 50, 50), 100),
             Item("BIG", (500, 500, 500), 10),
             Item("HEAVY", (50, 50, 50), 99_999)]
    sol = greedy2_pack(items, carton, time_budget_ms=100, seed=1)
    placed = sum(len(c.placements) for c in sol.cartons)
    assert placed == 1
    assert placed + len(sol.rejects) == len(items)
