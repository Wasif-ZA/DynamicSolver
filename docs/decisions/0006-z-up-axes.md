# ADR-0006: z is up

- **Status:** accepted. Supersedes the axis convention in
  [ADR-0002](0002-units-and-coordinates.md); its units and corner rule still stand.
- **Date:** recorded 2026-10-30

## Context

[ADR-0002](0002-units-and-coordinates.md) chose y as the up axis, to match common 3D renderers.
The solver was built with z up instead, and every response, fixture and test already uses it.

## Decision

**x is width, y is depth, z is height (up).** Every size is `[x, y, z]`. Every response states
this in its own `coordinate_system` block:

```json
{ "up": "z", "handedness": "right", "origin": "min_corner" }
```

The origin is still the inside bottom corner of the carton, and a position is still the item's
corner nearest the origin.

## Why

- **It is what the code, schemas and fixtures already do.** Changing it now would touch every
  layer for no gain.
- **Gravity is one axis.** The support rule, "lowest point first" placement and the pass ordering
  all read `z`, which keeps the geometry code plain.
- **The response says it explicitly,** so a renderer that wants y up swaps two axes once when it
  draws, and nothing is left to guess.

## Consequences

- The visualiser maps solver `[x, y, z]` to its own axes in one place.
- The Portal's box and item fields map Width to x, Length to y and Depth to z (`portal.py`,
  `AXIS_ORDER`). That mapping is still to be confirmed with the Portal team.
