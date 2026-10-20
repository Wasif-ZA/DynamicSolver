"""The boundary. JSON in, JSON out. Nothing past this file knows JSON exists.

Validation and rejection codes live here — "invalid format" is defined by
this module, published in the contract repo, and returned per-item as a
structured rejection, never as a whole-request failure.
"""
from __future__ import annotations

import hashlib
import uuid

from .domain import Carton, Item, Reject, Solution

SOLVER_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_BUDGET_MS = 1200


class RequestError(ValueError):
    """The request as a whole is unusable (bad JSON shape, no cartons)."""


def request_seed(payload: dict) -> int:
    """Deterministic seed derived from the request content.

    Same order + same catalogue -> same seed -> same search sequence.
    This is what makes results reproducible for debugging and disputes.
    """
    canon = repr(sorted(
        (i["item_ref"], tuple(i["dims"]), i["mass"], i.get("quantity", 1))
        for i in payload.get("items", [])
    )) + repr(sorted(
        (c["sku"], tuple(c["inner_dims"])) for c in payload.get("cartons", [])
    ))
    return int.from_bytes(hashlib.sha256(canon.encode()).digest()[:8], "big")


def _maximum_boxes(c: dict) -> int | None:
    """How many of this carton one solution may use. Missing or null = unlimited."""
    value = c.get("maximum_boxes")
    if value is None:
        return None
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise RequestError(f"carton {c.get('sku')}: maximum_boxes must be an integer >= 0")
    return value


def parse_request(payload: dict) -> tuple[list[Item], list[Carton],
                                          list[Reject], int, str]:
    """Returns (items, cartons, per-item rejects, budget_ms, order_id)."""
    if not isinstance(payload, dict):
        raise RequestError("request body must be a JSON object")
    if not payload.get("cartons"):
        raise RequestError("at least one carton is required")
    if not payload.get("items"):
        raise RequestError("at least one item is required")

    budget = int(payload.get("time_budget_ms", DEFAULT_BUDGET_MS))
    if budget < 1:
        raise RequestError("time_budget_ms must be >= 1")
    order_id = str(payload.get("order_id", ""))

    cartons: list[Carton] = []
    for c in payload["cartons"]:
        dims = tuple(int(x) for x in c["inner_dims"])
        if len(dims) != 3 or any(x <= 0 for x in dims):
            raise RequestError(f"carton {c.get('sku')}: invalid inner_dims")
        cartons.append(Carton(
            sku=str(c["sku"]), inner_dims=dims,  # type: ignore[arg-type]
            tare_mass=int(c.get("tare_mass", 0)),
            max_contents_mass=(int(c["max_contents_mass"])
                               if c.get("max_contents_mass") is not None else None),
            maximum_boxes=_maximum_boxes(c),
        ))

    items: list[Item] = []
    rejects: list[Reject] = []
    for raw in payload["items"]:
        ref = str(raw.get("item_ref", "?"))
        try:
            dims = tuple(int(x) for x in raw["dims"])
        except (KeyError, TypeError, ValueError):
            rejects.append(Reject(ref, "INVALID_DIMENSIONS",
                                  "dims must be three integers (mm)"))
            continue
        if len(dims) != 3 or any(x <= 0 for x in dims):
            rejects.append(Reject(ref, "INVALID_DIMENSIONS",
                                  "dims must be three positive integers (mm)"))
            continue
        if "mass" not in raw or int(raw["mass"]) < 0:
            rejects.append(Reject(ref, "MISSING_MASS",
                                  "mass (g) is required and non-negative"))
            continue
        item = Item(
            ref=ref,
            dims=dims,  # type: ignore[arg-type]
            mass=int(raw["mass"]),
            label=str(raw.get("label", ref)),
            allowed_rotations=str(raw.get("allowed_rotations", "any")),
            dg_class=raw.get("dg_class"),
            incompatible_with=frozenset(raw.get("incompatible_with", [])),
            tags=tuple(raw.get("tags", [])),
        )
        for _ in range(int(raw.get("quantity", 1))):
            items.append(item)
    return items, cartons, rejects, budget, order_id


def emit_document(solution: Solution, order_id: str,
                  input_rejects: list[Reject]) -> dict:
    """Solution -> self-contained contract document.

    Denormalised on purpose: labels, dims and masses are repeated in every
    placement so a visualiser renders with zero further network calls.
    """
    cartons = []
    for n, pc in enumerate(solution.cartons, start=1):
        placements = []
        for p in pc.placements:
            placements.append({
                "placement_id": f"p{n}_{p.sequence}",
                "item_ref": p.item.ref,
                "label": p.item.label,
                "position": list(p.pos),
                "dims": list(p.dims),
                "orientation": p.orientation,
                "mass": p.item.mass,
                "sequence": p.sequence,
                "tags": list(p.item.tags),
            })
        cartons.append({
            "carton_id": f"c{n}",
            "sku": pc.carton.sku,
            "inner_dims": list(pc.carton.inner_dims),
            "tare_mass": pc.carton.tare_mass,
            "contents_mass": pc.contents_mass,
            "fill_rate": round(pc.fill_rate, 4),
            "centre_of_mass": list(pc.centre_of_mass),
            "placements": placements,
        })
    all_rejects = input_rejects + solution.rejects
    return {
        "schema_version": SCHEMA_VERSION,
        "solution_id": f"sol_{uuid.uuid4().hex[:12]}",
        "order_id": order_id,
        "solver": {
            "version": SOLVER_VERSION,
            "seed": solution.seed,
            "mode": solution.mode,
            "time_budget_ms": solution.time_budget_ms,
            "elapsed_ms": solution.elapsed_ms,
            "tier": solution.tier,
        },
        "coordinate_system": {"up": "z", "handedness": "right",
                              "origin": "min_corner"},
        "units": {"length": "mm", "mass": "g"},
        "metrics": {
            "carton_count": solution.carton_count,
            "fill_rate": round(solution.fill_rate, 4),
            "total_mass": solution.total_mass,
        },
        "cartons": cartons,
        "rejects": [
            {"item_ref": r.item_ref, "reason_code": r.reason_code,
             "message": r.message}
            for r in all_rejects
        ],
    }
