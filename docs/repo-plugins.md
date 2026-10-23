# Per-repository plugins

Code repositories carry no agent setup. What an agent needs to know about one repository lives in the tasks repository, as a plugin of its own beside the team plugin, made the first time work needs it. This file defines that plugin, so the onboarding step can generate it and the asdlc hooks and commands can read it.

## Where it lives

```
<tasks repository>/
  .claude-plugin/marketplace.json     lists `team` and every repository plugin
  plugins/
    team/                             the team's own skills and rules
    <repo-slug>/
      .claude-plugin/plugin.json
      layers.toml                     optional
      commands.toml
      rules/*.md                      optional
      skills/<name>/SKILL.md          optional
      review.md                       optional: review rules of this repository's own, added to the team's
      README.md                       optional: what this plugin knows about the repository
```

`review.md`, when there is one, adds to the team's review policy (`plugins/team/review.md`): `asdlc review-next` names both in its `policies`, the team's first, and the reviewer applies both. It never loosens the team's.

`<repo-slug>` is `owner-repo` from the code repository's `origin` remote, lowercase, with anything other than letters and digits turned into hyphens: `git@github.com:Acme/Web-App.git` and `https://github.com/acme/web-app` are both `acme-web-app`. The host and any group above the owner are dropped, so two repositories whose last two path parts are the same share a slug; rename one plugin by hand if that ever happens. `scripts/repo_slug.py` (`repo_slug(url)`, `slug_of(repo_path)`) is the one implementation; everything in asdlc that names a repository uses it. The same slug is the Backlog `project` of every task in that repository.

## `.claude-plugin/plugin.json`

```json
{
  "name": "acme-web-app",
  "version": "0.1.0",
  "description": "Conventions, layers and verified commands for acme/web-app.",
  "author": { "name": "The team" }
}
```

`name` is the slug. The marketplace lists it beside `team`:

```json
{ "name": "acme-web-app", "source": "./plugins/acme-web-app", "description": "Conventions, layers and verified commands for acme/web-app." }
```

`claude plugin validate plugins/<repo-slug>` and `claude plugin validate .` (from the tasks repository) must pass.

## `layers.toml`

The repository's layers, as path globs relative to its root. When the rule loader injects one of this repository's rules, it names the layer of the file being worked on.

```toml
# Layers of acme/web-app. The first layer whose globs match a file is its layer.
[layers.ui]
paths = ["src/components/**", "src/screens/**"]
summary = "React components and screens. No data fetching; props in, events out."

[layers.application]
paths = ["src/features/**"]
summary = "Feature state and use cases. Calls ports, never adapters."
depends_on = ["core"]

[layers.core]
paths = ["src/core/**"]
summary = "Pure domain types and logic. No I/O, no framework imports."
```

- Each `[layers.<name>]` needs `paths`, a non-empty list of globs. Tables are tried in file order and the first match wins, so put narrow layers before broad ones.
- `summary` and `depends_on` are for people and for the onboarding and lead agents; the rule loader reads only the name and `paths`.
- A file no layer matches has no layer, and a rule injected for it says nothing about layers.
- A `layers.toml` the loader can't read is reported once per context as a system message, and the rules are delivered without a layer.

## `rules/*.md`

Rules hold the few lines that must be in front of an agent whenever it works on certain files of this repository. The rule loader delivers them; Claude Code does not load a plugin's rules itself.

```markdown
---
layer: core
paths:
  - "src/core/**"
---
# The core layer

Applies to code in src/core.

- No imports from src/features or src/components: the core is used by both. The import check (`pnpm lint`) enforces it.
- Domain errors are values of `DomainError`, never thrown strings.
- How to add a domain type end to end: the `acme-web-app:domain-types` skill, also at {plugin_root}/skills/domain-types/SKILL.md.
```

- Frontmatter `paths` is a list of globs relative to the code repository's root: one `- "glob"` per line, or a flow list `["a", "b"]`. `**/` is any number of folders (none included), `**` anything, `*` anything within one folder, `?` one character, `{a,b}` either; a glob ending in `/` is everything under that folder. No `paths` means every file in the repository. An empty `paths` list is refused, since it would never apply.
- A layer's rule says so with `layer: <name>` and uses that layer's globs from `layers.toml`. Each layer has one; the loader names a file's layer only when it delivers one of the repository's rules, so a layer with no rule is never mentioned. Other rules, such as the testing rule, have no `layer`.
- Start the body with one line saying when it applies, then a few lines of judgement, each with its reason. Name the skill that holds any procedure.
- `{plugin_root}` in the body becomes this plugin's folder in the reader's clone of the tasks repository, so a rule can point at a skill or template beside it even on a machine where the plugin isn't installed.
- Each rule is delivered whole the first time it matches in a context (a session, or one subagent), and again after compaction. All rules delivered at once share a 10,000-character cap, so keep each well under it; anything cut says where the full rule is.
- One topic per rule. Something a program could check belongs in the repository's lint or a check, not in a rule.

Team rules (`plugins/team/rules/`) use the same format and apply in every repository. Put a convention in the repository's plugin when it depends on that repository's layout, framework or language. Testing techniques for languages the team plugin has no rule for (Swift, Kotlin, TypeScript) are drafted here, from the tests the repository already has, as rules such as `rules/testing-swift.md`.

## `skills/`

Ordinary Claude Code skills: `skills/<name>/SKILL.md`, with a `description` that says what it does, when to load it, and what goes wrong without it. Claude Code loads them, named `<repo-slug>:<name>`, on machines where the plugin is installed (`/plugin install <repo-slug> --marketplace <owner>/<tasks repo>`). A rule that relies on a skill names it and gives its `{plugin_root}` path too, for machines where it isn't.

## `commands.toml`

The repository's build, test and lint commands, each one run and seen to work when it was written down. Workers run them to verify their changes, reviewers run the full set, and the team's testing skill points here.

```toml
# Verified commands for acme/web-app. Each runs from the repository's root unless `cwd` says otherwise.

[build]
run = "pnpm install --frozen-lockfile && pnpm build"
verified = 2026-10-22

[test]
run = "pnpm test"
verified = 2026-10-22

[lint]
run = "pnpm lint"
verified = 2026-10-22

[typecheck]
run = "pnpm typecheck"
verified = 2026-10-22

[e2e]
run = "pnpm test:e2e"
needs = ["a running Android emulator"]
```

- `build`, `test` and `lint` are required tables. Others (`typecheck`, `format`, `e2e`, ...) are optional, named for what they check.
- `run`: one shell command that exits non-zero on failure. If a check takes several commands, join them so it is still one.
- `verified`: the date the command was last run on a clean checkout of the default branch and passed. Only `asdlc-plugin verify-command` writes it, by running the command. A table with no `verified` was written down but never seen to pass; an agent using it says so in its evidence. Every table is verified except one with `needs`, which can't run on every machine.
- `cwd` (optional): a folder relative to the repository's root to run it from.
- `needs` (optional): what must be on the machine first, in words: a tool, an emulator, a service.
- `test` is the full suite. A worker narrows it to what the change touches the way the repository's test runner allows, and records the exact command it ran.
- Never weaken a verified command to make it pass. A command that stops working is a finding on a task, and its `verified` date stays as it was until someone fixes it and runs it again.

## Making one

The first time work needs a repository that has no plugin, the orchestrator runs the asdlc `onboard-repo` skill. The judgement is the skill's; `scripts/asdlc-plugin` does the rest:

- `asdlc-plugin status <code-repo> [--json]`: the slug, and whether `plugins/<slug>/` is published or being made.
- `asdlc-plugin scaffold <code-repo>`: opens a detached worktree of the tasks repository at `<tasks clone>.worktrees/plugin-<slug>`, from `origin/main`, and writes the skeleton and the marketplace entry there, never overwriting a file. The tasks clone itself is never edited, so `asdlc` keeps working while a plugin is made. Run on a published plugin, it opens that plugin for changes.
- `asdlc-plugin verify-command <code-repo> <build|test|lint|...>`: runs one command in a checkout with no uncommitted changes whose `HEAD` is `origin`'s default branch, and on success writes today's date to its `verified`. That is the clone itself when it is one; otherwise a detached worktree beside it, `<code-repo>.worktrees/asdlc-verify`, reset to `origin`'s default branch on every run and kept so that what `build` installs is there for `test`. The clone is never touched. A command that fails, or changes tracked files, leaves `commands.toml` as it was.
- `asdlc-plugin check <slug> [--repo <code-repo>]`: every rule on this page, plus `claude plugin validate` on the plugin and the marketplace when the CLI is installed. With `--repo`, each layer and rule must match files the repository has, and each layer must own at least one of them.
- `asdlc-plugin publish <slug> [--repo <code-repo>]`: refuses unless `check` is clean, then commits the plugin's folder and its marketplace entry on top of `origin/main` with every git hook off, pushes, and retries when someone pushed first. It refuses if someone else published the same plugin meanwhile. Then it updates the tasks clone, removes the worktree, and prints a record of what it published for the task's notes.
