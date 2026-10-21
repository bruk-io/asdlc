# Plan: AI review on every pull request

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: draft. Merging this file approves the plan; implementation starts after it.
- Delivers: R15, R18 (the review job only), R29 (review runs only)

Every pull request gets a review from Anthropic's `code-review` plugin, run by `claude-code-action` in CI with a subscription token, posting findings inline and never approving. It comes now because version 0's own review showed that a reviewer the author runs is advisory: it ran only because the author chose to. The review is judged before it is trusted: a seeded-defect pair now, the full recall and false-refusal evals (evals file, Deploy) later.

Two choices shape it:

- **Anthropic's reviewer first, ours only if it fails.** The managed Code Review service is for Team and Enterprise plans, so it is out. Writing our own reviewer before the existing one has been measured would be building the library before the case.
- **The rules come from `main`, never from the pull request.** A pull request must not be able to loosen what judges it, the same principle as R21 and R23. The workflow runs on `pull_request_target`, so its definition, `REVIEW.md` and `CLAUDE.md` all come from the base branch. The pull request's code is read, never run.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `REVIEW.md` | yes | The passes (bugs, security, compliance with the spec and the plan the change cites), what counts as Important, a cap of five nits, and what to skip because CI already enforces it | R15 |
| `.github/workflows/review.yml` | yes | On `pull_request_target`: check out the base branch only, run `claude-code-action@v1` with the `code-review` plugin, `--comment` and `REVIEW.md` appended to its system prompt, tools limited to reading and posting comments, a turn cap and a job timeout; then write the run's cost to the job summary | R15, R18, R29 |
| `scripts/review_cost.py` | yes | Turns the action's execution file into the cost summary: total at API prices, duration, turns, and tokens per model | R29 |
| `tests/test_review_cost.py` | yes | The summary from a recorded result, and a missing file never failing the job | R29 |
| `CLAUDE.md` | no | One line: reviews come from CI, read their rules from `main`, and never approve | R15 |
| `README.md` | no | That every pull request is reviewed, and how to ask for another review | R15 |
| `tests/test_workflows.py` | yes | Static checks on `review.yml` and `protected-paths.yml`: triggered by `pull_request_target`, check out only the base, read-only permissions; for review, a turn cap, a timeout, `REVIEW.md` from the base, and cost recorded even on failure | R18 |

## Order of work

1. The repository owner installs the Claude GitHub App on the repository and adds `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) as a repository secret. Nothing below runs without them.
2. Read how the `code-review` plugin gets the change and its surrounding code: through the GitHub API, the local checkout, or both. That decides whether the pull request's files need to be on disk, and where.
3. `REVIEW.md`, then `review.yml` built from the documented example: `plugin_marketplaces` and `plugins` for `code-review@claude-code-plugins`, the `/code-review:code-review --comment` prompt, and `--allowedTools` naming the inline-comment tool.
4. Check whether the plugin reads `REVIEW.md`. If it doesn't, pass the base branch's copy with `--append-system-prompt`.
5. `tests/test_workflows.py`; `./scripts/check` passes.
6. Open two throwaway pull requests from branches in this repository: one that plants a known bug (an off-by-one in `artefacts.py`'s requirement numbering) and one that only fixes a typo in the README. Close both after reading the reviews.
7. `CLAUDE.md` and README lines.

## Risks

- **`pull_request_target` with a secret.** A workflow that runs the pull request's code with the token in reach would hand the token to anyone who can open one. Mitigation: the job checks out the base branch as its working tree, the pull request's files are only read, no step runs them, and step 5's test fails if that changes. The action also refuses actors without write access and bot actors, so a stranger's fork can't start a run.
- **Prompt injection from pull request content.** A diff or description can carry instructions. Mitigation: the reviewer's tools are reading and posting inline comments only, so the worst outcome is a misleading comment, and findings never approve or block.
- **The plugin may not read `REVIEW.md`.** Step 4 checks; the fallback passes it explicitly.
- **The reviewer may be weak on this repository.** Step 6 is a smoke test of two cases, not an eval. If it misses the planted bug or flags the typo fix, that becomes an intent for our own reviewer, judged by the Deploy evals.
- **Usage.** Each review counts against the subscription. The turn cap and timeout bound one run, and the job summary records each run's tokens (R29) so the cost is visible from the first review.
- **The token belongs to one person's subscription.** Fine for this repository; another maintainer would need their own token or an API key.

## Found while building

- The `code-review` plugin reads the change through `gh pr diff` and `gh pr view`, so the pull request's files never need to be on disk; the job checks out only the base branch, which also makes `CLAUDE.md` the base branch's.
- The plugin does not read `REVIEW.md`, so step 4's fallback applies: the workflow passes it with `--append-system-prompt-file`.
- The plugin skips pull requests it judges trivial, and any it has already commented on, so it reviews a pull request once rather than on every push.
- A `pull_request_target` workflow runs from the base branch, so this review can only start reviewing once this change is on `main`. Step 6's smoke tests run after the merge.
- Found in step 6: checking out `github.event.pull_request.base.sha` gives the base as it was when the pull request was opened. For a pull request older than this change, that `main` has no `REVIEW.md` or cost script, so the review and its cost step failed. Both base-branch workflows now check out with no `ref`, which on `pull_request_target` is the base branch's current tip, and the workflow test forbids any `ref`.

## Proof

- `./scripts/check` passes, including `tests/test_workflows.py`.
- On the planted-bug pull request, the review posts an inline finding on the changed numbering logic.
- On the typo pull request, the review reports no issues, or skips it as trivial, which the `code-review` plugin does by design.
- A pull request that edits `REVIEW.md` is still reviewed under `main`'s `REVIEW.md`, shown by a rule that exists only on `main` still applying.
- Each run's job summary shows its tokens and duration.
