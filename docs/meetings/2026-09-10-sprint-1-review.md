# Sprint 1 review and presentation planning, 10 September 2026

| | |
|---|---|
| **When** | Thursday 10 September 2026, 16:59 AEST, about 25 minutes |
| **Where** | Google Meet |
| **Chair** | Wasif |
| **Attendees** | Wasif, Jesse, Khuslee, Jacob (joined late) |
| **Sprint** | 1 (week 7, closing) |
| **Source** | Gemini meeting notes, checked against the transcript by Wasif |

## Agenda

1. The week 8 MVP presentation: format, timing, who says what.
2. Solver status and performance.
3. C++ after Sprint 1.
4. Grading structure.
5. Minutes and retrospective.

## Discussion

**1. Presentation.** The team is third to present in week 8, as the whole Dynamic Fit division. There is no published spec, and nobody knew if it is marked. Without a spec, the team sets its own criteria and shows the MVP. Wasif first proposed a small demo-only site walking through the flow end to end. Khuslee estimated about 10 minutes for the whole division, leaving the solver team about 3 minutes, so Wasif dropped the demo site: it would take the full slot. Instead, each subteam presents its part and the division shows one live demo at the end. With four speakers, that is about 40 seconds each.

**2. Speakers.**
- Jesse: the code, file parsing and the acceptance and rejection rules (he wrote most of it).
- Jacob: the algorithm and benchmarks, plus a 30 second video of the algorithm packing.
- Khuslee: input and output, from the portal's JSON through the solver and back.
- Wasif: the opening and close, and the live repo demo if the other subteams agree.

Wasif said he had not read the code in a while, so Jesse took the slides.

**3. Performance and C++.** The Python code has known bugs, but the design and algorithm come first. Wasif proposed moving to C++ after Sprint 1. Jesse's benchmark packs 32,000 random items in about 5.3 seconds (other random runs 4.6 to 4.7 s). Khuslee relayed the client's view: results just need to feel instant, with no target time. C++ would save 1 to 2 seconds at most, and only two of four members know it. Wasif withdrew the proposal.

**4. Grading.** Khuslee read the unit guide: 40% report, 30% product, 30% development process. The process mark covers retrospectives, documentation and CI, so Jesse suggested more visible work on the board and in CI.

## Decisions

| Decision | Why |
|---|---|
| Stay on Python | 5.3 s for 32,000 items is already fast enough; C++ saves at most 1 to 2 s; half the team does not know C++ |
| Subteams present their parts, the division demos at the end | Fits about 3 minutes per subteam |
| Every member speaks | Individual contributions should be visible |

Gemini's notes list C++ under "needs further discussion". The transcript shows the proposal was withdrawn.

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Jesse | Email Enzo or Kate about presentation requirements and marking | Not recorded |
| Jesse | Make 2 to 3 slides | Slides committed on 14 Sep (`a31042f`, branch `docs/user-stories`) |
| Jesse | Set up a meeting with the portal and visualiser subteams (Aaron, Stephanie) | Presentation given jointly on 16 Sep |
| Jesse, Khuslee | Agree the input and output talking points | Presented on 16 Sep |
| Jacob | 30 second algorithm video | Not recorded |
| Wasif | Minutes and the Sprint 1 retrospective | Retrospective submitted; minutes are this file |
