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

Workers and reviewers run as background subagents of your orchestrator, and nobody is there to answer a permission prompt: a command that prompts stalls the worker or is refused. Normal work should never prompt. `asdlc permissions` prints the Claude Code allow rules it needs on this machine:

- `asdlc` and `asdlc-plugin`, every subcommand (the board guard still refuses what is a person's, such as `asdlc accept`);
- `backlog`'s read commands (`task list`, `task view`, `draft list`, `draft view`, `doc list`, `doc view`, `search`), since every change to the board goes through `asdlc board`;
- `git`, all of it: workers run `git -C <worktree> ...`, which no narrower rule matches, and the board guard refuses pushes to a default branch and force pushes whatever this allows;
- `gh pr create`, `gh pr view` and `gh pr comment`, for pull requests and review comments;
- `uv run`, which runs the plugin's scripts when they aren't on your `PATH`;
- each registered repository's verified commands from its plugin's `commands.toml` (each part of a command joined with `&&` gets a rule of its own, since Claude Code matches the parts separately);
- edits in the worktree folders beside each registered clone and beside your tasks clone, and those folders as `additionalDirectories`, so agents can read and edit there.

Add them to your user settings, `~/.claude/settings.json`, in your own terminal:

```sh
asdlc permissions --write
```

It keeps everything already in the file, adds only what is missing, and backs the file up first (`settings.json.<time>.bak`). Run it again after you register a repository or a repository's plugin changes its commands; `asdlc doctor` warns, naming the missing rules, whenever it is due. The board's guard only ever refuses or allows, never asks, so it adds no prompts of its own. The rule syntax is Claude Code's: <https://code.claude.com/docs/en/permissions>.

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
2. **Approve plans of size 2 and up.** Your orchestrator shows you the plans; you approve them in your own terminal: `asdlc approve <task id>...`. It records your approval on the task, and until it is there a worker can't record a check or finish the task: `asdlc record-check` and `asdlc finish` refuse. A `size-1` task is small and mechanical, so its plan skips approval; the orchestrator notes why on the task, and the reviewer checks that it really was small.
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

If nobody works on it for `stale_after` and its claim is reaped, it goes back to To Do still reserved for you, and the next claim resumes its branch from what was pushed, never from the default branch. Workers never force-push; the guard refuses it.

### Reviewing others' work

With `review: true`, your orchestrator also claims reviews of other engineers' finished tasks when a slot is free, longest-waiting first. Its reviewer works from a fresh context, in a worktree of your registered clone, and posts its findings on the task and as a comment on the pull request. It never approves. If nobody else reviews a task within `review_fallback_after` (thirty minutes by default), its author's own machine may review it with a fresh reviewer, and the task says it was a same-machine review.

### Seeing how it's going

- `asdlc mine --as <you>`: your workers' tasks, reviews, leads and reserved work.
- `asdlc stats [--since 2026-11-01]`: tasks claimed, in review and done; how long work takes from claim to review and from review to Done; how long reviews wait; round trips; the share of same-machine reviews; lost races; onboardings; and size-1 tasks that skipped plan approval.

### When an asdlc command is interrupted

Ctrl-C, closing the terminal or killing an agent mid-command is safe. A change that hadn't been pushed is dropped, at once or by the next asdlc command on that clone ("dropping 1 unpushed board change(s) an interrupted asdlc command left"); it was never pushed, so nobody saw it, and it is never pushed later. If you commit to your clone of the tasks repository by hand and don't push, asdlc stops and says so rather than push or drop your commit: push it or remove it.

### Known limits

- In a registered clone, every Claude Code session with the asdlc plugin is guarded: it can't edit code outside a claimed task's worktree, and there is no switch to turn that off for one session. To work on a registered clone with Claude outside the board, unset its board for that while (`git -C ~/src/api config --unset asdlc.board`) and run `asdlc register` there again afterwards.
- The `asdlc` and `asdlc-plugin` on your `PATH` come from your clone of the plugin's repository, and the skills and agents from the installed plugin. If the two are at different releases, a skill can ask for a command the script doesn't have, or the reverse. Keep the clone at the plugin's release (`git -C ~/src/asdlc pull` when the plugin updates); `asdlc doctor` doesn't compare them yet.
- The guard parses shell commands, so it is a guardrail, not a wall: a determined script can get past it. When it can't tell what a command does (a `cd` to a variable, say), it allows it and says so.

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
