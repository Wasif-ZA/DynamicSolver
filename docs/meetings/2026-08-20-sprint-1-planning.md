# Sprint 1 planning, 20 August 2026

- **Attendees:** Wasif, Jesse, Jacob, Khuslee
- **Source:** Google Meet notes by Gemini, checked by Wasif

## Summary

Set the working rules for Sprint 1 and listed what the MVP needs from the portal team.

## Decisions

- **Every code change goes through a pull request** so the team reviews it. Issues are for bugs only.
- **Progress goes on the GitHub project board.** It was already set up when the tutor asked for one.
- **The Python greedy heuristic is enough for the MVP.** Jacob noted OR-Tools does not scale to thousands of boxes, and C++ or Go would not change that for our scope.

## Needs further discussion

- **Communication model.** Either the portal sits in the middle of all data flow, or the solver sends results straight to the visualiser. This needs the visualiser team.

## Discussion

- The solver takes a JSON order and returns a JSON result. We need concrete example input from the portal team to check our output against it.
- Wasif proposed one shared repository for integration tests across portal, solver and visualiser. Using the portal team's repository, with the others as submodules, was also discussed. Not decided.
- CI has never run successfully. Fixing it is a priority.
- Jesse proposed handling high-priority orders with a fast best-fit pass and low-priority orders with a slower, more optimal one. Out of scope for the MVP; kept as a later extension.

## Actions

| Owner | Action |
|---|---|
| Jacob | Review Wasif's open PR before the next meeting |
| Wasif | Set up a meeting with the portal team to settle the input format |
| All | Agree the JSON format and data flow with the portal and visualiser teams |
| Jesse | Test the connection with the portal team's implementation |
| Jesse | Review the portal connection PR and decide whether to merge |
| Khuslee | Review the CI PR for gaps in test coverage |
