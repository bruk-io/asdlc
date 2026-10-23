# Joining the pilot

This page is for a developer joining the asdlc pilot. You talk to one Claude Code session, your orchestrator. It picks work from the team's board, runs workers that plan and build each task in a worktree of its own, and reviews other engineers' finished work. You make four decisions it never makes for you (below). The board, a Backlog.md board in the team's tasks repository, is the only thing the orchestrators share.

Setting up takes about twenty minutes. `asdlc doctor` tells you when you're done.

## Install

1. **uv.** The plugin's hooks and scripts are Python 3.15 scripts run through uv, which fetches 3.15 the first time: <https://docs.astral.sh/uv/>.
2. **Backlog.md 1.55.2.** `npm i -g backlog.md@1.55.2`. Older versions drop asdlc's own keys from tasks when they edit them, so asdlc refuses anything before 1.55.1.
3. **gh, signed in for git too.** Install the GitHub CLI, then `gh auth login` and `gh auth setup-git`. Workers open pull requests with it, reviewers comment on them, and `setup-git` stores a credential git uses without asking, which background plugin updates need.
4. **The asdlc plugin.** In Claude Code: `/plugin install asdlc --marketplace bruk-io/asdlc`. It brings the skills, the worker and reviewer agents, the board guard and the rule loader.
5. **The `asdlc` and `asdlc-plugin` commands.** Clone the plugin's repository and link its two scripts onto your `PATH`:

   ```sh
   git clone https://github.com/bruk-io/asdlc ~/src/asdlc
   ln -s ~/src/asdlc/scripts/asdlc ~/.local/bin/asdlc
   ln -s ~/src/asdlc/scripts/asdlc-plugin ~/.local/bin/asdlc-plugin
   ```

   Keep the clone at the release the plugin is on (`git -C ~/src/asdlc pull` when the plugin updates).
6. **The tasks repository's marketplace.** The tasks repository is also a plugin marketplace holding the team's skills and rules, and one plugin per code repository. Ask the pilot's owner for its `owner/repo`, then in Claude Code:

   ```
   /plugin install team --marketplace <owner>/<tasks repo>
   ```

7. **Auto-update for it.** It is off by default for a marketplace you add yourself, so new repository plugins would reach you only when you update by hand. In Claude Code: `/plugin`, then Marketplaces, choose the tasks repository's marketplace, then Enable auto-update. The update runs in the background and never prompts, so it relies on the credential from step 3.
8. **The authoring kit, if the owner shares it.** Onboarding a new repository uses `authoring-kit` to choose between a rule, a skill and a check and to audit what it writes. Without it, onboarding still works and says so on the task.

## Set up

1. Tell asdlc who you are, once per machine. Use your handle without the `@`:

   ```sh
   git config --global asdlc.engineer kyle
   ```

   Don't set `asdlc.board` globally: every repository on the machine would then be guarded.
2. Clone the tasks repository, for example to `~/src/tasks`.
3. Add your preferences to it: copy `devs/example.yaml` to `devs/<your name>.yaml`, set `name`, the repositories you `prefer` and `avoid`, how many `workers` may run at once, and whether you `review` other engineers' work (`true` unless you have a reason). The format is in `devs/README.md`. Commit and push it:

   ```sh
   git -C ~/src/tasks add devs/kyle.yaml
   git -C ~/src/tasks commit -m "Add kyle's preferences"
   git -C ~/src/tasks push
   ```

4. In each code repository you work in, register your clone with the board:

   ```sh
   cd ~/src/api && asdlc register --board ~/src/tasks
   ```

   It records the clone on this machine only and sets `asdlc.board` in that repository. Work is offered to you only in repositories registered here.
5. Let background workers run without asking you: `asdlc permissions --write` (next section).
6. Run `asdlc doctor`. Every line says pass, warn or FAIL, and each warning or failure says what to do. Fix the failures and run it again until it exits cleanly. Warnings are worth reading: a missing `gh` means your workers can't open pull requests, and missing permissions mean a worker will stop at a prompt nobody answers.

## Permissions

Workers and reviewers run as background subagents of your orchestrator, and nobody is there to answer a permission prompt: a command that prompts stalls the worker or is refused. The aim is that background workers and reviewers run without prompts; your orchestrator's own foreground work may still ask now and then (onboarding a new repository, for example, may ask for a few reads in your registered clone), and you answer those. `asdlc permissions` prints the Claude Code allow rules for that on this machine, as narrow as the work allows:

- `asdlc` and `asdlc-plugin` by name, by the plugin's absolute path, and through `uv run --script <plugin>/scripts/asdlc` (the board guard still refuses what is a person's, such as `asdlc accept`);
- `backlog`'s read commands only (`task list`, `task view`, `draft list`, `draft view`, `doc list`, `doc view`, `search`), since every change to the board goes through `asdlc board`;
- the git subcommands agents run in a task's or a review's worktree, written as `git -C <clone>.worktrees/* <subcommand> *` (fetch, status, diff, log, show, add, commit, push, rebase, merge, switch, `checkout -b`, rev-parse, branch, symbolic-ref, mv, rm, restore, stash and reset; each also without arguments), the few a reviewer runs in your registered clone (fetch, worktree, show, rev-parse, symbolic-ref), and in both the read-only ones agents use to find their way around (ls-files, grep, blame, cat-file, ls-tree, merge-base, rev-list, describe, show-ref, `remote get-url`). Agents never `cd`: Claude Code asks you before any line that changes directory and runs git, whatever the rules say, so the agents use `git -C`, `asdlc record-check --in <worktree>` and the file tools instead. The board guard refuses pushes to a default branch and force pushes whatever these allow;
- `gh pr create`, `gh pr view` and `gh pr comment`;
- each registered repository's verified commands from its plugin's `commands.toml`, as exact rules. A command with a `*`, a pipe, `;`, `&&`, `||`, a backtick, `$(` or a redirect gets no rule, since a rule can't say what it would allow; the output lists them and why. Agents run those through `asdlc record-check`, which `asdlc *` covers;
- edits in the worktree folders beside each registered clone and beside your tasks clone, and those folders as `additionalDirectories`. `--write` makes any that don't exist yet: a session leaves out a folder missing when it starts, and the first claim in a repository makes its folder later.

Write them, in your own terminal, from your clone of the tasks repository:

```sh
asdlc permissions --write
```

They go into that clone's own `.claude/settings.local.json`, which applies only to sessions started in the tasks clone, so always start Claude Code there for your orchestrator; the workers and reviewers it launches run under the same settings. Nothing is added to your user settings, so no other project gets them. On your first day, watch the first worker your orchestrator launches until it has recorded a check and pushed: if it stops at a prompt, note the command, tell the pilot's owner, and approve it. The file stays untracked (asdlc adds it to the clone's `.git/info/exclude`), so Claude Code applies it as your own without a trust prompt. The command keeps everything already in the file, adds only what is missing, backs the file up first (`settings.local.json.<time>.bak`), and writes it atomically. Run it again after you register a repository or a repository's plugin changes its commands; `asdlc doctor` warns, naming the missing rules, whenever it is due. Claude Code may warn at startup about the `git -C <folder>/* ...` rules, since their wildcard comes before the subcommand; they still apply. The board's guard only ever refuses or allows, never asks, so it adds no prompts of its own. The rule syntax is Claude Code's: <https://code.claude.com/docs/en/permissions>.

asdlc works through the `backlog` CLI only. Don't add Backlog.md's MCP server: it writes the board's files without committing or pushing them and bypasses the board's rules, the guard's included. `asdlc doctor` warns when one is configured.

## A day with it

Open Claude Code in your clone of the tasks repository and ask it to orchestrate: "work the board", "pick up work", or "keep going on the team's tasks". It loads the `orchestrate` skill and, each round:

- releases claims nobody has touched for `stale_after` (two hours by default), on anyone's machine;
- claims work for its workers: reserved for you first, then your preferred repositories, then priority;
- takes the lead on a large piece of work if nobody has, and otherwise follows the lead's spec and contracts on the board;
- onboards a repository the first time work needs it, so its rules reach every worker;
- launches a worker per task, which writes its plan first;
- heartbeats what its agents are working on at the top of every round, and sees each task through to In Review with a pull request;
- reviews other engineers' finished work before it starts new work of its own, so reviews never wait on a full queue.

It brings you every plan that needs approval in one batch, with the one command that approves them. You approve in your own terminal, `asdlc approve TASK-7 TASK-9`; for a plan you reject, tell it what to change and it puts that on the task and has the worker plan again.

If you close the session, or start a new one, it picks up from the board: `asdlc mine` lists what your workers still hold, and it asks you whether to resume or release each.

### Your four stops

Agents can't do these; the board guard refuses them, with the reason.

1. **Accept work.** A lead writes an intent and its child tasks as drafts. When you agree with them, accept them all in your own terminal: `asdlc accept <intent id>`.
2. **Approve plans of size 2 and up.** Your orchestrator shows you the plans, each with its digest, and gives you the command: `asdlc approve TASK-7 TASK-9 --plan-hash <digest of 7> --plan-hash <digest of 9>`. It shows each plan again as it approves it, refuses one that changed since you were shown it, and records your approval with the plan's digest and the task's size. Until then a worker can't record a check or finish the task, and if the plan or the size changes after you approve, they refuse again until you approve the new one. A claim waiting for your approval is kept for `approval_wait` (a day by default) rather than reaped at `stale_after`. A `size-1` task is small and mechanical, so its plan skips approval; the orchestrator notes why on the task, and the reviewer checks that it really was small.
3. **Merge the pull request.** When a review has passed (the task is labelled `review-passed`), read the review on the pull request and merge it yourself. Agents never approve, request changes on, or merge a pull request.
4. **Mark it Done.** After the merge, in your own terminal: `asdlc board task edit <id> -s Done`.

### When a claim is refused

The message always says why, and your orchestrator usually moves on by itself:

- "Another agent claimed it first": two machines raced and the other won. It picks the next task.
- Reserved for someone else, in a repository not registered here, waiting on another task, or too big (`size-8` must be split first): it isn't yours to start yet. If it should be, register the repository (`asdlc register`) or ask the lead to split the task.
- At your `workers` cap: it waits for a worker or reviewer to finish.
- Keeping a slot for a review: with `review: true`, `asdlc next` won't take your last free slot while another engineer's work waits for your review. Your orchestrator reviews it first.
- "Already claimed by @kyle.w1: another session may be using that name": two of your sessions are using the same worker names. Give each its own.

Each attempt goes in this machine's log, `~/.local/state/asdlc/events.jsonl`, which `asdlc stats` counts.

### When a review asks for changes

Another engineer's reviewer judged your task and found something Important. The task goes back In Progress, still assigned to the worker that built it, labelled `changes-requested`, with the findings in its comments and on the pull request. Your orchestrator hands it back to that same worker name, which may already be building something else: a worker name can hold a sent-back task alongside new work, and picks its own task up again. You only hear about it when the findings question the plan or the contract rather than the code.

If nobody works on it for `stale_after` and its claim is reaped, it goes back to To Do still reserved for you for one more `stale_after`, then open to anyone, and the next claim resumes its branch from what was pushed, never from the default branch. Workers never force-push; the guard refuses it.

### Reviewing others' work

With `review: true`, your orchestrator also claims reviews of other engineers' finished tasks when a slot is free, longest-waiting first. Its reviewer works from a fresh context, in a worktree of your registered clone, and posts its findings on the task and as a comment on the pull request. It never approves. If nobody else reviews a task within `review_fallback_after` (thirty minutes by default), its author's own machine may review it with a fresh reviewer, and the task says it was a same-machine review.

### Seeing how it's going

- `asdlc mine --as <you>`: your workers' tasks, reviews, leads and reserved work.
- `asdlc stats [--since 2026-11-01] [--stage plan|design|build|test|deploy|maintain|coordination]`: the playbook's numbers by stage, each beside the playbook's own name for it, and the ones the board can't measure, with what they need. "What the numbers mean", below, defines each one.

### When an asdlc command is interrupted

Ctrl-C, closing the terminal or killing an agent mid-command is safe. A change that hadn't been pushed is dropped, at once or by the next asdlc command on that clone ("dropping 1 unpushed board change(s) an interrupted asdlc command left"); it was never pushed, so nobody saw it, and it is never pushed later. Only `backlog/` is restored: an uncommitted edit of yours elsewhere in the clone is left alone, and asdlc names it and waits for you to commit or undo it. If you commit to your clone of the tasks repository by hand and don't push, asdlc stops and says so rather than push or drop your commit, and tells you how to keep it when an interrupted change sits under it.

### Known limits

- In a registered clone, every Claude Code session with the asdlc plugin is guarded: it can't edit code outside a claimed task's worktree, and there is no switch to turn that off for one session. To work on a registered clone with Claude outside the board, unset its board for that while (`git -C ~/src/api config --unset asdlc.board`) and run `asdlc register` there again afterwards.
- The `asdlc` and `asdlc-plugin` on your `PATH` come from your clone of the plugin's repository, and the skills and agents from the installed plugin. If the two are at different releases, a skill can ask for a command the script doesn't have, or the reverse. Keep the clone at the plugin's release (`git -C ~/src/asdlc pull` when the plugin updates); `asdlc doctor` doesn't compare them yet.
- The guard parses shell commands, so it is a guardrail, not a wall: a determined script can get past it. When it can't tell what a command does (a `cd` to a variable, say), it allows it and says so.

## What the numbers mean

`asdlc stats` reads the board's history (every commit on the tasks repository's `main`), the tasks' own notes and comments, this machine's event log, the hook decision logs on this machine and, for merge times, `gh` when it is installed and signed in. It changes nothing on the board. It caches the history it has parsed, by commit, in your tasks clone's `.asdlc/stats/` (ignored by git), so later runs read only new commits. `--since <date>` counts what happened from then on; each number says what its moment is (a claim, a verdict, a Done commit). `--json` gives the same numbers under `stages.<stage>.metrics`, each with `play`, `playbook` (the playbook's name for it), `source` and, for one that can't be computed, `measured: false` and `needs`.

**Commit times come from different machines.** A board commit is stamped by the clock of the machine that made it, and a span that starts on one machine and ends on another (In Review on ann's, the review claim on kyle's) is off by however far apart their clocks are. Keep machines on network time; read a span of a few minutes with that in mind. Where an order matters more than a length (the spec came before or after a plan, a bug was filed after a task was Done), stats uses the order of commits, which every machine agrees on. Times inside notes (when a check ran) and the intent's start come from the machine that wrote them.

### Plan (plays 01 and 10)

- **Conversation to committed intent** (play 01, leading): from when the conversation began, which the `capture-intent` skill records with `asdlc intent-started`, to the commit that created the intent's draft. Intents with no start recorded are listed; they predate this, or the session didn't note the time.
- **Survival rate** (play 01, lagging): intent drafts accepted, out of those accepted, archived or deleted. A draft still open isn't counted.
- **Post-spec churn** (play 01): commits that change an intent's title, description or acceptance criteria after the first commit of a spec document linked on it (`--add-doc`, a document of type `specification` or titled "Spec"). Comments, statuses, leads and ticked boxes don't count.
- **Draft to accept wait** (play 10): the intent draft's first commit to the commit that accepted it, a person's gate.

### Design (play 02)

- **Intent to spec**: the intent's first commit, or its acceptance when it was accepted before the spec, to the first commit of its spec document.
- **Spec rework**: commits to the spec documents after the first plan was written on any task under the intent.

### Build (plays 03 and 06)

- **Claim to In Review**: a task's first claim to its first move to In Review.
- **Merged from the first pass** (play 03): tasks Done whose first review verdict was clean, out of the Done tasks that were reviewed.
- **Approval to merge**: the last plan approval to the pull request's merge time from `gh pr view --json mergedAt` when gh can say, else the task's Done commit; the line says how many came from each.
- **Rework cycles**: changes-requested verdicts per reviewed task.
- **Diff still matches the plan**: the reviews that recorded `--plan-matched yes`, out of those that recorded it either way.
- **Plan written to approved**: the first commit with a plan on the task to its first `asdlc approve`, a person's gate.
- **Small tasks that skipped approval**: claimed `size-1` tasks with no approval, out of every claimed task, naming any whose notes don't say why.
- **Concurrent claims per engineer** (play 06): over the time each engineer's workers held at least one task In Progress, the most they held at once and the time-weighted median.
- **Done per engineer per week** (play 06): tasks Done, by the engineer whose workers built them and by ISO week, beside that engineer's rework rate (changes-requested verdicts per reviewed task of theirs).

### Test (plays 07 and 08)

- **First-pass check success** (play 07): of each task's first `record-check` after a change (a check on a later commit than the worker's baseline, or with uncommitted changes), the share that passed. The baseline, which the worker records before changing anything, is counted apart: a red baseline means the task started from a broken branch.
- **Checks per task** and **failed checks**: the `record-check` notes on each task, and how many exited non-zero.
- **Eval pass rate** (play 08): not measured until there is an eval suite whose results are recorded per change.

### Deploy (plays 05, 09 and 10)

- **Time to first review**: each move to In Review to the next review claim. Tasks waiting now, with nobody reviewing them, are named.
- **Review duration**: a review claim to its verdict.
- **Changes fixed by the worker alone**: of the rounds where a review asked for changes and the task came back, the share where every commit since the review carries the `Asdlc-Worker` trailer the worker agent signs with (`record-check` notes it on a sent-back task; merges don't count). A commit without it is a person's.
- **Defects caught before merge**: Important findings per reviewed task, from `review-done --findings important=<n>,nit=<n>`.
- **Findings citing a policy** (play 05, lagging): per policy or rule named with `review-done --policy`, how many reviews cited it, by ISO week. As agents learn a policy, its line should fall.
- **Defects escaped**: bug tasks whose `--ref` names a task that was Done when the bug was filed, by the week it was filed.
- **Same-machine reviews**: review claims taken by the author's own machine after the fallback, out of all review claims.
- **In Review to Done**: a task's first move to In Review to its Done commit.
- **Gate waits** (play 10): accept (draft to accept), approval (plan written to approved) and merge (a clean verdict to the merge, from gh when it can say, else the Done commit): the time work waits for a person.
- **Guard refusals by rule** (play 10): the board guard's and the test-edit guard's refusals in the hook decision logs on this machine (`.asdlc/hooks.jsonl` in your tasks clone and in each registered repository), counted by the rule that refused.

### Maintain (play 12)

Not measured until play 12, closing the loop on metrics, is built: it needs detection bands over these numbers in versioned config, and each diagnosis written as an intent.

### Coordination

Lost races per claim (this machine's event log), holds reaped by `asdlc reap` by kind (claims, leads, reviews and reservations released), tasks released by hand, and each repository's onboarding with the time from the newest claim in that repository to its plugin's first publish.

### Not measurable from the board

Change failure rate, CI-versus-production regressions, the DORA metrics, and pipeline failures triaged without paging (play 11) need deployment and incident data the board doesn't hold. `asdlc stats` lists them with what each needs.

The event log and the hook decision logs are this machine's: each engineer's `asdlc stats` counts their own races and refusals, and the board's numbers are the same for everyone.

## Running evals

This section is for whoever changes the plugin itself. The eval suite runs real Claude Code agents, headless, against throwaway fixtures (a tasks repository, a code repository, an engineer's machine), and grades what they did with deterministic checks the agent never sees. How to write a case is in [`evals/README.md`](../evals/README.md).

```sh
scripts/eval validate                        # every case's reference and null runs; no model calls
scripts/eval run --case small-request-no-intent --trials 1
scripts/eval run                             # every case, 3 trials each
scripts/eval report                          # the latest run: pass rates, counts, cost, sample transcripts
scripts/eval regrade .eval-results/<run>     # grade a run again after fixing a check; no model calls
```

- **Validate** builds each case's fixture twice: a scripted reference run must pass every check, and a run that does nothing must fail at least one. It is free and deterministic, and `./scripts/check` runs it.
- **Run** builds a fresh fixture for every trial in a temporary folder, runs `claude -p` with the case's prompt, performs the case's person steps between sessions (approving plans, say) and resumes the same session, then grades the outcome. Each case runs `--trials` times (3 by default). Real runs count against your Claude subscription or API key, so start with one case and one trial.
- **The plugin under test** is `--plugin <git ref or folder>`, `origin/main` by default: exported to a temporary folder, read-only, without `evals/`, `tests/` or the evals spec, so the agent can't read its answers and never runs from your working copy (R21).
- **Models** follow each case (`model` in its `case.toml`) and, for workers, `asdlc route`; `--model` overrides the session's model. `--arm without-skills` runs with the plugin's scripts, hooks and commands but no skills or agents, to measure what the skills add; cases that need the plugin's agents are skipped there.
- **Isolation.** Each trial's agent gets a fresh Claude Code configuration folder (no other plugins, no memory), its own home and git identity, the narrow rules `asdlc permissions --write` gives a pilot machine, permission prompts answered "no" (`--permission-prompts none`), no web tools, and a rule denying reads of this repository. Background tasks are off, so workers run in the foreground and the session waits for them.
- **In the container**, `--container` runs each session inside the eval image instead: only the fixture is mounted (read-write) and the release (read-only), Bash runs in Claude Code's sandbox with no network of its own, and the image holds no credentials. Build the image once with `docker build -t asdlc-evals:local .devcontainer`, and pass `CLAUDE_CODE_OAUTH_TOKEN` (from `claude setup-token`) or `ANTHROPIC_API_KEY` in your environment. The same image is the repository's dev container.
- **Results** go to `.eval-results/<time>-<commit>-<arm>/` (ignored by git): per trial, every session's transcript, subagent transcripts, `outcome.json` and `trial.json` with each check's verdict and the counts. `report` gives each case's pass@k, pass^k and mean pass rate, the overall mean with its standard error clustered by case, the smallest change a run of that size can detect, tokens by model, turns, tool calls and errors, cost at API prices from `evals/prices.toml` beside Claude Code's own figure, and the key moments of a few failing and passing transcripts, so you can check the checks.

## Stop and remove it

To stop for the day, tell your orchestrator to stop, or close the session. Claims it held go stale and are released after `stale_after`. To hand them back now, list them with `asdlc mine --as <you>` and release each:

```sh
asdlc release TASK-7 --as kyle.w1
asdlc release TASK-3 --as kyle.lead     # a lead
```

To leave the pilot:

1. Release everything you hold, as above.
2. Remove the worktrees beside your clones once their work is merged: `git -C ~/src/api worktree remove ~/src/api.worktrees/task-7`. `asdlc doctor` lists any left over from onboarding or reviews.
3. In each registered repository: `git -C ~/src/api config --unset asdlc.board`.
4. Remove this machine's records: `rm -r ~/.config/asdlc ~/.local/state/asdlc`.
5. Uninstall the plugins: `claude plugin uninstall team@<tasks marketplace>`, `claude plugin marketplace remove <tasks marketplace>`, and `claude plugin uninstall asdlc@asdlc`.
6. Remove the links (`rm ~/.local/bin/asdlc ~/.local/bin/asdlc-plugin`) and `git config --global --unset asdlc.engineer`.
7. Delete `devs/<you>.yaml` from the tasks repository, commit and push.
