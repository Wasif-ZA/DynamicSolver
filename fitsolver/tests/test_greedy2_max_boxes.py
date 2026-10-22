"""maximum_boxes: a carton type may be used at most N times per solution."""
from collections import Counter

import pytest
from hypothesis import given, settings
from hypothesis import strategies as st

from fitsolver import io
from fitsolver.domain import Carton, Item, PackedCarton
from fitsolver.engine import solve
from fitsolver.greedy2.pack import caps_left, pack

MED = (400, 400, 400)
BIG = (400, 400, 450)


def _items(n, dims=(380, 380, 200), dg=None, prefix="I"):
    return [Item(ref=f"{prefix}{k}", dims=dims, mass=1000, dg_class=dg)
            for k in range(n)]


def _use(sol):
    return Counter(pc.carton.sku for pc in sol.cartons)


def _placed(sol):
    return {p.item.ref for pc in sol.cartons for p in pc.placements}


def _conserved(sol, n):
    return sum(len(pc.placements) for pc in sol.cartons) + len(sol.rejects) == n


def test_teammate_repro_cap_of_two_is_respected():
    cartons = [Carton("MED", MED, 0, maximum_boxes=2), Carton("BIG", BIG, 0)]
    sol = pack(_items(12), cartons, 1200, 0)
    assert _use(sol)["MED"] == 2
    assert not sol.rejects


def test_cap_is_shared_across_conflict_groups():
    items = _items(2, dg="3", prefix="A") + _items(2, dg="8", prefix="B")
    cartons = [Carton("MED", MED, 0, maximum_boxes=1), Carton("BIG", BIG, 0)]
    sol = pack(items, cartons, 1200, 0)
    assert _use(sol)["MED"] <= 1
    assert not sol.rejects


def test_left_over_items_are_rejected_not_lost():
    cartons = [Carton("MED", MED, 0, maximum_boxes=1)]
    sol = pack(_items(5), cartons, 1200, 0)
    assert _use(sol)["MED"] == 1
    assert {r.reason_code for r in sol.rejects} == {"UNPLACEABLE"}
    assert all("maximum_boxes" in r.message for r in sol.rejects)
    assert _conserved(sol, 5)


def test_used_up_type_does_not_starve_items_behind_the_window():
    big = [Item(ref=f"B{k}", dims=(390, 390, 440), mass=1000) for k in range(300)]
    small = [Item(ref=f"S{k}", dims=(50, 50, 50), mass=10) for k in range(10)]
    cartons = [Carton("BIGONLY", BIG, 0, maximum_boxes=1),
               Carton("SML", (60, 60, 60), 0)]
    sol = pack(big + small, cartons, 1200, 0)
    assert all(f"S{k}" in _placed(sol) for k in range(10))
    assert _conserved(sol, 310)


def test_type_used_up_by_one_group_does_not_starve_the_next_group():
    # Group A (DG 3) uses the only BIGONLY. Group B (DG 8) then starts with 300
    # items that only fit BIGONLY, ahead of 10 small ones that fit SML.
    # A0's first dimension is the smallest in the order, so canonical sorting
    # creates, and packs, group A first.
    a = [Item(ref="A0", dims=(45, 390, 440), mass=1000, dg_class="3")]
    b_big = [Item(ref=f"B{k}", dims=(390, 390, 440), mass=1000, dg_class="8")
             for k in range(300)]
    b_small = [Item(ref=f"S{k}", dims=(50, 50, 50), mass=10, dg_class="8")
               for k in range(10)]
    cartons = [Carton("BIGONLY", BIG, 0, maximum_boxes=1),
               Carton("SML", (60, 60, 60), 0)]
    sol = pack(a + b_big + b_small, cartons, 1200, 0)
    assert _use(sol)["BIGONLY"] == 1
    assert all(f"S{k}" in _placed(sol) for k in range(10))
    assert _conserved(sol, 311)


def test_repack_counts_the_cartons_it_keeps():
    # Found by random search: without the cap in the repack move, M (cap 1)
    # came back used twice, because repacking the tail started a fresh count.
    dims_mass = [((300, 215, 184), 607), ((214, 242, 147), 2991),
                 ((293, 139, 171), 425), ((197, 210, 179), 2100),
                 ((148, 149, 95), 278), ((77, 132, 116), 1855),
                 ((228, 182, 95), 903)]
    items = [Item(ref=f"i{k}", dims=d, mass=m) for k, (d, m) in enumerate(dims_mass)]
    cartons = [Carton("S", (200, 150, 100), 0),
               Carton("M", (350, 260, 220), 0, maximum_boxes=1),
               Carton("L", (500, 400, 300), 0, maximum_boxes=0)]
    sol = pack(items, cartons, 1200, 1)
    assert _use(sol)["M"] <= 1
    assert _use(sol)["L"] == 0
    assert _conserved(sol, len(items))


def test_caps_left_counts_only_limited_types():
    a, b = Carton("A", MED, 0, maximum_boxes=3), Carton("B", BIG, 0)
    kept = [PackedCarton(a), PackedCarton(a), PackedCarton(b)]
    assert caps_left(kept, [a, b]) == [1, None]


def test_zero_means_never_use():
    cartons = [Carton("MED", MED, 0, maximum_boxes=0), Carton("BIG", BIG, 0)]
    sol = pack(_items(4), cartons, 1200, 0)
    assert _use(sol)["MED"] == 0
    assert not sol.rejects


def test_zero_on_the_only_fitting_type_rejects_with_the_limit_reason():
    cartons = [Carton("MED", MED, 0, maximum_boxes=0)]
    sol = pack(_items(3), cartons, 1200, 0)
    assert not sol.cartons
    assert {r.reason_code for r in sol.rejects} == {"UNPLACEABLE"}


def test_contract_field_reaches_the_solver():
    # The shape apps/portal/backend/app/solver_adapter.py sends.
    req = {"order_id": "x",
           "items": [{"item_ref": "I", "dims": [380, 380, 200], "mass": 1000,
                      "quantity": 12}],
           "cartons": [{"sku": "MED", "inner_dims": list(MED), "tare_mass": 0,
                        "max_contents_mass": 20000, "maximum_boxes": 2},
                       {"sku": "BIG", "inner_dims": list(BIG), "tare_mass": 0,
                        "max_contents_mass": 20000, "maximum_boxes": None}]}
    doc = solve(req)
    assert Counter(c["sku"] for c in doc["cartons"])["MED"] == 2
    assert not doc["rejects"]


@pytest.mark.parametrize("bad", [-1, 2.5, True, "2"])
def test_invalid_maximum_boxes_is_a_request_error(bad):
    req = {"order_id": "x",
           "items": [{"item_ref": "I", "dims": [1, 1, 1], "mass": 1}],
           "cartons": [{"sku": "M", "inner_dims": [4, 4, 4], "tare_mass": 0,
                        "maximum_boxes": bad}]}
    with pytest.raises(io.RequestError):
        solve(req)


def test_no_limits_gives_the_same_layout_as_before():
    # Unlimited and "limit far above what is used" must pack identically.
    items = _items(30) + [Item(ref=f"s{k}", dims=(100, 120, 90), mass=300)
                          for k in range(40)]
    free = [Carton("MED", MED, 0), Carton("BIG", BIG, 0)]
    high = [Carton("MED", MED, 0, maximum_boxes=999),
            Carton("BIG", BIG, 0, maximum_boxes=999)]
    def layout(sol):
        return [(pc.carton.sku, [(p.item.ref, p.pos, p.dims) for p in pc.placements])
                for pc in sol.cartons]

    assert layout(pack(items, free, 1200, 0)) == layout(pack(items, high, 1200, 0))


@settings(max_examples=60, deadline=None)
@given(n=st.integers(1, 14),
       caps=st.lists(st.one_of(st.none(), st.integers(0, 3)), min_size=3, max_size=3),
       two_groups=st.booleans(), seed=st.integers(1, 50))
def test_no_type_ever_exceeds_its_cap(n, caps, two_groups, seed):
    items = _items(n) if not two_groups else (
        _items(n // 2 + 1, dg="3", prefix="A") + _items(n // 2, dg="8", prefix="B"))
    cartons = [Carton("S", (200, 200, 220), 0, maximum_boxes=caps[0]),
               Carton("A", MED, 0, maximum_boxes=caps[1]),
               Carton("B", BIG, 0, maximum_boxes=caps[2])]
    sol = pack(items, cartons, 1200, seed)
    use = _use(sol)
    for c in cartons:
        assert c.maximum_boxes is None or use[c.sku] <= c.maximum_boxes
    assert _conserved(sol, len(items))
