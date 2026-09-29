"""greedy2's solver. Phase 1 is a faithful copy of v1's three functions.

    place(item, carton, placed)  -> first feasible Placement, or None
    fill_carton(carton, items)   -> greedily fill one carton
    pack(items, cartons)         -> choose cartons until everything is placed

Objective is LEXICOGRAPHIC: fewest unplaced, then fewest cartons, then least
total carton volume. Fill rate is deliberately NOT optimised. Maximising fill
rewards many small tight cartons, the opposite of the client's "reduce the
number of boxes required". Fill is reported, not chased.

WHY THIS STARTS AS A COPY. Phase 1's whole job is to prove the scaffold: the
new package, the algorithm selection in engine.py, and the parametrized
property tests. If greedy2 both moved into a new package and changed
behaviour in one step, a wrong layout later could not be attributed to either.
So Phase 1 is measured on being identical, and tests/test_greedy2_scaffold.py
asserts exactly that. That test is removed in Phase 2, when greedy2 is
supposed to diverge.

KNOWN LIMITS INHERITED FROM v1, and the phase that addresses each:

    Phase 2  candidates() returns dead points: positions inside placed items
             and on or beyond the carton walls. Sorting bottom-first and then
             capping at MAX_CANDIDATES means those dead low points crowd out
             live high points, so the solver stops stacking. Measured on the
             W1 benchmark: 50% of the points scanned are dead, and the cap
             discards live points in 25% of placement attempts.
    Phase 3  no boundary pre-checks and no memo of positions already known to
             be infeasible, so the same hopeless test is repeated.
    Phase 4  one item ordering only (volume descending). No single ordering
             wins on every workload.
    Phase 5  split_compatible is quadratic in the item count.

v1 also has an up-front filter for items no carton can ever hold. This copy is
taken from algo-test's v1, which does not have it, so greedy2 does not have it
in Phase 1 either. It arrives in Phase 3, whose first step is exactly that
check, done per carton type.
"""
from __future__ import annotations

import time
from collections.abc import Sequence

from ..domain import Carton, Item, PackedCarton, Placement, Reject, Solution
from .geometry import candidates, fits, orientations

MAX_CANDIDATES = 64   # corner points considered per placement
CHUNK = 120           # items offered to each carton; bounds n^2 growth


def split_compatible(items: Sequence[Item]) -> list[list[Item]]:
    """Greedy colouring over the conflict graph.

    An edge means "cannot share a carton": an explicit incompatibility, or two
    differing dangerous-goods classes. Each colour class packs independently.
    This is how DG segregation, incompatibility and customer rules are
    enforced, before any geometry runs, so the geometry stays constraint-free.
    """
    def conflict(a: Item, b: Item) -> bool:
        if b.ref in a.incompatible_with or a.ref in b.incompatible_with:
            return True
        return bool(a.dg_class and b.dg_class and a.dg_class != b.dg_class)

    groups: list[list[Item]] = []
    for item in items:
        for g in groups:
            if not any(conflict(item, other) for other in g):
                g.append(item)
                break
        else:
            groups.append([item])
    return groups


def place(item: Item, carton: Carton, placed: list[Placement],
          contents_mass: int) -> Placement | None:
    """First feasible placement, scanning corner points bottom-left-first.

    Candidates are pre-sorted by (z, y, x), so first-fit is already the
    gravity-sensible choice. Whether scoring them by contact area instead is
    worth anything is re-tested in Phase 6: v1's ablation said no, but it ran
    while the candidate cap was discarding live points, so the result is not
    trustworthy.
    """
    if (carton.max_contents_mass is not None
            and contents_mass + item.mass > carton.max_contents_mass):
        return None
    for pos in candidates(placed, carton)[:MAX_CANDIDATES]:
        for orient_idx, dims in orientations(item):
            if fits(pos, dims, carton, placed):
                return Placement(item=item, pos=pos, dims=dims,
                                 orientation=orient_idx, sequence=len(placed))
    return None


def fill_carton(carton: Carton, items: Sequence[Item]
                ) -> tuple[PackedCarton, list[Item]]:
    """Greedily place items, in the given order, into one carton."""
    pc = PackedCarton(carton=carton)
    mass = 0
    left: list[Item] = []
    for item in items:
        p = place(item, carton, pc.placements, mass)
        if p is None:
            left.append(item)
        else:
            pc.placements.append(p)
            mass += item.mass
    return pc, left


def pack_one(ordering: Sequence[Item], cartons: Sequence[Carton]
             ) -> tuple[list[PackedCarton], list[Item]]:
    """Fill cartons with items in the given order.

    THE ONE THING THAT MATTERS. At each step, evaluate EVERY carton type
    against the remaining items and take the one packing the most items,
    tie-breaking on the smallest carton. The obvious alternative, opening the
    smallest carton that fits the next item, produces 73 cartons where this
    produces 28 on the same input.

    Only the first CHUNK remaining items are offered to each carton. Without
    this, cost grows about n^1.6 and a 1600-item order takes 11 s. Nothing is
    dropped: items past the window are considered for the next carton, and the
    ordering is volume-descending, so the near-term items were the right ones
    to try anyway. Phase 5 re-measures whether 120 is still the right number
    once placement is cheaper.
    """
    remaining = list(ordering)
    out: list[PackedCarton] = []
    by_volume = sorted(cartons, key=lambda c: c.volume)

    while remaining:
        window, rest = remaining[:CHUNK], remaining[CHUNK:]
        best: tuple[PackedCarton, list[Item]] | None = None
        best_key: tuple[int, int] | None = None
        for carton in by_volume:
            pc, left = fill_carton(carton, window)
            if not pc.placements:
                continue
            key = (-len(pc.placements), carton.volume)
            if best_key is None or key < best_key:
                best_key, best = key, (pc, left)
        if best is None:
            return out, remaining
        pc, left = best
        out.append(pc)
        remaining = left + rest
    return out, remaining


def pack(items: Sequence[Item], cartons: Sequence[Carton],
         time_budget_ms: int, seed: int) -> Solution:
    """Solve. One deterministic pass per conflict group.

    Fully deterministic: no randomness, no wall-clock dependence. The same
    request returns the same layout on any machine, every time, which matters
    when a packer re-scans an order and expects the same picture.

    `time_budget_ms` and `seed` are honoured as contract fields, reported back
    in the solution document, but unused by this implementation. From Phase 4
    the budget does steer how much work is done, but only through a fixed
    size-based table, never by reading the clock mid-solve, because a
    clock-dependent decision would make the layout differ between runs.
    """
    t0 = time.monotonic()

    all_cartons: list[PackedCarton] = []
    all_unplaced: list[Item] = []
    for group in split_compatible(items):
        ordering = sorted(group, key=lambda i: i.volume, reverse=True)
        packed, unplaced = pack_one(ordering, cartons)
        all_cartons.extend(packed)
        all_unplaced.extend(unplaced)

    rejects = [Reject(item_ref=i.ref, reason_code="NO_FITTING_CARTON",
                      message="Exceeds every carton in all permitted orientations")
               for i in all_unplaced]
    return Solution(cartons=all_cartons, rejects=rejects, seed=seed,
                    time_budget_ms=time_budget_ms,
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    tier=1)
