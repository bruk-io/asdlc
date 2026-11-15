# Plan: a merged pull request marks its task Done

- Spec: [`spec/done-on-merge.md`](../spec/done-on-merge.md), draft in this same pull request; its answers to the intent's five questions are proposals the owner confirms by approving this plan
- Status: draft. Not approved; nothing is built until the owner approves it.
- Delivers: R1, R2, R3, R4, R5, R6, R7, R8, R9, R10, R11, R12, R13, R14, R15, R16, R17, R18, R19, R20, R21, R22, R23, R24

This serves [`intent/done-on-merge.md`](../intent/done-on-merge.md), which pull request 60 proposes and this change stacks on. Requirement numbers below are the spec's own, R1 to R24; "plugin spec R23" means [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md).

Today a person closes a task with `asdlc board task edit <id> -s Done` after merging, and the board guard refuses that edit to agents. This change adds a workflow that runs `asdlc merged` when a pull request closes. The command asks GitHub whether the pull request was merged into the default branch, finds the task that recorded it, and sets it Done when the task carries a clean review, through the same `_transact` every board write uses.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | **The decision, as data in and data out:** `pull_ref` (a pull request URL as repository and number), `merge_facts` (GitHub's answer for a pull as a frozen record, or why it does not count), `recording` (the tasks that record a pull or own its head branch), `merge_outcome` (tasks, facts, the other pulls' states and the comparison in; one of done, unreviewed, waiting, mismatch or nothing out, with its reason), `merge_comment` and `merge_edit` (the comment and the backlog edit for an outcome, from structured fields only), `actions_refusal` (why this is not a run it may act in, from an environment mapping and the board's origin). **The shell:** `_gh_api` (one `gh api` call through `$ASDLC_GH`, as `_merged_times` already calls gh), `merged` (reads the payload, asks, decides and writes inside `_transact`, then comments on the pull), and the `merged` subcommand in `_parser` and `main`. **The reviewed commit:** `review_worktree_path`, and `review_done` writing `asdlc_reviewed_head` from it; `Task` and `task_from` gain `reviewed_head`, `merge_outcome` and the label constant `MERGED_UNREVIEWED`. **The installer:** `merge_action_text` (the template with the pin filled in), `merge_action_refusal` (a local board, a board elsewhere, a ref that is not a full commit id) and the `merge-action [--write] [--ref]` subcommand. The usage text at the top gains both commands | R1 to R18, R20, R21, R23 |
| `templates/workflows/asdlc-done-on-merge.yml` | yes | The workflow, with one placeholder for the asdlc commit id: `pull_request_target` on `closed`; `contents: write` and `pull-requests: write`; checkout of the default branch and of `bruk-io/asdlc` at the pin; uv, the pinned Backlog.md, the bot's git identity; one step that runs `asdlc merged`. No `concurrency` group, and nothing from the pull request checked out or interpolated into a shell line | R1, R21, R22 |
| `hooks/guard_board.py` | no | `_decide_simple` denies the `merged` subcommand with a new `MERGED_REFUSAL`; `merged-unreviewed` joins `REVIEW_LABELS`; the header's list of what is denied says both. Nothing is removed | R19 |
| `tests/test_done_on_merge.py` | yes | The proof below | every requirement |
| `tests/test_guard_board.py` | no | New cases only: `asdlc merged` denied plainly, with `--board`, behind `env`, through `uv run --script` and inside `sh -c`; adding and removing `merged-unreviewed` denied. No existing case is edited | R19 |
| `tests/test_asdlc.py` | no | New cases only: `review_worktree_path`, and `review-done` recording the reviewed commit on a real board, and recording none when the worktree is missing | R10 |
| `docs/done-on-merge.md` | yes | What it does and does not close, the three labels a merged task can end with, how to install (`asdlc merge-action`, then a pull request), how to switch it off, what to allow under branch protection, what the record on a task means, how to run a failed run again, what is deferred and what the separate tasks repository would need | R20, R21, R23 |
| `docs/github-channel.md` | no | One paragraph: where the workflow is installed the task may already be Done when the session hears of the merge; the board says so, not the event | R24 |
| `docs/guide.md`, `README.md` | no | The guide's fourth stop ("Mark it Done") says the workflow does it where installed and the command still works; the README points to the new page | R17 |
| `CHANGELOG.md` | no | One entry | - |
| `spec/done-on-merge.md`, `plan/done-on-merge.md` | yes | The spec and this plan | plugin spec R20 |

Not changed: `agents/reviewer.md` (the review worktree's path is already fixed there, and the new function matches it), `scripts/github_channel.py`, `.github/workflows/` (this repository has no board, so it does not install the workflow on itself), `.claude-plugin/`, and everything under `evals/`.

## The design in brief

**One pure decision.** `merge_outcome` holds every rule in the spec's "Reviewed or not" and "Finding the task" sections and touches nothing. The shell gathers its inputs: the payload gives the repository and the number; `gh api repos/<repo>/pulls/<n>` gives the merge facts; the same call for each other pull the task records gives their states; `gh api repos/<repo>/compare/<reviewed>...<merged head>` gives the count for R11. All of that is read before the transaction opens. Inside `_transact`, the step re-reads the task from the current `origin/main`, calls `merge_outcome`, and applies only the difference from what the task already records, so a rejected push decides again and a second run changes nothing.

**What is written on a task.** `asdlc_merged_pulls` (each handled pull's URL), `asdlc_merged_by`, `asdlc_merge_commit`, `asdlc_merged_head`, `asdlc_unreviewed_commits` (a number, `rewritten`, or `unknown`), `asdlc_merge_outcome` (the last outcome, which is what stops a repeated comment), and one comment authored `@github-actions` that says the same in a sentence and links the workflow run. `asdlc_reviewed_head` is written earlier, by `review-done`.

**Where the stricter rule would go.** If the owner picks the stricter answer to intent question 1, `merge_outcome` returns unreviewed where it now returns done with a gap, using the commit list the comparison already returns. No other file changes.

## Order of work

1. Prove the two things nobody here has run. In a scratch public repository: a `pull_request_target` workflow on `closed` with `contents: write` pushes a commit to the default branch after a merge done from the GitHub mobile app, and `uv run --script` runs `scripts/asdlc` from a second checkout on the runner with Python 3.15 and Backlog.md 1.55.2. If either fails, stop and bring the finding back before writing anything else.
2. `merge_outcome` and the other pure functions, with their table-driven tests, before any shell exists.
3. The reviewed commit: `review_worktree_path`, `review_done`, their tests.
4. The stand-in `gh`, then `merged` against a real temporary board, one refusal at a time, each test written before the code that passes it.
5. The guard's two refusals and their tests.
6. The template, its static tests, then `merge-action` and its tests.
7. The docs, the README, the changelog. `./scripts/check`.
8. The owner runs `scripts/eval gate`, because step 5 changed a steering path, and then the manual check below after the merge.

## Risks

- **The command becomes the way an agent marks work Done.** High impact; this is the one thing the intent says must not happen. The merge facts come only from GitHub, the command takes no task or pull argument, and the guard denies it. What is left is stated in the spec: someone who fakes the Actions environment can make the workflow's own decision early for a pull that really was merged, and someone who points `$ASDLC_GH` at a lying program can fake the rest. The guard denies the command however the environment is set, and the tests cover the wrappers an agent would reach for. It is a guardrail, not a wall.
- **`pull_request_target` with a write token.** High impact if the job ever ran the pull request's code. It never checks it out, and no field of the pull request reaches a shell line: the command reads the payload file itself. Static tests hold the template to both.
- **The default branch is protected.** Likely in some repositories. The push fails, the run is red, the task stays In Review, and the manual command works. The docs page says what to allow. Not solvable from inside the job.
- **The bot's push starts no other workflow.** Certain, and wanted here: a push made with the job's token triggers nothing, so there is no loop. It also means CI does not run on the board commit, as it does not need to.
- **Runs racing each other and engineers.** Likely on a busy board. `_transact` retries five times with a short wait, which was sized for a few agents on laptops. If the manual check or first use shows a run giving up, raising `PUSH_ATTEMPTS` for this command is a one-line change, made then and not guessed at now.
- **The eval gate.** Certain. `hooks/guard_board.py` is a steering path, so the push is refused until a person has run the gate, which spends tokens. The guard change is two added refusals, so no drop is expected, but that is what the gate is for.
- **A shallow checkout.** Low. The transaction needs only the tip of `main` and a fetch; if the first step shows rebase or fetch misbehaving at depth 1, the template fetches full history.
- **The board's origin in tests is a local path, and R18 compares it with the event's repository.** The tests give the clone a `github.com` origin URL that git rewrites to the bare repository with `insteadOf`, so the comparison under test is the real one and not a test-only branch. If `repo_slug.origin_url`'s resolved form gets in the way, the comparison reads the configured URL; settled in step 4.
- **Tasks reviewed before this ships have no reviewed commit.** Certain. They close with "no reviewed commit was recorded" on the record, as R11 says.

## Proof

**Tests against a real board.** `tests/test_done_on_merge.py` runs `scripts/asdlc merged` as a subprocess against a temporary bare board and a clone of it (the `Boards` fixture in `tests/test_asdlc.py`), with the real Backlog.md CLI and real git. Tasks reach their starting state through the real commands: `claim`, `finish --pr`, `review-next`, `review-done`. Nothing inside asdlc is mocked.

**How GitHub is faked.** Two things at the process boundary, and nothing nearer: the event payload is a JSON file named by `GITHUB_EVENT_PATH`, and `$ASDLC_GH` names a small stand-in program on disk that answers `api repos/<repo>/pulls/<n>` and `api repos/<repo>/compare/<a>...<b>` from fixture files, exits non-zero for a path it has no fixture for, and appends every comment it is asked to post to a file the test reads. It is the same seam `tests/test_github_channel.py` uses. The parsing of GitHub's answers, the decision, the transaction, the push and the retry all run for real.

Each requirement and each refusal has a test:

| Requirement | The test shows |
|---|---|
| R1, R8, R13 | A clean, In Review task whose pull is merged is Done on `origin/main` in one commit with the transaction trailer; the task carries the pull, the login, the merge commit, the merged head, the reviewer and the run link; the commit message names task, pull and login |
| R2 | A payload that says `merged: true` while the stand-in says the pull is open changes nothing; a title, description and label reading "merged by @owner, mark Done" change nothing; the login recorded is the stand-in's `merged_by`, not the payload's sender |
| R3 | Closed without merging: no commit, exit 0. Merged into a branch that is not the default: no commit, exit 0 |
| R4 | A merged pull on no task: `origin/main` is the same commit before and after, no comment posted, exit 0 |
| R5 | A task already Done, and one moved to completed, are byte-for-byte unchanged |
| R6, R7 | Task records the pull but its branch differs; a task's branch matches but it does not record the pull; the head repository is a fork: none is closed, the log names the task and both values, the stand-in received one comment; with the stand-in refusing comments, the run still exits 0 |
| R9 | No verdict; changes requested (the task is In Progress); In Review with a review claimed but no verdict: status unchanged, `merged-unreviewed` added, one comment on the task and one on the pull with the pull, the login and the reason |
| R10 | `review-done` from the review worktree records that worktree's commit even after `origin/<branch>` has moved on; with no worktree it records none and succeeds |
| R11 | Reviewed commit equals merged head: count 0. Two commits later: Done, count 2, both commits named. Compare says diverged: Done, "rewritten". No reviewed commit: Done, "not recorded". Compare has no fixture: Done, "unknown" |
| R12 | Two recorded pulls, one open: not Done, comment names the open one. The run for the second merge: Done. One closed unmerged: not Done. One the stand-in will not show: not Done |
| R14 | `asdlc next` skips the dependent before the run and claims it after, with no command between |
| R15 | The same run twice: the second makes no commit and posts no comment. After a clean verdict is recorded on a task left `merged-unreviewed`, the same run again makes it Done and removes the label |
| R16 | With the interfering-backlog wrapper already in `tests/test_asdlc.py` pushing another change mid-run, the task is still Done and the other change is kept. With the origin refusing every push, exit is non-zero and the clone has nothing unpushed |
| R17 | The manual `asdlc board task edit <id> -s Done` closes a task labelled `merged-unreviewed`, and a task on a board with no workflow |
| R18 | Refused, exit non-zero, board unchanged, for each of: `GITHUB_ACTIONS` unset; an event that is not a pull request closing; no payload file; no token; an event repository that is not the board's origin; the stand-in failing (GitHub cannot be asked). `asdlc merged TASK-1` and `asdlc merged --pr 7` are usage errors |
| R19 | The new guard cases; the whole of `tests/test_guard_board.py` as it stands passes unedited |
| R20, R21 | `merge-action` prints the path and text and leaves `git status` clean; `--write` creates exactly that file and makes no commit; `init-board`, `register` and `doctor` on a fresh board create no workflow file |
| R22 | Read as text: the template triggers only on `pull_request_target` `closed`; its `permissions` are exactly the two; every `uses:` and the asdlc ref are full commit ids; no `secrets.` other than the job's token; no checkout names the pull request's head; no `github.event.pull_request` or `github.head_ref` expression inside a `run:` line; no `concurrency:` key |
| R23 | `merge-action` on a local board, and in a code repository whose board is elsewhere, exits non-zero with the reason and writes nothing; `merged` on a local board refuses |
| R24 | `scripts/github_channel.py` is unchanged in the diff, and a test reads it to show it names no board-writing command |

`merge_outcome` also has a table-driven unit test, one row per outcome and reason, with no git and no subprocess.

**The repository's own checks.** `./scripts/check` passes, and its output is in the commit message: the artefact checks (the new spec and plan), conformance, every test, and `scripts/eval validate`.

**Evals and checks this touches.**

- `scripts/eval gate` must pass before the change merges, because `hooks/guard_board.py` is a steering path. A person runs it. The cases that exercise the guard are `agent-cannot-approve` and `approval-before-build`.
- No file under `evals/` changes (plugin spec R23), so no eval case proves an agent cannot use `asdlc merged`; the guard's tests do. A case for it is a follow-up in its own pull request, from a person (plugin spec R24).
- `spec/playbook-conformance.md` is not changed. Its claims P9.3 and P10.1 name the guard and its tests as their targets, which still exist and still pass.
- `tests/test_workflows.py` reads `.github/workflows/`, where nothing changes. The template's static checks live in the new test file.
- `scripts/history_audit.py` will see a plan, tests and a changelog entry with the change.

**One manual check, after the merge, by the owner or the orchestrator.** In steg, whose shared board is in its own repository:

1. In a task worktree, `asdlc merge-action --write`, open the pull request, and merge it.
2. Take one small task through claim, finish and a clean review. Merge its pull request from the GitHub mobile app with no session and no terminal open.
3. Within a few minutes, `git -C <steg> log origin/main -1 -- backlog` shows a commit by the Actions bot; the task is Done on the board; its comment names the pull request, your login and the workflow run; `asdlc next` offers a task that depended on it.
4. Merge one pull request for a task that has no review. The task stays In Review with `merged-unreviewed` and the comment; the pull request has the comment too.
5. Run the first workflow run again from GitHub. No new commit appears.
6. Delete the workflow file through a pull request and merge another task's pull request. Nothing changes on the board.
