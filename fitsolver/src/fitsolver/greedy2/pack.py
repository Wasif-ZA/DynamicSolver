"""greedy2's solver: a greedy corner-point packer with multi-start and a
carton elimination post-pass.

    place(item, state)          -> first feasible Placement, or None
    fill_carton(carton, items)  -> greedily fill one carton
    pack(items, cartons, ...)   -> the full solve

Objective, lexicographic: fewest unplaced items, then fewest cartons, then
least total carton volume. Fill rate is reported but never optimised.

Why each design choice was made, what was measured, and what was tried and
rejected is in DESIGN_NOTES.md in this folder. Comments here only explain
what the code does and the rules it must not break.
"""
from __future__ import annotations

import random
import time
from bisect import insort
from collections.abc import Sequence

from ..domain import Carton, Item, PackedCarton, Placement, Reject, Solution
from .geometry import (
    contact_area,
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

# --------------------------------------------------------------------------- #
# Tuning constants. Each value was measured; see DESIGN_NOTES.md section 4.
# --------------------------------------------------------------------------- #

# Corner points considered per placement. A safety bound, not a choice: the
# most live points ever measured in one carton is 118.
MAX_CANDIDATES = 128

# Items offered to each carton per round. Bounds the quadratic cost of very
# large orders; has no effect below 240 items.
CHUNK = 240

# Score positions by contact area instead of taking the first fit. Measured
# worse, so OFF. Kept so bench/ablate_contact.py can re-run the comparison.
CONTACT_SCORING = False

# Carton elimination post-pass. The flags exist only so
# bench/ablate_phase12.py can switch each half off; production leaves all on.
ELIMINATE = True
ELIMINATE_EMPTY = True
ELIMINATE_REPACK = True

# Emptying: cartons tried as the victim per round, and total attempts.
ELIMINATE_VICTIMS = 3
ELIMINATE_ATTEMPTS = 8

# Repacking: the last 2 cartons into 1, then the last 3 into 2.
REPACK_SPANS = (2, 3)

# Repacking only runs when the cartons it would merge hold at most this many
# items. A cost bound: no carton count changes anywhere in the measured range.
REPACK_MAX_ITEMS = 40

# Above this many items, a different ordering is tried first.
LARGE_ORDER_ITEMS = 250

# Seeded restarts pick each next item from the first RESTART_WINDOW items
# still unclaimed in volume order. 1 would reproduce the volume ordering.
RESTART_WINDOW = 2

# Ceiling on passes per solve. A safety bound only: the budget divided by
# PASS_COST_MS is the real limit, and more passes can never make the result
# worse, because the best pass is kept.
MAX_PASSES = 64

# Measured cost of ONE pass, as (up to this many items, milliseconds), from
# bench/calibrate_passes.py using the slowest ordering. A fixed table rather
# than a clock, so the number of passes never depends on machine load.
PASS_COST_MS: tuple[tuple[int, int], ...] = (
    (25, 15), (50, 50), (100, 205), (200, 620), (300, 1300),
    (500, 2450), (750, 4100), (1000, 5600),
)

# Past the table, cost is extrapolated from the last row.
_LAST_N, _LAST_MS = PASS_COST_MS[-1]


# --------------------------------------------------------------------------- #
# Conflict groups: DG segregation and incompatibility, before any geometry.
# --------------------------------------------------------------------------- #

def conflict(a: Item, b: Item) -> bool:
    """Can these two never share a carton?

    True for an explicit incompatibility either way round, or two different
    dangerous-goods classes. An unset dg_class conflicts with nothing. This is
    the readable reference definition; the tests check the fast path against it.
    """
    if b.ref in a.incompatible_with or a.ref in b.incompatible_with:
        return True
    return bool(a.dg_class and b.dg_class and a.dg_class != b.dg_class)


class _Group:
    """One conflict group, with summaries that make admission a set lookup."""

    __slots__ = ("items", "dg", "member_refs", "barred_refs")

    def __init__(self) -> None:
        self.items: list[Item] = []
        # The one regulated class present, if any. Two differing classes
        # conflict, so a group can never hold more than one.
        self.dg: str | None = None
        self.member_refs: set[str] = set()
        # Every ref any member refuses to share with.
        self.barred_refs: set[str] = set()

    def admits(self, item: Item) -> bool:
        if self.dg is not None and item.dg_class and self.dg != item.dg_class:
            return False
        if item.ref in self.barred_refs:
            return False
        return not (item.incompatible_with and
                    item.incompatible_with & self.member_refs)

    def add(self, item: Item) -> None:
        self.items.append(item)
        if item.dg_class:
            self.dg = item.dg_class
        self.member_refs.add(item.ref)
        if item.incompatible_with:
            self.barred_refs |= item.incompatible_with


def split_compatible(items: Sequence[Item]) -> list[list[Item]]:
    """Greedy colouring of the conflict graph. Each group packs independently.

    Each item joins the first group that admits it, so the result is the same
    as testing every pair, but in linear rather than quadratic time.
    """
    groups: list[_Group] = []
    for item in items:
        for g in groups:
            if g.admits(item):
                g.add(item)
                break
        else:
            g = _Group()
            g.add(item)
            groups.append(g)
    return [g.items for g in groups]


# --------------------------------------------------------------------------- #
# One carton: live corner points and first-fit placement.
# --------------------------------------------------------------------------- #

class CartonState:
    """One carton being filled: its placements, its mass, its live points.

    The live point list is updated in place after each placement instead of
    being rebuilt. That is only correct because a dead point stays dead: free
    space never grows (see geometry.is_live). `points` is always kept sorted
    bottom-first, so place() can scan it from the front.

    Created per carton. Never cache this in a module-level dict keyed by id():
    ids are recycled after garbage collection.
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
        """Record a placement: drop the points it covers, offer its 3 corners.

        Containment is half-open, so a box never covers its own exposed
        corners, and the order of the two steps does not matter.
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
        """Forget points whose room is narrower than every remaining item.

        `smallest_item_dim` must be the SUFFIX MINIMUM over the items still to
        come, not the next item's smallest side, because some orderings put a
        thin item before a fat one. Cannot change any placement.
        """
        self.points = [q for q in self.points
                       if min(room_at(q, self.carton)) >= smallest_item_dim]

    def packed(self) -> PackedCarton:
        return PackedCarton(carton=self.carton, placements=self.placements)


def place(item: Item, state: CartonState) -> Placement | None:
    """First feasible placement, scanning live corner points bottom-first.

    Points are sorted by (z, y, x), so first-fit already prefers the lowest
    position. With CONTACT_SCORING on, the position sharing the most face area
    wins instead, ties going to the lowest.
    """
    carton = state.carton
    if (carton.max_contents_mass is not None
            and state.contents_mass + item.mass > carton.max_contents_mass):
        return None

    shape = (item.dims, item.allowed_rotations)
    best: Placement | None = None
    best_score = -1
    for pos in state.points[:MAX_CANDIDATES]:
        memo_key = (pos, *shape)
        if memo_key in state.infeasible:
            continue

        # Exact O(1) check: is there room here for any orientation at all?
        if not room_admits(item, room_at(pos, carton)):
            state.infeasible.add(memo_key)
            continue

        # A support failure is NOT permanent: a later item can become this
        # one's floor. Memoising it would silently refuse legal placements.
        support_blocked = False
        feasible_here = False
        for orient_idx, dims in orientations(item):
            if not inside(pos, dims, carton):
                continue
            if any(overlaps(pos, dims, p.pos, p.dims) for p in state.placements):
                continue
            if not supported(pos, dims, state.placements):
                support_blocked = True
                continue
            candidate = Placement(item=item, pos=pos, dims=dims,
                                  orientation=orient_idx,
                                  sequence=len(state.placements))
            if not CONTACT_SCORING:
                return candidate
            feasible_here = True
            score = contact_area(pos, dims, carton, state.placements)
            if best is None or score > best_score:
                best, best_score = candidate, score

        if not support_blocked and not feasible_here:
            # Bounds and overlap failures are permanent: the carton never
            # grows and items are never removed.
            state.infeasible.add(memo_key)

    # Only reached with scoring on.
    return best


def smallest_dim_suffixes(items: Sequence[Item]) -> list[int]:
    """suffix[i] = the smallest dimension among items[i:], or 0 past the end."""
    suffix = [0] * (len(items) + 1)
    for i in range(len(items) - 1, -1, -1):
        suffix[i] = min(suffix[i + 1] or min(items[i].dims), min(items[i].dims))
    return suffix


def _fill_state(state: CartonState, items: Sequence[Item]) -> list[Item]:
    """Greedily place items, in the given order, into `state`. Returns the rest."""
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
    return left


def fill_carton(carton: Carton, items: Sequence[Item]
                ) -> tuple[PackedCarton, list[Item]]:
    """Greedily place items, in the given order, into one carton."""
    state = CartonState(carton)
    left = _fill_state(state, items)
    return state.packed(), left


def _top_up(packed: PackedCarton, rest: list[Item]
            ) -> tuple[PackedCarton, list[Item]]:
    """Keep offering the chosen carton more items, CHUNK at a time.

    Only called when the carton took its WHOLE window, so it may have room for
    more. Stops after the first chunk it cannot take completely, so the cost
    stays bounded exactly as CHUNK intends.
    """
    state = state_from(packed)
    while rest:
        window, rest = rest[:CHUNK], rest[CHUNK:]
        left = _fill_state(state, window)
        if left:
            return state.packed(), left + rest
    return state.packed(), []


# --------------------------------------------------------------------------- #
# Many cartons: choose a carton type, fill it, repeat.
# --------------------------------------------------------------------------- #

def caps_left(kept: Sequence[PackedCarton], cartons: Sequence[Carton]
              ) -> list[int | None]:
    """Uses left per carton type (None = unlimited) after `kept` is counted.

    Cartons are matched by identity: every PackedCarton holds the very Carton
    object from `cartons` that fill_carton was given.
    """
    caps = [c.maximum_boxes for c in cartons]
    index = {id(c): i for i, c in enumerate(cartons)}
    for pc in kept:
        i = index[id(pc.carton)]
        if caps[i] is not None:
            caps[i] -= 1
    return caps


def _has_open_carton(item: Item, cartons: Sequence[Carton],
                     table: dict[tuple, tuple[int, ...]],
                     caps: list[int | None]) -> bool:
    """Could this item still go in a carton type that has uses left?"""
    for idx in table[(item.dims, item.allowed_rotations)]:
        if caps[idx] == 0:
            continue
        limit = cartons[idx].max_contents_mass
        if limit is None or item.mass <= limit:
            return True
    return False


def _set_aside_capped(items: Sequence[Item], cartons: Sequence[Carton],
                      table: dict[tuple, tuple[int, ...]],
                      caps: list[int | None], capped_out: list[Item]
                      ) -> list[Item]:
    """Keep the items some carton type with uses left can hold.

    The rest go to capped_out. Left in, a CHUNK of them would fill the window,
    pack nothing, and falsely reject the placeable items behind them. Order is
    preserved, so nothing else moves.
    """
    keep: list[Item] = []
    for item in items:
        (keep if _has_open_carton(item, cartons, table, caps)
         else capped_out).append(item)
    return keep


def _same_goods(item: Item) -> tuple:
    """canonical_key without the ref: two items with this key are interchangeable."""
    return canonical_key(item)[:-1]


def _replicate(pc: PackedCarton, remaining: list[Item], cap: int | None
               ) -> tuple[list[PackedCarton], list[Item]]:
    """Clone a finished carton while `remaining` still holds its exact contents.

    A clone is the same carton with interchangeable goods in the same
    positions, so it is valid by construction: nothing is re-placed. This is
    what makes long runs of identical items cheap.
    """
    need: dict[tuple, int] = {}
    for p in pc.placements:
        k = _same_goods(p.item)
        need[k] = need.get(k, 0) + 1
    # Tracked by POSITION in `remaining`, never by id(): io.py expands
    # quantity by repeating the same Item object, so ids are not unique.
    have: dict[tuple, list[int]] = {}
    for idx, item in enumerate(remaining):
        k = _same_goods(item)
        if k in need:
            have.setdefault(k, []).append(idx)
    copies = min(len(have.get(k, ())) // n for k, n in need.items())
    if cap is not None:
        copies = min(copies, cap)
    if copies <= 0:
        return [], remaining
    next_of = {k: iter(v) for k, v in have.items()}
    clones: list[PackedCarton] = []
    used: set[int] = set()
    for _ in range(copies):
        placements = []
        for p in pc.placements:
            idx = next(next_of[_same_goods(p.item)])
            used.add(idx)
            placements.append(Placement(item=remaining[idx], pos=p.pos,
                                        dims=p.dims, orientation=p.orientation,
                                        sequence=p.sequence))
        clones.append(PackedCarton(carton=pc.carton, placements=placements))
    return clones, [it for idx, it in enumerate(remaining) if idx not in used]


def pack_one(ordering: Sequence[Item], cartons: Sequence[Carton],
             table: dict[tuple, tuple[int, ...]],
             caps: list[int | None] | None = None
             ) -> tuple[list[PackedCarton], list[Item]]:
    """Fill cartons with items in the given order, one carton at a time.

    Each round, EVERY usable carton type is test-filled with the next CHUNK
    items, and the one packing the most volume is kept, ties going to the
    smaller carton. This is the most important decision in the solver.

    `caps` is the uses left per carton type (maximum_boxes, None = unlimited).
    It is decremented in place, so a caller can share it across calls.
    """
    if caps is None:
        caps = [c.maximum_boxes for c in cartons]
    limited = any(cap is not None for cap in caps)
    capped_out: list[Item] = []
    remaining = list(ordering)
    if limited:
        # A type may already be used up by an earlier conflict group.
        remaining = _set_aside_capped(remaining, cartons, table, caps, capped_out)
    out: list[PackedCarton] = []
    by_volume = sorted(range(len(cartons)), key=lambda i: cartons[i].volume)

    while remaining:
        window, rest = remaining[:CHUNK], remaining[CHUNK:]
        # Skip carton types that cannot hold a single item in the window.
        usable = {idx for item in window
                  for idx in table[(item.dims, item.allowed_rotations)]}
        best: tuple[PackedCarton, list[Item]] | None = None
        best_key: tuple[int, int] | None = None
        best_ci = -1
        for ci in by_volume:
            if ci not in usable or caps[ci] == 0:
                continue
            carton = cartons[ci]
            pc, left = fill_carton(carton, window)
            if not pc.placements:
                continue
            packed_volume = sum(p.dims[0] * p.dims[1] * p.dims[2]
                                for p in pc.placements)
            key = (-packed_volume, carton.volume)
            if best_key is None or key < best_key:
                best_key, best, best_ci = key, (pc, left), ci
        if best is None:
            return out, capped_out + remaining
        pc, left = best
        if not left and rest:
            # Without this a carton can never hold more than CHUNK items.
            pc, rest = _top_up(pc, rest)
        out.append(pc)
        remaining = left + rest
        if caps[best_ci] is not None:
            caps[best_ci] -= 1
        if not left and remaining:
            clones, remaining = _replicate(pc, remaining, caps[best_ci])
            out.extend(clones)
            if caps[best_ci] is not None:
                caps[best_ci] -= len(clones)
        if caps[best_ci] == 0:
            remaining = _set_aside_capped(remaining, cartons, table, caps,
                                          capped_out)
    return out, capped_out + remaining


# --------------------------------------------------------------------------- #
# Carton elimination: try to remove a carton from a finished layout.
# --------------------------------------------------------------------------- #

def state_from(packed: PackedCarton) -> CartonState:
    """Rebuild the live-point state of an already filled carton.

    Replaying the placements reproduces the point set exactly.
    drop_points_too_small_for is deliberately not replayed: it depended on
    which items were still to come, and those are now different.
    """
    state = CartonState(packed.carton)
    for p in packed.placements:
        state.add(p)
    return state


def _admits(item: Item, placements: Sequence[Placement]) -> bool:
    """Can this item join these placements, on conflict rules alone?

    Needed because elimination moves items between cartons that may come from
    different conflict groups. Geometry would never catch a DG clash.
    """
    return not any(conflict(item, p.item) for p in placements)


def _empty_into(victim: PackedCarton, others: Sequence[PackedCarton]
                ) -> list[PackedCarton] | None:
    """Move every item of `victim` into `others`, or return None.

    Largest items first, since they are the likeliest to fail.
    """
    free = 0
    for pc in others:
        if pc.carton.max_contents_mass is None:
            free = None
            break
        free += pc.carton.max_contents_mass - pc.contents_mass
    if free is not None and victim.contents_mass > free:
        return None   # cannot fit by mass alone; skip the geometry

    # States are rebuilt lazily: a carton already full by mass is skipped
    # without replaying its placements, which was most of the solve time.
    states: list[CartonState | None] = [None] * len(others)
    mass = [pc.contents_mass for pc in others]
    items = sorted((p.item for p in victim.placements), key=lambda i: -i.volume)
    for item in items:
        for k, pc in enumerate(others):
            limit = pc.carton.max_contents_mass
            if limit is not None and mass[k] + item.mass > limit:
                continue
            if not _admits(item, pc.placements if states[k] is None
                           else states[k].placements):
                continue
            if states[k] is None:
                states[k] = state_from(pc)
            p = place(item, states[k])
            if p is not None:
                states[k].add(p)
                mass[k] += item.mass
                break
        else:
            return None
    return [pc if st is None else st.packed() for pc, st in zip(others, states)]


def _repack_tail(out: Sequence[PackedCarton], span: int,
                 cartons: Sequence[Carton],
                 table: dict[tuple, tuple[int, ...]]
                 ) -> list[PackedCarton] | None:
    """Re-pack the last `span` cartons from scratch, hoping for span - 1.

    Returns None unless the result uses fewer cartons AND places everything.
    """
    tail = out[-span:]
    items = [p.item for pc in tail for p in pc.placements]
    # Repacking is a small full solve, so it is capped by item count.
    if len(items) > REPACK_MAX_ITEMS:
        return None
    # pack_one enforces no conflict rules, so only repack a tail that forms a
    # single conflict group.
    if len(split_compatible(items)) != 1:
        return None
    for _name, sort_key in SORT_KEYS:
        # The cartons outside the tail still count against maximum_boxes.
        got, left = pack_one(sorted(items, key=sort_key), cartons, table,
                             caps_left(out[:-span], cartons))
        if not left and len(got) < span:
            return list(out[:-span]) + got
    return None


def eliminate(out: Sequence[PackedCarton], cartons: Sequence[Carton],
              table: dict[tuple, tuple[int, ...]]) -> list[PackedCarton]:
    """Remove cartons from a finished layout, if any can be removed.

    1. Empty the carton holding the fewest items into the others.
    2. Re-pack the last two, then the last three, cartons into one fewer.

    A move is only taken if it removes a carton and places every item, so the
    result is never worse than the input. Bounded by fixed counts, not a clock.
    """
    result = list(out)
    attempts = 0
    removed = ELIMINATE_EMPTY
    while removed and len(result) > 1 and attempts < ELIMINATE_ATTEMPTS:
        # Fewest items, then smallest carton, then position: a total order,
        # so the choice of victim is deterministic.
        order = sorted(range(len(result)),
                       key=lambda i: (len(result[i].placements),
                                      result[i].carton.volume, i))
        removed = False
        for vi in order[:ELIMINATE_VICTIMS]:
            if attempts >= ELIMINATE_ATTEMPTS:
                break
            attempts += 1
            merged = _empty_into(result[vi],
                                 [pc for i, pc in enumerate(result) if i != vi])
            if merged is not None:
                result, removed = merged, True
                break

    for span in REPACK_SPANS if ELIMINATE_REPACK else ():
        while len(result) >= span:
            better = _repack_tail(result, span, cartons, table)
            if better is None:
                break
            result = better
    return result


# --------------------------------------------------------------------------- #
# Order preparation: fit table, rejects, canonical order.
# --------------------------------------------------------------------------- #

def carton_fit_table(items: Sequence[Item], cartons: Sequence[Carton]
                     ) -> dict[tuple, tuple[int, ...]]:
    """For each item SHAPE, the carton types that could hold it when empty.

    Keyed by (dims, allowed_rotations), so 1000 items over 40 SKUs cost 40
    tests. Values are carton indices in the caller's order.
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
    """Could any carton hold this item, on both geometry and mass?"""
    for idx in table[(item.dims, item.allowed_rotations)]:
        limit = cartons[idx].max_contents_mass
        if limit is None or item.mass <= limit:
            return True
    return False


def _reject_message(item: Item, cartons: Sequence[Carton],
                    table: dict[tuple, tuple[int, ...]]) -> str:
    """Why this item could not be packed: too big, or too heavy."""
    if table[(item.dims, item.allowed_rotations)]:
        return "Fits geometrically, but exceeds the mass limit of every carton"
    return "Exceeds every carton in all permitted orientations"


def canonical_key(item: Item) -> tuple:
    """Total order over items by content, ignoring request order.

    The same goods submitted in a different sequence must give the same
    layout. dg_class is split in two because None cannot be compared to str.
    """
    return (item.dims, item.mass, item.allowed_rotations,
            item.dg_class is None, item.dg_class or "",
            tuple(sorted(item.incompatible_with)), item.ref)


# --------------------------------------------------------------------------- #
# Orderings: the four named sort keys, then seeded restarts.
# --------------------------------------------------------------------------- #

# Keys return NEGATED values so a plain ascending sort is descending. Python's
# sort is stable, so ties keep canonical order and never vary between runs.
SORT_KEYS: tuple[tuple[str, object], ...] = (
    ("volume", lambda i: (-i.volume,)),
    ("longest_edge", lambda i: (-max(i.dims), -min(i.dims))),
    ("mass", lambda i: (-i.mass, -i.volume)),
    ("base_area", lambda i: (-(i.dims[0] * i.dims[1]), -i.volume)),
)

# Best-first order of the named keys, by order size. Volume wins up to 250
# items; longest edge wins above. Mass is weakest at large sizes, so last.
_SMALL_FIRST = ("volume", "longest_edge", "base_area", "mass")
_LARGE_FIRST = ("longest_edge", "base_area", "volume", "mass")


def sort_keys_for(n_items: int) -> tuple[tuple[str, object], ...]:
    """The named orderings to try, best-first for an order of this size."""
    by_name = dict(SORT_KEYS)
    names = _SMALL_FIRST if n_items <= LARGE_ORDER_ITEMS else _LARGE_FIRST
    return tuple((n, by_name[n]) for n in names)


def restart_ordering(group: Sequence[Item], rng: random.Random,
                     window: int | None = None) -> list[Item]:
    """A seeded permutation of one group that stays close to volume order.

    Each next item is chosen at random from the first `window` still unclaimed
    in volume-descending order, so big items still come first. Deterministic
    for a given `rng`; ties stay canonical because the input is canonical.
    """
    w = RESTART_WINDOW if window is None else window
    pool = sorted(group, key=lambda i: (-i.volume,))
    out: list[Item] = []
    while pool:
        out.append(pool.pop(rng.randrange(min(w, len(pool)))))
    return out


def ordering_for_pass(p: int, keys: Sequence[tuple[str, object]],
                      seed: int) -> object:
    """The function that orders a group on pass `p`.

    Passes 0 to len(keys) - 1 use the named keys; later passes are seeded
    restarts. Each restart gets its own Random seeded from (seed, p), so pass
    7 is the same whether or not passes 5 and 6 ran.
    """
    if p < len(keys):
        return lambda group, k=keys[p][1]: sorted(group, key=k)
    rng = random.Random(seed * 1_000_003 + p)
    return lambda group, r=rng: restart_ordering(group, r)


# --------------------------------------------------------------------------- #
# Budget and bounds.
# --------------------------------------------------------------------------- #

def estimated_pass_ms(n_items: int) -> int:
    """What one pass over this many items is expected to cost."""
    for limit, ms in PASS_COST_MS:
        if n_items <= limit:
            return ms
    return max(_LAST_MS, _LAST_MS * n_items // _LAST_N)


def passes_for(n_items: int, time_budget_ms: int) -> int:
    """How many passes to run: budget over estimated cost, 1 to MAX_PASSES.

    Always at least one, because an answer is not optional. So an order whose
    single pass costs more than the budget overruns it: a correct late answer,
    never a wrong prompt one. No clock is read.
    """
    if n_items <= 0:
        return 1
    affordable = time_budget_ms // estimated_pass_ms(n_items)
    return max(1, min(MAX_PASSES, affordable))


def lower_bound(groups: Sequence[Sequence[Item]],
                cartons: Sequence[Carton]) -> int:
    """Fewest cartons any correct solution could use.

    For a set of items: the larger of total volume over the largest carton
    volume, and total mass over the largest mass limit. Taken over the whole
    order, and summed per dangerous-goods class, since two classes can never
    share a carton; the larger of the two is returned. Not summed per conflict
    group: greedy colouring can split an incompatible_with chain into more
    groups than a solution needs. The mass bound only counts when EVERY
    carton has a limit. Integer ceilings only.
    """
    biggest_volume = max((c.volume for c in cartons), default=0)
    limits = [c.max_contents_mass for c in cartons]
    biggest_mass = None if any(x is None for x in limits) else max(limits)

    def bound(items: Sequence[Item]) -> int:
        b = 1
        if biggest_volume:
            b = max(b, -(-sum(i.volume for i in items) // biggest_volume))
        if biggest_mass:
            b = max(b, -(-sum(i.mass for i in items) // biggest_mass))
        return b

    items = [i for group in groups for i in group]
    if not items:
        return 0
    by_class: dict[str, list[Item]] = {}
    for i in items:
        if i.dg_class:
            by_class.setdefault(i.dg_class, []).append(i)
    return max(bound(items), sum(bound(c) for c in by_class.values()))


def result_key(packed: Sequence[PackedCarton],
               unplaced: Sequence[Item]) -> tuple[int, int, int]:
    """The objective: unplaced, then cartons, then total carton volume."""
    return (len(unplaced), len(packed),
            sum(c.carton.volume for c in packed))


# --------------------------------------------------------------------------- #
# The solve.
# --------------------------------------------------------------------------- #

def _run_pass_ordered(groups: Sequence[list[Item]], cartons: Sequence[Carton],
                      table: dict[tuple, tuple[int, ...]], order_fn
                      ) -> tuple[list[PackedCarton], list[Item]]:
    """One full pass over every conflict group, ordered by `order_fn`.

    Groups are visited in a fixed order, so a restart's Random is consumed in
    a fixed order too.
    """
    packed: list[PackedCarton] = []
    unplaced: list[Item] = []
    caps = [c.maximum_boxes for c in cartons]   # fresh for every pass
    for group in groups:
        out, left = pack_one(order_fn(group), cartons, table, caps)
        packed.extend(out)
        unplaced.extend(left)
    return packed, unplaced


def _run_pass(groups: Sequence[list[Item]], cartons: Sequence[Carton],
              table: dict[tuple, tuple[int, ...]], sort_key
              ) -> tuple[list[PackedCarton], list[Item]]:
    """One pass in one named sort order. Used by the bench scripts."""
    return _run_pass_ordered(groups, cartons, table,
                             lambda group: sorted(group, key=sort_key))


def pack(items: Sequence[Item], cartons: Sequence[Carton],
         time_budget_ms: int, seed: int) -> Solution:
    """Solve: several orderings, each followed by elimination, best kept.

    Steps: reject items no carton can hold; sort into canonical order; split
    into conflict groups; compute the lower bound; then run up to
    passes_for(...) passes and keep the best under result_key, stopping early
    if a pass reaches the lower bound.

    Deterministic: the same request and seed give the same layout on any
    machine. The only randomness is seeded from `seed`, and the only clock
    read is elapsed_ms, measured after the answer is fixed.
    """
    t0 = time.monotonic()
    table = carton_fit_table(items, cartons)

    # Reject unplaceable items up front. Left in, a CHUNK of them would fill
    # pack_one's window and falsely reject the placeable items behind them.
    packable: list[Item] = []
    all_unplaced: list[Item] = []
    for item in items:
        (packable if _fits_some_carton(item, cartons, table)
         else all_unplaced).append(item)

    canonical = sorted(packable, key=canonical_key)
    groups = split_compatible(canonical)
    bound = lower_bound(groups, cartons)
    min_volume = min((c.volume for c in cartons), default=0)

    best: tuple[list[PackedCarton], list[Item]] | None = None
    best_key: tuple[int, int, int] | None = None
    keys = sort_keys_for(len(canonical))
    for p in range(passes_for(len(canonical), time_budget_ms)):
        order_fn = ordering_for_pass(p, keys, seed)
        packed, unplaced = _run_pass_ordered(groups, cartons, table, order_fn)
        if ELIMINATE:
            packed = eliminate(packed, cartons, table)
        key = result_key(packed, unplaced)
        if best_key is None or key < best_key:
            best_key, best = key, (packed, unplaced)
        if (not unplaced and len(packed) == bound
                and all(c.carton.volume == min_volume for c in packed)):
            break  # optimal on count and volume; no ordering can beat it

    all_cartons, group_unplaced = best if best is not None else ([], [])

    rejects = [Reject(item_ref=i.ref, reason_code="NO_FITTING_CARTON",
                      message=_reject_message(i, cartons, table))
               for i in all_unplaced]
    # These all fit some carton type, empty, on geometry and mass, so they
    # were left only because each type they fit reached maximum_boxes.
    # UNPLACEABLE is already in the contract, so no schema change is needed.
    rejects += [Reject(item_ref=i.ref, reason_code="UNPLACEABLE",
                       message="Fits, but every carton type it fits has reached "
                               "its maximum_boxes limit")
                for i in group_unplaced]
    return Solution(cartons=all_cartons, rejects=rejects, seed=seed,
                    time_budget_ms=time_budget_ms,
                    elapsed_ms=int((time.monotonic() - t0) * 1000),
                    tier=1)
