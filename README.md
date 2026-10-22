# asdlc

An agentic SDLC as a Claude Code plugin, built on Anthropic's AI-native SDLC playbook. It builds itself: every change carries a plan, approved before it is built, in the same pull request as the change.

## Install

uv is the one prerequisite: the plugin's hooks and checks are Python 3.15 scripts run through it, and uv fetches 3.15 on first use. Install it from <https://docs.astral.sh/uv/>.

Then, in Claude Code:

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

## What version 0 does

| Play | What you get |
|---|---|
| Capture intent | `/asdlc:intent` and the `capture-intent` skill: an interview, an intent in the requester's words as a draft on the board, accepted by a person with `asdlc accept` |
| Plan mode | `/asdlc:plan` and the `plan-change` skill: files, order, risks and proof in the task's plan section, numbered steps for `size-1`, approved by the engineer for size 2 and up |
| Skills | The `write-policy-skill` skill and a template that names each policy's owner, source and enforcement |
| Feedback loop | One check command per repository, and a hook that stops a bug fix on a `fix/` branch from changing an existing test, through the file tools or plain shell writes |
| Hooks | Every hook decision logged to `.asdlc/hooks.jsonl` |
| CLAUDE.md | A check that keeps it to at most 60 lines |

Templates for intents, specs and plans are in `templates/`, and `scripts/artefacts.py` checks that each artefact has what the next stage needs.

## Shared board

For a team whose engineers each run several agents. Work is tracked on a [Backlog.md](https://github.com/MrLesk/Backlog.md) board in its own repository, with no code in it. Every board change is committed and pushed straight to that repository's `main` with git hooks off, an agent claims a task before it starts, and each claimed task gets its own worktree in the code repository. `scripts/asdlc` does all of it; link it onto your `PATH` as `asdlc`. It needs Backlog.md 1.55.1 or later (`npm i -g backlog.md@1.55.2`), because older versions drop frontmatter keys they don't know when a task is edited.

Set up once:

```sh
asdlc init-board ~/src/team-board            # git init, backlog init, this board's statuses, types and size labels
git -C ~/src/team-board remote add origin <the board repository's url>
git -C ~/src/team-board push -u origin main
```

Each person clones the board, then points each code repository at their clone: `git config asdlc.board ~/src/team-board`. `--board <path>` or `ASDLC_BOARD` override it.

| Command | What it does |
|---|---|
| `asdlc board <backlog arguments>` | Runs `backlog` on the board and pushes what it committed. If someone pushed first it rebases and retries; if the rebase conflicts, your change is dropped and the message names the task file, so run it again on the new state. |
| `asdlc next --as <agent>` | Claims the highest-priority unassigned To Do leaf task that can start, and prints its worktree. Prints `no work available` when there is none. |
| `asdlc claim <id> --as <agent>` | Claims one task: In Progress, assigned to `@<agent>`, pushed. Of two agents claiming at once, git accepts one push; the other is told "Another agent claimed <id> first" and its claim is undone. |
| `asdlc release <id> --as <agent>` | Puts your claimed task back to To Do with no assignee. Its worktree is left alone. |
| `asdlc route <id>` | The model and effort for a task, as JSON: intents, spikes and parents get opus/high, `size-1` haiku (its plan needs numbered steps), `size-2` to `size-5` sonnet/medium. `size-8` is refused until it is split, and a task needs exactly one size label. |
| `asdlc whoami` | The engineer (`git config asdlc.engineer`), the board, their `devs/<name>.yaml` preferences, and the repositories registered on this machine. |
| `asdlc register [--board <path>]` | Run in a clone of a code repository: sets its `asdlc.board`, records its slug (`owner-repo` from `origin`) and path in `${XDG_CONFIG_HOME:-~/.config}/asdlc/repos.toml`, and adds the slug to the board's `projects`. `asdlc repos` lists what is registered. |
| `asdlc lead <intent> --as <engineer>.lead` | Claims the lead on an intent, draft or accepted, with the same compare-and-swap push as a claim. `asdlc lead-of <id>` names the lead of a task's intent. |
| `asdlc heartbeat <id> --as <worker>` | A board commit touching a task the worker holds, an intent it leads, or a task whose review it holds, so `reap` leaves it. |
| `asdlc reap [--older-than 2h]` | Releases claims, leads and review claims whose task file has had no commit for `stale_after` (in the board's `asdlc.toml`, default 2h), keeping a person's reservation, with a comment saying why. Any orchestrator may run it. |
| `asdlc accept <intent>` | A person's command: promotes an intent draft and all its draft children in one board commit, keeping the children under it and their dependencies on each other. The guard refuses it from agents. |
| `asdlc mine --as <engineer>` | That engineer's workers' tasks (and which came back from review), review claims, leads and reserved work, with the workers cap. |
| `asdlc record-check <id> -- <command>` | Runs a check, appends the command, exit code and the end of its output to the task's notes, and exits with the check's code. |
| `asdlc review-next --as <engineer>.r<n> [--fallback]` | Claims the review of the In Review task that has waited longest, in a repository registered here, that nobody reviews and that hasn't passed review, and prints its branch, pull request, the repository's path here, and the review's model and effort. Not your own engineer's work, unless `--fallback` and it has waited longer than `review_fallback_after`. |
| `asdlc review-done <id> --as <reviewer> --verdict clean\|changes --notes <findings>` | The claiming reviewer's verdict: the findings as a comment; `changes` sends it back In Progress to its worker, labelled `changes-requested`; `clean` labels it `review-passed` and leaves it In Review for a person to merge. |

`claim`, `next`, `lead`, `lead-of`, `mine`, `repos`, `reap`, `accept`, `whoami`, `review-next` and `review-done` take `--json`.

A claimed task's worktree is `<repo>.worktrees/<id>` beside the repository, on a branch named from the task, started from `origin`'s default branch and tracking nothing. Its `.asdlc-task` marker says which task it holds.

### Orchestration

Each engineer sets their name once (`git config --global asdlc.engineer kyle`; don't set `asdlc.board` globally, or every repository on the machine is guarded) and registers each code repository they work in. A task's Backlog `project` is its repository's slug, and its worktree is made in the clone registered for that slug, wherever the command runs. An engineer's workers are `kyle.w1`, `kyle.w2`, and so on; asdlc refuses a worker name that isn't the engineer's name and a dot.

A To Do task assigned only to a person (`@kyle`) is reserved for that person's workers; a claim keeps the person and adds the worker, and a release or a reap puts it back reserved. `asdlc next` offers only tasks whose repository is registered on this machine, whose dependencies are Done and that the routing table accepts. It ranks work reserved for the engineer first, then their `prefer` repositories in order, then priority and ordinal, skips their `avoid` repositories unless the work is reserved for them, starts each worker at a different place among equally good tasks (`kyle.w2` second), and stops at their `workers` cap.

The `orchestrate` skill runs an engineer's loop: reap, pick, check or claim the intent's lead, launch `worker` subagents with the model and effort `asdlc route` gives, gather plans of size 2 and up for the engineer to approve in one batch, heartbeat, and see each task through the worker's finish step to In Review. The `lead` skill covers the lead's spec, contracts, breakdown into draft children and consistency checks. Children are drafted under the draft intent (`asdlc board task create ... --draft -p DRAFT-<n>`; asdlc records the draft parent, which Backlog itself refuses), and the person accepts them all at once with `asdlc accept`.

The `guard_board` hook refuses, with the reason:

- Editing a board's `backlog/` files by hand, so every change is committed and pushed where other agents see it.
- `backlog` or `asdlc board` setting To Do or Done, promoting a draft, or creating a task without `--draft` (it would start as accepted To Do work), and `asdlc accept`: accepting and closing work are a person's decisions. `asdlc release` is the way to hand a task back. The command `asdlc record-check` runs is judged like any other.
- Editing a code repository that has `asdlc.board` set outside a claimed task's worktree, so no two agents change the same work.
- `git push` to that repository's default branch, so changes arrive through review. Pushes to the board are allowed.
- `gh pr review --approve` or `--request-changes`, `gh pr merge`, and the same through `gh api`: approving and merging a pull request are a person's.

A claim with no update for `stale_after` (in `asdlc.toml`, default 2h) is released by `asdlc reap`, which any orchestrator runs; `asdlc heartbeat` keeps a live claim fresh. `asdlc release` hands a task back by hand.

### Cross-machine review

A finished task is In Review with its branch and pull request recorded. Any orchestrator whose engineer didn't write it, with `review: true` in their `devs/<name>.yaml` and the repository registered, may claim its review with `asdlc review-next`; the claim is a compare-and-swap push like any other, recorded on the task as `asdlc_reviewer`. The orchestrator launches the `reviewer` agent (sonnet, medium effort, from the routing table), which reads the task, its plan, its acceptance criteria, its intent's contracts and `REVIEW.md`, reviews the diff in a detached worktree of the registered repository (so the repository's rules reach it), records the verdict with `asdlc review-done`, and posts the same findings on the pull request as a comment when `gh` can reach it. A review never approves on GitHub; a person merges.

`changes` sends the task back to the worker that built it, which fixes the findings and sets it In Review again. If no other engineer's reviewer claims a task within `review_fallback_after` (in `asdlc.toml`, default 30m) of it entering In Review, its author's own orchestrator may review it with a fresh reviewer agent (`review-next --fallback`), and the task records `asdlc_review_kind: same-machine` so the person who merges knows. Review claims count against the `workers` cap, are kept alive by `heartbeat`, and are released by `reap`.

## Tasks repository as a marketplace

The board's repository is also a Claude Code plugin marketplace, so the team's conventions reach every engineer's agents without any setup in the code repositories. `asdlc init-board` adds, and on an existing board adds only what is missing, never overwriting:

- `.claude-plugin/marketplace.json`, listing the `team` plugin (and later one plugin per code repository).
- `plugins/team/`: the team's testing skill and rules, and the contract a lead writes for a large feature. Its README says where a new team skill or rule goes and how rules are scoped.
- `asdlc.toml`: how long a claim lives without a heartbeat, and how long a review waits for another machine.
- `devs/`: each engineer's preferences, `devs/<name>.yaml`.

Each developer installs the team plugin once: `/plugin install team --marketplace <owner>/<tasks repo>`. Its skills then load like any plugin's.

Claude Code doesn't load a plugin's rules, so asdlc's `load_rules` hook does. When an agent reads or edits a file in a code repository that has a board, it injects each team rule (`plugins/team/rules/`) and each of that repository's rules (`plugins/<owner-repo>/rules/`) whose `paths` match the file, once per session and per subagent, and again after compaction, naming the file's layer for a repository rule. Rules come from the local board clone, capped at 10,000 characters per injection. The per-repository plugin's format (layers, rules, skills, verified commands) is [`docs/repo-plugins.md`](docs/repo-plugins.md).

## Onboarding a repository

A code repository gets its plugin in the tasks repository the first time work needs it. The orchestrator runs the `onboard-repo` skill, which reads the repository and decides its commands, layers and rules; `scripts/asdlc-plugin` (link it onto your `PATH` beside `asdlc`) does the rest:

| Command | What it does |
|---|---|
| `asdlc-plugin status <repo> [--json]` | The repository's slug, and whether its plugin is published or being made. |
| `asdlc-plugin scaffold <repo>` | Opens a worktree of the tasks repository beside your clone, `<tasks>.worktrees/plugin-<slug>`, with the plugin's skeleton and marketplace entry. Never overwrites a file, and never edits the clone itself, so claims keep working meanwhile. |
| `asdlc-plugin verify-command <repo> <name>` | Runs one command from `commands.toml` on a clean checkout of the default branch (a worktree beside your clone when the clone isn't one); dates it `verified` only if it passes without changing tracked files. |
| `asdlc-plugin check <slug> [--repo <repo>]` | Checks the plugin against [`docs/repo-plugins.md`](docs/repo-plugins.md), its layers and rules against the repository's files, and runs `claude plugin validate` when it can. |
| `asdlc-plugin publish <slug> [--repo <repo>]` | Refuses unless the check is clean, then pushes the plugin to the tasks repository's `main` with hooks off, retrying when someone pushed first, updates your clone, and prints a record for the task's notes. |

The skill uses the owner's authoring kit (`authoring-kit`) when the session has it, to choose between a rule, a skill and a check and to audit the result, and says on the task when it doesn't.

## Review

Every pull request to this repository is reviewed by Claude in CI, using Anthropic's `code-review` plugin under the rules in [`REVIEW.md`](REVIEW.md), both read from `main`. Findings arrive as inline comments and never approve or block; the cost of each review is in the run's job summary.

## What it does not do yet

- No eval suite, so changes merge on review alone until the eval gate lands.
- The requirements-and-design play, approval gates, CI/CD and closing the loop on metrics are specified in `spec/agentic-sdlc-plugin.md` and come in later versions.

## How it is built

- [The intent](intent/agentic-sdlc-plugin.md)
- [The spec](spec/agentic-sdlc-plugin.md) and [its evals](spec/agentic-sdlc-plugin-evals.md)
- [The plan for version 0](plan/v0-bootstrap.md)
