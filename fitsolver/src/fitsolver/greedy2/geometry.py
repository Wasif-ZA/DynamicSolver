"""Geometry core for greedy2. All integer arithmetic: no floats, no epsilons.

This is greedy2's own copy of the v1 geometry helpers, deliberately duplicated
rather than imported. v1's geometry.py is frozen, so copying is what lets
greedy2 change candidate generation in later phases without any risk of
altering v1's output.

Phase 2 changes one thing here: candidate points that nothing can ever be
placed at are no longer returned. Orientation, overlap and support are still
v1's, unchanged.
"""
from __future__ import annotations

from ..domain import Carton, Item, Placement

# The 6 axis-aligned permutations of (w, d, h).
# Index = the `orientation` field in the contract. Never reorder this table:
# a renderer reads the index back, so reordering silently rotates every
# historical placement. Must stay identical to v1's table.
_PERMS: tuple[tuple[int, int, int], ...] = (
    (0, 1, 2), (0, 2, 1), (1, 0, 2), (1, 2, 0), (2, 0, 1), (2, 1, 0),
)


def orientations(item: Item) -> list[tuple[int, tuple[int, int, int]]]:
    """(orientation_index, rotated_dims) pairs permitted for this item."""
    w, d, h = item.dims
    base = (w, d, h)
    if item.allowed_rotations == "fixed":
        return [(0, base)]
    if item.allowed_rotations == "upright":
        # The height axis stays vertical, so only the two yaw rotations are
        # permitted. A square footprint yields just one distinct result.
        out = [(0, (w, d, h))]
        if w != d:
            out.append((2, (d, w, h)))  # perm (1,0,2)
        return out
    seen: set[tuple[int, int, int]] = set()
    out = []
    for idx, perm in enumerate(_PERMS):
        dims = (base[perm[0]], base[perm[1]], base[perm[2]])
        if dims not in seen:
            seen.add(dims)
            out.append((idx, dims))
    return out


def overlaps(pos_a: tuple[int, int, int], dims_a: tuple[int, int, int],
             pos_b: tuple[int, int, int], dims_b: tuple[int, int, int]) -> bool:
    """Do two axis-aligned boxes share any interior volume?

    Touching faces do not count as overlapping, which is why the comparison
    is strict on both sides: items may sit flush against each other.
    """
    return all(pos_a[i] < pos_b[i] + dims_b[i] and pos_b[i] < pos_a[i] + dims_a[i]
               for i in range(3))


def inside(pos: tuple[int, int, int], dims: tuple[int, int, int],
           carton: Carton) -> bool:
    """Is the box wholly within the carton interior?

    Flush against a wall is inside, so the far edge is compared with <=.
    """
    return all(pos[i] >= 0 and pos[i] + dims[i] <= carton.inner_dims[i]
               for i in range(3))


def _support_area(pos: tuple[int, int, int], dims: tuple[int, int, int],
                  placed: list[Placement]) -> int:
    """Area of this item's base resting on the floor or on tops of items."""
    x, y, z = pos
    w, d, _ = dims
    if z == 0:
        return w * d
    area = 0
    for p in placed:
        if p.pos[2] + p.dims[2] != z:
            continue  # its top is not at our base level
        ox = min(x + w, p.pos[0] + p.dims[0]) - max(x, p.pos[0])
        oy = min(y + d, p.pos[1] + p.dims[1]) - max(y, p.pos[1])
        if ox > 0 and oy > 0:
            area += ox * oy
    return area


def supported(pos: tuple[int, int, int], dims: tuple[int, int, int],
              placed: list[Placement], min_ratio_pct: int = 70) -> bool:
    """At least min_ratio_pct% of the base must rest on something.

    Integer comparison: area*100 >= base*ratio avoids float division.
    """
    base = dims[0] * dims[1]
    return _support_area(pos, dims, placed) * 100 >= base * min_ratio_pct


def point_sort_key(pt: tuple[int, int, int]) -> tuple[int, int, int]:
    """Bottom-first ordering: z, then y, then x.

    Gravity-sensible positions are tried first, which is what makes plain
    first-fit produce stable, human-packable layouts without any scoring.
    """
    return (pt[2], pt[1], pt[0])


def covered_by(pt: tuple[int, int, int], pos: tuple[int, int, int],
               dims: tuple[int, int, int]) -> bool:
    """Does a box occupy this point, so that nothing can ever start here?

    Half-open on every axis: `pos <= q < pos + dims`. The far face is excluded
    because a point exactly on the top or far side of a box is the position
    where the NEXT box starts, which is the whole basis of corner-point
    packing. Getting this bound wrong would delete the stacking positions.
    """
    return all(pos[a] <= pt[a] < pos[a] + dims[a] for a in range(3))


def is_live(pt: tuple[int, int, int], carton: Carton,
            placed: list[Placement]) -> bool:
    """Could any item ever start at this point?

    Two ways to be dead, and both are permanent, because placed items are
    never removed and the carton never grows:

      1. on or beyond a wall. x == W is outside the carton, not flush with it:
         flush means x + w == W, which is a different point.
      2. inside a placed item.

    Permanence is what makes the incremental cache in pack.py correct. A point
    this returns False for can be deleted and never reconsidered.
    """
    if any(pt[a] >= carton.inner_dims[a] for a in range(3)):
        return False
    return not any(covered_by(pt, p.pos, p.dims) for p in placed)


def candidates(placed: list[Placement], carton: Carton) -> list[tuple[int, int, int]]:
    """Every live corner point, rebuilt from scratch, bottom-first.

    THIS IS THE SLOW PATH and pack.py does not use it. CartonState maintains
    the same list incrementally. It is kept because it is an obviously correct
    definition of what that cache is supposed to contain, and the tests check
    the cache against it after every placement.

    The difference from v1: v1 returns dead points too. Sorted bottom-first
    and then capped, those dead low points crowd out the live high ones, so
    the solver stops stacking. Measured on the W1 benchmark, half of every
    scan was dead points, and the cap discarded live points in a quarter of
    all placement attempts.
    """
    pts: set[tuple[int, int, int]] = {(0, 0, 0)}
    for p in placed:
        x, y, z = p.pos
        w, d, h = p.dims
        pts.add((x + w, y, z))
        pts.add((x, y + d, z))
        pts.add((x, y, z + h))
    return sorted((q for q in pts if is_live(q, carton, placed)), key=point_sort_key)


def fits(pos: tuple[int, int, int], dims: tuple[int, int, int],
         carton: Carton, placed: list[Placement]) -> bool:
    """Inside the carton, clear of every placed item, and adequately supported."""
    return (inside(pos, dims, carton)
            and not any(overlaps(pos, dims, p.pos, p.dims) for p in placed)
            and supported(pos, dims, placed))
