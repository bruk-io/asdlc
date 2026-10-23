# Plan: stage metrics

- Spec: [`spec/agentic-sdlc-plugin.md`](../spec/agentic-sdlc-plugin.md), approved 2026-10-20 (#2)
- Status: approved by the owner in the session before building; it ships in the same pull request as the change.
- Delivers: the metrics R19 detects over (its bands and runbooks are play 12, later), R15 (review findings by severity, now counted), R16 and R26 (hook decisions counted by rule)

`asdlc stats` (#22) counted what the pilot needed to start: claims, review waits, round trips, races. This change makes it report the playbook's own numbers, grouped by the playbook's stages, each beside the playbook's name for it, so a team can judge each play by the measure the playbook gives it. Every figure comes from the board's git history, the tasks' notes, the local event log and hook decision logs, and `gh` where it can say. What can't be computed says what it would need, and what the board can never measure (change failure rate, DORA) is listed with the data it needs. Three numbers need data nothing recorded yet, so the change also records it: when an intent's conversation began, a review's findings by severity and the policies they cite with whether the diff matched the plan, and which commits a worker agent made.

## Files that change

| File | New | What it holds | Requirements |
|---|---|---|---|
| `scripts/asdlc` | no | Task keys `asdlc_intent_started`, `asdlc_review_findings`, `asdlc_review_policies`, `asdlc_plan_matched` and `documentation`; `intent-started`; `review-done --findings/--policy/--plan-matched` (`ReviewRecord`, `parse_findings`, `review_record_refusal`); `record-check` notes commits since the review carrying `Asdlc-Worker` (`worker_commits`, `since_review_line`); stats: `parse_checks`, `substance`, `replay` into a `Ledger` of lives, documents and stories, one function per stage (`plan_stage`, `design_stage`, `build_stage`, `test_stage`, `deploy_stage`, `maintain_stage`, `coordination_stage`), `refusal_rule`, `stats_report`, `stats_lines`; the shell reads git, caches parsed commits in `.asdlc/stats/history.json`, asks `gh` for merge times (cached), reads the hook logs; `--stage` | R15, R16, R19, R26 |
| `agents/worker.md` | no | Every commit carries `--trailer "Asdlc-Worker: <worker>"` | R19 |
| `agents/reviewer.md` | no | `--findings`, `--policy` and `--plan-matched` on `review-done`, and what each means | R15, R19 |
| `skills/orchestrate/SKILL.md` | no | The worker's trailer (people leave it off); the reviewer's verdict carries its counts | R19 |
| `skills/capture-intent/SKILL.md` | no | Note the time as the conversation starts; `asdlc intent-started <draft> --at <time>` after creating the draft | R19 |
| `docs/guide.md` | no | "What the numbers mean": each metric, its source, its playbook name, and the clock-skew caveat | R19 |
| `README.md` | no | `stats`, `review-done` and `intent-started` rows; a Metrics row in what version 0 does | - |
| `CHANGELOG.md` | no | Unreleased: stage metrics | - |
| `tests/test_asdlc.py` | no | Check notes read back, the trailer count, findings, replay and each stage on one fixed history, the cache round trip, refusal rules against the guard's own reasons; against real repositories: review-done's record and refusals, the trailer note and stats, intent-started, stats by stage | R15, R16, R19 |
| `tests/test_guard_board.py` | no | The new commands in the skills and agents are among those walked through the guard and the permission rules | R16 |
| `tests/test_demo_review.py`, `tests/test_demo_pilot.py` | no | `review-done` with its record; the pilot story's numbers under their stages | - |
| `tests/test_demo_stats.py` | yes | Two machines, two days, kyle's clock two minutes fast: every stage's numbers asserted and, with `ASDLC_DEMO=1`, printed | R19 |
| `plan/stage-metrics.md` | yes | This plan | - |

## Order of work

1. The recorded data: the Task keys, `intent-started`, `review-done`'s record and its refusals, `record-check`'s trailer count; tests on fixed inputs, then against real repositories.
2. The core: `parse_checks` and `substance` over task text, `replay` over fixed commits, then each stage function on one fixed history whose numbers are worked out by hand in the test.
3. The shell: the history from `git log --name-status` and `git cat-file --batch`, cached by commit; `gh` merge times; hook logs; `--stage`; the existing stats tests moved to the new structure.
4. The skills and agents, with the guard and permission walks still passing and extended to find the new commands.
5. The demonstration, the guide, the README, the changelog; `./scripts/check` and `claude plugin validate .`.

## Risks

- **Clock skew.** A span from a commit on one machine to a commit on another carries their clock difference. Order questions (spec before plan, bug after Done, the commits of a review round) use commit order, never time; the guide says so and the demonstration runs one clock two minutes fast to show it.
- **Stale review keys.** The verdict's counts are frontmatter keys overwritten by each `review-done`. A verdict from an older asdlc that doesn't write them, after a newer one did, would be read with the earlier counts. Every review now requires them; the risk lasts only while machines run mixed releases, which the guide already warns against.
- **Reason text as the rule.** The hook log has no rule field, so `refusal_rule` reads it from the refusal's wording. A test runs every guard refusal constant and backlog refusal through it, so a reworded refusal fails the test rather than counting as "other".
- **Draft ids are reused.** Each draft's life is keyed by its id and a generation, ended by the commit that deletes it: accepted (a task appears with `asdlc_accepted_from` in that commit), archived, or deleted. A test reuses an id.
- **A cache from another release.** The cache key holds a version and Task's field names; any other cache is rebuilt. A cache that can't be written only makes the next run slower.
- **gh.** Called only for Done tasks with a pull request, once each (a known merge time is cached), with a 20-second timeout; any failure falls back to the Done commit and the line says which source each time came from.

## Proof

- `./scripts/check` passes: the stage functions on the fixed history, the commands against real repositories and the backlog CLI, the guard and permission walks.
- `claude plugin validate .` passes.
- `ASDLC_DEMO=1` on `tests/test_demo_stats.py` prints `asdlc stats` after the two-machine story; the pull request quotes it.

## Departures from the brief

- The playbook files couldn't be read in this session (no Projects tool), so each metric's playbook name is the brief's wording for it (for example "Conversation to committed intent (leading)", "Survival rate (lagging)", "Post-spec churn"), or the play and a plain name where the brief gave none.
- `review-done --findings` is required, like `--plan-matched`, and must fit the verdict (changes needs an Important finding, clean has none): an optional count would leave the defect numbers with gaps nobody notices. Older verdicts without it are counted as "without findings recorded".
- First-pass check success counts each task's first check after a change, not its first check: the worker's first `record-check` is the baseline it records before changing anything (worker.md, phase 2), so it measures the branch it started from. The baseline's share is reported beside it.
- The start of an intent's conversation is recorded with `asdlc intent-started <draft> [--at <time>]`, a command of its own, rather than a flag on `asdlc board`, whose arguments all belong to backlog. The skill notes the time with `date -u` when the conversation starts.
- Post-spec churn counts commits that change the intent's title, description or acceptance criteria, not every commit touching its file: comments, lead claims and heartbeats touch it too and aren't churn.
- A spec document is a document linked on the intent with type `specification` or a title starting "Spec", which is what the lead skill writes.
- Worker-only fixes are judged from the last check of each round: `record-check` counts commits since `origin/<branch>` (what the reviewer saw), merges aside, so the worker's check before it pushes the fix covers the round.
- Refusals are counted by a rule name read from the refusal's wording, since the decision log has no rule field; adding one would change every hook's log format.
- Concurrency's median is time-weighted over the time an engineer held at least one claim.
- The cache lives in `.asdlc/stats/` with its own `.gitignore`, so it stays out of git even on a board whose `.gitignore` predates `.asdlc/`.
- Coordination also counts tasks released by hand, beside reaped holds.
