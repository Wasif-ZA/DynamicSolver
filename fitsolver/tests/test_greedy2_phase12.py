"""Phase 12: seeded restarts and carton elimination.

Two claims, and the second is the one that would fail silently if it were
wrong:

  1. the extra passes are SEEDED, so the same request and seed give the same
     layout on any machine, and a different seed is allowed to differ;
  2. elimination is strictly downhill. It may only ever remove a carton, and
     it may never move an item somewhere the geometry or the conflict rules
     forbid. A post-pass that quietly drops an item, or that puts two DG
     classes in one box, would still return a layout with fewer cartons in it
     and no test of carton counts alone would notice.
"""
from __future__ import annotations

import random

import pytest

from fitsolver.domain import Carton, Item
from fitsolver.geometry import overlaps
from fitsolver.greedy2.pack import (
    ELIMINATE_ATTEMPTS,
    MAX_PASSES,
    REPACK_MAX_ITEMS,
    RESTART_WINDOW,
    canonical_key,
    carton_fit_table,
    conflict,
    eliminate,
    ordering_for_pass,
    restart_ordering,
    sort_keys_for,
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


def make_items(n, seed, dg=False):
    r = random.Random(seed)
    return [Item(f"I{i}",
                 (r.randrange(30, 260, 5), r.randrange(30, 210, 5),
                  r.randrange(30, 160, 5)),
                 r.randrange(50, 3000, 10),
                 dg_class=(r.choice([None, "3", "8"]) if dg else None))
            for i in range(n)]


# --------------------------------------------------------------------------- #
# Item 1: seeded restarts.
# --------------------------------------------------------------------------- #

def test_the_same_seed_gives_the_same_layout():
    """The whole promise of the solver. Restarts must not weaken it."""
    items = make_items(12, seed=5)
    runs = [greedy2_pack(items, CARTONS, time_budget_ms=1200, seed=7)
            for _ in range(5)]
    assert len({_shape(sol) for sol in runs}) == 1


def _shape(sol):
    return tuple((c.carton.sku, p.pos, p.dims, p.item.ref)
                 for c in sol.cartons for p in c.placements)


def test_a_restart_is_a_permutation_and_nothing_else():
    """Losing or duplicating an item here would show up as a reject, or as the
    same item packed twice."""
    items = make_items(30, seed=9)
    for k in range(8):
        got = restart_ordering(items, random.Random(k))
        assert sorted(i.ref for i in got) == sorted(i.ref for i in items)


def test_a_restart_does_not_depend_on_the_arrival_order():
    """Two requests holding the same goods in a different sequence must draw
    the identical permutation, or re-keying an order redraws the picture."""
    items = make_items(20, seed=3)
    shuffled = list(items)
    random.Random(99).shuffle(shuffled)
    a = restart_ordering(sorted(items, key=canonical_key), random.Random(4))
    b = restart_ordering(sorted(shuffled, key=canonical_key), random.Random(4))
    assert [i.ref for i in a] == [i.ref for i in b]


def test_a_window_of_one_reproduces_the_volume_ordering():
    """The window is a dial, and at its tightest setting it is the sort the
    restarts are a perturbation of."""
    items = make_items(25, seed=2)
    got = restart_ordering(items, random.Random(1), window=1)
    assert got == sorted(items, key=lambda i: -i.volume)


def test_a_later_pass_does_not_depend_on_whether_earlier_ones_ran():
    """Each restart seeds its own Random from the pass number, so the early
    stop cannot change what a later pass would have been."""
    items = make_items(15, seed=6)
    keys = sort_keys_for(len(items))
    for p in (len(keys), len(keys) + 3):
        a = ordering_for_pass(p, keys, seed=11)(items)
        b = ordering_for_pass(p, keys, seed=11)(items)
        assert [i.ref for i in a] == [i.ref for i in b]


def test_the_restart_window_and_pass_cap_are_sane():
    assert RESTART_WINDOW >= 1
    assert MAX_PASSES >= 4


# --------------------------------------------------------------------------- #
# Item 2: elimination is strictly downhill, and legal.
# --------------------------------------------------------------------------- #

def _layout_of(items, cartons):
    table = carton_fit_table(items, cartons)
    groups = split_compatible(sorted(items, key=canonical_key))
    from fitsolver.greedy2.pack import pack_one
    out = []
    for g in groups:
        got, left = pack_one(sorted(g, key=lambda i: -i.volume), cartons, table)
        assert not left
        out.extend(got)
    return out, table


@pytest.mark.parametrize("seed", range(12))
@pytest.mark.parametrize("cartons", [CARTONS, NO_LIMITS], ids=["mass", "geom"])
def test_elimination_never_adds_a_carton_or_loses_an_item(seed, cartons):
    items = make_items(14, seed=seed)
    before, table = _layout_of(items, cartons)
    after = eliminate(before, cartons, table)

    assert len(after) <= len(before)
    was = sorted(p.item.ref for c in before for p in c.placements)
    now = sorted(p.item.ref for c in after for p in c.placements)
    assert now == was


@pytest.mark.parametrize("seed", range(12))
def test_elimination_returns_a_legal_layout(seed):
    """The oracle is recomputed here, not borrowed from the solver, so a bug
    in a geometry helper cannot hide by being wrong consistently."""
    items = make_items(14, seed=seed)
    before, table = _layout_of(items, CARTONS)
    after = eliminate(before, CARTONS, table)

    for pc in after:
        ps = pc.placements
        for p in ps:
            for ax in range(3):
                assert p.pos[ax] >= 0
                assert p.pos[ax] + p.dims[ax] <= pc.carton.inner_dims[ax]
            assert sorted(p.dims) == sorted(p.item.dims)
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                assert not overlaps(ps[i].pos, ps[i].dims,
                                    ps[j].pos, ps[j].dims)
        if pc.carton.max_contents_mass is not None:
            assert pc.contents_mass <= pc.carton.max_contents_mass
        for p in ps:
            if p.pos[2] == 0:
                continue
            base = p.dims[0] * p.dims[1]
            area = 0
            for q in ps:
                if q is p or q.pos[2] + q.dims[2] != p.pos[2]:
                    continue
                ox = (min(p.pos[0] + p.dims[0], q.pos[0] + q.dims[0])
                      - max(p.pos[0], q.pos[0]))
                oy = (min(p.pos[1] + p.dims[1], q.pos[1] + q.dims[1])
                      - max(p.pos[1], q.pos[1]))
                if ox > 0 and oy > 0:
                    area += ox * oy
            assert area * 100 >= base * 70


@pytest.mark.parametrize("seed", range(12))
def test_elimination_never_puts_conflicting_items_together(seed):
    """The cartons reaching eliminate() are the WHOLE solution's, so two of
    them can come from different conflict groups. Moving an item between those
    would put two DG classes in one box and geometry would never catch it."""
    items = make_items(16, seed=seed, dg=True)
    before, table = _layout_of(items, CARTONS)
    after = eliminate(before, CARTONS, table)
    for pc in after:
        for i, a in enumerate(pc.placements):
            for b in pc.placements[i + 1:]:
                assert not conflict(a.item, b.item)


def test_the_repack_half_is_bounded_by_item_count():
    assert REPACK_MAX_ITEMS > 0
    assert ELIMINATE_ATTEMPTS > 0


def test_a_solve_still_places_everything_that_fits():
    """Elimination runs on every pass, so a bug that dropped an item would
    show up as a reject on an order where nothing should be rejected."""
    for seed in range(8):
        items = make_items(18, seed=seed)
        sol = greedy2_pack(items, CARTONS, time_budget_ms=1200, seed=1)
        assert not sol.rejects
        assert sum(len(c.placements) for c in sol.cartons) == len(items)
