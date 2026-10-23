# How the team reviews a task

A reviewer agent judges one finished task from the board, from a fresh context: its diff against the repository's default branch, judged against the task and this policy. A repository can add its own policy in its plugin, `plugins/<repo-slug>/review.md`, which adds to this one and never loosens it. Change either file through a pull request to the tasks repository, like any other change; whoever merges approves it.

The review records its findings and a verdict on the task with `asdlc review-done`, and posts the same findings on the pull request as a comment. It never approves, requests changes on, or merges a pull request: a person merges.

## What the work is judged against

- The task: its description, acceptance criteria, plan, and the notes and checks its worker recorded.
- The contract and the spec, when the task has a parent intent: the documents linked on the intent. Only the intent's lead changes them.
- This policy, and the repository's own when its plugin has one.

## Passes

Tag every finding with its pass.

- **Bugs.** Logic errors, unhandled edge cases, regressions, code that won't build or run, and tests that don't test what they claim.
- **Security.** Secrets or tokens in code or logs, input reaching a shell, a query or a file path unchecked, permissions widened, and errors swallowed instead of reported.
- **Compliance.** Does the change do what the task's plan says, and meet each acceptance criterion? Compare the files it touches with the plan's files and its order of work. A change that builds against something other than the contract is a finding. A departure from the plan is a finding unless the task's notes say what changed and why.
- **Evidence.** Were the checks the worker recorded run on this branch, after its last change, and did they pass? A check recorded before the last commit, or not at all, is a finding.
- **Size and approval.** A task larger than `size-1` needs "Plan approved by @<engineer>" in its comments. A `size-1` task skipped plan approval, and its notes say "size-1: plan approval skipped; small because ...": its plan must be numbered steps, and the change must really be small and mechanical, a few lines in a few files with no design choice the steps left open. Either missing or untrue is an Important Compliance finding.

## Severity

- **Important**: breaks behaviour, leaves an acceptance criterion unmet, weakens a check or a test, leaks a credential, departs from the plan or the contract without saying so, or skipped plan approval on work that wasn't small.
- **Nit**: anything else. Report at most five nits per review, and summarise the rest as a count.

The verdict is `changes` when there is at least one Important finding, and `clean` otherwise; nits alone don't send work back.

## Skip

- Anything the repository's own checks already enforce: formatting, lint and type errors they catch, tests they run.
- Wording and style preferences, unless the wording would make a reader or a model do the wrong thing.
