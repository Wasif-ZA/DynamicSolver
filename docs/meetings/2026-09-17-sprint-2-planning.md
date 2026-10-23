# Sprint 2 planning, 17 September 2026

- **Attendees:** Wasif (chair), Jesse, Jacob (minutes), Khuslee
- **Source:** Google Meet notes by Gemini, checked by Wasif

## Summary

Agreed to combine the two solvers into one, stay on Python, and split the work for the mid-session break.

## Decisions

- **Combine Jacob's and Jesse's solvers** into one codebase in Sprint 2. Khuslee asked whether picking one would be simpler. Wasif argued that picking one keeps its known weaknesses.
- **Python is the final language.** C++ adds edge cases and memory bugs, and FastAPI is Python only.

## Discussion

- **Caching.** Wasif proposed caching failed placements so the solver stops retrying positions it already knows fail.
- **Finding placement bugs.** Run solver output through the existing visualiser instead of building a new renderer.
- **Hazardous items.** The current rules cover only three items, so hazardous goods can end up next to food. Jacob proposed packing tagged groups, such as corrosive and food, in separate batches. Jesse will test it.
- **Deferred to Sprint 3:** item orientation (arrows in the JSON) and padding for damaged warehouse boxes. Both are nice to have, not required.
- **Goal.** Build the best product we can, not just a passing one.
- **Weights.** Documentation carries 40% of the grade, so documentation and CI tracking are a priority alongside code.
- Tutor feedback on the end-to-end demo was positive.

## Actions

| Owner | Action |
|---|---|
| Jesse, Jacob | Combine the two solvers into one codebase |
| Jesse, Jacob | Add the failed-placement cache |
| Jesse | Test further runtime optimisations |
| Jesse | Scaffold the project documentation |
| Wasif, Khuslee | Find the documentation requirements and add them to the repo |
| Wasif | Review every PR before it merges |
| Wasif | Add process diagrams to the repo |
| Wasif | Send the Gemini notes to Jacob for the minutes |
