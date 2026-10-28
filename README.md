# asdlc

An agentic SDLC as a Claude Code plugin, built on Anthropic's AI-native SDLC playbook. It builds itself: every change carries a plan, approved before it is built, in the same pull request as the change.

## Install

uv is the one prerequisite: the plugin's hooks and checks are Python 3.15 scripts run through it, and uv fetches 3.15 on first use. Install it from <https://docs.astral.sh/uv/>.

Then, in Claude Code:

```
/plugin install asdlc --marketplace bruk-io/asdlc
```

Joining the team pilot? Start with [the guide](docs/guide.md): install, set up, a day with it, and how to remove it.

## What version 0 does

| Play | What you get |
|---|---|
| Capture intent | `/asdlc:intent` and the `capture-intent` skill: an interview, an intent in the requester's words as a draft on the board, accepted by a person with `asdlc accept` |
| Plan mode | `/asdlc:plan` and the `plan-change` skill: files, order, risks and proof in the task's plan section, numbered steps for `size-1`, approved by the engineer for size 2 and up |
| Skills | The `write-policy-skill` skill and a template that names each policy's owner, source and enforcement |
| Feedback loop | One check command per repository, and a hook that stops a bug fix (a `bug` task's worktree, or a `fix/` branch) from changing an existing test, through the file tools or plain shell writes |
| Hooks | Every hook decision logged to `.asdlc/hooks.jsonl` |
| CLAUDE.md | A check that keeps it to at most 60 lines |
| Metrics | `asdlc stats`: the playbook's numbers by stage from the board's history, each beside the playbook's name for it, and the ones the board can't measure with what they need |

Templates for intents, specs and plans are in `templates/`, and `scripts/artefacts.py` checks that each artefact has what the next stage needs.

## Shared board

For a team whose engineers each run several agents. Work is tracked on a [Backlog.md](https://github.com/MrLesk/Backlog.md) board in its own repository, with no code in it. Every board change is committed and pushed straight to that repository's `main` with git hooks off, an agent claims a task before it starts, and each claimed task gets its own worktree in the code repository. `scripts/asdlc` does all of it; link it onto your `PATH` as `asdlc`. It needs Backlog.md 1.55.1 or later (`npm i -g backlog.md@1.55.2`), because older versions drop frontmatter keys they don't know when a task is edited.

Set up once:

```sh
asdlc init-board ~/src/team-board            # git init, backlog init, this board's statuses, types, size and review labels
git -C ~/src/team-board remote add origin <the board repository's url>
git -C ~/src/team-board push -u origin main
```

Each person clones the board, then points each code repository at their clone: `git config asdlc.board ~/src/team-board` (`asdlc register` does it). `asdlc`, `asdlc-plugin` and the rule loader all look the board up in one order: `--board <path>`, then `ASDLC_BOARD`, then `git config asdlc.board`. Every `asdlc` command also takes `--in <folder>` to run as if from that folder, so agents never `cd`.

| Command | What it does |
|---|---|
| `asdlc board <backlog arguments>` | Runs `backlog` on the board and pushes what it committed. If someone pushed first it rebases and retries; if the rebase conflicts, your change is dropped and the message names the task file, so run it again on the new state. |
| `asdlc next --as <agent>` | Claims the highest-priority unassigned To Do leaf task that can start, and prints its worktree. Prints `no work available` when there is none, or when the engineer reviews and the last free slot is kept for a review waiting for them. |
| `asdlc claim <id> --as <agent>` | Claims one task: In Progress, assigned to `@<agent>`, its branch recorded on it (`asdlc_branch`), pushed. Of two agents claiming at once, git accepts one push; the other is told "Another agent claimed <id> first" and its claim is undone. A task already held under the same name is refused: another session may be using it. |
| `asdlc release <id> --as <agent>` | Puts your claimed task back to To Do, still reserved for any person it was reserved for (and, when a review asked for changes, for its author's engineer). Its worktree is left alone. |
| `asdlc route <id>` | The model and effort for a task, as JSON: intents, spikes and parents get opus/high, `size-1` haiku (its plan needs numbered steps), `size-2` to `size-5` sonnet/medium. `size-8` is refused until it is split, and a task needs exactly one size label. |
| `asdlc whoami` | The engineer (`git config asdlc.engineer`), the board, their `devs/<name>.yaml` preferences, and the repositories registered on this machine. |
| `asdlc register [--board <path>]` | Run in a clone of a code repository: sets its `asdlc.board`, records its slug (`owner-repo` from `origin`) and path in `${XDG_CONFIG_HOME:-~/.config}/asdlc/repos.toml`, and adds the slug to the board's `projects`. `asdlc repos` lists what is registered. |
| `asdlc lead <intent> --as <engineer>.lead [--new]` | Claims the lead on an intent, draft or accepted, with the same compare-and-swap push as a claim. A draft id your lead was accepted from is refused, since Backlog gives it to the next new draft; `--new` means that new draft. `asdlc lead-of <id>` names the lead of a task's intent, the nearest intent up its parents, finding an accepted draft's task by its old id. |
| `asdlc heartbeat <id> --as <worker>` | A board commit touching a task the worker holds In Progress, an intent it leads, or a task whose review it holds, so `reap` leaves it. A claim is its first heartbeat. On the worker's task once it is In Review it is a no-op that says to stop; an accepted draft's old id finds its task. |
| `asdlc reap [--older-than 2h]` | Releases claims, leads and review claims whose task file has had no commit for `stale_after` (in the board's `asdlc.toml`, default 2h), keeping a person's reservation, with a comment saying why; a claim whose plan waits for approval gets `approval_wait` (default 24h), and a sent-back task's reservation for its author expires after one more `stale_after`. Any orchestrator may run it. |
| `asdlc accept <intent>` | A person's command: promotes an intent draft and every draft under it, at any depth, in one board commit, re-parenting each level and keeping their dependencies on each other; comments the old and new ids on the intent and marks each task with `asdlc_accepted_from`. The guard refuses it from agents. |
| `asdlc approve <id>... [--plan-hash <digest>]...` | A person's command: shows each plan and approves it, recording who, the plan's digest and the task's size; refuses a plan that changed since the person was shown it (`--plan-hash`, one per id) and a task no worker holds. Its workers can't record checks or finish without it, or once the plan or the size changed since. The guard refuses it from agents. |
| `asdlc mine --as <engineer>` | That engineer's workers' tasks (with each one's size, branch, plan approval, and whether it came back from review), review claims, leads (with the draft id an accepted one had), reserved work, the reviews waiting for them, and the workers cap. |
| `asdlc record-check <id> --in <worktree> --as <worker> -- <command>` | Run in the task's worktree (named with `--in`, so the worker never has to `cd`; or run from inside it) by the worker holding it, with its plan approved (size 2 and up): runs a check, appends the command, exit code, the worktree, branch and commit it ran on, and the end of its output to the task's notes, and exits with the check's code. |
| `asdlc finish <id> --as <worker> [--pr <url>] --notes <text>` | The worker holding the task hands it to review: In Review, its branch and pull request recorded, the notes appended, and `changes-requested` removed when it comes back from a review. Refuses unless the worker holds it In Progress and, for size 2 and up, its plan was approved. |
| `asdlc review-next --as <engineer>.r<n> [--fallback]` | Claims the review of the In Review task that has waited longest, in a repository registered here, that nobody reviews and that hasn't passed review, and prints its branch, pull request, the repository's path here, and the review's model and effort. Not your own engineer's work, unless `--fallback` and it has waited longer than `review_fallback_after`. |
| `asdlc review-done <id> --as <reviewer> --verdict clean\|changes --findings important=<n>,nit=<n> [--policy <name>]... --plan-matched yes\|no --notes <findings>` | The claiming reviewer's verdict: the findings as a comment, with their counts, the policies or rules they cite, and whether the diff still matched the plan recorded on the task; `changes` (at least one Important) sends it back In Progress to its worker, labelled `changes-requested`; `clean` (no Important) labels it `review-passed` and leaves it In Review for a person to merge. |
| `asdlc intent-started <draft> [--at <time>]` | Records on an intent draft when the conversation that wrote it began, once; the `capture-intent` skill runs it right after creating the draft. |
| `asdlc doctor` | Checks that this machine is ready, each line pass, warn or FAIL with what to do: git, uv and Python 3.15, Backlog.md 1.55.1 or later, `asdlc` and `asdlc-plugin` on `PATH`, `gh` and `claude` (warnings only); your `asdlc.engineer` and `devs/<name>.yaml`; the board clean, on `main` and its `origin` reachable without a prompt; `asdlc.toml`; each registered repository; the tasks repository's marketplace, the team plugin, auto-update and the authoring kit (through `claude plugin list` when `claude` is installed); the Claude Code allow rules and folders normal work needs (a warning naming what is missing and `asdlc permissions --write`); a configured Backlog.md MCP server (a warning: asdlc works through the CLI only); leftover onboarding, verification and review worktrees; and `asdlc-plugin check` on every published repository plugin. Exits 1 on any FAIL. |
| `asdlc permissions [--write]` | The Claude Code allow rules background workers and reviewers need on this machine, so they run without prompts (in sessions started in the tasks clone), as narrow as the work allows: asdlc's own commands (by name, by path, through `uv run --script`), backlog's reads, the git subcommands agents run in worktrees (`git -C <clone>.worktrees/* <subcommand> *`, each also in its bare form, including mv, rm, restore, stash and reset there) and the few a reviewer runs in a clone, with the read-only ones both use to find their way (ls-files, grep, blame, cat-file, ls-tree, merge-base, rev-list, describe, show-ref, `remote get-url`), `gh pr create`/`view`/`comment`, each registered repository's simple verified commands as exact rules (the rest are listed with why), and edits in the worktree folders, also added as `additionalDirectories`; and `deny` rules for git that runs a program or sets configuration (`-c`, `git config`, `grep -O`, `--upload-pack`, `--ext-diff`, `rebase -x`, `env GIT_*` and the like), which the board guard also refuses, since deny beats the allow rules' `*`. `--write`, a person's command the guard refuses from agents, merges them into the tasks clone's own `.claude/settings.local.json` (untracked), keeping everything there, after a backup, atomically; never into user settings. |
| `asdlc stats [--since <date>] [--stage <stage>]` | The playbook's numbers by stage (plan, design, build, test, deploy, maintain) and for the board's own coordination, each beside the playbook's name for it, from the board's history, the tasks' notes, this machine's event log and hook decision logs, and `gh` for merge times when it can. A number that can't be computed says what it would need, and the ones the board can't measure (change failure rate, DORA) are listed. The parsed history is cached by commit in the tasks clone's ignored `.asdlc/stats/`. [What the numbers mean](docs/guide.md#what-the-numbers-mean). |

`claim`, `next`, `finish`, `lead`, `lead-of`, `mine`, `repos`, `reap`, `accept`, `whoami`, `review-next`, `review-done`, `permissions`, `doctor` and `stats` take `--json`. `claim`, `next`, `review-next` and `lead` append one line per attempt (claimed, lost race, or refused, with the reason) to `${XDG_STATE_HOME:-~/.local/state}/asdlc/events.jsonl` on the machine.

A claimed task's worktree is `<repo>.worktrees/<id>` beside the repository, on the branch recorded on the task at its first claim, tracking nothing. A branch nobody pushed starts from `origin`'s default branch; one already pushed (an earlier round, or a worker whose claim was reaped) is resumed from `origin/<branch>`, so nothing is ever rebuilt from main and forced over it. Its `.asdlc-task` marker says which task it holds.

Every board commit asdlc makes carries an `Asdlc-Transaction` trailer, and a marker in the clone's git folder covers a change while it runs. A command that is interrupted (Ctrl-C, SIGTERM, a closed terminal) drops its unpushed change at once; one killed outright leaves it, and the next asdlc command on that clone drops it. asdlc never pushes an earlier unpushed change, and refuses, saying how to fix it, when the clone has commits it didn't make. Commands wait at most 45 seconds for another asdlc command's lock on the clone.

### Orchestration

Each engineer sets their name once (`git config --global asdlc.engineer kyle`; don't set `asdlc.board` globally, or every repository on the machine is guarded) and registers each code repository they work in. A task's Backlog `project` is its repository's slug, and its worktree is made in the clone registered for that slug, wherever the command runs. An engineer's workers are `kyle.w1`, `kyle.w2`, and so on; asdlc refuses a worker name that isn't the engineer's name and a dot.

A To Do task assigned only to a person (`@kyle`) is reserved for that person's workers; a claim keeps the person and adds the worker, and a release or a reap puts it back reserved. `asdlc next` offers only tasks whose repository is registered on this machine, whose dependencies are Done and that the routing table accepts. It ranks work reserved for the engineer first, then their `prefer` repositories in order, then priority and ordinal, skips their `avoid` repositories unless the work is reserved for them, starts each worker at a different place among equally good tasks (`kyle.w2` second), and stops at their `workers` cap.

The `orchestrate` skill runs an engineer's loop: reap, pick, check or claim the intent's lead, launch `worker` subagents with the model and effort `asdlc route` gives, gather plans of size 2 and up into one batch for the engineer, who approves them with `asdlc approve` in their own terminal, heartbeat what its agents are working on at the top of every round, and see each task through the worker's `asdlc finish` to In Review. The `lead` skill covers the lead's claim, contracts, change requests, plan checks and consistency checks, and sequences the `write-spec` and `break-down-intent` skills. Children are drafted under the draft intent (`asdlc board task create ... --draft -p DRAFT-<n>`; asdlc records the draft parent, which Backlog itself refuses), and the person accepts them all at once with `asdlc accept`.

The `guard_board` hook refuses, with the reason:

- Editing a board's `backlog/` files by hand, so every change is committed and pushed where other agents see it.
- `backlog` or `asdlc board` setting To Do or Done, promoting a draft, archiving or demoting a task, or creating a task without `--draft` (it would start as accepted To Do work), and `asdlc accept`, `asdlc approve` and `asdlc permissions --write`: accepting work, approving plans, closing work and changing a person's Claude Code settings are a person's decisions. `asdlc release` is the way to hand a task back. The command `asdlc record-check` runs is judged like any other.
- `backlog` or `asdlc board` setting In Progress or In Review, changing a task's assignees, or adding or removing `review-passed` or `changes-requested`: claims, `asdlc finish`, `asdlc release` and `asdlc review-done` do those, checking who holds the task, so a worker whose claim was reaped can't finish someone else's.
- Changing the size of accepted work (a `size-*` label on a task that isn't a draft, or replacing or clearing its labels): an approval holds for the size it approved.

These rules apply to `task edit`, `task create`, `draft create` and `draft edit` only: listings, views and searches that filter by status, label or assignee are never refused. A test walks every command the skills and agents give through the guard.
- Editing a code repository that has `asdlc.board` set outside a claimed task's worktree, so no two agents change the same work.
- `git push` to that repository's default branch, so changes arrive through review, and any force push there (`--force`, `-f`, `--force-with-lease`, `+refspec`), so a task branch under review is never rewritten. Pushes to the board are allowed.
- `gh pr review --approve` or `--request-changes`, `gh pr merge`, and the same through `gh api`: approving and merging a pull request are a person's.

The guard only ever denies or allows, never asks, so it adds no permission prompts. asdlc works through the `backlog` CLI only; Backlog.md's MCP server would bypass the board's rules, and `asdlc doctor` warns when one is configured.

A claim with no update for `stale_after` (in `asdlc.toml`, default 2h) is released by `asdlc reap`, which any orchestrator runs; `asdlc heartbeat` keeps a live claim fresh. `asdlc release` hands a task back by hand.

### Cross-machine review

A finished task is In Review with its branch and pull request recorded. Any orchestrator whose engineer didn't write it, with `review: true` in their `devs/<name>.yaml` and the repository registered, may claim its review with `asdlc review-next`; the claim is a compare-and-swap push like any other, recorded on the task as `asdlc_reviewer`. The orchestrator launches the `reviewer` agent (sonnet, medium effort, from the routing table), which reads the task, its plan, its acceptance criteria, its intent's contracts and the team's review policy (`plugins/team/review.md` in the tasks repository, plus the repository plugin's own `review.md` when it has one; never this plugin's own `REVIEW.md`, which is for changes to asdlc), reviews the diff in a detached worktree of the registered repository (so the repository's rules reach it), records the verdict with `asdlc review-done`, and posts the same findings on the pull request as a comment when `gh` can reach it. A review never approves on GitHub; a person merges.

`changes` sends the task back to the worker that built it, which fixes the findings and hands it back with `asdlc finish`. If its claim is reaped meanwhile, it goes back to To Do reserved for its author's engineer, and the next claim resumes its pushed branch. If no other engineer's reviewer claims a task within `review_fallback_after` (in `asdlc.toml`, default 30m) of it entering In Review, its author's own orchestrator may review it with a fresh reviewer agent (`review-next --fallback`), and the task records `asdlc_review_kind: same-machine` so the person who merges knows. Review claims count against the `workers` cap, are kept alive by `heartbeat`, and are released by `reap`. An engineer who reviews keeps one slot for a waiting review: `asdlc next` won't take the last free slot while a review waits for them and none of their reviewers holds one.

## Tasks repository as a marketplace

The board's repository is also a Claude Code plugin marketplace, so the team's conventions reach every engineer's agents without any setup in the code repositories. `asdlc init-board` adds, and on an existing board adds only what is missing, never overwriting:

- `.claude-plugin/marketplace.json`, listing the `team` plugin (and later one plugin per code repository).
- `plugins/team/`: the team's testing skill and rules, its review policy (`review.md`), and the contract a lead writes for a large feature. Its README says where a new team skill or rule goes and how rules are scoped.
- `asdlc.toml`: how long a claim lives without a heartbeat, and how long a review waits for another machine.
- `devs/`: each engineer's preferences, `devs/<name>.yaml`.
- `.gitignore`, with `.asdlc/`, where the hooks log their decisions.

Each developer installs the team plugin once: `/plugin install team --marketplace <owner>/<tasks repo>`. Its skills then load like any plugin's.

Claude Code doesn't load a plugin's rules, so asdlc's `load_rules` hook does. When an agent reads or edits a file in a code repository that has a board, it injects each team rule (`plugins/team/rules/`) and each of that repository's rules (`plugins/<owner-repo>/rules/`) whose `paths` match the file, once per session and per subagent, and again after compaction, naming the file's layer for a repository rule. Rules come from the local board clone, capped at 10,000 characters per injection. The per-repository plugin's format (layers, rules, skills, verified commands) is [`docs/repo-plugins.md`](docs/repo-plugins.md).

## Onboarding a repository

A code repository gets its plugin in the tasks repository the first time work needs it. The orchestrator runs the `onboard-repo` skill, which reads the repository and decides its commands, layers and rules; `scripts/asdlc-plugin` (link it onto your `PATH` beside `asdlc`) does the rest:

| Command | What it does |
|---|---|
| `asdlc-plugin status <repo> [--json]` | The repository's slug, and whether its plugin is published or being made. Here and below, `<repo>` is the clone's path or, when it is registered on this machine, its slug. |
| `asdlc-plugin scaffold <repo>` | Opens a worktree of the tasks repository beside your clone, `<tasks>.worktrees/plugin-<slug>`, with the plugin's skeleton and marketplace entry. Never overwrites a file, and never edits the clone itself, so claims keep working meanwhile. |
| `asdlc-plugin verify-command <repo> <name>` | Runs one command from `commands.toml` on a clean checkout of the default branch (a worktree beside your clone when the clone isn't one); dates it `verified` only if it passes without changing tracked files. |
| `asdlc-plugin check <slug> [--repo <repo>]` | Checks the plugin against [`docs/repo-plugins.md`](docs/repo-plugins.md), its layers and rules against the repository's files, and runs `claude plugin validate` when it can. |
| `asdlc-plugin publish <slug> [--repo <repo>]` | Refuses unless the check is clean, then pushes the plugin to the tasks repository's `main` with hooks off, retrying when someone pushed first, updates your clone, and prints a record for the task's notes. |

The skill uses the owner's authoring kit (`authoring-kit`) when the session has it, to choose between a rule, a skill and a check and to audit the result, and says on the task when it doesn't.

## Review

Every pull request to this repository is reviewed by Claude in CI, using Anthropic's `code-review` plugin under the rules in [`REVIEW.md`](REVIEW.md), both read from `main`. Findings arrive as inline comments and never approve or block; the cost of each review is in the run's job summary.

## What it does not do yet

- The eval suite runs by hand and in `./scripts/check` (reference and null runs only); nothing gates a merge on its scores yet (R22).
- The requirements-and-design play, approval gates, CI/CD and closing the loop on metrics are specified in `spec/agentic-sdlc-plugin.md` and come in later versions.

## Evals

`scripts/eval` runs the eval suite in `evals/`: real Claude Code agents, headless, against throwaway fixtures, graded by deterministic checks the agent never sees. [Running evals](docs/guide.md#running-evals) says how to run it; [`evals/README.md`](evals/README.md) says how to write a case.

| Command | What it does |
|---|---|
| `scripts/eval validate [--case <name>]` | Every case's scripted reference run must pass every check and its null run must fail one. No model calls; `./scripts/check` runs it. |
| `scripts/eval run [--case <name>]... [--trials 3] [--model M] [--arm with-plugin\|without-skills] [--plugin <ref or folder>] [--container]` | Builds a fresh fixture per trial, runs `claude -p` with the case's prompt and its person steps between resumed sessions, and grades the outcome. The plugin is a read-only export of `origin/main` by default, without the suite. |
| `scripts/eval gate [--base <ref>] [--all] [--trials 3]` | What a change to `CLAUDE.md`, `skills/`, `hooks/`, `agents/` or `commands/` must pass: the regression cases (every case with `--all`) against the working copy, judged, with a report under `.eval-results/gate/` that `scripts/gate_evidence.py verify` checks and the push guard asks. Spends tokens; a person runs it. [The gate](docs/guide.md#the-gate). |
| `scripts/eval calibrate [--dimension <name>] [--judge-model M]` | Asks a rubric judge about your labelled samples in `evals/calibration/<dimension>.toml`, reports its agreement against the bar and records it. A judge gates trials only when calibrated for its model; until then it is advisory. Spends tokens. [Judging](docs/guide.md#judging-what-no-check-can-decide). |
| `scripts/eval regrade <results>` | Grades a run's stored outcomes again with the checks as they are now, and recounts its transcripts, keeping the earlier verdicts beside: a check fixed after a run judges that run without new model calls. |
| `scripts/eval report [<results>]` | pass@k, pass^k and the mean pass rate per case, the overall mean with its standard error clustered by case and the smallest change the run can detect, tokens by model, turns, tool calls and errors, cost at API prices (`evals/prices.toml`), and a sample of transcripts. |

The first suite: six regression cases from the independent review's findings and the owner (a reaped worker stops, a sent-back branch survives, nothing is built before approval, the reviewer's full verdict and no approving or merging, a grandchild follows the real lead, a small request isn't an intent), and three capability cases (reviewer recall, reviewer false alarms, and a 20-request trigger set for `capture-intent` and `orchestrate`). The eval image is `.devcontainer/`.

## How it is built

- [The intent](intent/agentic-sdlc-plugin.md)
- [The spec](spec/agentic-sdlc-plugin.md) and [its evals](spec/agentic-sdlc-plugin-evals.md)
- [The plan for version 0](plan/v0-bootstrap.md)
