"""The boundary. JSON in, JSON out. Nothing past this file knows JSON exists.

Validation and rejection codes live here — "invalid format" is defined by
this module, published in the contract repo, and returned per-item as a
structured rejection, never as a whole-request failure.
"""
from __future__ import annotations

import hashlib
import uuid
from collections.abc import Sequence

from .domain import Carton, Item, Reject, Solution

SOLVER_VERSION = "0.1.0"
SCHEMA_VERSION = "1.0.0"
DEFAULT_BUDGET_MS = 1200
ROTATION_MODES = frozenset({"any", "upright", "fixed"})

# Ceiling on units after `quantity` is expanded. `quantity` is one number in
# a small request body, so without a bound a ~200 byte request can ask for
# millions of units: quantity=100000 does not return at all, and 10**30
# raised MemoryError as a 500 while trying to build the list.
#
# 2000 is the point BENCHMARK.md already routes to the async batch path, and
# it is measured: 2000 mixed items take ~2.4 s, 5000 take ~6.8 s, and 15000
# identical items take ~23 s against a 1200 ms budget. Orders above this
# belong on the batch endpoint, not on a synchronous request that ties up a
# worker for half a minute.
#
# Checked across the whole request, not per line: ten lines of 500 cost the
# same as one line of 5000.
MAX_UNITS = 2_000


class RequestError(ValueError):
    """The request as a whole is unusable (bad JSON shape, no cartons)."""


def _as_int(value: object) -> int:
    """Strict integer read. Rejects floats, bools and numeric strings.

    int("3") and int(1.9) both succeed in Python and both hide a caller's
    mistake: 1.9 units silently becomes 1. The contract says integers, so
    anything else is the caller's error and is reported as one.
    """
    if isinstance(value, bool) or not isinstance(value, int):
        raise ValueError(f"expected an integer, got {type(value).__name__}")
    return value


def _as_ref_set(value: object, field: str) -> frozenset[str]:
    """A list of item_refs. A bare string is a caller error, not a sequence.

    frozenset("AB") would silently become {"A", "B"} -- two refs that match
    nothing, so the incompatibility is dropped without a word.
    """
    if value is None:
        return frozenset()
    if isinstance(value, str) or not isinstance(value, list):
        raise ValueError(f"{field} must be a list of item_ref strings")
    return frozenset(str(v) for v in value)


def request_seed(items: Sequence[Item], cartons: Sequence[Carton]) -> int:
    """Deterministic seed derived from the parsed request.

    Same order + same catalogue -> same seed -> same search sequence.
    This is what makes results reproducible for debugging and disputes.

    Derived from parsed objects, not the raw payload: reading raw fields
    here meant a request missing `mass` raised KeyError before parsing
    could turn it into the MISSING_MASS rejection it has a code for.
    """
    canon = repr(sorted((i.ref, i.dims, i.mass) for i in items)) + repr(
        sorted((c.sku, c.inner_dims) for c in cartons))
    return int.from_bytes(hashlib.sha256(canon.encode()).digest()[:8], "big")


def parse_request(payload: dict) -> tuple[list[Item], list[Carton],
                                          list[Reject], int, str]:
    """Returns (items, cartons, per-item rejects, budget_ms, order_id)."""
    if not isinstance(payload, dict):
        raise RequestError("request body must be a JSON object")
    if not isinstance(payload.get("cartons"), list) or not payload["cartons"]:
        raise RequestError("at least one carton is required")
    if not isinstance(payload.get("items"), list) or not payload["items"]:
        raise RequestError("at least one item is required")

    try:
        budget = _as_int(payload.get("time_budget_ms", DEFAULT_BUDGET_MS))
    except ValueError as e:
        raise RequestError(f"time_budget_ms: {e}") from e
    if budget < 1:
        raise RequestError("time_budget_ms must be >= 1")
    order_id = str(payload.get("order_id", ""))

    cartons: list[Carton] = []
    for c in payload["cartons"]:
        if not isinstance(c, dict):
            raise RequestError("each carton must be a JSON object")
        try:
            dims = tuple(_as_int(x) for x in c["inner_dims"])
            tare = _as_int(c.get("tare_mass", 0))
            limit = (None if c.get("max_contents_mass") is None
                     else _as_int(c["max_contents_mass"]))
        except (KeyError, TypeError, ValueError) as e:
            raise RequestError(f"carton {c.get('sku')}: {e}") from e
        if len(dims) != 3 or any(x <= 0 for x in dims):
            raise RequestError(f"carton {c.get('sku')}: invalid inner_dims")
        cartons.append(Carton(
            sku=str(c["sku"]), inner_dims=dims,  # type: ignore[arg-type]
            tare_mass=tare, max_contents_mass=limit,
        ))

    items: list[Item] = []
    rejects: list[Reject] = []
    for raw in payload["items"]:
        if not isinstance(raw, dict):
            raise RequestError("each item must be a JSON object")
        ref = str(raw.get("item_ref", "?"))
        try:
            dims = tuple(_as_int(x) for x in raw["dims"])
        except (KeyError, TypeError, ValueError):
            rejects.append(Reject(ref, "INVALID_DIMENSIONS",
                                  "dims must be three integers (mm)"))
            continue
        if len(dims) != 3 or any(x <= 0 for x in dims):
            rejects.append(Reject(ref, "INVALID_DIMENSIONS",
                                  "dims must be three positive integers (mm)"))
            continue
        try:
            mass = _as_int(raw["mass"])
        except (KeyError, TypeError, ValueError):
            rejects.append(Reject(ref, "MISSING_MASS",
                                  "mass (g) is required and non-negative"))
            continue
        if mass < 0:
            rejects.append(Reject(ref, "MISSING_MASS",
                                  "mass (g) is required and non-negative"))
            continue
        try:
            quantity = _as_int(raw.get("quantity", 1))
        except (TypeError, ValueError):
            quantity = 0
        if quantity < 1:
            rejects.append(Reject(ref, "INVALID_QUANTITY",
                                  "quantity must be an integer of at least 1"))
            continue
        # Checked before expanding, not after: materialising the list is the
        # cost we are guarding against.
        if len(items) + quantity > MAX_UNITS:
            raise RequestError(
                f"request expands to more than {MAX_UNITS} units; "
                f"split it or use the batch path")

        rotations = str(raw.get("allowed_rotations", "any"))
        if rotations not in ROTATION_MODES:
            # Never fall back to "any": a mistyped lock would silently permit
            # orientations the caller meant to forbid.
            rejects.append(Reject(ref, "INVALID_ROTATION",
                                  f"allowed_rotations must be one of "
                                  f"{', '.join(sorted(ROTATION_MODES))}"))
            continue
        try:
            incompatible = _as_ref_set(raw.get("incompatible_with"),
                                       "incompatible_with")
            tags = _as_ref_set(raw.get("tags"), "tags")
        except ValueError as e:
            rejects.append(Reject(ref, "INVALID_FIELD", str(e)))
            continue

        item = Item(
            ref=ref,
            dims=dims,  # type: ignore[arg-type]
            mass=mass,
            label=str(raw.get("label", ref)),
            allowed_rotations=rotations,
            dg_class=raw.get("dg_class"),
            incompatible_with=incompatible,
            tags=tuple(sorted(tags)),
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
