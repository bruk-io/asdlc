# Evals for an agentic SDLC plugin that builds itself

Part of [the spec](agentic-sdlc-plugin.md). Every stage has evals, each one is a trace check, a task eval or an outcome metric, and each says how it is measured.

## Kinds of measurement

| Kind | What it is | Data it reads | Cost | When it runs |
| --- | --- | --- | --- | --- |
| Trace check | A script over what already happened | Committed artefacts and their git history, commits, CI runs, the hook decision log, the session index | Free | Every merge, and backfilled over existing history for a baseline |
| Task eval | A frozen past task replayed with a plugin version, then scored | A past task at its parent commit, its acceptance criteria, its proof commands | Tokens per run | On every change to the plugin, on a model change, and in ablations |
| Outcome metric | A playbook indicator tracked over time with bands | The trace checks, rolled up weekly | Free | Weekly; a breach writes an intent |

Task evals are scored by deterministic checks wherever possible: the repository's own check tiers, the task's proof commands, the artefact checks. A model judge is the last resort, and each one is calibrated against human labels before it gates anything.

## Stand-ins

When nobody else is at a gate, its stand-in runs and is shown there (spec R6).

| Gate | Owner in the playbook | Stand-in |
| --- | --- | --- |
| Intent accepted | Product owner | Correction rate, tracked over time |
| Spec approved | Product owner, policy owners | Requirement coverage; decision reversals |
| Plan approved | Engineer, tech lead if high risk | Cold implementation from the plan alone |
| Change approved | Code owner | Reviewer recall and false refusals on seeded defects |
| Release | Release manager | Release smoke test and human device checks |
| Incident triaged | On-call, service owner | Detector backtest on past incidents |

## Plan: is the intent what the requester meant?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Correction rate | How much of the draft was rewritten? | Lines changed in the intent between its first commit and the commit that accepted it | Trace | Falling against the baseline |
| Intent shape | Is every part there and checkable? | A check at acceptance: every template section present, every outcome phrased so a check or a reviewer can judge it | Trace | Zero findings |
| Survival rate | Was the work worth writing down? | Intents accepted versus closed without acceptance | Outcome | Watch only; a sudden drop means intents are being captured too eagerly |
| Outcomes changed | Did the intent hold once work began? | Share of intents whose acceptance criteria were edited after acceptance, from git history | Outcome | Falling |
| Intent replay | Does the current plugin draft what was accepted? | Replay the original request from the session transcript; compare the new draft with the accepted intent, outcome by outcome, using a calibrated judge | Task | No worse than the previous version |
| Should-not-capture | Does it stay out of small work? | Requests that took a handful of tool calls must not produce an intent | Task (two-sided) | Zero intents |
| Time to intent | How long from asking to a committed intent? | First session message to the intent's first commit | Outcome | Watch only |

## Design: did the spec and decisions hold?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Requirement coverage | Does every requirement reach a plan? | A script matching each numbered requirement in the spec to the plans that cite it | Trace | Zero uncited requirements |
| Spec rework | Did requirements change after build began? | Spec commits dated after the first plan for the same intent was accepted | Trace | Falling |
| Decision reversal | Did a decision survive contact with the build? | Recorded decisions superseded or rewritten within 30 days of acceptance, from git history | Trace | Watch; each reversal is read by hand |
| Open questions settled | Did the spec answer or carry forward each question? | A script over the intent's open questions: each answered in the spec or carried forward with a reason | Trace | All settled |
| Spec replay | Does the plugin produce the spec that was approved? | Replay an accepted intent; judge the new spec's requirements against the approved one with a calibrated rubric | Task | No worse than the previous version |
| Spec threshold | Does it skip the spec when it should? | Small intents confined to one area must not get a spec | Task (two-sided) | Zero unneeded specs |

## Build: does the plan carry the work?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Plan drift | Did the change land where the plan said? | Overlap between the files the plan named and the files its commits touched (Jaccard) | Trace | Most changes near 1; low ones read by hand |
| Cold implementation | Could someone who never saw the conversation implement it? | Replay: a fresh session gets only the plan at its parent commit; score its proof commands and criteria | Task | No worse than the previous version |
| First-pass acceptance | Was the first implementation accepted? | Changes accepted at their first review, from review records | Outcome | Rising against the baseline |
| Boundaries | Did agents stay inside their declared scope? | Import-boundary and write-guard findings on agent commits | Trace | Zero |
| Delegation fit | Was work delegated only when it was big enough? | Subagents spawned per change against its size, from the session index | Trace | No subagents on small changes unless the plan said so |
| Worktree freshness | Did a worker commit from a stale base? | Commits whose worktree branched before a fix that main already had | Trace | Zero |
| Collision | Did two sessions take the same work? | The same task started or closed by two sessions, from git history and `Claude-Session` trailers | Trace | Zero |

## Test: is the feedback loop honest?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Claim honesty | Do the notes say what the tools said? | Every "passes" claim in a change's notes matched to a recorded check run with exit code 0 | Trace | Zero unbacked claims |
| First-pass CI | Does agent work pass CI first time? | First CI run per agent-authored push, from the CI API | Outcome | Rising against the baseline |
| Repro first | Was every bug reproduced before it was fixed? | Bug fixes with a committed failing test that predates the fix, or a recorded reason there is none | Trace | All bug fixes |
| Test strength | Would the tests catch a real regression? | Mutation score (a mutation tool for the language, such as StrykerJS or mutmut) on the files a change touched, before and after | Trace | Not lower than before the change |
| Weakening attempts | How often does the agent try to loosen a check? | Guard denials for test deletion or check loosening, from the hook log | Trace | Watch; each one read by hand |
| Count-preserving swaps | Were tests replaced just to keep the count? | Deleted test plus added test in one commit, with the mutation score flat or down | Trace | Each one needs a person's sign-off |
| Over-verification | Is the model re-running checks it already passed? | Check runs per change beyond the declared check tiers, from the session index | Trace | Falling |

## Deploy: does the reviewer catch what matters?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Reviewer recall | Does it refuse a change with a real defect? | Take accepted past changes, plant a known defect in the diff (a mutation, a missed criterion, an edited reproduction test), run the reviewer | Task | Most seeded defects refused |
| Reviewer false refusals | Does it accept a clean change? | The same changes unmodified | Task (two-sided) | Few clean changes refused |
| Escapes | Did an accepted change let a bug through? | Bug reports traced back to an earlier accepted change | Outcome | Falling |
| Broken main | Did a merge break main? | Main's CI red after a merge, including conflict markers | Trace | Zero |
| Release smoke | Does the release install and run? | The release workflow's smoke test | Trace | Every release |
| Human check age | How long do human-only checks wait? | Age of open work waiting on a human-only check, such as one on a device | Outcome | Watch; this is a human queue |

The recall and false-refusal pair keeps the reviewer from drifting toward refusing everything or accepting everything.

## Maintain: does a problem become an intent?

| Eval | Question it answers | How it's measured | Kind | Bar |
| --- | --- | --- | --- | --- |
| Detector backtest | Would the bands have caught past problems? | Replay the weekly metrics over past history; check they breach for known incidents, such as a conflict marker reaching main, a task closed twice, or a hook prompting too often | Task | Every known incident caught |
| Detector precision | Are breaches worth an intent? | Breaches dismissed versus accepted | Outcome | Dismissals tune the bands |
| Breach to intent | How fast does a breach become an intent? | Detection log timestamp to the intent's first commit | Outcome | Within a day |
| Repeat incidents | Does a class of problem come back? | Incidents labelled by class; recurrences after a fix and its eval landed | Outcome | Zero repeats for classes with an eval |
| Incident to eval | Does every incident leave a guard behind? | Incidents closed without a matching eval case | Trace | Zero |

Bands start wide: one metric, a rolling baseline, and a breach writing a draft intent rather than acting.

## The self-building gate

A case is one closed task, frozen as its parent commit, the task as accepted, its acceptance criteria and proof commands, and the stage it exercises. The suite grows to 20 to 50 cases across the six stages, plus a should-stay-quiet case for each skill and hook.

A run:

1. Check out the case's parent commit in a fresh worktree.
2. Install the plugin version under test there.
3. Run the stage the case exercises, headless, with the task as the only input.
4. Score with the repository's checks first, then the artefact checks, then a calibrated judge only where nothing deterministic exists.
5. Record the score, tokens, wall time, prompts shown, and which skills and hooks fired.

Each case runs three times per version so the gate can tell a real change from noise; a drop larger than the run-to-run spread blocks the merge. Whether three is enough is measured on the first suite.

About a quarter of the cases sit in a private holdout set that only CI reads (spec R30). The gate needs both the public suite and the holdout to hold, and a widening gap between their scores is itself a signal that the plugin is fitting its public cases.

## Build order

1. Trace checks over existing history, for baselines.
2. The hook decision log and the session index.
3. One task eval, end to end, before any harness library.
4. The reviewer pair: seeded defects and their clean twins.
5. Grow to 20 to 50 cases across the six stages.
6. The gate on plugin changes: `scripts/eval gate` run by a person on a machine first, with hooks that check for its evidence; CI runs the same command later.
7. Ablation, starting with the largest components.
8. Bands and detection, once there are weeks of metrics.
