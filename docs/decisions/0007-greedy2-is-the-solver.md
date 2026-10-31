# ADR-0007: greedy2 is the solver; v1 and bin4d are frozen baselines

- **Status:** accepted
- **Date:** recorded 2026-10-30

## Context

Three packers existed: **v1** (`fitsolver/pack.py`, a corner-point greedy), **bin4d** (a layer
packer in the style of the client's current library, BoxPacker) and **greedy2**, developed
beside v1 so the two could be compared on identical input. Developing three in parallel split the
effort and left it unclear which one shipped.

## Decision

**greedy2 is the only solver under development, and the one `engine.solve` runs.** v1 and bin4d
are kept unchanged as baselines for benchmarks, and are never edited.

## Why

Measured, cartons used (fewer is better):

| Workload | v1 | greedy2 |
|---|---:|---:|
| 1000 items, all different shapes | 36 | **20** |
| 1000 items from 40 SKUs | 32 | **20** |
| 40 small orders of 5 to 60 items | 60 | **46** |

Against proven optima on 62 small orders, greedy2 is 8.7% above optimum with no mass limits and
2.6% above with realistic mass limits (v1: 23.2% and 13.2%), and never more than one carton over.
bin4d was ruled out because it does not enforce support, rotation rules or conflict rules, and
40% of its items float.

The biggest single gain came from **dropping dead corner points**, which had been crowding out
the positions that let items stack.

## Consequences

- One codebase to improve, test and document.
- Every greedy2 change is measured against v1 and the proven optima before it is kept. The keep
  rule: a change must reduce cartons somewhere and make nothing worse.
- What greedy2 cannot do is recorded too: some tight layouts need positions that first-fit never
  tries. Smarter free-space tracking (empty maximal spaces) is the next large improvement, and
  [ADR-0009](0009-further-optimise.md) covers the small-order case in the meantime.
