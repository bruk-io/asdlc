---
name: onboard-repo
description: Onboard a code repository by generating its plugin in the tasks repository - verified build, test and lint commands, a layer map read from the code, one rule per layer, and a testing rule for its language - then checking and publishing it. Load it when a task's repository has no plugins/<slug>/ in the tasks repository, when asked to onboard a repository or to fix or extend its plugin, and before writing any of its commands, layers or rules by hand. Without it, agents write down commands they never ran, invent layers the code doesn't have, restate the team's testing policy instead of the repository's own techniques, and push a plugin that misleads every later worker.
argument-hint: <code repository path> [task id]
---

# Onboard a repository

The plugin you make here is read by every agent that later works in this repository: its rules arrive whenever they touch a matching file, and its commands are how they prove their work. A wrong layer map or a command nobody ran misleads all of them, so put down only what the code and the toolchain show you, and keep the plugin small.

The caller gives the code repository's path (`<repo>` below) and usually the task that needed it (`<task>`). `asdlc-plugin` is `${CLAUDE_PLUGIN_ROOT}/scripts/asdlc-plugin`; run it as that path. It does everything deterministic. You supply the judgement.

## 1. Open the plugin

1. `asdlc-plugin status <repo> --json`. If `published` is true and you weren't asked to change the plugin, stop: there is nothing to onboard.
2. `asdlc-plugin scaffold <repo>`. It prints the plugin's folder, in a worktree of the tasks repository (`<tasks>.worktrees/plugin-<slug>/plugins/<slug>/`). Edit files there and nowhere else: never in the tasks clone itself, which other agents on this machine are using.

## 2. Find and prove the commands

1. Read how the repository is built and checked, most trusted first: its CI configuration (`.github/workflows/`, `.gitlab-ci.yml`, `Jenkinsfile`, `bitrise.yml`, `fastlane/`), then its manifests and task runners (`package.json` scripts, `pyproject.toml`, `Makefile`, `build.gradle*`, `Package.swift`, `Cargo.toml`, `justfile`), then `README` and `CONTRIBUTING`. Prefer exactly what CI runs.
2. Write each into `commands.toml`: `run` (one shell command; join steps with `&&`), `cwd` if it runs from a subfolder, `needs` for anything the machine must have first, in words. `build`, `test` and `lint` are required; add `typecheck`, `format` or `e2e` only when the repository has them.
3. Prove each one: `asdlc-plugin verify-command <repo> <name>`, build first, since later commands may rely on what it installs. Only this writes `verified`; never type a date yourself. It runs on a clean checkout of `origin`'s default branch, making one beside `<repo>` when the clone itself isn't.
4. When a command fails, read the output tail it prints and fix the command (a missing install step, the wrong folder, a tool CI installs first), then run it again. Never weaken it to pass: no `|| true`, no skipped tests, no narrower paths than CI checks. A command that needs something this machine can't have (a device, a cloud account) gets `needs` and stays unverified, and only an optional one can: the check refuses an unverified `build`, `test` or `lint`. If one of those can't pass on a clean checkout, or the repository has no linter at all, stop and put that on `<task>` for the engineer; don't invent a substitute.

## 3. Map the layers

1. Read the source tree and its framework's conventions: where the views or screens are, view models or controllers, the domain or core, networking, persistence, analytics, generated code, as this repository actually has them. Imports tell you which way dependencies run.
2. Write `layers.toml`: one `[layers.<name>]` per part an agent must tell apart, usually three to seven, named the way this repository names them. `paths` are globs relative to the repository's root, narrow layers first (the first match wins). Give each a one-sentence `summary`, and `depends_on` only where the imports show it.
3. Leave out what the code doesn't show. An empty folder, a convention you expect but can't find, or a layer you would like the repository to have is not a layer.

## 4. Write the rules

1. One rule per layer, `rules/<layer>.md`, shaped like the example in `${CLAUDE_PLUGIN_ROOT}/docs/repo-plugins.md` (the check holds you to it). Its few lines are what an agent must know when it changes code there, each with its reason, taken from the code: where state comes from, what the layer must not import, the pattern its files follow and one file that shows it. One topic per rule: testing belongs in the testing rule. Name the lint that already enforces something rather than restating it, and anything a lint could enforce but doesn't is a follow-up on `<task>`, not a rule line.
2. A testing rule, `rules/testing-<language>.md`, one per language the tests are written in. Start from the team's principles in the tasks worktree (`plugins/team/skills/testing/SKILL.md`, `plugins/team/rules/testing.md`, and `rules/testing-<language>.md` there when it exists) and read the repository's own tests: framework, layout, shared helpers and fakes, fixtures, how one test or one file is run. Write only what is specific to this repository: its techniques, its helpers by name, and how to narrow the `test` command to a change. Scope `paths` to its test files. Don't repeat the team's rules; they arrive alongside.
3. A skill (`skills/<name>/SKILL.md`) only for a real multi-step procedure this repository needs that its own docs or scripts show, such as adding a migration or regenerating an API client. Most repositories need none. A rule that relies on it names it as `<slug>:<name>` and gives its path, `{plugin_root}/skills/<name>/SKILL.md`.
4. A short `README.md`: what the repository is, its layers in one line each, and the commit you onboarded it from.

## 5. Use the authoring kit when the session has it

When the `authoring-kit` skills are in this session:

- Load `authoring-kit:choosing-extension-types` before deciding whether something is a rule, a skill or a check. Something a program could check belongs in the repository's lint or CI: record it on `<task>` as a follow-up, since this plugin carries no hooks (`authoring-kit:authoring-hooks` helps you say what that check would be).
- Load `authoring-kit:authoring-rules` before writing the rules, and `authoring-kit:authoring-skills` before writing a skill.
- When the files are written, run the `authoring-kit:authoring-auditor` agent on the plugin's folder in the worktree, fix what it reports that is wrong for this repository, and note on `<task>` anything you chose not to change and why.

When it isn't, say so on `<task>` ("authoring kit not available; checked with asdlc-plugin check only") and go on.

## 6. Check and publish

1. `asdlc-plugin check <slug> --repo <repo>`. Each finding says what to fix; fix the plugin, not the check, and run it again until it is clean. `--repo` makes it compare every layer and rule with the files the repository has.
2. `asdlc-plugin publish <slug> --repo <repo>`. It runs the check again, commits the plugin and its marketplace entry to the tasks repository's `main`, and removes the worktree. If it says someone else published this plugin meanwhile, compare the two, merge by hand in the worktree, and publish again.

## 7. Record it on the task

`publish` ends by printing a record of what it published: the commit, each command with its `verified` date, the layers, the rules and the skills. Append that record to `<task>` as it is, then add what only you know: why any command is unverified, whether the authoring kit was used and what its audit changed, the follow-ups for the repository's lint, and anything left for the engineer.

```sh
asdlc board task edit <task> --append-notes "<publish's record, then your additions>"
```
