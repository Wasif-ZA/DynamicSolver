"""Phase 6: the contact-area score, and the ablation that decided against it.

The conclusion of this phase is "do not use it", and that conclusion is only
worth anything if the score being rejected is the right score. A function that
always returned zero would also have "shown no gain". So the arithmetic is
checked against hand-worked cases first, and only then is the flag's effect
measured.
"""
from __future__ import annotations

import pytest

from fitsolver.domain import Carton, Item, Placement
from fitsolver.greedy2.geometry import contact_area
from fitsolver.greedy2.pack import CONTACT_SCORING

CARTON = Carton("T", (100, 100, 100), 0)


def placed(pos, dims, ref="P") -> Placement:
    return Placement(item=Item(ref, dims, 1), pos=pos, dims=dims,
                     orientation=0, sequence=0)


# --------------------------------------------------------------------------- #
# Walls and floor.
# --------------------------------------------------------------------------- #

def test_a_box_in_the_origin_corner_touches_three_walls():
    # 10x20x30 at the origin: floor 10*20, the x=0 wall 20*30, the y=0 wall
    # 10*30. Nothing else is in reach of a 100 mm carton.
    assert contact_area((0, 0, 0), (10, 20, 30), CARTON, []) == (
        10 * 20 + 20 * 30 + 10 * 30)


def test_a_box_filling_the_carton_touches_all_six_walls():
    assert contact_area((0, 0, 0), (100, 100, 100), CARTON, []) == 6 * 100 * 100


def test_a_box_floating_in_the_middle_touches_nothing():
    assert contact_area((10, 10, 10), (20, 20, 20), CARTON, []) == 0


def test_the_far_wall_counts_as_much_as_the_near_one():
    near = contact_area((0, 10, 10), (10, 20, 30), CARTON, [])
    far = contact_area((90, 10, 10), (10, 20, 30), CARTON, [])
    assert near == far == 20 * 30


def test_one_millimetre_short_of_a_wall_scores_nothing():
    """Exact integer comparison, no epsilon. A box that nearly touches has
    stranded a millimetre of space and should not be rewarded for it.

    Both directions: a mutation that relaxes only the far-wall comparison is
    invisible if the near wall is the only one tested.
    """
    assert contact_area((1, 10, 10), (10, 20, 30), CARTON, []) == 0       # near
    assert contact_area((89, 10, 10), (10, 20, 30), CARTON, []) == 0      # far
    assert contact_area((10, 1, 10), (20, 10, 30), CARTON, []) == 0
    assert contact_area((10, 89, 10), (20, 10, 30), CARTON, []) == 0
    assert contact_area((10, 10, 1), (20, 30, 10), CARTON, []) == 0
    assert contact_area((10, 10, 89), (20, 30, 10), CARTON, []) == 0


@pytest.mark.parametrize("axis", [0, 1, 2])
def test_each_axis_contributes_both_of_its_walls(axis):
    """Six walls, six separate comparisons, any of which could be wrong on its
    own. Each is pinned by placing a thin slab flush to it."""
    dims = [20, 20, 20]
    dims[axis] = 100                      # spans the carton on this axis
    expected_face = (dims[(axis + 1) % 3] * dims[(axis + 2) % 3])
    pos = [10, 10, 10]
    pos[axis] = 0
    # Flush on both walls of `axis`, and nothing else is in reach.
    assert contact_area(tuple(pos), tuple(dims), CARTON, []) == 2 * expected_face


# --------------------------------------------------------------------------- #
# Neighbours.
# --------------------------------------------------------------------------- #

def test_two_boxes_flush_along_x_share_their_whole_face():
    neighbour = placed((50, 0, 0), (50, 40, 30))
    # Our box ends exactly where the neighbour starts, and they line up fully
    # on y and z, so the shared face is 40*30. Plus floor, x=0 and y=0 walls.
    area = contact_area((0, 0, 0), (50, 40, 30), CARTON, [neighbour])
    walls = 50 * 40 + 40 * 30 + 50 * 30
    assert area == walls + 40 * 30


def test_a_stacked_box_shares_the_footprint_it_sits_on():
    floor_box = placed((0, 0, 0), (40, 40, 20))
    area = contact_area((0, 0, 20), (40, 40, 20), CARTON, [floor_box])
    walls = 40 * 20 + 40 * 20          # x=0 and y=0 walls only, not the floor
    assert area == walls + 40 * 40


def test_partial_overlap_shares_only_the_overlapping_part():
    neighbour = placed((50, 0, 0), (50, 10, 30))
    area = contact_area((0, 0, 0), (50, 40, 30), CARTON, [neighbour])
    walls = 50 * 40 + 40 * 30 + 50 * 30
    assert area == walls + 10 * 30, "only the 10 mm of shared y should count"


def test_a_gap_between_neighbours_scores_nothing():
    neighbour = placed((51, 0, 0), (49, 40, 30))
    area = contact_area((0, 0, 0), (50, 40, 30), CARTON, [neighbour])
    assert area == 50 * 40 + 40 * 30 + 50 * 30, "the 1 mm gap must not count"


def test_diagonal_neighbours_do_not_touch():
    """Meeting only along an edge or at a corner is not a shared face."""
    neighbour = placed((50, 50, 0), (50, 50, 30))
    area = contact_area((0, 0, 0), (50, 50, 30), CARTON, [neighbour])
    assert area == 50 * 50 + 50 * 30 + 50 * 30


def test_contact_accumulates_over_several_neighbours():
    right = placed((50, 0, 0), (50, 40, 30), "R")
    above = placed((0, 0, 30), (50, 40, 30), "A")
    area = contact_area((0, 0, 0), (50, 40, 30), CARTON, [right, above])
    walls = 50 * 40 + 40 * 30 + 50 * 30
    assert area == walls + 40 * 30 + 50 * 40


def test_the_score_is_an_integer():
    """Millimetres and grams, no floats anywhere near this."""
    assert isinstance(contact_area((0, 0, 0), (7, 11, 13), CARTON, []), int)


# --------------------------------------------------------------------------- #
# The flag itself.
# --------------------------------------------------------------------------- #

def test_scoring_is_off_by_default():
    """The ablation says it costs cartons and time on this workload set. If
    this assertion is ever changed, bench/ablate_contact.py must be re-run and
    its table in greedy2/pack.py updated to justify the change."""
    assert CONTACT_SCORING is False


@pytest.mark.parametrize("scoring", [False, True])
def test_every_invariant_still_holds_with_scoring_either_way(scoring):
    """Scoring changes which position is chosen, never whether it is legal."""
    import fitsolver.greedy2.pack as mod
    from fitsolver.greedy2.geometry import overlaps

    boxes = [Carton("S", (220, 160, 120), 120, 5000),
             Carton("L", (450, 350, 300), 380, 20000)]
    items = [Item(f"S{i}", (40 + (i % 6) * 25, 30 + (i % 4) * 30,
                            20 + (i % 5) * 20), 100 + i * 7)
             for i in range(60)]

    before = mod.CONTACT_SCORING
    mod.CONTACT_SCORING = scoring
    try:
        sol = mod.pack(items, boxes, time_budget_ms=1200, seed=1)
    finally:
        mod.CONTACT_SCORING = before

    placed_n = 0
    for pc in sol.cartons:
        ps = pc.placements
        placed_n += len(ps)
        for i, a in enumerate(ps):
            for ax in range(3):
                assert a.pos[ax] >= 0
                assert a.pos[ax] + a.dims[ax] <= pc.carton.inner_dims[ax]
            for b in ps[i + 1:]:
                assert not overlaps(a.pos, a.dims, b.pos, b.dims)
        assert pc.contents_mass <= pc.carton.max_contents_mass
    assert placed_n + len(sol.rejects) == len(items)
