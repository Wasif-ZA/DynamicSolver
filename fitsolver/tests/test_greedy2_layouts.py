"""greedy2 lays out exactly what it is recorded as laying out.

The guard for every phase that is supposed to change nothing. A carton count
would not catch a regression here: two runs can agree on how many cartons they
used and disagree about where every item went, so this compares placement by
placement over roughly 2500 placements.

When a phase changes behaviour on purpose, the fixture is re-recorded with
tests/golden_layouts.py --write and the carton deltas are reported. It is
never re-recorded to turn a red test green.
"""
from __future__ import annotations

import json
from functools import lru_cache

import pytest

from golden_layouts import DATA, produce

GOLDEN = json.loads(DATA.read_text())


@lru_cache(maxsize=1)
def _current() -> dict:
    """Solve every recorded workload once, not once per parametrized case."""
    return produce()


@pytest.mark.parametrize("key", sorted(GOLDEN))
def test_layout_matches_the_recorded_baseline(key):
    assert _current()[key] == GOLDEN[key]


def test_every_recorded_workload_still_exists():
    """Guards the fixture itself. If golden_layouts.py's workloads change but
    the data file is not re-recorded, the comparisons above silently stop
    covering what they claim to."""
    assert sorted(_current()) == sorted(GOLDEN)
