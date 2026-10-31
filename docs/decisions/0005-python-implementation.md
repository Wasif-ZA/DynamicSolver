# ADR-0005: Write the solver in Python

- **Status:** accepted. Supersedes [ADR-0004](0004-cpp-implementation.md).
- **Date:** recorded 2026-10-30. The solver has been Python since its first working version; this
  record catches the log up with what was built.

## Context

[ADR-0004](0004-cpp-implementation.md) chose C++20 for speed headroom, and said plainly that if C++
slowed the team down, the honest move was to supersede it. A working solver, with tests and
benchmarks, mattered more in a thirteen-week unit than raw speed.

## Decision

**The solver is the Python package `fitsolver`** (Python 3.11 or newer), served over HTTP with
FastAPI.

## Why

- **The algorithm decides the speed, not the language.** greedy2 answers small orders in
  milliseconds and spends the rest of the 1 to 2 second budget on extra orderings
  ([ADR-0007](0007-greedy2-is-the-solver.md)).
- **Faster to build and to change.** The solver went through twelve measured phases. Each was a
  short change with its own benchmark, which would have cost far more in C++.
- **Better testing for this problem.** pytest and Hypothesis generate random orders and check every
  invariant (bounds, overlaps, support, conservation) automatically.
- **Integers still work.** Python integers never overflow, so
  [ADR-0002](0002-units-and-coordinates.md)'s integer millimetres and grams carry over with no
  64-bit volume worries.

## What it costs

- **Less headroom on very large orders.** One pass over about 300 items already costs about the
  whole budget, so those orders run a single pass and can overrun. Profiling, then targeted fixes
  (or a compiled hot loop), come before any rewrite.
- **The C++ layout in the old architecture plan was never built.** `architecture.md` now describes
  the real package.
