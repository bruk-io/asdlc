# Plan: the suite after its first real run

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md); follows `plan/eval-suite.md`
- Status: approved by the owner in session, 2026-10-29 ("go for it")
- Delivers: R22 (cases that measure the agent), R23 (suite changes in their own pull request)

The first real run (20 cases, 3 trials, with the plugin, $6.59) scored 0.27. Reading the transcripts showed 12 cases failing on "no approval surface" denials: the `solo` fixture granted the agent no Bash permissions, and `acceptEdits` refuses writes under `.claude/` when nobody can answer. Those cases measured the missing permission, not the agent.

## Files that change

| File | What changes |
|---|---|
| `evals/fixtures.py` | `solo` writes `.claude/settings.local.json` with the git, test and read-only shell rules a solo engineer would allow, adds the plugin folder, and keeps `.claude/` out of the repository's status |
| `evals/cases/policy-skill-*/case.toml` | `permission_mode = "auto"`, since these cases write under `.claude/` |

## Order of work

1. Give `solo` the permissions and re-run the cases it broke.
2. Run the policy cases in `auto` mode and re-run them.
3. Run `./scripts/check`, open the pull request.

## Proof

- `./scripts/check` passes.
- Re-run on the 12 affected cases, 1 trial each: 7 passed after the fixture fix, two more policy cases after `auto`. The three still failing show agent behaviour (`repeat-mistake-claude-line`, `policy-skill-flags-an-enforcement-gap`, `policy-skill-backed-by-hook-and-ci`) and stay as they are.
- `scripts/protected_paths.py --base origin/main` passes: no plugin file changes here.

## Risks

- `auto` mode lets the agent's own classifier approve writes. Low: the cases run in throwaway fixtures with the network denied.
- Allow rules could hide a real permission problem in the plugin. The plugin-side permission gaps found in this run are fixed in their own pull request, not papered over here.
