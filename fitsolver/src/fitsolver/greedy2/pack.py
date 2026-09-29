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
from .geometry import (
    covered_by,
    fits_empty_carton,
    inside,
    is_live,
    orientations,
    overlaps,
    point_sort_key,
    room_admits,
    room_at,
    supported,
)

# Corner points considered per placement. None means no cap.
#
# The cap exists to bound the scan, not to choose between points. In v1 it did
# both, badly: half the list was dead points, so a cap of 64 often meant fewer
# than 32 real options, and the live high points that would have continued a
# stack were the ones pushed out. With dead points gone, 64 is 64.
#
# Swept at 64, 128 and uncapped once pruning was in. 128 and uncapped give
# identical layouts, which matches the measured maximum of 118 live points, so
# at 128 this is a safety bound rather than a choice between points. It is
# worth 2 cartons on W1 against 64 (25 rather than 27) for about 9 percent
# more time, and changes nothing on W2, W3 or W4.
MAX_CANDIDATES = 128

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

    __slots__ = ("carton", "placements", "contents_mass", "points", "infeasible")

    def __init__(self, carton: Carton) -> None:
        self.carton = carton
        self.placements: list[Placement] = []
        self.contents_mass = 0
        self.points: list[tuple[int, int, int]] = []
        # (point, dims, allowed_rotations) triples known to be unplaceable.
        # See place() for why a support failure must never be recorded here.
        self.infeasible: set[tuple] = set()
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

    def drop_points_too_small_for(self, smallest_item_dim: int) -> None:
        """Forget points whose room is narrower than the smallest item left.

        The room at a point only shrinks, and the items still to come only get
        smaller under a descending sort, so a point too tight for every
        remaining item is finished. Dropping it keeps later scans short.

        This cannot change any placement: a point is removed only when no
        remaining item could occupy it in any orientation, since an item needs
        its own smallest dimension to fit in the room's smallest dimension
        whichever way it is turned.
        """
        self.points = [q for q in self.points
                       if min(room_at(q, self.carton)) >= smallest_item_dim]

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

    shape = (item.dims, item.allowed_rotations)
    for pos in state.points[:MAX_CANDIDATES]:
        memo_key = (pos, *shape)
        if memo_key in state.infeasible:
            continue

        # O(1) exact pre-check: is there room here for any orientation at all?
        if not room_admits(item, room_at(pos, carton)):
            state.infeasible.add(memo_key)
            continue

        # Whether any orientation got as far as failing ONLY on support. That
        # failure is not permanent: a later item can become this one's floor,
        # so the point must stay open for retry. Memoising it would refuse
        # placements that are legal a moment later, which loses cartons
        # silently rather than failing a test.
        support_blocked = False
        for orient_idx, dims in orientations(item):
            if not inside(pos, dims, carton):
                continue
            if any(overlaps(pos, dims, p.pos, p.dims) for p in state.placements):
                continue
            if not supported(pos, dims, state.placements):
                support_blocked = True
                continue
            return Placement(item=item, pos=pos, dims=dims,
                             orientation=orient_idx,
                             sequence=len(state.placements))

        if not support_blocked:
            # Every orientation was out of bounds or hit a placed item, and
            # neither can come undone: the carton never grows and items are
            # never removed. So this shape can never be placed here again.
            state.infeasible.add(memo_key)
    return None


def smallest_dim_suffixes(items: Sequence[Item]) -> list[int]:
    """suffix[i] = the smallest dimension among items[i:], or 0 past the end.

    Computed once per carton fill rather than rescanned after every placement,
    which is what keeps the point removal below cheaper than the scans it
    saves.
    """
    suffix = [0] * (len(items) + 1)
    for i in range(len(items) - 1, -1, -1):
        suffix[i] = min(suffix[i + 1] or min(items[i].dims), min(items[i].dims))
    return suffix


def fill_carton(carton: Carton, items: Sequence[Item]
                ) -> tuple[PackedCarton, list[Item]]:
    """Greedily place items, in the given order, into one carton."""
    state = CartonState(carton)
    suffix = smallest_dim_suffixes(items)
    left: list[Item] = []
    for i, item in enumerate(items):
        p = place(item, state)
        if p is None:
            left.append(item)
        else:
            state.add(p)
            # Only after a placement can a point have become too tight, and
            # only the items still to come matter.
            if suffix[i + 1]:
                state.drop_points_too_small_for(suffix[i + 1])
    return state.packed(), left


def pack_one(ordering: Sequence[Item], cartons: Sequence[Carton],
             table: dict[tuple, tuple[int, ...]]
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
    by_volume = sorted(range(len(cartons)), key=lambda i: cartons[i].volume)

    while remaining:
        window, rest = remaining[:CHUNK], remaining[CHUNK:]
        # Carton types that cannot hold a single item in the window are not
        # worth filling: the result is always empty. With a window of mostly
        # large items this skips the small cartons outright.
        usable = {idx for item in window
                  for idx in table[(item.dims, item.allowed_rotations)]}
        best: tuple[PackedCarton, list[Item]] | None = None
        best_key: tuple[int, int] | None = None
        for ci in by_volume:
            if ci not in usable:
                continue
            carton = cartons[ci]
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


def carton_fit_table(items: Sequence[Item], cartons: Sequence[Carton]
                     ) -> dict[tuple, tuple[int, ...]]:
    """Per item SHAPE, which carton types could hold it if they were empty.

    Keyed by (dims, allowed_rotations), which is everything that decides the
    answer, so a 1000-item order over 40 distinct SKUs does 40 tests rather
    than 1000. The value is carton indices, in the caller's order.

    Two uses, both pure speed: skip carton types an item can never fit, and
    identify items that fit nothing before any geometry runs.
    """
    table: dict[tuple, tuple[int, ...]] = {}
    for item in items:
        key = (item.dims, item.allowed_rotations)
        if key not in table:
            table[key] = tuple(i for i, c in enumerate(cartons)
                               if fits_empty_carton(item, c))
    return table


def _fits_some_carton(item: Item, cartons: Sequence[Carton],
                      table: dict[tuple, tuple[int, ...]]) -> bool:
    """Is there a carton this item could go in, on both geometry and mass?

    Mass is checked here rather than in the shape table because two items of
    the same shape can have different masses.
    """
    for idx in table[(item.dims, item.allowed_rotations)]:
        limit = cartons[idx].max_contents_mass
        if limit is None or item.mass <= limit:
            return True
    return False


def _reject_message(item: Item, cartons: Sequence[Carton],
                    table: dict[tuple, tuple[int, ...]]) -> str:
    """Why this item could not be packed, in the packer's terms.

    An item that fits but is too heavy told "exceeds every carton in all
    permitted orientations" sends a packer looking for a bigger box, which is
    not the problem. The two causes need different words.
    """
    if table[(item.dims, item.allowed_rotations)]:
        return "Fits geometrically, but exceeds the mass limit of every carton"
    return "Exceeds every carton in all permitted orientations"


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
    table = carton_fit_table(items, cartons)

    # Items no carton can ever hold are rejected before packing, not
    # discovered during it. Left in, a CHUNK-sized run of them fills
    # pack_one's window, packs nothing, and takes every placeable item behind
    # them down as a false rejection.
    packable: list[Item] = []
    all_unplaced: list[Item] = []
    for item in items:
        (packable if _fits_some_carton(item, cartons, table)
         else all_unplaced).append(item)

    all_cartons: list[PackedCarton] = []
    for group in split_compatible(packable):
        ordering = sorted(group, key=lambda i: i.volume, reverse=True)
        packed, unplaced = pack_one(ordering, cartons, table)
        all_cartons.extend(packed)
        all_unplaced.extend(unplaced)

    rejects = [Reject(item_ref=i.ref, reason_code="NO_FITTING_CARTON",
                      message=_reject_message(i, cartons, table))
               for i in all_unplaced]
    return Solution(cartons=all_cartons, rejects=rejects, seed=seed,
                    time_budget_ms=time_budget_ms,
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    tier=1)
