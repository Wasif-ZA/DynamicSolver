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


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _int_vec3(value: object) -> tuple[int, int, int] | None:
    if not isinstance(value, list) or len(value) != 3:
        return None
    if not all(_is_int(x) for x in value):
        return None
    return tuple(value)  # type: ignore[return-value]


def _str_list(value: object) -> list[str] | None:
    if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
        return None
    return value


def request_seed(payload: dict) -> int:
    """Deterministic seed derived from the request content.

    Same order + same catalogue -> same seed -> same search sequence.
    This is what makes results reproducible for debugging and disputes.
    """
    def item_key(i):
        try:
            return (i["item_ref"], tuple(i["dims"]), i["mass"], i.get("quantity", 1))
        except (KeyError, TypeError, AttributeError):
            return ("?", repr(i))

    def carton_key(c):
        try:
            return (c["sku"], tuple(c["inner_dims"]))
        except (KeyError, TypeError, AttributeError):
            return ("?", repr(c))

    def canonical(keys):
        try:
            return repr(sorted(keys))
        except TypeError:
            return repr(sorted(keys, key=repr))

    canon = (canonical([item_key(i) for i in payload.get("items", [])])
             + canonical([carton_key(c) for c in payload.get("cartons", [])]))
    return int.from_bytes(hashlib.sha256(canon.encode()).digest()[:8], "big")


def parse_request(payload: dict) -> tuple[list[Item], list[Carton],
                                          list[Reject], int, str]:
    """Returns (items, cartons, per-item rejects, budget_ms, order_id)."""
    if not isinstance(payload, dict):
        raise RequestError("request body must be a JSON object")
    if not payload.get("cartons"):
        raise RequestError("at least one carton is required")
    if not payload.get("items"):
        raise RequestError("at least one item is required")

    budget = payload.get("time_budget_ms", DEFAULT_BUDGET_MS)
    if not _is_int(budget) or budget < 1:
        raise RequestError("time_budget_ms must be an integer >= 1")
    order_id = str(payload.get("order_id", ""))

    cartons: list[Carton] = []
    if not isinstance(payload["cartons"], list) or not isinstance(payload["items"], list):
        raise RequestError("cartons and items must be arrays")
    for c in payload["cartons"]:
        if not isinstance(c, dict) or not isinstance(c.get("sku"), str):
            raise RequestError("every carton needs a string sku")
        dims = _int_vec3(c.get("inner_dims"))
        if dims is None or any(x <= 0 for x in dims):
            raise RequestError(f"carton {c['sku']}: invalid inner_dims")
        tare = c.get("tare_mass", 0)
        if not _is_int(tare) or tare < 0:
            raise RequestError(f"carton {c['sku']}: tare_mass must be a non-negative integer")
        limit = c.get("max_contents_mass")
        if limit is not None and (not _is_int(limit) or limit < 0):
            raise RequestError(
                f"carton {c['sku']}: max_contents_mass must be a non-negative integer")
        cartons.append(Carton(
            sku=c["sku"], inner_dims=dims, tare_mass=tare, max_contents_mass=limit,
        ))

    items: list[Item] = []
    rejects: list[Reject] = []
    for raw in payload["items"]:
        if not isinstance(raw, dict):
            raise RequestError("every item must be an object")
        ref = str(raw.get("item_ref", "?"))
        quantity = raw.get("quantity", 1)
        if not _is_int(quantity) or quantity < 1:
            raise RequestError(f"item {ref}: quantity must be an integer >= 1")
        incompatible = _str_list(raw.get("incompatible_with", []))
        tags = _str_list(raw.get("tags", []))
        if incompatible is None or tags is None:
            raise RequestError(f"item {ref}: incompatible_with and tags must be string arrays")
        dg_class = raw.get("dg_class")
        if dg_class is not None and not isinstance(dg_class, str):
            raise RequestError(f"item {ref}: dg_class must be a string or null")
        dims = _int_vec3(raw.get("dims"))
        if dims is None or any(x <= 0 for x in dims):
            rejects.append(Reject(ref, "INVALID_DIMENSIONS",
                                  "dims must be three positive integers (mm)"))
            continue
        mass = raw.get("mass")
        if not _is_int(mass) or mass < 0:
            rejects.append(Reject(ref, "MISSING_MASS",
                                  "mass (g) is required and a non-negative integer"))
            continue
        item = Item(
            ref=ref,
            dims=dims,
            mass=mass,
            label=str(raw.get("label", ref)),
            allowed_rotations=str(raw.get("allowed_rotations", "any")),
            dg_class=dg_class,
            incompatible_with=frozenset(incompatible),
            tags=tuple(tags),
        )
        for _ in range(quantity):
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
