"""Regression tests for the 2026-10-13 bug sweep."""
from __future__ import annotations

from fastapi.testclient import TestClient

from fitsolver.api import app

CLIENT = TestClient(app)


def test_invalid_json_is_a_400():
    res = CLIENT.post("/v1/solve", content=b"{not json",
                      headers={"content-type": "application/json"})
    assert res.status_code == 400
