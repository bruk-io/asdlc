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

## Check that it triggers

Ask for the task the policy covers in several different ways, in fresh sessions, and confirm the skill loads each time. A skill that doesn't trigger does nothing, however well it is written.

## Review

The policy owner approves the skill, and later changes to it, in a pull request like any other change.
