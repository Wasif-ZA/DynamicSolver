# Sprint 0 review, 13 August 2026

| | |
|---|---|
| **When** | Thursday 13 August 2026, 14:53 AEST, about 50 minutes |
| **Where** | Google Meet |
| **Chair** | Wasif |
| **Attendees** | Wasif, Jesse, Jacob, Khuslee |
| **Sprint** | 0 (closing) |
| **Source** | Gemini meeting notes and transcript, checked by Wasif |

## Agenda

1. Recap the Sprint 0 review from the Wednesday session (Wasif was absent).
2. Choose the language.
3. Choose the first algorithm.
4. Requirements and MVP for Sprint 1.
5. Inputs and outputs with the portal and visualiser teams.
6. Task tracking and code review.
7. Actions before next week.

## Discussion

**1. Sprint 0 recap.** Jesse summarised Wednesday's review: the team agreed on communication (Discord), a GitHub repository, and a way to track tasks. Nothing else was decided.

**2. Language.** Wasif argued for C++ from the start: once a Python version exists, nobody will rewrite it. Jesse argued for Python: the solver is isolated from the other subsystems and only has to hand over a fixed JSON format, so the language does not affect anyone else. Python is easier to read for most of the team, and C++ could be called from Python later for hot paths. Wasif agreed that Python is easier to review. Vote: unanimous for Python.

**3. Algorithm.** Jesse demoed his greedy packer. It checks that an order is feasible (rejecting orders that cannot fit), then packs items to keep the box count low, and writes the result as JSON. Jacob shared a GitHub reference for the 3D bin packing problem. The problem is NP-hard, so there is no exact fast solution. Jacob suggested Jesse's greedy heuristic for the MVP because it works and everyone understands it. Wasif agreed, with the aim of improving the algorithm once the visualiser integration works.

**4. Requirements.** The solver must handle length, width, depth and weight: a 4D knapsack problem. Jacob noted the client changed his answer on box weight limits between sessions, so requirements need re-checking. Jesse and Wasif each hold notes from the client session; these are to be merged into one requirements document. Jacob proposed defining the MVP and requirements by the end of Sprint 1.

**5. Inputs and outputs.** Output is JSON for the visualiser. Input will come from the portal, but it is not known whether as a file, a request or a database read. Khuslee noted that our input parameters must match whatever the portal sends. Jacob noted that who interprets the raw boxes is an interface question to settle with the portal team. The portal team had not been active on Discord, so this is a risk. Questions go to the client, Daniel, at the next session.

**6. Tracking and review.** GitHub Projects chosen over Jira. Code goes through pull requests with reviewers. Wasif said reviews will be critical by design, aimed at the code, not the person. Repository access was checked live: only Jacob had accepted his invite, so fresh invites were sent.

## Decisions

| Decision | Why |
|---|---|
| Python is the project language (reverses the C++ choice in ADR-0004 of 5 Aug; recorded as Dynamic Fit ADR-0005) | Readable for the whole team; the solver's language does not affect other subsystems; C++ stays an option for hot paths |
| Greedy heuristic for the MVP | Works now, simple, understood by everyone; better algorithms researched later |
| GitHub Projects for task tracking | Lives next to the code |
| Code reaches the repo through pull requests with review | Shared understanding of the code |

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Jesse | Document the greedy code and open a PR | Pushed as "MPV Preliminary code" (`e140a4d`, 13 Aug), directly, before the PR rule of 20 Aug |
| All | Review submitted PRs | Review rule restated at the 20 Aug meeting |
| Wasif | Write the minutes and client questions | Client session record added the same day (`7fbaae0`, `docs/client-qa-2026-08-05.md`) |
| Wasif | Write the Sprint 0 retrospective | Submitted |
| Khuslee | Re-share the repository link | Done in the meeting |
| Jacob | Research better algorithms | BFS greedy, commit `1ed7bcd` |
| All | Add 5 user stories and 5 requirements each | User stories by Jesse on branch `docs/user-stories` |
| All | Sprint 0 personal log by the end of the week | Submitted |
| All | Agree inputs and outputs with the portal and visualiser teams | Carried to 20 Aug |
