# Intent: evals for the team's own agent setup

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-10-23

## Problem

Every agent on a team's board reads the same setup: the team plugin's skills, rules and review policy, and a generated plugin per code repository, all in the tasks repository. Those files change through ordinary pull requests, and nothing shows whether a change made the agents worse, or whether a skill still loads when it should. That setup is exactly what the playbook's continuous evals are for (play 08): rerun a suite whenever the configuration changes, gate the change on its pass rate, and make every incident a permanent case.

asdlc's own nine evals cover asdlc itself. They don't cover anything a team writes, they don't run on a schedule, and they don't stop a change that lowers the pass rate (R14, R22). An escaped bug on the board has no route to becoming a case.

## Proposed outcome

- A change to the team plugin or a repository's plugin in a tasks repository can be run against an eval suite before it merges, and the result shows its pass rate beside the default branch's.
- Every skill in the team plugin and the repository plugins has a trigger set: requests that should load it and requests that shouldn't. The suite reports misses and false alarms per skill.
- An escaped bug (a bug task on the board that names a task already Done) has a written route to becoming an eval case, and `asdlc stats` reports the time from the bug to its case.
- asdlc's own suite runs on a schedule and on every change to the plugin's agents, skills, hooks or commands. A change that lowers the pass rate beyond the measured run-to-run spread doesn't merge without a person seeing that result (R22).

## Affected users and systems

- Engineers who change the team plugin or a repository plugin, and whoever reviews and merges those changes.
- The tasks repository's layout and its pull requests.
- asdlc's eval runner (`scripts/eval`), its container image, and wherever the runs happen.
- `asdlc stats`, which today reports the eval pass rate as not measured.

## Constraints

- Runs locally in the same container as asdlc's evals, without depending on GitHub; CI uses the same container when there is one.
- New cases come only from incidents or from a person (R24), and checks are deterministic first, with a model judge only where none exists (R28).
- A change can't alter the evals that judge it (R23).
- Each run records its tokens and cost, so a team can choose a cadence it can afford.

## Open questions

- [ ] Where does a team's suite live: an `evals/` folder in the tasks repository, or beside each repository plugin?
- [ ] Who writes the first cases, and how many real tasks does a team need before the suite means anything?
- [ ] Which changes trigger a run: any change under `plugins/`, or only skills, rules and review policies?
- [ ] Does a team's suite gate the merge, or only report on the pull request until it has a track record?
- [ ] Can the reference-run and null-run validation asdlc uses for its own cases apply to a team's cases, or do team cases need a lighter bar?
- [ ] What budget and cadence fit: every change, nightly, or weekly?
