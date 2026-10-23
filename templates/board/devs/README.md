# Developer preferences

Each engineer on the team has one file here, `devs/<name>.yaml`, where `<name>` is their
handle without the `@` (an engineer is `@<name>`, their workers `@<name>.<label>`). It says
which work they'd like their agents to pick up. `asdlc next` reads it to rank work, after
work reserved for them and before priority.

Only preferences belong here. Facts about one machine, such as which code repositories
are cloned where, are never in this file: they are registered on that machine.

## The format

A strict, flat subset of YAML, so it can be read without a YAML library. Anything outside
it is refused with a message naming the line.

- One `key: value` per line, at the start of the line. `#` starts a comment.
- A value is a word, a quoted string, `true` or `false`, a whole number, or a list in
  brackets: `[acme-web, acme-api]`.
- No nesting, no multi-line values, no anchors.

| Key | Value | Default | Meaning |
|---|---|---|---|
| `name` | the handle | required | Must match the file name. |
| `prefer` | list of repository slugs, best first | `[]` | Rank work in these repositories first, in this order. |
| `avoid` | list of repository slugs | `[]` | Never pick up work in these repositories unless it is reserved for you. |
| `workers` | whole number | `3` | The most workers your orchestrator runs at once. |
| `review` | `true` or `false` | `true` | Whether your orchestrator claims other engineers' reviews. |

A repository slug is `owner-repo` from the code repository's `origin`, lowercase, with
anything other than letters and digits turned into hyphens: `git@github.com:Acme/Web-App.git`
is `acme-web-app`.

`example.yaml` shows every key. It is not a person: copy it to `<your name>.yaml`.
