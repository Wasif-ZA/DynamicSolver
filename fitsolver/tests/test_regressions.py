"""Bugs found by audit, each with the input that produced it.

Every test here failed before its fix. They guard the two guarantees the
project makes loudest: never falsely reject goods that fit, and never turn
one bad item into a whole-request failure.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fitsolver import io
from fitsolver.api import app
from fitsolver.domain import Carton, Item
from fitsolver.engine import solve
from fitsolver.io import MAX_UNITS
from fitsolver.pack import CHUNK, fits_any_carton, pack

SMALL = Carton("S", (200, 200, 200), 0)


@pytest.mark.parametrize("n_giants", [CHUNK - 1, CHUNK, CHUNK + 50])
def test_unplaceable_items_never_starve_placeable_ones(n_giants):
    """A CHUNK-sized run of items no carton can hold used to abandon every
    item behind it. 120 giants + 5 small items returned 125 rejects and zero
    cartons; the 5 fit trivially.

    The five smalls also have to land in ONE carton. Below the window size
    the old code placed them but spread them over five cartons, because the
    giants occupied every window slot ahead of them.
    """
    giants = [Item(f"G{i}", (500, 500, 500), 100) for i in range(n_giants)]
    smalls = [Item(f"S{i}", (50, 50, 50), 10) for i in range(5)]

    sol = pack(giants + smalls, [SMALL], time_budget_ms=1000, seed=1)

    placed = [p.item.ref for c in sol.cartons for p in c.placements]
    assert sorted(placed) == sorted(f"S{i}" for i in range(5))
    assert sorted(r.item_ref for r in sol.rejects) == sorted(
        f"G{i}" for i in range(n_giants))
    assert sol.carton_count == 1, "the five smalls all fit in one carton"


def test_conservation_counts_placements_not_just_rejects():
    """Conservation alone cannot catch this bug: the old code returned 0
    placed + 125 rejected, which still sums to 125. The placed count is what
    distinguishes a correct rejection from a false one."""
    giants = [Item(f"G{i}", (500, 500, 500), 100) for i in range(CHUNK)]
    smalls = [Item(f"S{i}", (50, 50, 50), 10) for i in range(5)]
    sol = pack(giants + smalls, [SMALL], time_budget_ms=1000, seed=1)
    placed = sum(len(c.placements) for c in sol.cartons)
    assert placed == 5
    assert placed + len(sol.rejects) == CHUNK + 5


def test_pack_filters_unplaceable_items_itself():
    """Guards the integration, not just the helper: reverting the filter in
    pack() while keeping fits_any_carton would leave the helper test green."""
    giants = [Item(f"G{i}", (500, 500, 500), 100) for i in range(CHUNK)]
    small = Item("S0", (50, 50, 50), 10)
    sol = pack([*giants, small], [SMALL], time_budget_ms=1000, seed=1)
    assert [p.item.ref for c in sol.cartons for p in c.placements] == ["S0"]


def test_fits_any_carton_respects_mass_and_rotation():
    tiny_limit = Carton("L", (500, 500, 500), 0, max_contents_mass=100)
    assert not fits_any_carton(Item("HEAVY", (10, 10, 10), 5000), [tiny_limit])
    # Fits ONLY when rotated: 190 exceeds the 50mm height, so this is false
    # unless the long axis is turned onto the floor.
    flat = Carton("F", (200, 200, 50), 0)
    assert fits_any_carton(Item("LONG", (10, 10, 190), 1), [flat])
    assert not fits_any_carton(
        Item("LONG", (10, 10, 190), 1, allowed_rotations="fixed"), [flat])


def _one_item(**overrides) -> dict:
    item = {"item_ref": "X", "dims": [50, 50, 50], "mass": 10}
    item.update(overrides)
    return {"order_id": "ORD", "items": [item],
            "cartons": [{"sku": "B", "inner_dims": [200, 200, 200],
                         "tare_mass": 0}]}


@pytest.mark.parametrize("bad_mass", ["heavy", None, [1], {}])
def test_unparseable_mass_is_a_reject_not_a_crash(bad_mass):
    """int("heavy") raised an uncaught ValueError that surfaced as HTTP 500.
    The dims path was guarded; mass was not."""
    doc = solve(_one_item(mass=bad_mass))
    assert [r["reason_code"] for r in doc["rejects"]] == ["MISSING_MASS"]


@pytest.mark.parametrize("bad_qty", [0, -3, "two", None])
def test_bad_quantity_is_rejected_not_silently_dropped(bad_qty):
    """quantity=0 expanded to zero items: the line was neither placed nor
    rejected, breaking the contract's conservation invariant."""
    doc = solve(_one_item(quantity=bad_qty))
    assert [r["reason_code"] for r in doc["rejects"]] == ["INVALID_QUANTITY"]


def test_valid_quantity_still_expands():
    doc = solve(_one_item(quantity=4))
    ids = [p["placement_id"] for c in doc["cartons"] for p in c["placements"]]
    assert len(ids) == 4
    assert len(set(ids)) == 4, "placement_id must be unique within a carton"


def test_malformed_json_body_is_400_not_500():
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/v1/solve", content=b"{not json",
                    headers={"content-type": "application/json"})
    assert r.status_code == 400


def test_item_missing_mass_is_rejected_not_a_crash():
    """request_seed() read raw payload fields before parse_request() had a
    chance to reject them, so the one input MISSING_MASS exists for raised
    KeyError and became a 500."""
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/v1/solve", json={
        "order_id": "ORD",
        "items": [{"item_ref": "X", "dims": [10, 10, 10]}],
        "cartons": [{"sku": "B", "inner_dims": [200, 200, 200], "tare_mass": 0}],
    })
    assert r.status_code == 200
    assert [x["reason_code"] for x in r.json()["rejects"]] == ["MISSING_MASS"]


@pytest.mark.parametrize("bad_rotation", ["fixd", "FIXED", "none", ""])
def test_mistyped_rotation_lock_is_rejected_not_silently_unlocked(bad_rotation):
    """A typo used to fall through to "any", so an item the caller locked
    upright could be placed on its side. Safety failure, not a typo."""
    doc = solve(_one_item(dims=[10, 10, 190], allowed_rotations=bad_rotation))
    assert [r["reason_code"] for r in doc["rejects"]] == ["INVALID_ROTATION"]
    assert doc["cartons"] == []


def test_incompatible_with_as_bare_string_is_rejected():
    """frozenset("AB") silently becomes {"A","B"}: two refs matching nothing,
    so the incompatibility is dropped without a word."""
    doc = solve(_one_item(incompatible_with="AB"))
    assert [r["reason_code"] for r in doc["rejects"]] == ["INVALID_FIELD"]


@pytest.mark.parametrize("field", ["incompatible_with", "tags"])
def test_null_list_fields_are_tolerated(field):
    doc = solve(_one_item(**{field: None}))
    assert doc["rejects"] == []
    assert doc["metrics"]["carton_count"] == 1


@pytest.mark.parametrize("body", [
    {"time_budget_ms": "soon"},
    {"items": ["not an object"]},
    {"cartons": [{"sku": "B", "inner_dims": "big", "tare_mass": 0}]},
])
def test_malformed_request_shapes_are_422_not_500(body):
    client = TestClient(app, raise_server_exceptions=False)
    payload = {
        "order_id": "ORD",
        "items": [{"item_ref": "X", "dims": [50, 50, 50], "mass": 10}],
        "cartons": [{"sku": "B", "inner_dims": [200, 200, 200], "tare_mass": 0}],
    }
    payload.update(body)
    assert client.post("/v1/solve", json=payload).status_code == 422


def test_overweight_item_gets_a_mass_message_not_a_size_one():
    """An item that fits geometrically but is too heavy was told it exceeded
    every carton's dimensions, sending a packer after the wrong problem."""
    carton = Carton("B", (200, 200, 200), 0, max_contents_mass=100)
    sol = pack([Item("HEAVY", (50, 50, 50), 9999)], [carton],
               time_budget_ms=100, seed=1)
    assert "mass" in sol.rejects[0].message.lower()


@pytest.mark.parametrize("quantity", [MAX_UNITS + 1, 100_000, 10 ** 30])
def test_oversized_quantity_is_refused_not_materialised(quantity):
    """`quantity` is one number in a ~200 byte body. Unbounded, it let a tiny
    request pin a worker: 100000 never returned, and 10**30 raised
    MemoryError as a 500 while building the list."""
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/v1/solve", json={
        "order_id": "ORD",
        "items": [{"item_ref": "X", "dims": [50, 50, 50], "mass": 10,
                   "quantity": quantity}],
        "cartons": [{"sku": "B", "inner_dims": [200, 200, 200], "tare_mass": 0}],
    })
    assert r.status_code == 422


def test_unit_cap_counts_the_whole_request_not_one_line():
    """Ten lines of 500 cost the same as one line of 5000."""
    lines = [{"item_ref": f"X{i}", "dims": [50, 50, 50], "mass": 10,
              "quantity": 500} for i in range(10)]
    with pytest.raises(io.RequestError):
        io.parse_request({"order_id": "ORD", "items": lines,
                          "cartons": [{"sku": "B", "inner_dims": [200, 200, 200],
                                       "tare_mass": 0}]})


def test_unit_cap_admits_a_legitimate_large_order():
    items, _, _, _, _ = io.parse_request({
        "order_id": "ORD",
        "items": [{"item_ref": "X", "dims": [50, 50, 50], "mass": 10,
                   "quantity": MAX_UNITS}],
        "cartons": [{"sku": "B", "inner_dims": [200, 200, 200], "tare_mass": 0}],
    })
    assert len(items) == MAX_UNITS


def test_one_bad_item_does_not_fail_the_whole_request():
    """Partial success is the normal case, not an error path."""
    client = TestClient(app, raise_server_exceptions=False)
    r = client.post("/v1/solve", json={
        "order_id": "ORD",
        "items": [{"item_ref": "GOOD", "dims": [50, 50, 50], "mass": 10},
                  {"item_ref": "BAD", "dims": [50, 50, 50], "mass": "heavy"}],
        "cartons": [{"sku": "B", "inner_dims": [200, 200, 200], "tare_mass": 0}],
    })
    assert r.status_code == 200
    doc = r.json()
    assert [p["item_ref"] for c in doc["cartons"] for p in c["placements"]] == ["GOOD"]
    assert [r_["item_ref"] for r_ in doc["rejects"]] == ["BAD"]
