"""Scaling behaviour and the synchronous ceiling.

These tests document, and guard, the limits found by measurement:
  - correctness (conservation, no overlap) holds at every size tested
  - carton count grows linearly, ~19 items/carton, at every size
  - wall time stays inside the budget up to ~300 items; past that the
    solver deliberately overruns rather than falsely rejecting items

The last point is a policy decision, not a bug: a request that cannot be
solved inside its budget gets a correct late answer, never a wrong prompt
one. Orders above SYNC_CEILING belong on the async batch path.
"""
from __future__ import annotations

import random
import time

import pytest

from fitsolver.domain import Carton, Item
from fitsolver.geometry import overlaps
from fitsolver.greedy2.pack import pack

SYNC_CEILING = 300   # items; beyond this, route to the batch endpoint

CARTONS = [
    Carton("S", (220, 160, 120), 120, 5000),
    Carton("M", (320, 240, 180), 210, 12000),
    Carton("L", (450, 350, 300), 380, 20000),
    Carton("XL", (600, 400, 400), 520, 30000),
]


def make_items(n: int, seed: int = 1) -> list[Item]:
    r = random.Random(seed)
    return [Item(ref=f"S{i}",
                 dims=(r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                       r.randrange(30, 160, 5)),
                 mass=r.randrange(50, 3000, 10))
            for i in range(n)]


@pytest.mark.parametrize("n", [1, 2, 5, 17, 50, 100, 250, 500, 1000])
def test_conservation_at_scale(n):
    """Every item is placed exactly once or rejected exactly once."""
    items = make_items(n)
    sol = pack(items, CARTONS, time_budget_ms=300, seed=7)
    placed = sum(len(c.placements) for c in sol.cartons)
    assert placed + len(sol.rejects) == n


@pytest.mark.parametrize("n", [50, 250, 1000])
def test_no_overlap_at_scale(n):
    """Geometry stays correct when the budget forces a fast-path answer."""
    sol = pack(make_items(n), CARTONS, time_budget_ms=300, seed=7)
    for pc in sol.cartons:
        ps = pc.placements
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                assert not overlaps(ps[i].pos, ps[i].dims,
                                    ps[j].pos, ps[j].dims)
            for ax in range(3):
                assert ps[i].pos[ax] >= 0
                assert (ps[i].pos[ax] + ps[i].dims[ax]
                        <= pc.carton.inner_dims[ax])


@pytest.mark.parametrize("n", [100, 400, 1600])
def test_carton_count_grows_linearly(n):
    """Guards the regression where fast-mode carton selection collapsed to
    first-fit-smallest: 800 items produced 166 cartons instead of 42."""
    sol = pack(make_items(n), CARTONS, time_budget_ms=300, seed=7)
    placed = sum(len(c.placements) for c in sol.cartons)
    assert placed / sol.carton_count > 12, "carton selection has degraded"


def test_budget_honoured_below_sync_ceiling():
    """Up to SYNC_CEILING items, a 1.5 s budget is respected with headroom."""
    items = make_items(SYNC_CEILING)
    t = time.monotonic()
    pack(items, CARTONS, time_budget_ms=1500, seed=7)
    assert time.monotonic() - t < 2.0


def test_single_item_and_empty_edge_cases():
    sol = pack(make_items(1), CARTONS, time_budget_ms=100, seed=7)
    assert sol.carton_count == 1
    sol = pack([], CARTONS, time_budget_ms=100, seed=7)
    assert sol.carton_count == 0 and not sol.rejects
