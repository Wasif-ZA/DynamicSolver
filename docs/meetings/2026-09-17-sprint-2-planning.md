# Sprint 2 planning, 17 September 2026

| | |
|---|---|
| **When** | Thursday 17 September 2026, 16:59 AEST |
| **Where** | Google Meet |
| **Chair** | Wasif |
| **Attendees** | Wasif, Jesse, Jacob (minutes), Khuslee |
| **Sprint** | 2 (week 8) |
| **Source** | Gemini meeting notes, checked by Wasif |

## Agenda

1. Two solvers in one repository.
2. Language, settled for good.
3. Finding placement bugs.
4. Hazardous items.
5. Requests deferred to Sprint 3.
6. Grade weights and documentation.
7. Work split for the two-week break.

## Discussion

**1. Two solvers.** Jacob's and Jesse's solvers sat side by side, which made the repository confusing. Wasif proposed combining them to keep the strengths of both. Khuslee asked whether picking one would be simpler. Wasif argued that picking one keeps its known weaknesses. Jacob said aligning the JSON schemas needs only small code changes. Wasif also proposed caching failed placements, so the solver stops retrying positions it already knows fail.

**2. Language.** Khuslee raised API compatibility: FastAPI is Python only. Wasif and Jesse added that C++ brings edge cases and memory bugs without Python's safety rails, and would force plain HTTP calls instead of FastAPI. Python is final.

**3. Placement bugs.** Instead of building a new renderer, run solver output through the existing visualiser and step through the packing. Jesse agreed this finds placement bugs fastest.

**4. Hazardous items.** The current rules cover only three items, so hazardous goods could be packed next to food. Jacob proposed tagging items (for example corrosive, food) and packing each group in its own batch. Jesse supported it and will test it.

**5. Deferred to Sprint 3.** Item orientation (an arrow in the JSON for "this way up"), and padding for damaged warehouse boxes (proposed by Wasif). Both are nice to have, not required.

**6. Grades and documentation.** The team agreed to aim for the best product, not a pass. Khuslee found the weights in the unit guide: 30% product, 40% report and documentation, 30% development process. Since documentation carries so much weight, documentation and CI tracking are a priority alongside code. Tutor feedback on the end-to-end demo was positive.

**7. Break plan.** Jesse and Jacob combine the solvers in this repository. Wasif and Khuslee scaffold the documentation. Wasif reviews every pull request before it merges.

## Decisions

| Decision | Why |
|---|---|
| Combine the two solvers into one codebase | Picking one keeps its known weaknesses |
| Python is final | FastAPI is Python only; C++ adds memory bugs |
| Debug placements through the existing visualiser | Faster than a new renderer |
| Orientation and damaged-box padding wait for Sprint 3 | Nice to have; core requirements first |

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Jesse, Jacob | Combine the solvers | greedy2, PR #17: opened 29 Sep, merged 7 Oct |
| Jesse, Jacob | Cache failed placements | greedy2's infeasibility memo (`d723296`) |
| Jesse | Test further optimisations | greedy2 phases 4 to 12: multi-start, size ordering, seeded restarts, carton elimination |
| Wasif | Review every PR before merge | Reviewed #16 (17 Sep) and #17 (7 Oct); the #17 review found two bugs, fixed in `9ed091a` |
| Wasif, Khuslee | Find the documentation requirements and scaffold the docs | Not done in Sprint 2; carried to Sprint 3 |
| Wasif | Add process diagrams to the repo | Carried to Sprint 3 |
| Jesse | Draft the documentation scaffold | greedy2 README and design notes (`62f5df1`, `76efd6c`) |
| Wasif, Jacob | Minutes from the Gemini notes | This file |
