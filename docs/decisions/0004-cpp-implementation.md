# ADR-0004: Write the solver in C++

- **Status:** superseded by [ADR-0005](0005-python-implementation.md)
- **Date:** 2026-08-05

> **Superseded.** The team stayed in Python: no C++ was ever written, and the repository holds the
> Python package `fitsolver`. The decision is recorded in
> [ADR-0005](0005-python-implementation.md) (dynamic-fit ADR-0005 is dated 2026-08-25), and was
> carried into the 10 Sep presentation planning meeting. The text below is kept unchanged as the original argument.

## Context

The solver is the whole of our scope ([ADR-0003](0003-solver-only-scope.md)). Its job is geometry
and search: fit units into containers, check collisions, try orientations, do it again a few
thousand times per order, and come back inside the client's 1 to 2 second bar.

The other teams' choices do not constrain us. We exchange JSON over a documented contract
([`contract.md`](../contract.md)), so nothing about their stack leaks into ours.

## Decision

**The solver is written in C++20.**

## Why

**It suits the work.** Bin packing is tight loops over small value types with no I/O. That is the
case where C++ is straightforwardly good, and where a managed language spends its time on
allocation and indirection instead of the actual search.

**Headroom on the latency bar.** 1 to 2 seconds is generous for one order, and the naive heuristic
will meet it in any language. The value is what happens after: we can afford a more thorough search
inside the same budget, which shows up directly as better packing efficiency. Efficiency is the
client's number one priority on the solver side.

**The client asked for object-oriented and extensible.** C++ gives us both without ceremony:
abstract base classes for the mode interface, value semantics and RAII for the domain types.

**Exact integer arithmetic is natural.** [ADR-0002](0002-units-and-coordinates.md) commits us to
integer millimetres. C++ gives us fixed-width integer types and a compiler that will warn about
narrowing, rather than a language where every number is a double until it surprises you.

## What it costs

Being honest about the trade, because these are real and we should plan for them.

- **Slower to write.** Everything takes more lines than the equivalent Python. Build the naive
  heuristic first and get it correct before anyone optimises anything.
- **Memory-unsafe by default.** Geometry code is index arithmetic, which is precisely where
  out-of-bounds bugs live. Mitigated by building debug with `-fsanitize=address,undefined` and by
  preferring `std::vector`, `std::span` and range-based loops over raw pointer arithmetic.
- **Integer overflow is undefined behaviour, not a wrong answer.** Volumes in cubic millimetres
  exceed 32 bits for anything container-sized. `Dimensions::volume()` returns `std::int64_t` for
  this reason, and it is called out in [`architecture.md`](../architecture.md).
- **Build setup is a real task.** CMake, a JSON library, and a test framework need wiring before
  anyone writes a line of solver logic. Whoever picks this up should treat it as its own issue and
  not underestimate it.
- **Uneven team experience.** Likely the biggest practical risk. Pair on the first few pieces rather
  than letting whoever is most comfortable in C++ take all the interesting work. The unit rewards
  breadth of contribution, so concentrating the C++ knowledge in one person hurts everyone's mark as
  well as the project.

## Alternatives considered

**Python.** Much faster to write and the naive heuristic would still meet the latency bar. Rejected
because it leaves no headroom for a more thorough search, and search quality is the client's stated
priority.

**Java.** Fine middle ground, memory-safe, good tooling. Rejected as the worse of both: more
ceremony than Python without C++'s headroom.

## Consequences

- We need a build toolchain decision before implementation starts: CMake, a JSON library, and a test
  framework. That is a separate ADR once someone has tried them.
- The JSON boundary stays isolated in one directory, so the contract and the geometry can change
  independently.
- If C++ turns out to be sinking the team's velocity by mid-semester, the honest move is to
  supersede this record rather than quietly struggle. A working Python solver beats a half-finished
  C++ one, and the report can defend the change.
