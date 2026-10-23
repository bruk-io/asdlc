# The team plugin

The team's own conventions, shared with every engineer's agents. It lives in the tasks repository, which is also a Claude Code plugin marketplace. Install it once, in Claude Code, naming the tasks repository:

```
/plugin install team --marketplace <owner>/<repo>
```

On a Claude Code older than 2.1.275, add the marketplace first (`/plugin marketplace add <owner>/<repo>`), then `/plugin install team@<the name in .claude-plugin/marketplace.json>`.

Changes are pull requests to this folder, like any other change; whoever merges approves them. Run `claude plugin validate plugins/team` before opening one.

## What is here

| Path | What it is |
|---|---|
| `skills/testing/` | How the team chooses, writes and runs tests, verifies work with each repository's own checks, and records the evidence on the task |
| `skills/writing-a-contract/` | How a lead writes and keeps the cross-repository contract for a large feature |
| `review.md` | How a reviewer judges a finished task: the passes, the severities, the nit cap and the size-1 check. A repository plugin's own `review.md` adds to it |
| `templates/contract.md` | The contract a lead copies |
| `rules/testing.md` | The testing rule for any language |
| `rules/testing-python.md` | Python testing techniques |

## Skills and rules

A **skill** holds a procedure or a policy that an agent loads when the task calls for it, from its description. Claude Code loads this plugin's skills natively once the plugin is installed; they are named `team:<skill>`.

A **rule** holds the few lines that must be in front of an agent whenever it works on certain files. Claude Code does not load a plugin's rules, so the asdlc plugin's `load_rules` hook delivers them: when an agent reads or edits a file in a code repository whose board is this tasks repository, the hook injects each rule that matches the file, once per context (the session, and each subagent), and again after the context is compacted. It reads the rules from your local clone of this repository, so pull it to get the latest.

A rule is scoped by `paths` in its frontmatter: a list of globs, relative to the root of the code repository being worked on. `**` matches any number of folders, `*` anything within one folder, `{a,b}` either. A rule with no `paths` applies to every file in every repository.

```markdown
---
paths:
  - "**/*.py"
  - "src/api/**"
---
# Python

Applies to ... (one opening line saying when it applies)

- A few lines of judgement, each with its reason.
- The name of the skill that holds the procedure.
```

`{plugin_root}` in a rule's body becomes this plugin's folder in the reader's clone, so a rule can point at a skill or template beside it.

Keep a rule short: every agent that touches a matching file pays for it, and the hook cuts an injection at 10,000 characters. Put the procedure in a skill and name the skill in the rule. Anything a program could check belongs in a lint rule or a check, with its reason in the message, not in a rule.

## Team rules and repository rules

- **Team rules** are here, in `plugins/team/rules/`, and apply in every code repository.
- **Repository rules** are in that repository's own plugin, `plugins/<repo-slug>/rules/`, beside this one, and apply only there. The per-repository plugin's format, including its layers and verified commands, is `docs/repo-plugins.md` in the asdlc plugin.

A convention that holds everywhere goes here. One that depends on a repository's layout, framework or language goes in that repository's plugin.

## Adding a convention

The team writes its own conventions; nothing here is a default to accept. For example, analytics or observability conventions:

- The naming rules, required properties or span attributes that must be in front of an agent while it writes the code go in a rule, such as `rules/analytics.md`, scoped with `paths` to where events are sent (or with no `paths`, if they're sent from everywhere).
- How to add an event or a span end to end (the registry to update, the dashboard to check, who signs off) goes in a skill, such as `skills/analytics/SKILL.md`, with a description that says when to load it. Use the shape of `skills/testing/SKILL.md`: its owner, its source, and what enforces it.
- The contract template's "Analytics events" and "Traces and logs" sections defer to these conventions once they exist, so a lead's contract follows them.
- Conventions that differ per platform go in each repository's plugin instead.
