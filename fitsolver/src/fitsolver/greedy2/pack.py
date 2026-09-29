"""greedy2's solver.

    place(item, state)           -> first feasible Placement, or None
    fill_carton(carton, items)   -> greedily fill one carton
    pack(items, cartons)         -> choose cartons until everything is placed

Objective is LEXICOGRAPHIC: fewest unplaced, then fewest cartons, then least
total carton volume. Fill rate is deliberately NOT optimised. Maximising fill
rewards many small tight cartons, the opposite of the client's "reduce the
number of boxes required". Fill is reported, not chased.

PHASE 2, the change that made greedy2 worth having. v1 stopped stacking, and
the cause was candidate generation rather than anything in the packing logic:

  - v1 keeps corner points that lie inside placed items, and points on or
    beyond the carton walls. Nothing can ever be placed at either.
  - the list is sorted bottom-first and then cut to MAX_CANDIDATES, so those
    dead low points crowd out the live high ones. Measured on W1: half of
    every scan was dead, and the cut discarded live points in a quarter of all
    placement attempts.

So greedy2 drops dead points (geometry.is_live), and holds the survivors in a
per-carton CartonState updated incrementally rather than rebuilt inside every
placement attempt. Both halves matter: pruning is what recovers the stacking,
and the cache is what stops pruning from costing more than it saves.

STILL TO DO, and the phase that addresses each:

    Phase 3  no boundary pre-checks and no memo of positions already known to
             be infeasible, so the same hopeless test is repeated.
    Phase 4  one item ordering only (volume descending). No single ordering
             wins on every workload.
    Phase 5  split_compatible is quadratic in the item count.

v1 also has an up-front filter for items no carton can ever hold. This copy is
taken from algo-test's v1, which does not have it, so greedy2 does not have it
yet. It arrives in Phase 3, whose first step is exactly that check, done per
carton type.
"""
from __future__ import annotations

import time
from bisect import insort
from collections.abc import Sequence

from ..domain import Carton, Item, PackedCarton, Placement, Reject, Solution
from .geometry import covered_by, fits, is_live, orientations, point_sort_key

# Corner points considered per placement. None means no cap.
#
# The cap exists to bound the scan, not to choose between points. In v1 it did
# both, badly: half the list was dead points, so a cap of 64 often meant fewer
# than 32 real options, and the live high points that would have continued a
# stack were the ones pushed out. With dead points gone, 64 is 64.
MAX_CANDIDATES = 64

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


class CartonState:
    """One carton being filled: its placements, its mass, its live points.

    WHY THIS EXISTS. v1 rebuilds the whole candidate list inside every single
    placement attempt, walking every placed item to regenerate corners that
    have not changed. This keeps the list and updates it in place, which is
    correct only because deadness is permanent: free space never grows, so a
    point that nothing can start at stays that way (see geometry.is_live).

    It is a plain object created per carton in fill_carton, deliberately not a
    module-level dict keyed by id(). Two cartons packed in the same run would
    share such a dict, ids get recycled after garbage collection, and the
    lifetime of the entry would have nothing to do with the lifetime of the
    carton. That is a cache that goes wrong silently and intermittently.

    `points` is kept sorted bottom-first at all times, so place() can slice the
    front of it without sorting.
    """

    __slots__ = ("carton", "placements", "contents_mass", "points")

    def __init__(self, carton: Carton) -> None:
        self.carton = carton
        self.placements: list[Placement] = []
        self.contents_mass = 0
        self.points: list[tuple[int, int, int]] = []
        self._offer((0, 0, 0))

    def _offer(self, pt: tuple[int, int, int]) -> None:
        """Add a point, if it is live and not already held."""
        if pt not in self.points and is_live(pt, self.carton, self.placements):
            insort(self.points, pt, key=point_sort_key)

    def add(self, placement: Placement) -> None:
        """Record a placement and bring the live set up to date.

        Two steps: drop every point the new item now covers, then offer the
        new item's three exposed corners.

        Each corner is liveness-checked against every item placed so far,
        because a corner of this item can land inside an item placed earlier
        and must not enter the list. It does not need checking against this
        item: containment is half-open, so a box never covers its own exposed
        corners. That is also why the two steps commute, and why neither the
        order of the steps nor the position of the append below is
        load-bearing.
        """
        x, y, z = placement.pos
        w, d, h = placement.dims
        self.points = [q for q in self.points
                       if not covered_by(q, placement.pos, placement.dims)]
        self.placements.append(placement)
        self.contents_mass += placement.item.mass
        for corner in ((x + w, y, z), (x, y + d, z), (x, y, z + h)):
            self._offer(corner)

    def packed(self) -> PackedCarton:
        return PackedCarton(carton=self.carton, placements=self.placements)


def place(item: Item, state: CartonState) -> Placement | None:
    """First feasible placement, scanning live corner points bottom-first.

    Points are pre-sorted by (z, y, x), so first-fit is already the
    gravity-sensible choice. Whether scoring them by contact area instead is
    worth anything is re-tested in Phase 6: v1's ablation said no, but it ran
    while the candidate cap was discarding live points, so the result is not
    trustworthy.
    """
    carton = state.carton
    if (carton.max_contents_mass is not None
            and state.contents_mass + item.mass > carton.max_contents_mass):
        return None
    for pos in state.points[:MAX_CANDIDATES]:
        for orient_idx, dims in orientations(item):
            if fits(pos, dims, carton, state.placements):
                return Placement(item=item, pos=pos, dims=dims,
                                 orientation=orient_idx,
                                 sequence=len(state.placements))
    return None


def fill_carton(carton: Carton, items: Sequence[Item]
                ) -> tuple[PackedCarton, list[Item]]:
    """Greedily place items, in the given order, into one carton."""
    state = CartonState(carton)
    left: list[Item] = []
    for item in items:
        p = place(item, state)
        if p is None:
            left.append(item)
        else:
            state.add(p)
    return state.packed(), left


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
