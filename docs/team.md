# Team organisation and contribution

The FitSolver team in the Dynamic Fit division. This is a draft built from the repo history and the
meeting minutes. Check your own row, fix it, and commit the change yourself.

## Roles

| Name | GitHub | Role | Responsibilities in practice |
|---|---|---|---|
| Wasif Zaman | Wasif-ZA | Project manager, scrum master, reviewer | Chaired team meetings, wrote minutes and retrospectives, set the PR and review rules, reviewed PRs before merge, set up the Dynamic Fit monorepo |
| Jesse Osuna | jesseosu | Developer (algorithm lead) | Built the first greedy packer and greedy2, ran the benchmarks, wrote the user stories and the week 8 slides |
| Khuslee Batsuuri | khuslee0409 | Developer, project board | Added the `maximum_boxes` limit with tests, kept the board and issues current, checked the unit guide and rubric |
| Jacob Liu | JacobLiu124 | Developer, tester | Built the BFS greedy solver, wrote its tests, researched algorithms, reviewed and merged PRs |

## How we worked

- **Meetings:** Thursday afternoons on Google Meet. Minutes are in [`meetings/`](meetings/).
- **Reviews:** every change reaches `main` through a pull request, reviewed by another member, with the CI gate passing.
- **Board:** the "KanBan - DynamicSolver" GitHub Project. Every issue carries a `sprint-0` to `sprint-3` label.
- **Other subteams:** the JSON contract in [`contract.md`](contract.md) and the published schemas; the solver is merged into the [Dynamic Fit](https://github.com/Wasif-ZA/dynamic-fit) monorepo.

## Contribution

| Name | Built | Reviewed | Documented | Other (meetings, client contact, presenting) |
|---|---|---|---|---|
| Wasif Zaman | Portal adapter (PR #3), CI gate (#6), solver correctness fixes (#4, superseded by greedy2), two greedy2 fixes from review (`9ed091a`), CLI fix (#33); the Dynamic Fit monorepo | #7, #16, #17, #19; Dynamic Fit #6, #8, #9 | Decision records (Dynamic Fit ADR-0005 to ADR-0008), the SDD template and solver section, meeting minutes | Chaired the 13 Aug, 10 Sep and 17 Sep meetings; Sprint 0 and 1 retrospectives; close and Q&A at the week 8 presentation |
| Jesse Osuna | First greedy packer (`e140a4d`); greedy2 in 12 phases (PR #17) | | User stories (branch `docs/user-stories`), greedy2 README and design notes | Week 8 slides (`a31042f`); 32,000-item benchmark; relayed client and tutor feedback; hosted the 22 Oct meeting |
| Khuslee Batsuuri | `maximum_boxes` limit with tests (PR #19) | Opened issue #2, the greedy review that led to the correctness fixes | Closed issues #8 to #10; board issues #12 to #15 | Found the grade weights and rubric; input and output section at the week 8 presentation |
| Jacob Liu | BFS greedy solver (`1ed7bcd`); its tests (PR #7) and more tests (#16) | Merged #3 and #17; reviewer on #33 and #35 | Minutes at the 17 Sep meeting | Algorithm research (OR-Tools vs greedy); proposed grouping hazardous and food items |

## Peer agreement

Signed off by every member on [date]: the tables above are a fair account of who did what.
