"""Further Optimise: which cartons are tried, and in what order. Needs no OR-Tools.

CP-SAT is replaced by a stand-in that records which cartons it was asked about,
so these tests check the search order and the stopping rule, and run in CI.
"""
import pytest

from fitsolver.domain import Carton, Item, Placement
from fitsolver.greedy2 import optimise
from fitsolver.greedy2.pack import pack

# Three 100 mm cubes. M holds two (stacked), so greedy2 picks L, which holds all three.
ITEMS = [Item(f"c{k}", (100, 100, 100), 100) for k in range(3)]
S = Carton("S", (110, 110, 110), 0)
M = Carton("M", (110, 110, 220), 0)
L = Carton("L", (400, 400, 400), 0)


@pytest.fixture
def stand_in(monkeypatch):
    """Replace CP-SAT. Returns (asked, fits): cartons asked about, and which to accept."""
    asked: list[str] = []
    fits: set[str] = set()

    def fake_one_carton(cp_model, items, carton, seconds, seed):
        asked.append(carton.sku)
        if carton.sku not in fits:
            return None
        return [Placement(item=i, pos=(0, 0, 0), dims=i.dims, orientation=0, sequence=n)
                for n, i in enumerate(items)]

    monkeypatch.setattr(optimise, "_cp_model", lambda: object())
    monkeypatch.setattr(optimise, "_one_carton", fake_one_carton)
    return asked, fits


def test_greedy2_alone_picks_the_large_carton():
    assert [pc.carton.sku for pc in pack(ITEMS, [S, M, L], 1200, 1).cartons] == ["L"]


def test_next_size_down_is_tried_first_and_the_search_stops_there(stand_in):
    asked, fits = stand_in
    fits.update({"M", "S"})
    sol = optimise.further_optimise(ITEMS, [S, M, L], 1200, 1)
    assert asked == ["M"]                      # S is never tried once M fits
    assert [pc.carton.sku for pc in sol.cartons] == ["M"]
    assert sol.tier == 2


def test_a_smaller_carton_is_tried_when_the_next_size_down_does_not_fit(stand_in):
    asked, fits = stand_in
    fits.add("S")
    sol = optimise.further_optimise(ITEMS, [S, M, L], 1200, 1)
    assert asked == ["M", "S"]
    assert [pc.carton.sku for pc in sol.cartons] == ["S"]


def test_nothing_fits_returns_greedy2(stand_in):
    asked, _ = stand_in
    sol = optimise.further_optimise(ITEMS, [S, M, L], 1200, 1)
    assert asked == ["M", "S"]
    assert [pc.carton.sku for pc in sol.cartons] == ["L"] and sol.tier == 1


def test_without_ortools_greedy2_is_returned(monkeypatch):
    monkeypatch.setattr(optimise, "_cp_model", lambda: None)
    sol = optimise.further_optimise(ITEMS, [S, M, L], 1200, 1)
    assert [pc.carton.sku for pc in sol.cartons] == ["L"] and sol.tier == 1
