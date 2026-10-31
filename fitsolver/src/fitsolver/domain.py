"""Pure data. Integer millimetres and integer grams everywhere.

Conversion to/from external formats happens once, in io.py.
Nothing in here knows JSON exists.
"""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class Item:
    ref: str
    dims: tuple[int, int, int]          # base (w, d, h), mm
    mass: int                            # g
    label: str = ""
    allowed_rotations: str = "any"       # any | upright | fixed
    dg_class: str | None = None
    incompatible_with: frozenset[str] = field(default_factory=frozenset)
    tags: tuple[str, ...] = ()

    @property
    def volume(self) -> int:
        w, d, h = self.dims
        return w * d * h


@dataclass(frozen=True)
class Carton:
    sku: str
    inner_dims: tuple[int, int, int]     # mm
    tare_mass: int                       # g
    max_contents_mass: int | None = None
    maximum_boxes: int | None = None     # most uses per solution; None = unlimited

    @property
    def volume(self) -> int:
        w, d, h = self.inner_dims
        return w * d * h


@dataclass(frozen=True)
class Placement:
    item: Item
    pos: tuple[int, int, int]            # min corner, carton-local, mm
    dims: tuple[int, int, int]           # post-rotation dims, mm
    orientation: int                     # 0..5, index into permutations
    sequence: int                        # physical packing order in carton


@dataclass
class PackedCarton:
    carton: Carton
    placements: list[Placement] = field(default_factory=list)

    @property
    def contents_mass(self) -> int:
        return sum(p.item.mass for p in self.placements)

    @property
    def fill_rate(self) -> float:
        if self.carton.volume == 0:
            return 0.0
        used = sum(p.dims[0] * p.dims[1] * p.dims[2] for p in self.placements)
        return used / self.carton.volume

    @property
    def centre_of_mass(self) -> tuple[int, int, int]:
        total = self.contents_mass
        if total == 0:
            return (0, 0, 0)
        cx = sum((p.pos[0] + p.dims[0] // 2) * p.item.mass for p in self.placements)
        cy = sum((p.pos[1] + p.dims[1] // 2) * p.item.mass for p in self.placements)
        cz = sum((p.pos[2] + p.dims[2] // 2) * p.item.mass for p in self.placements)
        return (cx // total, cy // total, cz // total)


@dataclass(frozen=True)
class Reject:
    item_ref: str
    reason_code: str
    message: str


@dataclass
class Solution:
    cartons: list[PackedCarton]
    rejects: list[Reject]
    seed: int
    time_budget_ms: int
    elapsed_ms: int
    tier: int                            # 0=cache, 1=greedy, 2=search
    mode: str = "rigid"

    @property
    def carton_count(self) -> int:
        return len(self.cartons)

    @property
    def total_mass(self) -> int:
        return sum(c.carton.tare_mass + c.contents_mass for c in self.cartons)

    @property
    def fill_rate(self) -> float:
        vol = sum(c.carton.volume for c in self.cartons)
        if vol == 0:
            return 0.0
        used = sum(p.dims[0] * p.dims[1] * p.dims[2]
                   for c in self.cartons for p in c.placements)
        return used / vol
