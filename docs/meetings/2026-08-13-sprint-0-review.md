# Sprint 0 review, 13 August 2026

- **Attendees:** Wasif (chair), Jesse, Jacob, Khuslee
- **Source:** Google Meet notes by Gemini, checked by Wasif

## Summary

Closed Sprint 0. The team picked the language and the first algorithm, and agreed how to track work.

## Decisions

- **Python** is the project language. Wasif first suggested C++ for speed. Jesse argued for Python for readability, with C++ kept as an option for hot paths later. The vote was unanimous.
- **Greedy heuristic** for the MVP. Jesse demoed a greedy packer that checks compatibility and writes JSON. Better algorithms get researched after the MVP.
- **GitHub Projects** for task tracking, chosen over Jira.

## Discussion

- The problem is a 4D knapsack: length, width, depth and weight. The MVP and its requirements must be defined in Sprint 1.
- Inputs: it is not yet known whether orders arrive as files or from a database. The portal and visualiser teams need to agree inputs and outputs with us. Questions about portal integration go to Daniel, the client, at the next session.
- Code review will be critical by design, aimed at the product, not the person.

## Actions

| Owner | Action |
|---|---|
| Jesse | Document the greedy code and open a PR for review |
| All | Review the submitted PRs |
| Wasif | Write the minutes and requirements, prepare client questions |
| Wasif | Write the Sprint 0 retrospective |
| Khuslee | Share the repository link in the team channel |
| Jacob | Research more efficient algorithms, write up findings or open a PR |
| All | Add 5 user stories and 5 requirements each to the shared requirements file |
| All | Finish the Sprint 0 personal log by the end of the week |
| All | Agree inputs and outputs with the portal and visualiser teams |
