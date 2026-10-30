# Sprint 3 delivery planning, 22 October 2026

| | |
|---|---|
| **When** | Thursday 22 October 2026, 17:05 AEDT, about 20 minutes |
| **Where** | Google Meet |
| **Host** | Jesse |
| **Attendees** | Wasif, Jesse, Khuslee |
| **Sprint** | 3 (week 11) |
| **Source** | Gemini meeting notes and transcript, checked by Wasif |

## Agenda

1. The final demo.
2. Algorithm readiness.
3. What gets marked: Kanban board, documentation, contributions.
4. The max boxes patch.
5. Deployment and submission links.
6. Presentation roles and rehearsal.

## Discussion

**1. Final demo.** Jesse relayed the brief: each division gets a JSON order, runs it through its portal, solver and visualiser, then packs the items into real boxes. The physical packing is scored, with a prize for the best result.

**2. Algorithm.** Jesse said only minor work remains. A screenshot shared by the visualiser team came from the old algorithm, so the new one still needs a run. Jesse will also work out a manually optimised packing to benchmark greedy2 against.

**3. What gets marked.**
- **Kanban board.** Rachel said boards must show the work as it happened. The team tracked work through pull requests, not issues. Wasif will convert closed PRs into issues with their dates and sprint labels (Sprints 1 to 3).
- **Documentation.** Khuslee and Wasif found the rubric: requirements, architecture, software quality, project management, team organisation and contribution. Requirements, user stories and decisions are spread across files. Wasif proposed one Software Design Document (SDD) from a template, covering user stories, requirements, architecture and design trade-offs. Documentation is combined by division in the monorepo.
- **Contributions.** Commit counts are uneven although the work was shared. Wasif proposed giving documentation and cleanup tasks to members with fewer commits, so the repository shows the work spread across the team. Wasif will put his local cleanup on branches for others to pick up.
- **Roles.** Name each member's role (tester, developer, project manager, scrum master) as the lecturers asked.

**4. Max boxes patch.** The portal team asked for a maximum boxes limit. Khuslee's PR #19 adds it. Wasif approved it on the morning of 22 October. It still needs to reach the monorepo.

**5. Deployment and links.** The portal team owns deployment, and the monorepo redeploys automatically on change, so the solver team only needs its code in the monorepo. Khuslee pointed out the submission: post the links to the GitHub repositories, the monorepo and the deployed app on the iLearn forum under assessments.

**6. Presentation.** One end-to-end practice run in class right before presenting. Jesse will make slides showing greedy2's layers, like Jacob's earlier ones.

## Decisions

| Decision | Why |
|---|---|
| Convert closed PRs to issues with sprint labels | The board is marked and must show the work over time |
| One SDD from a template, combined by division in the monorepo | The rubric asks for requirements, architecture and trade-offs in one place |
| Docs and cleanup tasks go to members with fewer commits | The repository should reflect that the work was shared |
| Practice run before the presentation | Check the full flow works on the day |
| Jesse makes the algorithm visuals | He wrote greedy2 |

## Actions

| Owner | Action | Outcome |
|---|---|---|
| Wasif | Convert closed PRs to labelled issues | Done 22 Oct: sprint labels on every issue, issues #21 to #24 for merged PRs, Dynamic Fit #1 to #3 on the board |
| Wasif | Upload the SDD template and push cleanup branches | Remaining work filed as issues #25 to #32 on 22 Oct, assigned by fewest commits |
| All | Merge the max boxes patch into the monorepo | PR #19 merged here on 22 Oct; Dynamic Fit re-sync filed as an issue |
| All | Write the SDD | Open |
| Jesse | Test and benchmark greedy2 | Open |
| Jesse | Algorithm visuals for the slides | Open |
| All | Practice run before the presentation | Planned for week 13 |
| All | Post repository and app links on iLearn | Open |
