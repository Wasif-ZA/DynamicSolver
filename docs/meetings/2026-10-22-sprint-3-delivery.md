# Sprint 3 delivery planning, 22 October 2026

- **Attendees:** Wasif, Jesse, Khuslee
- **Source:** Google Meet notes by Gemini, checked by Wasif

## Summary

Planned the final demo, the documentation and the submission links.

## Decisions

- **Kanban board.** Wasif turns closed PRs into issues on the board, with dates and Sprint 1, 2 and 3 labels, so the board shows the work as it happened.
- **Software Design Document.** The team writes one SDD from a shared template, covering requirements, user stories, architecture, design trade-offs and team roles.
- **Docs by division.** All subteams' documentation is combined by division in the monorepo.
- **Shared commits.** Documentation and cleanup tasks go to members with fewer commits, so the repo shows the work spread across the team.
- **Practice run.** One end-to-end run in class right before the presentation.
- **Algorithm visuals.** Jesse makes slides showing the new algorithm's layers, like Jacob's earlier ones.

## Discussion

- **Final demo.** We get a JSON order, run it through the portal, solver and visualiser, then pack the items into real boxes. The packing is scored.
- **Algorithm.** Jesse says only minor work remains. He will benchmark the new algorithm against a manually optimised packing.
- **Max boxes patch.** Khuslee's PR #19 adds the maximum boxes limit the portal team asked for. Wasif approved it on 22 October. It still needs to go into the monorepo.
- **Deployment.** The portal team owns deployment. It redeploys automatically when the monorepo changes.
- **Submission.** Links to the GitHub repos, the monorepo and the deployed app go on the iLearn forum under assessments.
- **Roles.** Name each member's role (tester, developer, project manager, scrum master) as the lecturers asked.

## Actions

| Owner | Action |
|---|---|
| Jesse | Test the new algorithm and benchmark it |
| Jesse | Make the algorithm visuals for the slides |
| Wasif | Convert closed PRs to labelled issues on the board |
| Wasif | Upload the SDD template and the cleanup branches |
| All | Merge the max boxes patch into the monorepo |
| All | Write the SDD |
| All | Practice run before the presentation |
| All | Post the repo and deployment links on iLearn |
