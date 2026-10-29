"""Large orders of identical items (the 10,000-mug order, MQ-008).

Before the fix a carton could never hold more than CHUNK (240) items, so a
big box was cut into many small loads, and elimination then spent most of
the solve rebuilding cartons. These pin both the carton count and the time.
"""
import time

from fitsolver.domain import Carton, Item
from fitsolver.engine import solve
from fitsolver.greedy2.pack import pack

TUBE = Carton("Tube", (100, 100, 600), 0, max_contents_mass=640)
P500 = Carton("P500", (525, 365, 310), 0, max_contents_mass=16000)


def mugs(n):
    return [Item(ref=f"Mug01#{k}", dims=(1, 1, 1), mass=10) for k in range(n)]


def test_big_box_takes_more_than_one_window():
    sol = pack(mugs(5000), [TUBE, P500], 1200, 1)
    assert not sol.rejects
    assert len(sol.cartons) == 4          # 50 kg over 16 kg cartons
    assert max(len(c.placements) for c in sol.cartons) == 1600


def test_identical_items_are_fast():
    t = time.monotonic()
    sol = pack(mugs(10000), [TUBE, P500], 1200, 1)
    assert len(sol.cartons) == 7
    assert time.monotonic() - t < 15      # was minutes; ~2.5 s measured


def test_clones_respect_maximum_boxes():
    capped = Carton("P500", (525, 365, 310), 0, max_contents_mass=16000,
                    maximum_boxes=2)
    sol = pack(mugs(5000), [TUBE, capped], 1200, 1)
    assert sum(c.carton.sku == "P500" for c in sol.cartons) <= 2
    placed = sum(len(c.placements) for c in sol.cartons)
    assert placed + len(sol.rejects) == 5000


def test_every_mug_is_placed_exactly_once():
    sol = pack(mugs(3000), [TUBE, P500], 1200, 1)
    refs = [p.item.ref for c in sol.cartons for p in c.placements]
    assert len(refs) == len(set(refs)) == 3000


def test_quantity_order_through_the_real_request_path():
    """io.py expands quantity by repeating ONE Item object. Every unit must
    still be placed or rejected; none may silently disappear."""
    doc = solve({"order_id": "MQ-008", "time_budget_ms": 1200,
                 "items": [{"item_ref": "Mug01", "dims": [1, 1, 1],
                            "mass": 10, "quantity": 10000}],
                 "cartons": [{"sku": "Tube", "inner_dims": [100, 100, 600],
                              "tare_mass": 0, "max_contents_mass": 640},
                             {"sku": "P500", "inner_dims": [525, 365, 310],
                              "tare_mass": 0, "max_contents_mass": 16000}]})
    placed = sum(len(c["placements"]) for c in doc["cartons"])
    assert placed + len(doc.get("rejects", [])) == 10000
    assert placed == 10000
    assert len(doc["cartons"]) == 7
