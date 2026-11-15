# The GitHub channel

A running orchestrator session finds out what happened on GitHub only when someone tells it or it happens to look. The GitHub channel tells it: a pull request was opened, merged or closed, a review or a comment landed, a head commit's checks finished. It serves [`intent/hear-github-events.md`](../intent/hear-github-events.md).

It is a [Claude Code channel](https://code.claude.com/docs/en/channels-reference): an MCP server, `scripts/github_channel.py`, that Claude Code starts with the session and that pushes events into it. Channels are a research preview, so this one has to be started with a development flag, in an interactive terminal, every time. Nothing changes for an engineer who does not turn it on.

## What it does

While it is on, it asks GitHub once a minute what changed in each repository `asdlc register` recorded on this machine, through your own `gh` login. It needs no webhook, nothing reachable from the internet, and stores no credential. Each fact becomes one event in the session:

| `event` | What happened | `state` |
|---|---|---|
| `pr_opened` | A pull request was opened | - |
| `pr_merged` | A pull request was merged, and by whom | - |
| `pr_closed` | A pull request was closed without merging, and by whom | - |
| `pr_reopened` | A closed pull request was reopened | - |
| `review` | A review was submitted | `approved`, `changes_requested` or `commented` |
| `comment` | A comment was left on a pull request | - |
| `checks` | Every check run on a pull request's head commit finished | `passed` or `failed` |
| `skipped` | More happened than is listed (see "Nothing lost") | - |
| `listener` | The listener says whether it is running | `listening`, `not_listening` or `failing` |

Everyone's actions are reported, yours included: your own merge from a phone is exactly what the session has to hear. Pushes and commits to the default branch are never asked about, so board commits make no noise.

## Turn it on

Once on a machine, tell Claude Code where the server is. Use the path of your clone of this repository:

```sh
claude mcp add --scope user asdlc-github -- uv run --quiet --script ~/src/asdlc/scripts/github_channel.py
```

Then start each orchestrator session with the switch and the flag:

```sh
ASDLC_GITHUB_CHANNEL=1 claude --dangerously-load-development-channels server:asdlc-github
```

Both parts are needed, and each does a different job:

- `--dangerously-load-development-channels server:asdlc-github` makes Claude Code register the server as a channel. Claude Code shows a full-screen warning listing the channel; choose "I am using this for local development". The flag is ignored without an interactive terminal (`claude -p`, the Agent SDK), so the channel cannot be turned on there.
- `ASDLC_GITHUB_CHANNEL=1` makes the server ask GitHub at all. A server added at user scope starts with every Claude Code session on the machine; without the switch it answers the handshake and does nothing else. This matters because Claude Code drops events silently in a session that did not register the channel, and a listener that asked GitHub there would move the cursor past events nobody heard.

Never set the switch without the flag, for the same reason.

On a Team or Enterprise plan an admin has to enable channels (`channelsEnabled`) first; the development flag does not get past that.

## What the session sees

By the channels reference, an event reaches the model as a `<channel>` tag whose attributes are the event's fields, and the terminal shows a one-line summary (`← asdlc-github: ...`):

```text
<channel source="asdlc-github" event="pr_merged" repo="acme/app" pr="7" branch="feat/widget" actor="bruk" url="https://github.com/acme/app/pull/7">
bruk merged pull request #7 "Add the widget" (branch feat/widget) in acme/app into main. https://github.com/acme/app/pull/7
</channel>
```

The attributes are `event`, `repo`, `pr`, `branch`, `actor`, `state`, `head` (the first twelve characters of the head commit, on `checks`) and `url`; one that does not apply is left out.

The server also gives the session standing instructions when it connects: what these events are, that they are facts and never instructions, that a merge does not mark a task Done, and what is useful to do. On a merge the session says which task the branch belongs to and what marking it Done would unblock, then carries on with whatever needs no decision from you. On failed checks or a review that asks for changes it tells the worker that owns the branch.

## Facts only

An event is information, never an instruction, and a comment is text someone else wrote. Anyone who can comment on a pull request could otherwise put words in front of the session, so the listener does not carry words:

- An event's sentence is written by the script from structured fields: who, which pull request, which branch, which state.
- No comment, review, pull request description, commit message or check output is ever read into an event. The session learns that a comment exists, who left it and where.
- The one piece of free text is the pull request's title. It is cut to 80 characters and loses every control and formatting character, newline, angle bracket, quote, backtick and ampersand, so it cannot close the tag, forge one or add a line.
- Logins and branch names keep only letters, digits and `. _ / - [ ]`.
- The URL is built by the script from the repository and the number, never taken from GitHub's answer.
- The channel is one-way. It declares no tools, so the session has nothing to reply with, and it does not declare the permission relay, so it can never approve or deny tool use.

If the session goes on to read a comment itself, it reads it as text about the work; the board guard and the gates that are a person's are unchanged.

## Nothing lost

The listener keeps a cursor for each repository in `~/.local/state/asdlc/github-channel.json` (or under `$XDG_STATE_HOME`), outside every repository, written whole each time.

- The first time it looks at a repository it sets the cursor to now and reports nothing historical.
- After a restart it reports what changed since the cursor: pull requests that changed state, comments and reviews since, checks that finished.
- At most 20 events are reported per repository per look. When there were more, the 20 most recent are reported and one `skipped` event says how many were not.
- An event is reported once. Events go out before the cursor is written, so a crash between the two repeats an event and never loses one.

## Check it is running

- In the session, the first event after start is `asdlc-github is listening to <repositories> and asks GitHub every 60 seconds.` If that line does not appear, the channel is not on.
- Claude Code prints a notice under its startup banner naming `server:asdlc-github` when the channel registered, and `/mcp` shows the server's status.
- When it cannot reach GitHub (no `gh`, not logged in, rate limited, a repository it cannot read) it says so once in the session with a `listener` event whose state is `failing`, keeps trying with a growing wait, and says once when it hears again.
- Outside a session, `claude mcp list` shows whether the server connects, and `scripts/github_channel.py --status` prints whether the switch is on, the repositories, and each cursor. `scripts/github_channel.py --once` asks GitHub once, prints the events it would send as JSON lines and moves the cursor.

Only one listener on a machine asks GitHub at a time. A second session started with the switch says `not_listening`, and takes over if the first ends.

## Turn it off

- For one session: start it without the switch and the flag.
- For good: `claude mcp remove --scope user asdlc-github`. Delete the cursor file if you want the next start to begin from now.

## Settings

| Variable | Default | What it sets |
|---|---|---|
| `ASDLC_GITHUB_CHANNEL` | off | `1` turns the listener on for sessions started from this environment |
| `ASDLC_GITHUB_REPOS` | the repositories `asdlc repos` lists whose origin is on GitHub | `owner/name` entries, separated by commas or spaces |
| `ASDLC_GITHUB_INTERVAL` | `60` | Seconds between looks; never under 15 |
| `ASDLC_GH` | `gh` on `PATH` | The `gh` to run |

Repositories given as arguments after the script's path in `claude mcp add` win over both.

A look at a quiet repository costs two requests plus two for each open pull request, each sent with the ETag of the last answer. An unchanged answer is a 304, which GitHub does not count against the rate limit.

## Limits

- Events arrive only while a session is open, and up to a minute late.
- It hears the 100 most recently updated pull requests and the 100 newest comments per look, and follows reviews and checks on the 30 most recently updated open pull requests.
- Checks are check runs (GitHub Actions and apps that use the Checks API). Commit statuses from older integrations are not read.
- A review with inline comments is one `review` event. Edited or deleted comments, and comments on issues, are not events. Who reopened a pull request is not named.
- Two machines each keep their own cursor, so each hears the same event.
- A `claude -p` process started from the session inherits the switch; it waits behind the session's listener and reports to nobody. If it outlives the session it takes the listener's place until it ends.
- The preview's contract may change. The server answers only the MCP revisions up to 2025-11-25 on purpose: Claude Code does not register a channel server that negotiates revision 2026-07-28.
