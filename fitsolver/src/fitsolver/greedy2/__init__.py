"""greedy2: a separate greedy packing solver, developed alongside v1.

v1 (fitsolver.pack, fitsolver.geometry) is frozen. All improvements go here, so
a change can never alter v1's output and the two can be benchmarked side by
side. What changed, what was measured, and what was rejected is in
DESIGN_NOTES.md in this folder.

Public surface mirrors v1's:

    from fitsolver.greedy2.pack import pack
    pack(items, cartons, time_budget_ms, seed) -> Solution

This package deliberately re-exports nothing. Hoisting `pack` here would make
`fitsolver.greedy2.pack` mean either the submodule or the function, depending
on import order.
"""
