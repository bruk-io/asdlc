# Intent: See where my Claude Code sessions' time and tokens go, tied to the work they were for

- Author: bruk.habtu@gmail.com
- Status: draft. Merging this file accepts it.
- Date: 2026-10-20

## Problem

I want to see where my Claude Code sessions' time and tokens go for work in this repository: which skills loaded, which subagents ran, how many tool calls and prompts each session took, and what it cost. Today I can't tie any of that to the intent or plan a session was working on, so I can't see what a piece of work actually cost.

## Proposed outcome

- For each Claude Code session in this repository, I can see which skills loaded, which subagents ran, the number of tool calls, the number of prompts, the time it took, the tokens it used, and what it cost.
- Each session is tied to the intent or plan it was working on, so the figures add up per piece of work.
- For one intent, spec or plan, I can see the total cost of the work done against it.
- A session that was not working on any intent or plan is still shown, as unattributed, rather than dropped.

## Affected users and systems

- Me, as the person who pays for and plans the work in this repository.
- Claude Code sessions run in this repository, including the skills and subagents they use.
- The intent and plan artefacts, which the sessions are tied to.

## Constraints

- Every pull request's description ends with this line: Co-authored with the asdlc plugin, version 0.
- It must not change how a session behaves or slow it noticeably.
- Nothing about a session's content (prompts, file contents) leaves my machine unless I choose to share it.

## Open questions

- [ ] Where do the session figures come from today, and are tokens, time and cost all recorded there?
- [ ] How is a session tied to an intent or plan: by what it was told to work on, by the branch, or by something I record?
- [ ] What counts as a piece of work: one intent, or the intent with its spec, plan and change together?
- [ ] Should sessions started outside this repository, or in other worktrees of it, count?
- [ ] Where should I see the result: in the terminal, on the pull request, or in a file in the repository?
- [ ] Is cost a dollar figure, a token count, or both, and does it need to match what I am billed?
- [ ] How far back should it look, and does it need to cover sessions that already happened?
