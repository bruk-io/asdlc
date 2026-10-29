# Plan: the policy skill backs a policy when asked, and a no-hooks arm for the comparison

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md)
- Status: draft. Merging this file, after the owner approves it in session, starts the build.
- Delivers: R11 (a policy that must always hold is also enforced by a hook or a check), R25 in part (what a component adds over its absence)

The first comparison of the plugin with the plain agent (`plan/arm-comparison.md`) found two things the owner asked to act on. The policy skill never backs a policy with a hook and a pull request check, so the playbook's play 5 case fails with the plugin and passes a third of the time without it. And the `without-skills` arm keeps the hooks, so it cannot say what the hooks add.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `skills/write-policy-skill/SKILL.md` | no | A step after **Enforced by**: when the engineer asks for the policy to be backed, and a check script already exists, register a `PostToolUse` hook in `.claude/settings.json` that runs that script on the edited file and exits 2 with the rule's name, and add a pull request workflow that runs the same script as a required check. Nothing is built that was not asked for. With no script, the skill still names the gap and does not write one | R11 |
| `templates/policy-skill.md` | no | The **Enforced by** line shows the hook and the check as the two things it names when the policy is backed | R11 |
| `scripts/eval` | no | A third arm, `without-hooks` (`hooks/` removed, so the guards do not run). A case that declares no `arms` keeps its two (`with-plugin`, `without-skills`) and does not pick up the new one by default | R25 |
| `tests/test_eval.py` | no | The new arm exports without `hooks/` and the default arms stay two | R25 |
| `docs/guide.md` | no | The arm in the evals section | - |
| `CHANGELOG.md` | no | Two lines | - |
| `plan/close-the-gaps.md` | yes | This plan | R11, R25 |

## Order of work

1. The skill and template edit. Re-run the four `policy-skill-*` cases against the working copy at 3 trials, `--plugin .`.
2. The arm, its test and the guide line.
3. `./scripts/check`, then one pull request.
4. A later suite-only pull request, once this merges, declares `without-hooks` on the cases that rely on a hook (`agent-cannot-approve`, `fix-cannot-edit-tests`, `approval-before-build`) and records the result. R23 forbids doing it here.

## Risks

- **The skill builds enforcement nobody wanted.** Medium. The wording ties it to the engineer's request. `policy-skill-names-the-real-backstop` (a check exists, nothing asked for it to be unskippable, `invents_no_enforcement`) and `policy-skill-preference-advisory` (nothing built) are the two cases that fail if it overreaches; both are re-run before and after.
- **A hook is a second place the rule lives.** The skill makes the hook run the same script the skill names, so one source states the rule and the hook only calls it.
- **Removing `hooks/` removes the board guard as well as the test-edit guard.** An agent without hooks can approve its own plan. That is the point of the arm, and it only ever runs in a throwaway fixture, but a reader of the results should know the arm removes every guard, not one.
- **Three trials.** A case moving from 0/3 to 3/3 is a signal; 1/3 to 2/3 is not.

## Proof

- The four policy cases, 3 trials, before and after: `policy-skill-backed-by-hook-and-ci` should move from 0/3 up, the other three should not move down.
- `./scripts/check` passes, its output pasted in the pull request.
- No file under `evals/` changes (R23).
