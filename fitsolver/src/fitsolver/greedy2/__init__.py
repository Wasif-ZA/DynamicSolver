"""greedy2: a separate greedy packing solver, developed alongside v1.

v1 (fitsolver.pack, fitsolver.geometry) is frozen. greedy2 is where the
improvements go, so that a regression here can never change v1's output and
the two can be benchmarked against each other on identical input.

Phase 1 is a faithful copy of v1: same algorithm, same layouts, byte-for-byte
identical solution documents. That is the point of the phase. It proves the
new package, the algorithm selection and the parametrized tests are wired up
correctly before any behaviour changes, so later phases can attribute any
difference in output to the change under test and nothing else.

Public surface mirrors v1's exactly, at the matching path:

    from fitsolver.greedy2.pack import pack
    pack(items, cartons, time_budget_ms, seed) -> Solution

This package deliberately re-exports nothing. Hoisting `pack` to the package
level would make `fitsolver.greedy2.pack` name both the submodule and the
function inside it, depending on whether the submodule had been imported yet,
and reaching anything else in that module through the package would then fail.
"""
