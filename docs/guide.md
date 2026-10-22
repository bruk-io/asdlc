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
5. Run `asdlc doctor`. Every line says pass, warn or FAIL, and each warning or failure says what to do. Fix the failures and run it again until it exits cleanly. Warnings are worth reading: a missing `gh` means your workers can't open pull requests.

## A day with it

Open Claude Code in your clone of the tasks repository and ask it to orchestrate: "work the board", "pick up work", or "keep going on the team's tasks". It loads the `orchestrate` skill and, each round:

- releases claims nobody has touched for `stale_after` (two hours by default), on anyone's machine;
- claims work for its workers: reserved for you first, then your preferred repositories, then priority;
- takes the lead on a large piece of work if nobody has, and otherwise follows the lead's spec and contracts on the board;
- onboards a repository the first time work needs it, so its rules reach every worker;
- launches a worker per task, which writes its plan first;
- keeps every claim alive while its worker runs, and sees each task through to In Review with a pull request.

It brings you every plan that needs approval in one batch. You can approve several at once, or say what to change; it records your answer on the task.

### Your four stops

Agents can't do these; the board guard refuses them, with the reason.

1. **Accept work.** A lead writes an intent and its child tasks as drafts. When you agree with them, accept them all in your own terminal: `asdlc accept <intent id>`.
2. **Approve plans of size 2 and up.** Your orchestrator asks; you answer in the session. A `size-1` task is small and mechanical, so its plan skips approval; the orchestrator notes why on the task, and the reviewer checks that it really was small.
3. **Merge the pull request.** When a review has passed (the task is labelled `review-passed`), read the review on the pull request and merge it yourself. Agents never approve, request changes on, or merge a pull request.
4. **Mark it Done.** After the merge, in your own terminal: `asdlc board task edit <id> -s Done`.

### When a claim is refused

The message always says why, and your orchestrator usually moves on by itself:

- "Another agent claimed it first": two machines raced and the other won. It picks the next task.
- Reserved for someone else, in a repository not registered here, waiting on another task, or too big (`size-8` must be split first): it isn't yours to start yet. If it should be, register the repository (`asdlc register`) or ask the lead to split the task.
- At your `workers` cap: it waits for a worker or reviewer to finish.

Each attempt goes in this machine's log, `~/.local/state/asdlc/events.jsonl`, which `asdlc stats` counts.

### When a review asks for changes

Another engineer's reviewer judged your task and found something Important. The task goes back In Progress, still assigned to the worker that built it, labelled `changes-requested`, with the findings in its comments and on the pull request. Your orchestrator hands it back to that same worker name, which may already be building something else: a worker name can hold a sent-back task alongside new work, and picks its own task up again. You only hear about it when the findings question the plan or the contract rather than the code.

### Reviewing others' work

With `review: true`, your orchestrator also claims reviews of other engineers' finished tasks when a slot is free, longest-waiting first. Its reviewer works from a fresh context, in a worktree of your registered clone, and posts its findings on the task and as a comment on the pull request. It never approves. If nobody else reviews a task within `review_fallback_after` (thirty minutes by default), its author's own machine may review it with a fresh reviewer, and the task says it was a same-machine review.

### Seeing how it's going

- `asdlc mine --as <you>`: your workers' tasks, reviews, leads and reserved work.
- `asdlc stats [--since 2026-11-01]`: tasks claimed, in review and done; how long work takes from claim to review and from review to Done; how long reviews wait; round trips; the share of same-machine reviews; lost races; onboardings; and size-1 tasks that skipped plan approval.

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
