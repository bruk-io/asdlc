# Contract: <the feature>

- Intent: <TASK-n, the intent this delivers>
- Owner: <@name, the orchestrator who wrote it>
- Version: 1, <YYYY-MM-DD>. Only its owner changes this document; see "Changes".

<Two or three sentences: what the feature does for whom, and which repositories take part.>

## Behaviour and states

<What a user or caller sees, as states and the events that move between them. Every client implements the same states with the same names.>

| State | Shown or returned | Entered when | Leaves when |
|---|---|---|---|
| <idle> | <what the user sees, or what the API returns> | <event> | <event> -> <next state> |

Edge cases every implementation handles the same way:

- <Offline, empty, error, permission denied, slow response: what happens in each.>

## API

<Each operation between repositories. Name the owning repository; give the shape exactly enough that two teams could build against it without talking.>

### <operation name>

- Owner: <repo-slug>
- Kind: <GraphQL query or mutation, REST endpoint, event, SDK function>
- Request: <fields, types, which are required>
- Response: <fields, types, nullability>
- Errors: <each error, its code, and what the caller does about it>
- Compatibility: <additive only, versioned, or behind a flag; how old clients behave>

## Analytics events

<Every event any platform sends for this feature. The name and properties are identical on every platform listed.>

| Event | Properties | Trigger | Platforms |
|---|---|---|---|
| <feature_action_done> | <`property`: type, meaning> | <the exact user action or state change that sends it, once> | <iOS, Android, Web, backend> |

## Traces and logs

<What an on-call engineer needs to follow one request through every repository.>

| Signal | Name | Attributes | Emitted by | When |
|---|---|---|---|---|
| Span | <feature.operation> | <attributes, including the ids that join repositories> | <repo-slug> | <start and end> |
| Log | <event name> | <fields; no personal data> | <repo-slug> | <the condition> |

## Who builds what

<Every part of this contract has exactly one child task. A part with no task, or two, is a gap to fix before plans are approved.>

| Part | Child task | Repository | Depends on |
|---|---|---|---|
| <API: operation name> | <TASK-n.m> | <repo-slug> | <TASK-n.k, or nothing> |
| <Analytics: event names> | <TASK-n.m> | <repo-slug> | <TASK-n.k> |

## Open questions

- [ ] <A question the contract can't settle yet, who answers it, and which parts wait on it.>

## Changes

<Newest first. A worker who needs a change asks on its task; the owner decides, edits this document, bumps the version, and notes each affected task.>

- v1, <YYYY-MM-DD>: first version.
