---
name: testing
description: The team's testing policy - which kind of test proves what, where doubles are allowed, how to run the repository's own checks, and how to record their output on the task as evidence. Load it before writing, changing, reviewing or planning tests, before fixing a bug, and before saying any task is done, even a small one. Without it, agents mock internals, assert on calls, edit the test that judges a bug fix, and report "tests pass" with no output on the task.
---

# Testing and verifying work

- Owner: the team. Changes arrive as pull requests to `plugins/team/` in the tasks repository, approved by whoever merges them.
- Source: this skill, `rules/testing.md`, and one techniques file per language beside it.
- Enforced by: the repository's own checks and CI. asdlc's test-edit guard stops a bug fix on a `fix/` branch from changing an existing test. The rest is advisory, and a reviewer holds it.

A test is evidence that something works, so it should prove one named thing, and its failure should say what broke. The evidence that a task is done comes from the toolchain, recorded on the task, never from an agent's account of it.

## Choosing a test

Name a test by what it proves, not by how big it is.

| Kind | Proves | Doubles |
|---|---|---|
| Unit | Logic: a function that takes data and returns data | None |
| Functional | Behaviour: a feature through its public entry point, with the outside world faked at the boundary | Fakes at the boundary only |
| Adapter | One gateway (a database, an HTTP client, a queue) against the real thing or its official emulator | None |
| End to end | A user's path through the deployed system | None |

"Integration test" means a different thing to each reader, so don't use it: say which of the four it is.

- Start from the outside. Write the functional test for the behaviour first, then unit tests for the logic it needs.
- Most logic should be pure, so most tests are cheap unit tests with plain inputs. When a test needs a page of setup and a stack of mocks, the code made that choice: move the decision out of the code that does I/O, then test the decision.
- Doubles appear only at the boundary with the outside world, and only as fakes: a working in-memory version that holds state. Assert on the fake's state afterwards, not on which calls were made. Never mock the code under test or its collaborators inside the boundary.
- Time, randomness and ids enter as parameters, so a test passes them in. Never patch the clock or a random generator.
- Test the shell (the thin code that reads files, calls networks, writes databases) lightly: an adapter test or two, not every branch.

## Writing a test

- One behaviour per test, named for that behaviour in the domain's words.
- Arrange, act, assert, in that order, with the assertion saying what the reader should expect.
- A test is independent: it builds its own data, cleans up after itself, and passes alone and in any order.
- Follow the repository's existing tests: their layout, framework and helpers. Where they differ from this policy, the repository's conventions govern; raise the difference on the task rather than restyling tests you weren't asked to touch.

## Languages

Techniques expire faster than principles, so they live in one rule per language, delivered when you touch that language's tests:

- Python: `rules/testing-python.md`.
- Swift, Kotlin and TypeScript: none yet. Onboarding a code repository drafts its techniques from the tests it already has, as rules in that repository's own plugin (`plugins/<repo-slug>/rules/`). Until then, follow the repository's existing tests and don't invent techniques.

## Verifying work

Check as you go, with the repository's own commands, in tiers:

- The worker runs the change's tier: the tests of what the change touches, and the static checks (lint, types).
- The reviewer runs the full check once.
- CI confirms it.

The commands are in the repository's plugin in the tasks repository, `plugins/<repo-slug>/commands.toml`, each one verified when it was written down. When there is none, use what the repository documents (its README, CONTRIBUTING, CI workflow), and say on the task that its commands aren't recorded yet.

### Bugs

1. Reproduce the bug as a failing test before changing any code, and confirm it fails for the expected reason, not a typo or a missing import.
2. Commit the failing test on its own.
3. Fix the code without editing that test. On a `fix/` branch, asdlc's test-edit guard refuses changes to existing tests.

### UI changes

Build it, take a screenshot, compare it with the design, and adjust. Two or three rounds is normal. Attach the final screenshot's path to the task.

### When a check is wrong

A check or test that looks wrong is a finding on the task, not something to change now. Never weaken a check, skip a test or loosen an assertion to make a change pass.

## Recording the evidence

Before saying a task is done, run the change's tier through `asdlc record-check`, from the task's worktree, so the reviewer judges the tool's output rather than an account of it:

```sh
asdlc record-check <task-id> --as <worker> -- <command>
```

It runs the command, exits with its code, and appends to the task the command, its exit code, the worktree, branch and commit it ran on, and the tail of its output; only the worker holding the task can record on it. Checks can take minutes: give the Bash call a long timeout (up to 600000 ms) or run it in the background and wait for it. For a bug, also record the failing run of the reproducing test from step 1, before the fix.

Done is measured against the task's acceptance criteria, written as things a check can show ("every test in `test_status.py` passes", "the lint command exits 0"). Whether the task closes is decided by its reviewer, not here.
