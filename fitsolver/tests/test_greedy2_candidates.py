"""Phase 2: dead-point pruning and the incremental live-point cache.

Two things have to be true, and they are tested separately because they fail
in different ways.

1. PRUNING IS RIGHT. A point is dead when nothing can ever be placed at it:
   it is on or beyond a wall, or inside a placed item. Prune too little and
   the crowding bug stays. Prune too much and the solver quietly loses
   positions, which does not fail any invariant, it just uses more cartons.

2. THE CACHE AGREES WITH THE DEFINITION. CartonState maintains the live set
   incrementally. geometry.candidates() recomputes it from scratch and is
   obviously correct by inspection. The cache is checked against it after
   every single placement, which is the check that would catch an incremental
   update that is subtly wrong only in the third carton of a long run.
"""
from __future__ import annotations

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fitsolver.domain import Carton, Item
from fitsolver.greedy2.geometry import candidates, covered_by, is_live
from fitsolver.greedy2.pack import CartonState, fill_carton, place
from fitsolver.greedy2.pack import pack as greedy2_pack
from fitsolver.pack import pack as v1_pack

CARTONS = [
    Carton("S", (220, 160, 120), 120, 5000),
    Carton("M", (320, 240, 180), 210, 12000),
    Carton("L", (450, 350, 300), 380, 20000),
    Carton("XL", (600, 400, 400), 520, 30000),
]

item_st = st.builds(
    Item,
    ref=st.uuids().map(lambda u: f"SKU-{u.hex[:6]}"),
    dims=st.tuples(st.integers(10, 400), st.integers(10, 400),
                   st.integers(10, 400)),
    mass=st.integers(1, 5000),
    allowed_rotations=st.sampled_from(["any", "upright", "fixed"]),
)


def _fill_checking_cache(carton: Carton, items: list[Item]) -> CartonState:
    """fill_carton, asserting the cache matches the reference after each add."""
    state = CartonState(carton)
    assert state.points == candidates(state.placements, carton)
    for item in items:
        p = place(item, state)
        if p is None:
            continue
        state.add(p)
        assert state.points == candidates(state.placements, carton), (
            f"cache drifted after placing {item.ref}")
    return state


@settings(max_examples=100, deadline=None)
@given(items=st.lists(item_st, min_size=1, max_size=25))
@pytest.mark.parametrize("carton", CARTONS, ids=lambda c: c.sku)
def test_cache_matches_the_reference_after_every_placement(carton, items):
    _fill_checking_cache(carton, items)


@settings(max_examples=100, deadline=None)
@given(items=st.lists(item_st, min_size=1, max_size=25))
@pytest.mark.parametrize("carton", CARTONS, ids=lambda c: c.sku)
def test_no_cached_point_is_dead(carton, items):
    """The two ways a point can be dead, checked directly rather than via
    candidates(), so a bug shared by both would still be caught."""
    state = _fill_checking_cache(carton, items)
    for q in state.points:
        for axis, wall in enumerate(carton.inner_dims):
            assert q[axis] < wall, f"{q} is at or beyond the wall on axis {axis}"
        for p in state.placements:
            assert not covered_by(q, p.pos, p.dims), f"{q} is inside {p.item.ref}"


@settings(max_examples=100, deadline=None)
@given(items=st.lists(item_st, min_size=1, max_size=25))
@pytest.mark.parametrize("carton", CARTONS, ids=lambda c: c.sku)
def test_cached_points_are_sorted_bottom_first_and_unique(carton, items):
    """place() slices the front of this list without sorting it, so the
    ordering is load-bearing, and a duplicate would waste a slot in the cap."""
    state = _fill_checking_cache(carton, items)
    keys = [(q[2], q[1], q[0]) for q in state.points]
    assert keys == sorted(keys)
    assert len(set(state.points)) == len(state.points)


def test_a_point_flush_against_a_wall_is_live_but_one_past_it_is_not():
    """x == W is outside the carton. Flush means x + w == W, a different
    point. Getting this off by one either loses the whole far column of
    positions or offers positions no item can occupy."""
    carton = Carton("T", (100, 100, 100), 0)
    assert is_live((99, 99, 99), carton, [])
    assert not is_live((100, 0, 0), carton, [])
    assert not is_live((0, 100, 0), carton, [])
    assert not is_live((0, 0, 100), carton, [])


def test_the_top_face_of_a_box_is_live_not_covered():
    """Half-open containment. The point on top of a box is where the next box
    starts, so treating it as covered would stop all stacking."""
    pos, dims = (0, 0, 0), (50, 50, 50)
    assert covered_by((0, 0, 0), pos, dims)
    assert covered_by((49, 49, 49), pos, dims)
    assert not covered_by((0, 0, 50), pos, dims)   # directly on top
    assert not covered_by((50, 0, 0), pos, dims)   # alongside
    assert not covered_by((0, 50, 0), pos, dims)


def test_the_origin_leaves_the_cache_once_it_is_covered():
    carton = Carton("T", (300, 300, 300), 0)
    state = CartonState(carton)
    assert state.points == [(0, 0, 0)]
    p = place(Item("A", (100, 100, 100), 1), state)
    assert p is not None and p.pos == (0, 0, 0)
    state.add(p)
    assert (0, 0, 0) not in state.points
    assert (0, 0, 100) in state.points, "the stacking position must survive"


def test_no_dead_corner_enters_the_cache_in_a_multi_item_pack():
    """A corner of a new item can land inside an item placed earlier, so
    every corner is liveness-checked against everything already placed."""
    carton = Carton("T", (300, 300, 300), 0)
    state = CartonState(carton)
    for item in [Item("A", (100, 100, 100), 1), Item("B", (100, 100, 100), 1),
                 Item("C", (100, 100, 100), 1), Item("D", (100, 100, 100), 1)]:
        p = place(item, state)
        assert p is not None
        state.add(p)
    for q in state.points:
        assert is_live(q, carton, state.placements)


def test_pruning_recovers_stacking_that_v1_loses():
    """The Phase 2 acceptance case, in miniature.

    Enough small items that v1's candidate window fills with dead low points
    while live high points wait behind them. greedy2 must use strictly fewer
    cartons. This is the test that fails if pruning is reverted.
    """
    items = [Item(f"S{i}", (40, 40, 40), 10) for i in range(400)]
    box = [Carton("L", (450, 350, 300), 380)]
    a = v1_pack(items, box, time_budget_ms=1200, seed=1)
    b = greedy2_pack(items, box, time_budget_ms=1200, seed=1)
    assert b.carton_count < a.carton_count
    placed = sum(len(c.placements) for c in b.cartons)
    assert placed == len(items), "no item may be dropped to win on count"


def test_fill_carton_returns_the_same_placements_the_state_holds():
    """fill_carton is the only public way in, so its PackedCarton and the
    state that built it must not drift apart."""
    items = [Item(f"S{i}", (60, 50, 40), 10) for i in range(30)]
    pc, left = fill_carton(CARTONS[2], items)
    state = _fill_checking_cache(CARTONS[2], items)
    assert [p.pos for p in pc.placements] == [p.pos for p in state.placements]
    assert len(pc.placements) + len(left) == len(items)
