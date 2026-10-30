# Decision log

One file per decision that was hard to make or would otherwise be re-argued every fortnight.

**Why bother.** Two reasons. Practically, it stops "why is everything in millimetres?" coming back
every sprint. For the unit, the Individual Reflective Report has to explicitly refer to artefacts,
and a dated record of a decision you argued for is far better evidence than a memory in November.

## Writing one

Copy the shape of an existing file. Number it next in sequence, keep it short, and put the reasoning
in, not just the conclusion. A decision with no "why" is worthless six weeks later.

Statuses: **proposed**, **accepted**, **superseded by ADR-NNNN**.

Never edit an accepted decision to change its meaning. Write a new one that supersedes it and mark
the old one. The trail of what we changed our minds about is the useful part.

## Index

| ADR | Decision | Status |
|---|---|---|
| [0001](0001-record-decisions.md) | Keep a decision log | accepted |
| [0002](0002-units-and-coordinates.md) | Integer millimetres and grams, origin at the inside corner | accepted |
| [0003](0003-solver-only-scope.md) | We build the solver only, and publish a contract | accepted |
| [0004](0004-cpp-implementation.md) | Write the solver in C++20 | superseded by 0005 |
| [0005](0005-python-implementation.md) | Write the solver in Python | accepted |
| [0006](0006-z-up-axes.md) | z is up | accepted (supersedes the axes in 0002) |
| [0007](0007-greedy2-is-the-solver.md) | greedy2 is the solver; v1 and bin4d are frozen baselines | accepted |
| [0008](0008-enforce-maximum-boxes.md) | Enforce `maximum_boxes` inside the solver | accepted |
| [0009](0009-further-optimise.md) | "Further Optimise": an opt-in exact search for one smaller carton | accepted |
