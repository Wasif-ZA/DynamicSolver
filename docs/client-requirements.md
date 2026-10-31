# Client requirements

From the client Q&A session, 2026-08-05. The client is the person who runs the warehouse operation.

**A note on the source.** These come from a machine transcript of a ~26 minute session and parts of
it are badly garbled. Anything below marked **[unconfirmed]** is our reading of a mangled passage,
not something the client clearly said. Do not quote the transcript in a report. The client is back
in two weeks, so the [open questions](#open-questions-for-the-client) are what we ask him.

**Updated 2026-10-30.** R7 and R8 and the changes to R5 and the out-of-scope list came after the
session, from the Portal's box data and the client's challenge order. The decisions they led to are
in [`decisions/`](decisions/README.md).

## The job

Given items to ship and the box types a warehouse stocks, decide which boxes to use and where each
item goes inside them.

We build the solver. The visualiser and the portal are other teams. See
[ADR-0003](decisions/0003-solver-only-scope.md).

## Requirements

### R1. Packing groups (core)

Certain items cannot share a box. The driver is legal: different dangerous goods classes may not be
packed together. The client was explicit that this is **a core requirement, not a nice-to-have**.

He also wants it **generic**. Not hardcoded to dangerous goods. A client with no safety concern at
all should be able to say "put the headphones in one box and the keyboards in another". That is why
the contract expresses rules over free-text **groups** rather than over item IDs.

He accepts that honouring this produces a less efficient packing. It is a legal constraint, so it
wins over efficiency.

### R2. Latency, 1 to 2 seconds

The client's bar for a single order. Longer than that and workers stop using the tool.

This is a **latency** requirement, not a throughput one. See R3.

### R3. Load is small

| Figure | Value |
|---|---|
| Concurrent users | Very few |
| Orders per day, small client | 50 |
| Orders per day, large client | 50,000 |
| Largest realistic single batch | ~1,000 |

He was asked directly whether the system should handle 50,000 requests and said no. 50,000 is a
daily total across a whole warehouse, not a burst. 1,000 orders at once would already be, in his
words, a legendary performance from the workers.

**He explicitly told us not to build rate limiting or request throttling.**

### R4. Reject orders that cannot be packed

The client said, plainly: "I'd say reject the order. Yep, just reject it."

**[unconfirmed]** The question this answered is not captured in the transcript. Context suggests it
was about an item that fits in no available box. Our contract returns per-unit reasons rather than a
bare error, so the portal can tell the packer which item failed and why. Confirm the exact trigger.

### R5. Inputs

- **Boxes.** A list. Each has width, height, depth, a maximum weight, and a tare weight, which is
  the weight of the empty box itself. Each box type also has a stock count, `MaximumBoxes`. See R7.
- **Items.** Each has a reference or ID, dimensions, and weight.
- Some additional reference data, not specified further.

### R6. Extensibility, via modes

The client raised this repeatedly and unprompted. The end goal is that this gets developed further
after we are gone. He named object-oriented design and gave a specific example: a box abstraction
where a shipping container and a small parcel are the same kind of thing. He noted that this also
solves the stacking and top-heavy questions later without a rewrite.

The concrete extension he wants to see is **modes**:

| Mode | What it does |
|---|---|
| **Standard** | The core problem. Real geometry, real fit. **This is what we build.** |
| **Fluid** | Ignores geometry. Box has X cubic space, items total Y, if Y fits in X the worker shoves it in. For liquids, and for apparel and anything squishable that fills air gaps. He said they already have this in house. |
| **Own packaging** | Some items ship in their own carton. No box, just a label on it. **[unconfirmed]**, the example is garbled but the rule is clear: some orders bypass packing entirely. |

We implement standard mode. The architecture must make the other two obvious drop-ins. That is what
he means by extensibility, and it is the cheapest way to score against his stated priority.

### R7. Box stock limits

Each box type in the Portal has `MaximumBoxes`: how many of that box are in stock. A layout that
needs more boxes than the warehouse has is not usable, so the solver never uses a box type more
often than its limit. Items left over when stock runs out are rejected with a clear reason.
See [ADR-0008](decisions/0008-enforce-maximum-boxes.md).

### R8. Cost: box price and packing time

The client's challenge order (October 2026) put a price on the result: 300 pesos per P200, 500 per
P300, 750 per P500, and 1 peso per second of packing time. So the smallest box that fits matters,
not just the fewest boxes, as long as finding it does not take too long.

The normal solve stays fast and aims for fewest boxes. An opt-in "Further Optimise" button spends
up to 30 seconds looking for one smaller box. See
[ADR-0009](decisions/0009-further-optimise.md).

## Priorities, in his order

1. **Efficiency.** The main thing on the solver side.
2. **Extensibility.** See R6.
3. **User experience** on the visualiser. Another team's problem, but it constrains our output:
   we must give them enough to build a good experience. See [what the visualiser needs](#what-the-visualiser-team-needs-from-us).

He also lowered the bar deliberately. This is a research prototype, not the shipping product. "You
don't have to make a very exciting place."

## Out of scope

The client ruled these out himself.

| Not building | Why he said so |
|---|---|
| Auth and access control | Robust access control already exists on their side. Access is at the level of the model as a whole. |
| Fragile / this-way-up | "Not really a consideration." Fragile items do not get packed alongside other things in reality, they are handled separately. He called it out of scope but "would be really cool to see". Stretch goal at best. |
| Rate limiting, throttling | See R3. |

**Weight limits are now enforced.** He first said they were not hitting the limit, so they were
out of scope. The solver enforces each box's limit on its **contents** today. Whether the empty
box's own weight should count against the limit, as he described, is still to be confirmed.

## Assumptions he handed us

- **Dimensions are captured accurately.** "At some point you've got to trust the data." We do not
  handle bad measurements.
- **Box dimensions are internal, not external.** He flagged that they ought to account for wall
  thickness, so the number we pack against is usable interior space. He called it "a consideration
  to work out", so this is written down rather than settled. It is [open question 2](#open-questions-for-the-client).

## Who the end users are

Not us, and not software engineers. The workflow: a picker walks the warehouse pulling items off
shelves and brings them back. A packer sits at a station with a label printer, a desktop, a stack of
boxes, and the pile of items.

**Assume desktop.** They use handheld scanners for scanning, but the visualiser is looked at sitting
at the desk. Mobile would open a new avenue but is not the target.

The UX constraint that matters, in his words, is that there are two extremes of warehouse worker:
full-timers and supervisors who do this every day, and casuals brought in for a single weekend who
have never done warehouse work and never will again. **Design for the casual.** His test: given the
context that they are seeing items being placed into a box, they look at the screen and go "ah, I
get that". No training.

That is the visualiser team's problem directly, but it shapes what we owe them.

## What the visualiser team needs from us

Two views, both wanted:

1. **The whole box at once**, in 3D, orbit around it and look from different angles.
2. **Step by step**, item one, then item two on top of it. He called this "really beautiful" and a
   student compared it to an instruction manual. This is the differentiator.

So every placement carries a `sequence`, its packing order within its box, and dimensions **as
placed** with rotation already resolved, so the visualiser never does geometry maths. See
[`contract.md`](contract.md).

The visualiser gets its own dedicated page rather than being embedded in the portal. His words: "for
your purposes, separate page."

## Things he offered

Someone should chase these. The videos are cheapest and probably most useful.

- A **site visit** to see the operation. He said he can organise it.
- **YouTube videos** they already made as marketing material, showing the process. He said he would
  send them through.
- Possibly **simulated data**. **[unconfirmed]**, his answer is garbled, but he did not say no.

## Open questions for the client

He is back in two weeks. Questions 1 and 2 block implementation, so ask those first.

1. **Can items be rotated?** Can the packer turn an item on its side, or do some items have a fixed
   orientation? This changes the search space enormously. Our contract assumes rotation is allowed
   and reports which one was used.
2. **Are box dimensions internal or external?** If external, do we get wall thickness?
3. **Are packing rules pairwise ("A cannot go with B") or class-based ("class 3 cannot go with
   class 5")?** Our contract assumes class-based over group tags, which covers both, but confirm.
4. What exactly triggers "reject the order"?
5. What format does the item and box data arrive in? What does the portal hand us?
6. How many box types does a typical warehouse stock? This decides whether box selection is a real
   search or a trivial loop.
7. For fluid mode, is it purely volumetric or is there a fill factor?
8. Can we get the simulated dataset, the videos, and the site visit? Who do we chase?

---

The session record this was written from is [`client-qa-2026-08-05.md`](client-qa-2026-08-05.md):
what the client said, in the order he said it, with the garbled passages marked. Go there to check
whether something here is his words or our reading. This file is what to build against.

The raw machine transcript is not in this repo. Ask Wasif if you need it.
