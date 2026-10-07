"""Property-based invariants. These are the tests that matter.

For any random order: no overlaps, nothing protrudes, weight limits hold,
every item is supported, no conflicting pair shares a carton, every input
item is either placed exactly once or rejected exactly once, and the same
request always produces the same document (determinism).
"""
from __future__ import annotations

from hypothesis import given, settings
from hypothesis import strategies as st

from fitsolver.domain import Carton, Item
from fitsolver.engine import solve
from fitsolver.geometry import overlaps
from fitsolver.greedy2.pack import pack

dims_st = st.tuples(st.integers(10, 400), st.integers(10, 400),
                    st.integers(10, 400))

item_st = st.builds(
    Item,
    ref=st.uuids().map(lambda u: f"SKU-{u.hex[:6]}"),
    dims=dims_st,
    mass=st.integers(1, 5000),
    allowed_rotations=st.sampled_from(["any", "upright", "fixed"]),
    dg_class=st.sampled_from([None, None, None, "3", "8"]),
)

CARTONS = [
    Carton(sku="S", inner_dims=(220, 160, 120), tare_mass=120,
           max_contents_mass=5000),
    Carton(sku="M", inner_dims=(320, 240, 180), tare_mass=210,
           max_contents_mass=12000),
    Carton(sku="L", inner_dims=(450, 350, 300), tare_mass=380,
           max_contents_mass=20000),
]


@settings(max_examples=150, deadline=None)
@given(items=st.lists(item_st, min_size=1, max_size=12))
def test_layout_invariants(items):
    sol = pack(items, CARTONS, time_budget_ms=50, seed=42)

    placed_count = 0
    for pc in sol.cartons:
        ps = pc.placements
        placed_count += len(ps)

        # nothing protrudes
        for p in ps:
            for ax in range(3):
                assert p.pos[ax] >= 0
                assert p.pos[ax] + p.dims[ax] <= pc.carton.inner_dims[ax]

        # no two items overlap
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                assert not overlaps(ps[i].pos, ps[i].dims,
                                    ps[j].pos, ps[j].dims)

        # weight limit holds
        if pc.carton.max_contents_mass is not None:
            assert pc.contents_mass <= pc.carton.max_contents_mass

        # rotated dims are a permutation of base dims
        for p in ps:
            assert sorted(p.dims) == sorted(p.item.dims)

        # upright/fixed items keep their height axis
        for p in ps:
            if p.item.allowed_rotations in ("upright", "fixed"):
                assert p.dims[2] == p.item.dims[2]

        # every item is supported: floor or >=70% base on tops of others
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

        # no conflicting pair shares a carton
        for i in range(len(ps)):
            for j in range(i + 1, len(ps)):
                a, b = ps[i].item, ps[j].item
                assert b.ref not in a.incompatible_with
                assert a.ref not in b.incompatible_with
                if a.dg_class and b.dg_class:
                    assert a.dg_class == b.dg_class

    # conservation: every item placed once or rejected once
    assert placed_count + len(sol.rejects) == len(items)


@settings(max_examples=30, deadline=None)
@given(items=st.lists(item_st, min_size=1, max_size=8))
def test_determinism(items):
    payload = {
        "order_id": "T1",
        "time_budget_ms": 30,
        "items": [{"item_ref": i.ref, "dims": list(i.dims), "mass": i.mass,
                   "allowed_rotations": i.allowed_rotations,
                   "dg_class": i.dg_class} for i in items],
        "cartons": [{"sku": c.sku, "inner_dims": list(c.inner_dims),
                     "tare_mass": c.tare_mass,
                     "max_contents_mass": c.max_contents_mass}
                    for c in CARTONS],
    }
    a, b = solve(payload), solve(payload)
    for doc in (a, b):
        doc["solution_id"] = ""  # uuid differs by design
        doc["solver"]["elapsed_ms"] = 0  # wall clock differs by design
    assert a == b
