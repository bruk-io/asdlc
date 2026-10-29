# Changelog

## Unreleased

### The reviewer cites the policy behind any finding ([plan](plan/reviewer-permissions.md))

- `agents/reviewer.md`: a finding tagged with a pass always rests on a review policy, so the reviewer passes `--policy` whenever it records any finding. `reviewer-full-verdict` went from 2/3 to 6/6.

### Two fixes from the first without-hooks run ([plan](plan/close-the-gaps.md))

- The `without-hooks` arm removes the hook registration and keeps the hooks' modules, which the `asdlc` scripts import; the first version deleted the folder and crashed.
- The worker agent is told not to look for rules in the tasks clone, where git is refused and the rule loader already supplies them. `approval-before-build` went from 0/3 to 3/3.

### A justfile with the standard entrypoints ([plan](plan/just-entrypoints.md))

- `just setup` checks git, uv, npm and gh, installs Python 3.15 and Backlog.md 1.55.2 when missing, links `asdlc` and `asdlc-plugin` into `~/.local/bin` and says what is left; running it again changes nothing. `just check`, `test`, `artefacts`, `conformance`, `validate`, `audit`, `doctor`, `try` and `eval` call the scripts that already exist.

### The policy skill backs a policy when asked, and a no-hooks eval arm ([plan](plan/close-the-gaps.md))

- `write-policy-skill`: when the engineer asks for a policy to be backed and a check script already exists, it adds a `PostToolUse` hook that runs that script and blocks, and a pull request workflow that runs the same script. It still builds nothing unasked, and names the gap when no script exists. Over three trials the four policy cases went from 0/3, 1/3, 3/3, 3/3 to 3/3 each.
- `scripts/eval run --arm without-hooks` removes `hooks/hooks.json`, so no hook is registered and no guard runs; a case runs it only when its `arms` names it.

### An audit of the repository's history against its own rules ([plan](plan/history-audit.md))

- `scripts/history_audit.py` reads the merged pull requests and reports, per rule, where a change to the plugin carried no plan, put the plan after the code, merged a new plan still marked draft, mixed the plugin with the eval suite, skipped tests or the changelog, or merged with a required check not green. It also prints the playbook's lagging indicators for each pull request. Known departures go in `scripts/history_waivers.toml` and stay listed.

### The plugin against the playbook, claim by claim ([plan](plan/playbook-conformance.md))

- `spec/playbook-conformance.md` lists 84 claims from the twelve plays, each with what builds it and what tests it, or why nothing does. `scripts/conformance.py`, run by `./scripts/check`, fails on a claim with no mapping, a target that does not exist, a repeated id, or a requirement that serves no claim and is not listed as beyond the playbook.

### The reviewer can diff and log a registered clone ([plan](plan/reviewer-permissions.md))

- `asdlc permissions` allows `git diff` and `git log` in a registered clone, and the reviewer agent is told that a branch name with `-c` in it trips the deny rules, so it diffs in its review worktree against `HEAD`.

### One orchestrator: no leads, heartbeats or reaping ([plan](plan/remove-multi-machine.md))

- Removed `asdlc lead`, `asdlc lead-of`, `asdlc heartbeat` and `asdlc reap`, with the `lead` skill, the `stale_after` and `approval_wait` settings, the `leads` list in `asdlc mine`, and the metric that counted reaped holds. They kept one orchestrator in charge of an intent across machines, kept a claim alive, and freed one whose machine went away; with one orchestrator launching its own workers none has a job. A task's old `asdlc_lead` and `asdlc_heartbeat` keys are ignored.
- `asdlc release` also gives up a review claim a reviewer holds, so a reviewer that died doesn't block a review; nothing else frees a claim now, so the orchestrate skill releases a worker's claim by hand when the worker is gone.
- `review_fallback_after` defaults to 0: the author's own orchestrator reviews at once with a reviewer it launches, which is separate from the worker that built the change.
- The orchestrate skill is one orchestrator's loop, and it checks each plan against the spec and contract itself. The worker and reviewer agents and the `write-spec`, `break-down-intent` and `capture-intent` skills no longer name a lead.

### The eval gate, run locally, and hooks that check for its evidence ([plan](plan/eval-suite.md))

- `scripts/eval gate`: when steering paths changed since the base, runs the regression cases (every case with `--all`) against the working copy, judges them, and writes a report keyed by a digest of the steering paths and the suite. Every trial of a regression case must pass; capability cases must be no worse than the last passing gate beyond their own noise.
- `scripts/gate_evidence.py verify` answers pass, fail, missing, stale, unknown or not needed, and is the only reader of a report. `./scripts/check` prints a reminder when evidence is missing and never fails for it.
- `hooks/guard_gate.py`, in a repository that has the suite: refuses a push while steering paths changed without passing evidence, `--no-verify`, hand-written files under `.eval-results/` and `.asdlc/`, and an edit that would mix the plugin and the suite in one branch (R23). `hooks/gate_status.py` says where the gate stands at session start.
- `guard_board.py` and `guard_test_edits.py` make a few helpers public for the new guard.
- A rubric judge (`scripts/rubric_judge.py`, `scripts/eval calibrate`): a case names rubric dimensions in `judges`, one judge per dimension, with `unknown` allowed. A judge gates trials only when its recorded agreement with the owner's labels reaches the bar for the model judging now; until then it is advisory and reports show it so.
- `scripts/eval report` lists what to look at: a case no trial passed (probably broken) and a capability case that passed every trial for three runs (may graduate to regression).

### The test-edit guard on bug tasks, and repeated findings turned into rules ([plan](plan/bug-guard-and-repeat-findings.md))

From the second review against the playbook (plays 04, 07 and 09).

- The test-edit guard covers a `bug` task claimed on the board, not only `fix/` branches: a claim records the task's type in its worktree's `.asdlc-task`, and the guard refuses changes to tests that exist on the default branch there. It finds the repository from the path written to (the file's folder, or a command's `-C`, `--in` and absolute paths), since board workers stay in the tasks clone; before, it judged the tasks clone's branch and never fired on board work. It also sees `git -C <folder> checkout` and the like as writes, reads `--git-dir`, `--work-tree`, attached `-C`, relative folders and `~` paths, and judges `cp` and `install` by their destination only, so copying an existing test to start a new one is allowed.
- `asdlc review-done` reports `repeats`: for each policy the verdict cites, the other tasks whose last review cited it too. The reviewer reads them and, when a finding is the same mistake, files one draft `rule-change` task naming the rule file and the line to add; the orchestrator tells the engineer, who adds the line through a pull request to the tasks repository and archives the draft, or archives it.
- The team testing skill puts a reproducing test in a new file, since the guard keeps existing tests fixed while a bug is fixed.

### Background agents without prompts or `cd` ([plan](plan/worker-permissions.md))

The first real eval run found 14 tool errors in 63 calls, nearly all from background workers refused a prompt nobody could answer.

- `asdlc record-check <id> --in <worktree> ...`: the check runs in the worktree named, from anywhere, so no worker has to `cd` (Claude Code always asks before a line that changes directory and runs git). Every `asdlc` command takes `--in <folder>`, before or after the subcommand.
- `asdlc permissions` allows the read-only git workers and reviewers reach for, in task worktrees and the registered clone: `ls-files`, `grep`, `blame`, `cat-file`, `ls-tree`, `merge-base`, `rev-list`, `describe`, `show-ref` and `remote get-url`, each also bare.
- Claims and review claims carry `github`, the origin's `owner/name` when `gh` is installed and the origin is on GitHub, so agents open or comment on pull requests with `gh --repo` without probing for `gh`.
- The board guard refuses git that runs a program the command doesn't name or sets configuration: global `-c`, `--config-env`, `--exec-path=`; `git config` writes; `grep -O`; `--upload-pack`, `--receive-pack`, `--exec` (and `-u` on clone and ls-remote); `--ext-diff`, `--textconv`; clone's `-c`/`--config` and clone or init `--template`; `rebase -x`; `difftool`, `mergetool`, `submodule foreach`, `bisect run`, `filter-branch`, `instaweb`; and `GIT_*` variables set in front of git, through `env` or with `export`. Attached and clustered short forms are parsed (`-ccore.x=y`, `-nO`, `-uevil`, `-ix`).
- `asdlc permissions` also writes `deny` rules for the same git forms (deny beats allow), since the `*` in the `git -C <worktree>/* ...` allow rules would otherwise let them through; `asdlc doctor` warns when they're missing.
- `asdlc permissions --write` makes each worktree folder it adds to `additionalDirectories`, since a session leaves out one that doesn't exist when it starts, and the first claim makes it later.
- `asdlc-plugin status`, `scaffold`, `verify-command` and `--repo` take a registered slug as well as a path, and refuse an unknown one naming the registered slugs.
- The worker and reviewer agents and the orchestrate, lead and onboard-repo skills say where each command runs: from the tasks clone, `--in`, `git -C`, `git -C <worktree> ls-files` and `git grep`, the Read tool, never `cd`, never an interpreter in a pipe. The tests walk every command they give and fail on any `cd`, or any part no allow rule covers.

### Evals

- `scripts/eval validate`, `run` and `report`: real Claude Code agents run headless against throwaway fixtures, with person steps between resumed sessions, graded afterwards by deterministic checks outside the agent's reach; reference and null runs for every case; trials, pass@k, pass^k, clustered standard errors and the smallest detectable change; tokens, turns, tool calls and cost at versioned API prices.
- The first suite in `evals/`: six regression and three capability cases, each citing its source.
- `.devcontainer/`: the eval image (Claude Code 2.1.309, uv with Python 3.15, Backlog.md 1.55.2, git, bubblewrap and socat), also the repository's dev container.
- `./scripts/check` runs `scripts/eval validate`.

### Stage metrics

- `asdlc stats` reports the playbook's numbers by stage (plan, design, build, test, deploy, maintain) and for coordination, each beside the playbook's name for it; `--stage <name>` for one stage, stage keys in `--json`, `--since` as before. A number that can't be computed says what it needs; change failure rate, CI-versus-production regressions, DORA and pipeline triage are listed as needing deployment and incident data. The parsed board history is cached by commit in the tasks clone's ignored `.asdlc/stats/`, and merge times come from `gh pr view --json mergedAt` when it can say.
- `asdlc review-done` requires `--findings important=<n>,nit=<n>` and `--plan-matched yes|no`, and takes `--policy <name>` for each policy or rule a finding cites; it refuses counts that don't fit the verdict and records them on the task.
- `asdlc intent-started <draft> [--at <time>]` records when the conversation behind an intent began; the `capture-intent` skill runs it.
- The worker agent signs its commits with an `Asdlc-Worker: <worker>` trailer, and `record-check` on a task sent back by a review notes how many commits since the review carry it.
- `docs/guide.md` gains "What the numbers mean": each number, its source, and the clock-skew caveat.

## 0.1.0 - 2026-10-22

The team pilot: several engineers, each with one orchestrator session and its workers, sharing one board. [docs/guide.md](docs/guide.md) is the page for a developer joining it.

### The shared board (#16)

- `scripts/asdlc`: a Backlog.md board in its own repository, every change committed and pushed straight to its `main` with git hooks off, retried when someone pushed first.
- Atomic claims: a claim is a pushed commit, so of two agents claiming one task exactly one wins and the other is told.
- A worktree per claimed task, beside the code repository, on a branch named from the task.
- Routing in one table: intents, spikes and parents get opus/high, `size-1` haiku with numbered steps, `size-2` to `size-5` sonnet/medium; `size-8` is refused until split.
- The board guard: no hand edits of `backlog/`, no To Do or Done, no promotion, no task created without `--draft`, no code edited outside a claimed worktree, no push to a code repository's default branch.

### The tasks repository as a marketplace (#17)

- `asdlc init-board` makes the tasks repository a Claude Code plugin marketplace with a `team` plugin (testing skill and rules, the lead's contract), `asdlc.toml` and `devs/`.
- The `load_rules` hook delivers the team's rules and each code repository's own rules, scoped by path and layer, once per session and subagent, capped at 10,000 characters.
- `docs/repo-plugins.md`: the format of a per-repository plugin.

### Orchestration (#18)

- Engineers (`git config asdlc.engineer`), workers (`kyle.w1`) and reservations in the assignee list.
- `asdlc next` ranks work reserved for you, then your preferred repositories, then priority, spreads workers over equal work, and stops at your `workers` cap.
- `whoami`, `register`, `repos`, `lead`, `lead-of`, `heartbeat`, `reap`, `accept`, `mine` and `record-check`.
- One lead per large piece of work, claimed like a task; the `orchestrate` and `lead` skills and the `worker` agent.
- `asdlc accept` promotes an intent and its draft children together; the guard refuses it from agents.

### Onboarding a repository (#19)

- `scripts/asdlc-plugin`: `status`, `scaffold`, `verify-command`, `check` and `publish` a repository's plugin, in a worktree of the tasks repository so claims keep working.
- Commands are dated `verified` only by running them on a clean checkout of the default branch.
- The `onboard-repo` skill reads the repository and writes its commands, layers and rules.

### Cross-machine review (#20)

- `asdlc review-next` and `review-done`: any other engineer's orchestrator claims a finished task's review atomically; changes go back to the worker that built it, a clean review waits for a person to merge.
- The author's own machine may review it after `review_fallback_after`, marked as a same-machine review.
- The `reviewer` agent: read-only, from a fresh context, comments on the pull request and never approves.

### Pilot readiness (this release)

- One board lookup order everywhere: `--board`, then `ASDLC_BOARD`, then `git config asdlc.board`.
- The guard refuses agents approving, requesting changes on or merging a pull request, through `gh pr` or `gh api`.
- The orchestrator decides onboarding with `asdlc-plugin status --json`; reviewers review in a worktree of the registered repository, so its rules reach them.
- `init-board` writes the `changes-requested` and `review-passed` labels.
- `asdlc doctor`: is this machine ready, with what to do about each problem.
- `asdlc stats`: claims, review times, round trips, same-machine reviews, lost races, onboardings and skipped plan approvals, from the board's history and a per-machine event log of claim attempts.
- `docs/guide.md` for developers joining the pilot.
- This repository's own loop is lighter: each change carries a plan, approved in the session before building, in the same pull request.

### Fixes from the independent review (this release)

An independent review of the combined pilot ran each claim below as an experiment; each fix has a regression test that reproduces it.

- A worker's state changes go through commands that check it still holds the task: `asdlc finish <id> --as <worker> [--pr <url>] --notes ...` hands a task to review (and back, after changes), and `asdlc record-check <id> --as <worker> -- <command>` runs only in the task's worktree and records the worktree, branch and commit. The guard refuses agents setting In Progress or In Review, changing assignees, archiving or demoting tasks, or touching the review labels through `asdlc board` or `backlog`, so a reaped worker can't finish a task someone else now holds.
- A claim records the task's branch (`asdlc_branch`); every later claim resumes it, from `origin/<branch>` once it was pushed. A reaped task that a review sent back stays reserved for its author's engineer. Workers never force-push, and the guard refuses force pushes to code repositories.
- An interrupted asdlc command drops its unpushed board change (at once on Ctrl-C or SIGTERM, on the next command after a kill) and never pushes it later; commits asdlc didn't make are refused, not pushed. Every board commit asdlc makes carries an `Asdlc-Transaction` trailer. The lock wait is 45 seconds.
- `asdlc approve <id>...`, a person's command the guard refuses from agents, records plan approval; `record-check` and `finish` refuse size 2 and up without it.
- `asdlc accept` promotes the whole draft subtree, at any depth, comments the old and new ids on the intent and marks each task with `asdlc_accepted_from`; heartbeats, releases and `lead-of` find a task by its old draft id, and `lead` refuses an old draft id unless `--new`.
- A claim is its first heartbeat; heartbeat on a task that left In Progress is a quiet no-op. The orchestrator heartbeats what its agents are working on at the top of every round, never from a detached loop, and adopts its engineer's claims on start.
- With `review: true`, `asdlc next` leaves a slot for a waiting review, and the orchestrator reviews before it picks; `mine` reports the reviews waiting.
- Reviewers judge a team's code by the team's policy, `plugins/team/review.md` in the tasks repository (plus a repository plugin's own `review.md`), named in the review claim's `policies`; never by asdlc's own `REVIEW.md`.
- No permission prompts in normal work: `asdlc permissions` prints narrow Claude Code allow rules for this machine (asdlc's commands by name, path and `uv run --script`, backlog's reads, the git subcommands agents run in worktrees, `gh pr create`/`view`/`comment`, each registered repository's simple verified commands, edits in the worktree folders), and `asdlc permissions --write`, a person's command, merges them into the tasks clone's own untracked `.claude/settings.local.json`, never user settings, after a backup and atomically. `asdlc doctor` warns when they are missing. The guard only denies or allows, never asks.
- asdlc works through the `backlog` CLI only: `asdlc doctor` warns when Backlog.md's MCP server is configured, and the guide says not to add it.
- The guard reads `~`, `git -C`, loops and conditionals, `bash -lc` and `xargs`; a claim under a name already holding the task is refused; `init-board` ignores `.asdlc/` in the tasks repository.
- Re-run `asdlc init-board` on an existing tasks repository to add `plugins/team/review.md` and the `.gitignore` line. It never overwrites, so a board made earlier keeps its old `plugins/team/skills/testing/SKILL.md`, whose evidence step now uses `asdlc record-check`: update it by hand.

### Second review round (this release)

- The guard applies its status, label and assignee rules only to `task edit`, `task create`, `draft create` and `draft edit`; listings, views and searches that filter by them are allowed. A test walks every command the skills, agents and guide give through the guard.
- `lead-of` names the nearest intent up a task's parents, so a grandchild finds its lead; `accept` on an accepted intent also promotes drafts under its accepted children.
- An approval records the plan's digest and the task's size; `record-check` and `finish` refuse once either changed, `approve` shows the plan, takes `--plan-hash` for the plan the person was shown, and refuses a task no worker holds; the guard refuses agents resizing accepted work.
- A claim whose plan waits for approval is kept for `approval_wait` (default 24h, in `asdlc.toml`); a sent-back task's reservation for its author expires after one more `stale_after`.
- Recovering from an interrupted command restores only `backlog/` and names other dirty files; only trailer-marked commits that touch nothing outside `backlog/` count as asdlc's own, and a person's commit on top of an interrupted change is kept, with how to keep it.
- The guard reads attached short flags (`-a@kyle.w2`, `-lreview-passed`).
- `doctor` flags a tasks repository without `plugins/team/review.md`, and `review-next` refuses to claim a review there; re-run `asdlc init-board` to add it.

### Third review round (this release)

- Re-running `asdlc init-board` on a shared board pushes the missing scaffolding through the board's own transaction, never leaving a local commit; the refusal for commits asdlc didn't make says to `git pull --rebase` before pushing.
- `asdlc permissions` adds bare forms of each worktree git subcommand and allows `mv`, `rm`, `restore`, `stash` and `reset` in task worktrees; the reviewer posts with `gh pr comment` only.
- The guide says what runs without prompts, that Claude Code starts in the tasks clone, and to watch the first worker on day one.
