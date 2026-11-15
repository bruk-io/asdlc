# Intent: checks are quiet and run only what a change affects

- Author: Bruk Habtu
- Status: draft. Merging this file accepts it.
- Date: 2026-11-13

## Problem

"We should be careful about which tests run - I want to avoid running all the tests for every change. Ideally this is handled automatically and not the model sorting it. The other part for tests is that we need the output to be quiet by default because of the token cost."

On steg I had this built by hand: a `justfile` as the one entrypoint, a tool that works out which crates a change affects, and a wrapper that prints one line when a step passes and the end of the output when it fails. Nothing in asdlc asks for any of it. Onboarding verifies whatever build, test and lint commands it finds, however much they print and however much they run, and `asdlc record-check` appends the end of whatever came out to the task. Every worker and reviewer in every repository then pays for that output on every check, and a worker left to choose which tests to run will sometimes choose wrong.

I want a repository asdlc works in to have one entrypoint for its commands, quiet by default and selective by default, without each project inventing it.

## Proposed outcome

- A repository's verified commands are named entrypoints a person and an agent both run, not raw tool commands each agent assembles.
- A check that passes costs a line or two of output. A check that fails shows enough to fix it and says where the full output is.
- The tests that run for a change are chosen from the change itself, by a program, the same way for everyone. Nobody chooses them by hand, and there is a way to run everything.
- When the selection cannot be trusted, such as a change to the build itself, everything runs.
- Onboarding says so when a repository's commands are noisy or run everything on every change, and that is visible to the engineer.
- What `asdlc record-check` puts on a task stays short for a pass and still shows the failure for a fail.

## Affected users and systems

- Every worker and reviewer, and whoever pays for their tokens.
- The onboard-repo skill, the repository plugin's `commands.toml`, the team plugin's testing skill and rules, `asdlc record-check`, and the worker agent.
- Repositories already onboarded, whose verified commands were recorded as found.

## Constraints

- Quiet never hides a failure, and a skipped test is never reported as a passed one.
- No check is weakened to make it quiet or fast. The full run stays available and is what CI uses.
- asdlc does not impose a build tool: a repository that has an entrypoint keeps it.
- Evidence on a task still shows which commit a check ran on and that it passed.

## Open questions

- [ ] Does asdlc ship the quiet wrapper and the selection as tools of its own, or describe what a repository's entrypoint must do and leave each repository to meet it?
- [ ] Selection is language specific (crates, packages, modules). Which languages get it first, and what does a repository in another language do?
- [ ] Is a noisy or run-everything command a finding that blocks onboarding, or a warning recorded in the plugin?
- [ ] Should `asdlc record-check` itself be the quiet wrapper, since it already captures the output?
- [ ] How is a wrong selection caught: by running everything in CI, by a periodic full run, or by a test of the selection itself?
- [ ] Does the reviewer run the affected tests again, or trust the recorded check?
