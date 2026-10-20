"""Regression tests for the 2026-10-13 bug sweep."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from fitsolver.api import app
from fitsolver.engine import solve

CLIENT = TestClient(app)


def _request(item=None, carton=None, **extra):
    item = {"item_ref": "A", "dims": [100, 100, 100], "mass": 500, **(item or {})}
    carton = {"sku": "S", "inner_dims": [300, 300, 300], "tare_mass": 0, **(carton or {})}
    return {"order_id": "o1", "items": [item], "cartons": [carton], **extra}

def _without(d, key):
    return {k: v for k, v in d.items() if k != key}

@pytest.mark.parametrize("drop", ["mass", "dims"])
def test_missing_item_field_is_a_reject_not_a_500(drop):
    req = _request()
    req["items"][0] = _without(req["items"][0], drop)
    res = CLIENT.post("/v1/solve", json=req)
    assert res.status_code == 200
    assert [r["item_ref"] for r in res.json()["rejects"]] == ["A"]

def test_invalid_json_is_a_400():
    res = CLIENT.post("/v1/solve", content=b"{not json",
                      headers={"content-type": "application/json"})
    assert res.status_code == 400

@pytest.mark.parametrize("req", [
    {"order_id": "o1", "items": [{"item_ref": "A", "dims": [1, 1, 1], "mass": 1}],
     "cartons": [{"inner_dims": [300, 300, 300], "tare_mass": 0}]},
    _request(carton={"inner_dims": [300, "x", 300]}),
    _request(carton={"tare_mass": -1000}),
    _request(carton={"max_contents_mass": "lots"}),
    _request(time_budget_ms="fast"),
    _request(item={"quantity": 0}),
    _request(item={"quantity": -2}),
    _request(item={"incompatible_with": "B"}),
    _request(item={"dg_class": 3}),
])
def test_malformed_request_is_a_422(req):
    assert CLIENT.post("/v1/solve", json=req).status_code == 422

@pytest.mark.parametrize("dims", [[True, True, True], [100.9, 100, 100], ["100", 100, 100]])
def test_non_integer_dims_are_rejected(dims):
    doc = solve(_request(item={"dims": dims}))
    assert [r["reason_code"] for r in doc["rejects"]] == ["INVALID_DIMENSIONS"]
    assert doc["cartons"] == []

@pytest.mark.parametrize("mass", ["heavy", 1.5, True])
def test_non_integer_mass_is_rejected(mass):
    doc = solve(_request(item={"mass": mass}))
    assert [r["reason_code"] for r in doc["rejects"]] == ["MISSING_MASS"]
