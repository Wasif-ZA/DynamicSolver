# Sprint 1 planning, 20 August 2026

| | |
|---|---|
| **When** | Thursday 20 August 2026, 14:57 AEST, about 55 minutes |
| **Where** | Google Meet |
| **Chair** | Wasif |
| **Attendees** | Wasif, Jesse, Jacob, Khuslee |
| **Sprint** | 1 (week 4) |
| **Source** | Gemini meeting notes, checked by Wasif |

## Agenda

1. How code and work are tracked.
2. What the MVP needs.
3. The JSON interface with the portal team.
4. How the portal, solver and visualiser talk to each other.
5. Integration testing across subsystems.
6. CI.
7. Reviews of the open pull requests.

## Discussion

**1. Workflow.** Wasif argued that pull requests are the only way code reaches `main`, so everyone understands what changed, and that issues are for bugs, not tasks. Khuslee raised the tutor's request for a project board; Wasif confirmed the GitHub board was already set up. Jesse stressed keeping progress on the board.

**2. MVP.** Jacob said the MVP has no rigid spec but must show a working algorithm. He noted Google OR-Tools does not scale to thousands of boxes, so a greedy heuristic suits our scope, and C++ or Go would not change that much.

**3. JSON interface.** The solver takes a JSON order and returns a JSON result. Jesse asked for a concrete example of the portal's input so our output can be checked against it. Wasif had reviewed the code and was pushing a PR to meet the portal team's FastAPI requirements.

**4. Communication model.** Two options: the portal sits in the middle of all data flow, or the solver sends results straight to the visualiser. Not settled; it needs the visualiser team.

**5. Integration testing.** Wasif proposed one shared repository to run the portal, solver and visualiser together. The team also discussed using the portal team's repository, with the others as submodules. Not settled.

**6. CI.** Wasif flagged that CI had never run successfully. Fixing it became a priority.

**7. Priority orders.** Jesse proposed splitting orders into high priority (a fast best-fit pass) and low priority (a slower, more optimal pass). Jacob noted it is realistic but out of scope for the MVP. Kept as a later extension.

## Decisions

| Decision | Why |
|---|---|
| All code changes go through pull requests with review | Everyone sees and understands every change |
| Issues are for bugs only | Keeps the issue list meaningful |
| Progress lives on the GitHub project board | Tutor requirement, one place to look |
| The Python greedy heuristic is enough for the MVP | OR-Tools does not scale; language is not the bottleneck |

**Needs further discussion:** the communication model (portal in the middle, or solver to visualiser directly) and where integration tests run.

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Jesse | Review the portal adapter PR (#3) | Merged by Jacob on 22 Aug |
| Jacob | Review the solver correctness PR (#4) | Commented "Its OK" on 1 Sep without approving; #4 later closed as superseded by greedy2 |
| Khuslee | Review the CI PR (#6) | Not reviewed; #6 merged on 25 Aug without review |
| Wasif | Set up a meeting with the portal team on the input format | Integration questions opened as Dynamic Fit issues #1 to #3 |
| All | Agree the JSON format and data flow with the portal and visualiser teams | Dynamic Fit ADR-0006 (the implemented schema is the contract) and ADR-0008 (how the portal reaches the solver), 25 Aug |
| Jesse | Test the connection with the portal implementation | Portal wired to solver and visualiser in Dynamic Fit PR #6, merged 26 Aug |

The shared integration repository became Dynamic Fit, created on 25 August with all three subsystems and their history (Dynamic Fit ADR-0007).
