# The project's entrypoints. Each recipe calls a script that already exists, so a check is defined once.
# `just` lists them. `just setup` once on a new machine.

set shell := ["bash", "-euo", "pipefail", "-c"]

[private]
default:
    @just --list

# set this machine up: Python 3.15, Backlog.md, and a launcher on your PATH for the installed plugin's asdlc commands. Safe to run again.
setup:
    #!/usr/bin/env bash
    set -euo pipefail
    root="{{justfile_directory()}}"
    ok()   { printf '  ok    %s\n' "$*"; }
    did()  { printf '  done  %s\n' "$*"; }
    warn() { printf '  WARN  %s\n' "$*"; }
    need() { command -v "$1" >/dev/null 2>&1 && ok "$1: $(command -v "$1")" || { printf '  FAIL  %s is missing: %s\n' "$1" "$2"; missing=1; }; }

    echo "tools"
    missing=0
    need git "https://git-scm.com/downloads"
    need uv  "https://docs.astral.sh/uv/"
    need npm "install Node.js, https://nodejs.org/"
    [ "$missing" = 0 ] || { echo "install what is missing and run 'just setup' again"; exit 1; }
    command -v gh >/dev/null 2>&1 && ok "gh: $(command -v gh)" || warn "gh is missing: workers open pull requests with it (https://cli.github.com/); then 'gh auth login' and 'gh auth setup-git'"

    echo "python 3.15"
    if uv python find 3.15 >/dev/null 2>&1; then ok "uv has Python $(uv python find 3.15)"; else uv python install 3.15 >/dev/null && did "installed Python 3.15 through uv"; fi

    echo "backlog.md"
    want=1.55.2
    have="$(backlog --version 2>/dev/null | head -1 || true)"
    if [ -n "$have" ] && [ "$(printf '%s\n%s\n' "$want" "$have" | sort -V | head -1)" = "$want" ]; then
        ok "backlog $have (1.55.2 or newer)"
    else
        npm install -g "backlog.md@$want" >/dev/null && did "installed backlog.md@$want${have:+ (was $have)}"
    fi

    echo "asdlc commands"
    mkdir -p "$HOME/.local/bin"
    linked=0
    for name in asdlc asdlc-plugin; do
        link="$HOME/.local/bin/$name"
        if [ -L "$link" ]; then
            case "$(readlink -f "$link")" in
                */scripts/"$name") linked=1; warn "$link is a link to $(readlink -f "$link"), so it runs whatever that clone has checked out, not the plugin you installed. Replace it: $root/scripts/asdlc install-command" ;;
            esac
        fi
    done
    # The launcher runs the installed plugin's scripts, whatever this clone has checked out. An old link is left until you replace it.
    [ "$linked" = 1 ] || "$root/scripts/asdlc" install-command | sed 's/^/  info  /' || warn "asdlc install-command left a file alone; see the line above"
    command -v claude >/dev/null 2>&1 && ok "claude: $(command -v claude)" || warn "claude is missing: the commands run the asdlc plugin Claude Code installed (/plugin install asdlc@asdlc)"
    case ":$PATH:" in *":$HOME/.local/bin:"*) ok "$HOME/.local/bin is on your PATH" ;; *) warn "$HOME/.local/bin is not on your PATH; add it to your shell profile" ;; esac

    echo "identity"
    if [ -n "$(git config --global asdlc.engineer || true)" ]; then ok "asdlc.engineer = $(git config --global asdlc.engineer)"; else warn "set who you are: git config --global asdlc.engineer <your handle without the @>"; fi

    echo "doctor"
    summary="$("$root/scripts/asdlc" doctor 2>&1 | tail -1 || true)"
    printf '  info  asdlc doctor on this machine: %s (the board and repository lines only apply inside a repository)\n' "$summary"
    echo "next: in a repository you work in, 'asdlc init-board --local .' (or register a shared board), then 'just doctor' there for the repository's own checks"

# every artefact check, every test, and every eval case's reference and null runs
check:
    ./scripts/check

# the unit tests alone
test:
    uv run --python 3.15 python -m unittest discover -s tests -t .

# the artefact checks alone
artefacts:
    uv run --script scripts/artefacts.py .

# the playbook conformance check alone
conformance:
    uv run --script scripts/conformance.py .

# every eval case's reference and null runs, with no model calls
validate:
    ./scripts/eval validate

# audit the history against the repository's own rules, with the indicators
audit:
    uv run --script scripts/history_audit.py --report

# check this machine and, inside a repository with a board, that repository
doctor:
    ./scripts/asdlc doctor

# a worktree of this commit, and how to load the plugin from it (never load it from this working copy)
try:
    #!/usr/bin/env bash
    set -euo pipefail
    dir=".worktrees/try-$(git rev-parse --short HEAD)"
    [ -d "$dir" ] || git worktree add --detach "$dir" HEAD >/dev/null
    echo "load it with:  claude --plugin-dir $(pwd)/$dir"

# name a release: set the plugin's version and file the changelog's Unreleased entries under it; installs only update when the version changes
release version:
    uv run --script scripts/release.py {{version}}

# run scripts/eval with your arguments; run, gate and calibrate spend tokens, so a person types them
eval *args:
    ./scripts/eval {{args}}
