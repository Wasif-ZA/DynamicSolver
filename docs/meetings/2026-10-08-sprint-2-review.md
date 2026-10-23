# Sprint 2 review and Sprint 3 planning, 8 October 2026

| | |
|---|---|
| **When** | Thursday 8 October 2026, 16:51 AEDT |
| **Where** | Google Meet |
| **Attendees** | Wasif, Jesse, Jacob |
| **Sprint** | 2 (week 9) |
| **Source** | Gemini meeting notes, checked by Wasif |

## Agenda

1. Client and tutor feedback.
2. State of the code after greedy2.
3. Sprint 3 plan.
4. Work with the portal and visualiser teams.

## Discussion

**1. Feedback.** Jesse relayed feedback from the client, Daniel: the divisions' portals look very alike. Our solver has its own features, such as CP-SAT. The tutor, Rachel, stressed team ownership and team dynamics, and mentioned a team caught copying code line for line. Rachel also expects coordination across subteams as part of the division.

**2. Code.** greedy2 was merged on 7 October. Wasif was still reviewing parts of the merged code. Jacob said he had not yet reviewed the code in depth and committed to more tests and a formal review.

**3. Sprint 3 plan.** Wasif proposed that Sprint 3 is cleanup: move old code to an archive branch so the repository is easier to read, update the stale architecture docs, then update the monorepo (Dynamic Fit). New features and further integrations wait for Sprint 4. The project description says no new features in Sprint 3.

**4. Other subteams.** Since the solver team is ahead, Wasif proposed helping the portal and visualiser teams with the visual side of their front ends. Jesse had proposed that the portal team validate items with zero weight or invalid dimensions before they reach the solver. The portal team will decide at its own meeting.

Wasif apologised for missing the previous meeting.

## Decisions

| Decision | Why |
|---|---|
| Sprint 3 is cleanup and documentation | The project description rules out new features in Sprint 3 |
| Old code moves to an archive branch | The repository is hard to read with three solvers in it |
| Architecture docs get updated | They describe the pre-greedy2 design |
| Monorepo updated only after cleanup and review | Ship one clean solver to Dynamic Fit |
| Features and integrations wait for Sprint 4 | Cleanup first |

**Needs further discussion:** whether the portal team takes over input validation (zero weight, invalid dimensions).

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Wasif | Move old code to an archive branch | Open: bin4d archive filed as an issue on 22 Oct |
| Wasif | Update the architecture docs | Open: filed as an issue on 22 Oct |
| All | Coordinate visual design and requirements with the visualiser and portal teams | Wasif reviewed and merged Dynamic Fit PR #8 (visualiser) on 20 Oct |
| All | Update the monorepo after cleanup | Open: Dynamic Fit re-sync filed as an issue on 22 Oct |
| Jacob | More tests and a formal code review | Reviewer on PRs #33 and #35 (22 Oct) |
