# ADR-0002: Integer millimetres and grams, origin at the inside corner

- **Status:** accepted. The axis convention (y up) is superseded by [ADR-0006](0006-z-up-axes.md);
  the units and the corner rule still stand.
- **Date:** 2026-08-05

## Context

Packing is geometry, and geometry with floating point goes wrong in ways that are painful to debug.
Two items that should touch end up 0.0000001 mm apart, or 0.0000001 mm overlapping. An overlap check
either produces false collisions or silently misses real ones depending on which way the rounding
went, and nothing about the failure points at floats as the cause.

We also hand our output to a visualiser team who has to draw it. Every ambiguity we leave in the
coordinate system becomes a bug in their renderer that looks like a bug in our solver.

## Decision

**All lengths are integer millimetres. All weights are integer grams.** No floats anywhere in the
geometry. No unit suffixes in the data. Volumes are cubic millimetres and are therefore large
integers, which is fine.

Ratios (`volumeRatio`, `volumeUtilisation`) are the one exception and are floats between 0 and 1.
They are reporting figures, never inputs to a geometric decision.

**The origin is the inside bottom-left-back corner of the box.** `x` is width, `y` is height going
up, `z` is depth.

**A position is the corner of the item nearest the origin, never its centre.**

**Sizes in a response are as placed**, with rotation already applied.

## Why these specifically

Millimetres because it is the smallest unit anyone in a warehouse measures in, so nothing needs a
fraction. Grams for the same reason.

Corner rather than centre because every collision and bounds check is then a comparison of two
numbers per axis with no division, and because "item starts here and is this big" is easier to hold
in your head than "item is centred here so it reaches half its width either side".

Size-as-placed because the alternative makes the visualiser team apply our rotation convention
correctly to draw anything at all. That is a shared bug waiting to happen for no benefit. We resolve
rotation once, on our side, where the tests are.

Height as `y` because that is what every 3D renderer they are likely to use assumes, and matching
saves them a conversion.

## Consequences

- Overlap and bounds checks are exact integer comparisons. No epsilon anywhere.
- Any input with fractional dimensions must be converted at the boundary, by the caller.
- The visualiser team can render a placement as a cuboid at `position` of `size` with no maths.
  `rotation` is informational and a renderer can ignore it.
- If a future mode needs sub-millimetre precision, this has to be revisited. Nothing the client
  described comes close to needing it.
