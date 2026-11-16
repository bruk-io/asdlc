"""asdlc: intents, specs, plans and tasks as files in git, each accepted by merging it.

Three layers, and only `cli` knows all of them:

- `domain` decides. It takes data and returns data, and imports nothing else here.
- `io` reads files, git and stdin. It decides nothing.
- `presentation` turns what the domain returned into text for a person or a hook.
"""
