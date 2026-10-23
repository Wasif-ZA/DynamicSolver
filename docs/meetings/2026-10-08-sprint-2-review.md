# Sprint 2 review and Sprint 3 planning, 8 October 2026

- **Attendees:** Wasif, Jesse, Jacob
- **Source:** Google Meet notes by Gemini, checked by Wasif

## Summary

Reviewed client and tutor feedback and planned Sprint 3 around cleanup and documentation.

## Decisions

- **Sprint 3 is cleanup.** Move old code to an archive branch and update the stale architecture docs.
- **Monorepo after cleanup.** Update Dynamic Fit only once cleanup and code review are done.
- **New features wait for Sprint 4,** along with any further visualiser or portal integration.

## Needs further discussion

- **Input checks.** We proposed that the portal team handles items with zero weight or invalid dimensions. The portal team will decide at its own meeting.

## Discussion

- **Client feedback.** Daniel said the divisions' portals look very similar. Our solver has its own features, such as CP-SAT.
- **Tutor feedback.** Rachel stressed team ownership and cross-team coordination. Since we are ahead, we offered to help the visualiser and portal teams with their front ends.
- Wasif is still reviewing the code Jesse merged. Jacob has not yet reviewed the code in depth.
- Wasif apologised for missing the previous meeting.

## Actions

| Owner | Action |
|---|---|
| Wasif | Move old code to an archive branch |
| Wasif | Update the architecture docs |
| All | Coordinate visual design and requirements with the visualiser and portal teams |
| All | Update the monorepo after cleanup and docs |
| Jacob | Run more tests and do a formal code review |
