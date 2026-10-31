"""Portal's request shape -> our contract shape.

Portal owns its own JSON vocabulary and we own ours. This is the one place
the two meet, so a rename on either side changes exactly one file.
"""
from __future__ import annotations

import math

# Which of Portal's fields is the vertical axis. Our dims are [x, y, z], z up.
# UNCONFIRMED with Portal: their only example box is cubic (400x400x400), which
# cannot disambiguate. client-requirements.md:63 records the client's boxes as
# "width, height, depth" and Portal's `length` sits in the height slot.
# Flipping this tuple is the whole change if Portal confirms otherwise.
AXIS_ORDER = ("width", "length", "depth")   # -> (x, y, z)

GRAMS_PER_KG = 1000

# Largest dimension or weight we accept. A shipping container is 12 m and the
# heaviest realistic load is a few tonnes, so 1e9 (1000 km, 1000 tonnes) is far
# past anything real while leaving headroom for the kg -> g multiply.
MAX_MAGNITUDE = 1e9


class PortalRequestError(ValueError):
    """Portal sent something we cannot translate. Becomes a 422."""


def _number(value: object, where: str) -> float:
    """Portal's numbers. Rejects bools, which Python counts as ints.

    Without this, `"width": true` becomes round(True) == 1 and a 1mm item is
    packed silently. The same bool-is-an-int trap was fixed in io.py this week.
    `where` names the field so a Portal developer can fix their caller without
    reading our source.
    """
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise PortalRequestError(
            f"{where}: expected a number, got {type(value).__name__}")
    try:
        # float() and isfinite() both raise OverflowError on a huge int
        # (JSON has no int limit), and a finite 1e308 overflows once we
        # multiply by 1000. Bounding here keeps every numeric path a 422.
        number = float(value)
        if not math.isfinite(number) or abs(number) > MAX_MAGNITUDE:
            raise PortalRequestError(
                f"{where}: expected a number below {MAX_MAGNITUDE:g}, got {value}")
    except OverflowError as e:
        raise PortalRequestError(f"{where}: number is too large") from e
    return number


def _text(value: object, where: str) -> str:
    """An identifier or label. str() would turn None into "None" and a list
    into "[1, 2]", inventing an id that matches nothing downstream."""
    if not isinstance(value, str):
        raise PortalRequestError(
            f"{where}: expected a string, got {type(value).__name__}")
    return value


def _require(obj: object, key: str, where: str) -> object:
    if not isinstance(obj, dict):
        raise PortalRequestError(f"{where}: expected an object")
    if key not in obj:
        raise PortalRequestError(f"{where}: missing required field '{key}'")
    return obj[key]


def _dims(obj: dict, where: str) -> list[int]:
    return [round(_number(_require(obj, axis, where), f"{where}.{axis}"))
            for axis in AXIS_ORDER]


def _grams(kg: object, where: str, allow_negative: bool = True) -> int:
    """Kilograms -> integer grams.

    Box weights must be non-negative: a negative tare reports a negative
    total_mass back to Portal, and a negative limit silently makes a carton
    reject everything. Item weights are left to the solver, which turns a
    negative one into a MISSING_MASS reject so the rest of the order still
    packs. One bad item never fails the whole request.
    """
    grams = round(_number(kg, where) * GRAMS_PER_KG)
    if grams < 0 and not allow_negative:
        raise PortalRequestError(f"{where}: weight cannot be negative")
    return grams


def _group(value: object, where: str) -> str | None:
    if value is not None and not isinstance(value, str):
        raise PortalRequestError(f"{where}: expected a string or null")
    return value


def _list(payload: dict, key: str) -> list:
    value = payload.get(key)
    if not isinstance(value, list) or not value:
        raise PortalRequestError(f"'{key}' must be a non-empty list")
    return value


def to_contract(payload: object) -> dict:
    """Portal request -> solver request.

    Raises PortalRequestError, naming the offending field, on anything we
    cannot translate. Per-item problems the solver can express as a reject
    (a negative or zero dimension) are passed through deliberately.
    """
    if not isinstance(payload, dict):
        raise PortalRequestError("request body must be a JSON object")

    items = []
    for n, i in enumerate(_list(payload, "items")):
        where = f"items[{n}]"
        code = _text(_require(i, "item_code", where), f"{where}.item_code")
        items.append({
            "item_ref": code,
            "label": _text(i.get("item_reference", code), f"{where}.item_reference"),
            "dims": _dims(i, where),
            "mass": _grams(_require(i, "weight", where), f"{where}.weight"),
            # Portal's one grouping field is segregation (R1). Passed through
            # as-is: "" and None are both falsy, so neither constrains packing.
            "dg_class": _group(i.get("box_group"), f"{where}.box_group"),
        })

    cartons = []
    for n, b in enumerate(_list(payload, "boxes")):
        where = f"boxes[{n}]"
        sku = _text(_require(b, "box_reference", where), f"{where}.box_reference")
        # Portal sends no tare. UNCONFIRMED: the client said a 1kg empty
        # box eats into the limit (client-requirements.md:104), so 0
        # overstates capacity.
        tare = _grams(b.get("tare_weight", 0), f"{where}.tare_weight",
                      allow_negative=False)
        gross = _grams(_require(b, "max_weight", where), f"{where}.max_weight",
                       allow_negative=False)
        if gross < tare:
            raise PortalRequestError(f"{where}: max_weight is below tare_weight")
        # max_weight is gross (contents plus tare), per docs/contract.md.
        cartons.append({
            "sku": sku,
            "inner_dims": _dims(b, where),
            "tare_mass": tare,
            "max_contents_mass": gross - tare,
        })

    return {"order_id": _text(_require(payload, "order_id", "request"), "order_id"),
            "items": items, "cartons": cartons}
