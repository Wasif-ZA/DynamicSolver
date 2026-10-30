"""Input validation and HTTP boundary regression tests."""

from __future__ import annotations

import sys
from pathlib import Path
from time import perf_counter

import pytest
from fastapi.testclient import TestClient

# Add the solver source directory to the import path.
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))

from fitsolver.api import app
from fitsolver.io import RequestError, parse_request

CLIENT = TestClient(app)


@pytest.fixture
def payload():
    return {
        "order_id": "ORD-1",
        "items": [{"item_ref": "ITEM-1", "dims": [10, 10, 10], "mass": 5}],
        "cartons": [{"sku": "B", "inner_dims": [100, 100, 100], "tare_mass": 10}],
    }


@pytest.mark.parametrize(
    "quantity",
    [10001, 10**7, 0, -1, 1.5, True, "3", None],
    ids=["above-limit", "huge", "zero", "negative", "float", "bool", "string", "null"],
)
def test_invalid_quantity_returns_422(payload, quantity):
    payload["items"][0]["quantity"] = quantity

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 422
    assert "ITEM-1" in response.json()["detail"]
    assert "quantity" in response.json()["detail"]


@pytest.mark.parametrize(
    "quantity",
    [10001, 10**7, 0, -1, 1.5, True, "3", None],
    ids=["above-limit", "huge", "zero", "negative", "float", "bool", "string", "null"],
)
def test_invalid_quantity_raises_request_error(payload, quantity):
    payload["items"][0]["quantity"] = quantity

    with pytest.raises(RequestError) as error:
        parse_request(payload)

    assert "ITEM-1" in str(error.value)
    assert "quantity" in str(error.value)


@pytest.mark.parametrize(("quantity", "expected_count"), [(1, 1), (10000, 10000)])
def test_quantity_boundaries_are_accepted(payload, quantity, expected_count):
    payload["items"][0].update(quantity=quantity, dims=[1, 1, 1])

    items, _, rejects, _, _ = parse_request(payload)

    assert len(items) == expected_count
    assert rejects == []
    assert all(item.ref == "ITEM-1" for item in items)


@pytest.mark.parametrize(("quantity", "expected_count"), [(1, 1), (2, 2)])
def test_valid_quantity_produces_one_placement_per_unit(payload, quantity, expected_count):
    payload["items"][0]["quantity"] = quantity

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 200
    document = response.json()
    placements = [p for c in document["cartons"] for p in c["placements"]]
    assert len(placements) == expected_count
    assert all(p["item_ref"] == "ITEM-1" for p in placements)
    assert document["rejects"] == []


def test_huge_quantity_returns_422_in_under_half_a_second(payload):
    payload["items"][0]["quantity"] = 10**7

    started = perf_counter()
    response = CLIENT.post("/v1/solve", json=payload)
    elapsed = perf_counter() - started

    assert response.status_code == 422
    assert "ITEM-1" in response.json()["detail"]
    assert "quantity" in response.json()["detail"]
    assert elapsed < 0.5


@pytest.mark.parametrize(
    "rotations",
    ["Fixed", "FIXED", "rotate", "", None, 1, ["any"]],
    ids=["title-case", "upper-case", "unknown", "empty", "null", "integer", "list"],
)
def test_invalid_rotations_return_422(payload, rotations):
    payload["items"][0]["allowed_rotations"] = rotations

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 422
    assert "ITEM-1" in response.json()["detail"]
    assert "allowed_rotations" in response.json()["detail"]


@pytest.mark.parametrize(
    "rotations",
    ["Fixed", "FIXED", "rotate", "", None, 1, ["any"]],
    ids=["title-case", "upper-case", "unknown", "empty", "null", "integer", "list"],
)
def test_invalid_rotations_raise_request_error(payload, rotations):
    payload["items"][0]["allowed_rotations"] = rotations

    with pytest.raises(RequestError) as error:
        parse_request(payload)

    assert "ITEM-1" in str(error.value)
    assert "allowed_rotations" in str(error.value)


@pytest.mark.parametrize("rotations", ["any", "upright", "fixed"])
def test_valid_rotations_are_preserved_and_pack(payload, rotations):
    payload["items"][0]["allowed_rotations"] = rotations

    items, _, rejects, _, _ = parse_request(payload)
    response = CLIENT.post("/v1/solve", json=payload)

    assert len(items) == 1
    assert items[0].allowed_rotations == rotations
    assert rejects == []
    assert response.status_code == 200
    document = response.json()
    assert [p["item_ref"] for c in document["cartons"] for p in c["placements"]] == ["ITEM-1"]
    assert document["rejects"] == []


def test_missing_rotations_default_to_any(payload):
    items, _, rejects, _, _ = parse_request(payload)
    response = CLIENT.post("/v1/solve", json=payload)

    assert len(items) == 1
    assert items[0].allowed_rotations == "any"
    assert rejects == []
    assert response.status_code == 200
    document = response.json()
    assert [p["item_ref"] for c in document["cartons"] for p in c["placements"]] == ["ITEM-1"]
    assert document["rejects"] == []


def test_fixed_rotation_preserves_dimension_order(payload):
    payload["items"][0].update(dims=[10, 20, 30], allowed_rotations="fixed")

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 200
    document = response.json()
    placements = [p for c in document["cartons"] for p in c["placements"]]
    assert len(placements) == 1
    assert placements[0]["item_ref"] == "ITEM-1"
    assert placements[0]["dims"] == [10, 20, 30]
    assert document["rejects"] == []


@pytest.mark.parametrize(
    "order_id", [None, 5, ["x"], {}], ids=["null", "integer", "list", "object"]
)
def test_invalid_order_id_returns_422(payload, order_id):
    payload["order_id"] = order_id

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 422
    assert "order_id" in response.json()["detail"]


@pytest.mark.parametrize(
    "order_id", [None, 5, ["x"], {}], ids=["null", "integer", "list", "object"]
)
def test_invalid_order_id_raises_request_error(payload, order_id):
    payload["order_id"] = order_id

    with pytest.raises(RequestError, match="order_id"):
        parse_request(payload)


def test_missing_order_id_defaults_to_empty_string(payload):
    payload.pop("order_id")

    _, _, _, _, order_id = parse_request(payload)
    response = CLIENT.post("/v1/solve", json=payload)

    assert order_id == ""
    assert response.status_code == 200
    assert response.json()["order_id"] == ""


@pytest.mark.parametrize("order_id", ["", "  Ord-007 / x  "])
def test_string_order_id_is_echoed_unchanged(payload, order_id):
    payload["order_id"] = order_id

    _, _, _, _, parsed_order_id = parse_request(payload)
    response = CLIENT.post("/v1/solve", json=payload)

    assert parsed_order_id == order_id
    assert response.status_code == 200
    assert response.json()["order_id"] == order_id


def test_missing_mass_rejects_only_the_invalid_item(payload):
    payload["items"].insert(0, {"item_ref": "NO-MASS", "dims": [10, 10, 10]})

    response = CLIENT.post("/v1/solve", json=payload)

    assert response.status_code == 200
    document = response.json()
    assert [p["item_ref"] for c in document["cartons"] for p in c["placements"]] == ["ITEM-1"]
    assert len(document["rejects"]) == 1
    assert document["rejects"][0]["item_ref"] == "NO-MASS"
    assert document["rejects"][0]["reason_code"] == "MISSING_MASS"


def test_non_json_body_returns_400():
    response = CLIENT.post(
        "/v1/solve",
        content=b"not JSON",
        headers={"content-type": "application/json"},
    )

    assert response.status_code == 400
