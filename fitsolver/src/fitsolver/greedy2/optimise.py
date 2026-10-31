"""Further optimise: can the whole order fit in ONE smaller carton?

Opt-in only, for the Portal's "Further Optimise" button. Normal solving never
calls this, and OR-Tools is only imported here, so it stays an optional
dependency (pip install -e ".[optimise]").

Steps:
  1. Run greedy2 as usual. Its answer is always the fallback.
  2. If the order is small, has no rejects and is one conflict group, try the
     carton types that would beat greedy2 under its own objective (one carton,
     less volume), starting with the next size down, and stop at the first one
     that fits. A slightly smaller carton is far easier to find a layout for than
     the smallest, so this finds a saving more often within the time limit.
  3. For each, CP-SAT looks for a layout under greedy2's rules: permitted
     orientations, inside the carton, no overlaps, 70% support, mass limit,
     maximum_boxes.
  4. The layout is re-checked with greedy2's own geometry before it is used.

Unlike greedy2, this reads the clock: it stops when the time limit runs out,
and CP-SAT with several workers may return a different (equally valid) layout
on a different run. That is accepted because it only runs when asked for.
"""
from __future__ import annotations

import itertools
import time
from collections.abc import Sequence

from ..domain import Carton, Item, PackedCarton, Placement, Solution
from .geometry import fits_empty_carton, inside, orientations, overlaps, supported
from .pack import canonical_key, pack, result_key, split_compatible

# Only orders of this many items or fewer are tried. Larger orders are left to
# greedy2: exact search time grows very fast with the item count.
MAX_ITEMS = 30

# Hard cap on the whole call, in seconds. If no smaller carton is found in time,
# greedy2's answer is returned. Measured on the client's challenge order (2-core
# machine), a smaller carton was found within 20 s in about 65% of runs, 25 s
# about 85%, 30 s about 90%.
TIME_LIMIT_S = 30

# Same rule as geometry.supported(), as an integer ratio.
SUPPORT_PCT = 70


def further_optimise(items: Sequence[Item], cartons: Sequence[Carton],
                     time_budget_ms: int, seed: int,
                     time_limit_s: float = TIME_LIMIT_S) -> Solution:
    """greedy2's answer, or a one-carton answer that beats it."""
    t0 = time.monotonic()
    base = pack(items, cartons, time_budget_ms, seed)
    if base.rejects or not base.cartons or len(items) > MAX_ITEMS:
        return base
    # One carton can only hold one conflict group.
    if len(split_compatible(sorted(items, key=canonical_key))) != 1:
        return base
    cp_model = _cp_model()
    if cp_model is None:
        return base

    base_key = result_key(base.cartons, [])
    mass = sum(i.mass for i in items)
    better = [c for c in cartons if (0, 1, c.volume) < base_key]
    for carton in sorted(better, key=lambda c: c.volume, reverse=True):
        if carton.maximum_boxes == 0:
            continue
        if carton.max_contents_mass is not None and mass > carton.max_contents_mass:
            continue
        if not all(fits_empty_carton(i, carton) for i in items):
            continue
        left = time_limit_s - (time.monotonic() - t0)
        if left <= 0:
            break
        placements = _one_carton(cp_model, items, carton, left, seed)
        if placements is not None:
            return Solution(cartons=[PackedCarton(carton, placements)], rejects=[],
                            seed=seed, time_budget_ms=time_budget_ms,
                            elapsed_ms=int((time.monotonic() - t0) * 1000), tier=2)

    base.elapsed_ms = int((time.monotonic() - t0) * 1000)
    return base


def _cp_model():
    """OR-Tools' CP-SAT module, or None when the optional install is missing."""
    try:
        from ortools.sat.python import cp_model
    except ImportError:
        return None
    return cp_model


def _one_carton(cp_model, items: Sequence[Item], carton: Carton,
                seconds: float, seed: int) -> list[Placement] | None:
    """A layout of every item in this carton, or None if none was found in time."""
    W, L, H = carton.inner_dims
    m = cp_model.CpModel()
    x, y, z, w, d, h, orient = [], [], [], [], [], [], []

    for k, item in enumerate(items):
        opts = orientations(item)                       # greedy2's own rotation rules
        pick = [m.NewBoolVar(f"o{k}_{j}") for j in range(len(opts))]
        m.AddExactlyOne(pick)
        orient.append((pick, opts))
        for axis, size, cap in ((0, w, W), (1, d, L), (2, h, H)):
            v = m.NewIntVar(0, cap, "")
            m.Add(v == sum(b * dims[axis] for b, (_, dims) in zip(pick, opts, strict=True)))
            size.append(v)
        for pos, size, cap in ((x, w, W), (y, d, L), (z, h, H)):
            v = m.NewIntVar(0, cap, "")
            m.Add(v + size[k] <= cap)                   # inside the carton
            pos.append(v)

    n = len(items)
    # A layout mirrored left-right or front-back is still valid, so keep the
    # largest item in the lower half on x and y and search one mirror image only.
    # Measured on the challenge: removes the runs that missed the time limit.
    big = max(range(n), key=lambda k: items[k].volume)
    m.Add(2 * x[big] + w[big] <= W)
    m.Add(2 * y[big] + d[big] <= L)
    for i, j in itertools.combinations(range(n), 2):    # no overlaps
        s = [m.NewBoolVar("") for _ in range(6)]
        m.AddBoolOr(s)
        m.Add(x[i] + w[i] <= x[j]).OnlyEnforceIf(s[0])
        m.Add(x[j] + w[j] <= x[i]).OnlyEnforceIf(s[1])
        m.Add(y[i] + d[i] <= y[j]).OnlyEnforceIf(s[2])
        m.Add(y[j] + d[j] <= y[i]).OnlyEnforceIf(s[3])
        m.Add(z[i] + h[i] <= z[j]).OnlyEnforceIf(s[4])
        m.Add(z[j] + h[j] <= z[i]).OnlyEnforceIf(s[5])

    for i in range(n):                                  # 70% support, as geometry.supported
        on_floor = m.NewBoolVar("")
        m.Add(z[i] == 0).OnlyEnforceIf(on_floor)
        m.Add(z[i] >= 1).OnlyEnforceIf(on_floor.Not())
        base = m.NewIntVar(0, W * L, "")
        m.AddMultiplicationEquality(base, [w[i], d[i]])
        held = []
        for j in range(n):
            if j == i:
                continue
            under = m.NewBoolVar("")
            m.Add(z[j] + h[j] == z[i]).OnlyEnforceIf(under)
            overlap = []
            for lo_i, sz_i, lo_j, sz_j, cap in ((x[i], w[i], x[j], w[j], W),
                                                (y[i], d[i], y[j], d[j], L)):
                hi_i, hi_j = m.NewIntVar(0, cap, ""), m.NewIntVar(0, cap, "")
                m.Add(hi_i == lo_i + sz_i)
                m.Add(hi_j == lo_j + sz_j)
                mn, mx = m.NewIntVar(0, cap, ""), m.NewIntVar(0, cap, "")
                m.AddMinEquality(mn, [hi_i, hi_j])
                m.AddMaxEquality(mx, [lo_i, lo_j])
                ov = m.NewIntVar(0, cap, "")
                m.AddMaxEquality(ov, [mn - mx, 0])
                overlap.append(ov)
            area = m.NewIntVar(0, W * L, "")
            m.AddMultiplicationEquality(area, overlap)
            part = m.NewIntVar(0, W * L, "")
            m.Add(part <= area)
            m.Add(part == 0).OnlyEnforceIf(under.Not())
            held.append(part)
        m.Add(100 * sum(held) >= SUPPORT_PCT * base).OnlyEnforceIf(on_floor.Not())

    solver = cp_model.CpSolver()
    solver.parameters.max_time_in_seconds = max(0.1, seconds)
    solver.parameters.num_workers = 8
    solver.parameters.random_seed = seed % (2 ** 31)
    if solver.Solve(m) not in (cp_model.OPTIMAL, cp_model.FEASIBLE):
        return None

    # Bottom-up is a physical packing order: whatever holds an item up is lower.
    rows = []
    for k, item in enumerate(items):
        pick, opts = orient[k]
        idx, dims = next(o for b, o in zip(pick, opts, strict=True) if solver.Value(b))
        pos = (solver.Value(x[k]), solver.Value(y[k]), solver.Value(z[k]))
        rows.append((pos, item, idx, dims))
    rows.sort(key=lambda r: (r[0][2], r[0][1], r[0][0]))

    placed: list[Placement] = []
    for pos, item, idx, dims in rows:                   # re-check with greedy2's geometry
        if (not inside(pos, dims, carton)
                or any(overlaps(pos, dims, p.pos, p.dims) for p in placed)
                or not supported(pos, dims, placed)):
            return None
        placed.append(Placement(item=item, pos=pos, dims=dims, orientation=idx,
                                sequence=len(placed)))
    return placed
