---
name: write-policy-skill
description: Turn one policy that is applied inconsistently - a security standard, an API convention, a brand rule - into a skill in the repository, with its owner, its source, and the hook or check that enforces it if it must always hold. Use when asked to write a skill for a policy or standard, or when review keeps finding the same policy broken.
---

# Write a policy skill

A skill makes a policy likely to be applied while code is written. It is advisory: nothing forces a session to follow it. So a policy that must hold every time needs a hook or a check behind it, and the skill names that backstop.

A skill is for knowledge that must be applied consistently. Day-one context about the repository belongs in `CLAUDE.md`, and a one-off instruction belongs in the prompt.

## Write it

1. Get the policy's owner and its written source. Without an owner, nobody can approve a change to it, so ask before writing.
2. Copy `${CLAUDE_PLUGIN_ROOT}/templates/policy-skill.md` to `.claude/skills/<policy-name>/SKILL.md` and fill it in from the source.
3. Write the `description` in the words a request would use, since the description is what makes the skill load.
4. State each rule so a reviewer could tell whether a change follows it, and say why the policy exists, so it can be applied to cases the rules don't name.
5. Fill in **Enforced by**: the hook or check that holds it every time, or "advisory only". If the policy must always hold and nothing enforces it, say so to the owner; that gap is a piece of work of its own.

## Back it when asked

Build enforcement only when the engineer asks for the policy to be backed or made unskippable, and a check script for it already exists. Then do both of these, with the same script the skill names, so the rule is stated in one place:

1. A `PostToolUse` hook for `Edit|Write` in `.claude/settings.json`, running a small script under `.claude/hooks/` that runs the check script on the file that changed and, on failure, exits 2 with a message naming the rule. A hook cannot undo the edit, so the message is what lets Claude fix it.
2. A pull request workflow in `.github/workflows/` that runs the same script, to be marked a required check. The hook does not fire when a shell command rewrites a file; the pull request check catches that.

A preference is advisory only: say so in **Enforced by** and stop; build nothing. When the engineer asked for nothing beyond the skill and a check already runs, name that check and build nothing. When a policy must always hold and no check script exists, write "advisory only" and tell the owner nothing enforces it yet; do not write the script unasked.

## Check that it triggers

Ask for the task the policy covers in several different ways, in fresh sessions, and confirm the skill loads each time. A skill that doesn't trigger does nothing, however well it is written.

## Review

The policy owner approves the skill, and later changes to it, in a pull request like any other change.
