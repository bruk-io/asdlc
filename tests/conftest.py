import json
import os
import re
import shutil
import subprocess
from dataclasses import dataclass
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent


@pytest.hookimpl(optionalhook=True)
def pytest_xdist_auto_num_workers() -> int:
    """Say how many workers `-n auto` starts: one a processor, and eight at most.

    Nearly all of a test's time here is starting git, and past eight workers the
    starts get in each other's way: on a machine with 28 processors the suite
    takes 8 seconds with 8 workers and 14 with 28.
    """
    return min(os.cpu_count() or 1, 8)


def git(root: Path, *args: str) -> str:
    command = [
        "git",
        "-C",
        str(root),
        "-c",
        "user.name=t",
        "-c",
        "user.email=t@example.com",
        *args,
    ]
    return subprocess.run(command, capture_output=True, text=True, check=True).stdout


@pytest.fixture
def example() -> Path:
    """The worked example: four intents, two replacing a requirement of the first."""
    return ROOT / "examples" / "claims"


@pytest.fixture(scope="session")
def repository_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """What `repository` copies. Git makes it once a session, and no test changes it."""
    root = tmp_path_factory.mktemp("repository-template").resolve()
    git(root, "init", "-q", "-b", "main")
    intent = root / "intent" / "claims" / "intent.md"
    intent.parent.mkdir(parents=True)
    intent.write_text("---\nkind: intent\nauthor: a\n---\n")
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", "intent")
    return root


@pytest.fixture
def repository(repository_template: Path, tmp_path: Path) -> Path:
    """A git repository whose main holds one accepted intent.

    It is a copy of one git made earlier in the session, file for file, so making
    it starts no process. The test owns the copy.
    """
    root = tmp_path.resolve()
    shutil.copytree(repository_template, root, dirs_exist_ok=True)
    return root


def task_text(step: int, requirement: str, size: int, title: str) -> str:
    """Give a task document as `asdlc task new` writes its frontmatter."""
    front = f"kind: task\nstep: {step}\ndelivers: [{requirement}]\nsize: {size}\n"
    return f"---\n{front}---\n# Task: {title}\n"


# What the remote's main holds: one intent with its spec, its plan and two tasks
# that depend on nothing, one of size 2 and one of size 8, and the checks.
ACCEPTED = {
    "intent/claims/intent.md": "---\nkind: intent\nauthor: a\n---\n# Intent: claims\n",
    "intent/claims/spec.md": (
        "---\nkind: spec\n---\n# Spec: claims\n### R1: one\n### R2: two\n"
    ),
    "intent/claims/plan.md": (
        "---\nkind: plan\n---\n# Plan: claims\n"
        "## Files that change\n- api/status.py (new)\n## Order of work\n"
        "### Step 1: the endpoint\n- delivers: R1\n"
        "### Step 2: the panel\n- delivers: R2\n"
    ),
    "intent/claims/tasks/01-endpoint/task.md": task_text(1, "R1", 2, "the endpoint"),
    "intent/claims/tasks/02-panel/task.md": task_text(2, "R2", 8, "the panel"),
    ".asdlc/checks": "echo checked\n",
}


def commit_files(root: Path, texts: dict[str, str], subject: str) -> None:
    """Write files into a working tree and commit them."""
    for relative, text in texts.items():
        (root / relative).parent.mkdir(parents=True, exist_ok=True)
        (root / relative).write_text(text)
    git(root, "add", "-A")
    git(root, "commit", "-q", "-m", subject)


def clone_of(origin: Path, folder: Path) -> Path:
    """Clone a bare repository into a new folder, with a name and an email set.

    The clone's `asdlc.gh` names `gh/gh` beside the bare repository. Nothing is
    there until the `gh` fixture puts its stand-in there, so a command run on the
    clone finds no `gh` at all, and never starts the one this machine has.
    """
    settings = {
        "user.name": "Dana",
        "user.email": "dana@example.com",
        "asdlc.gh": str(origin.parent / "gh" / "gh"),
    }
    kept = [word for key in settings for word in ("-c", f"{key}={settings[key]}")]
    git(origin.parent, "clone", "-q", *kept, str(origin), str(folder))
    return folder


def second_clone(remote: Path) -> Path:
    """Give another clone of the `remote` fixture's origin, beside the first."""
    return clone_of(remote.parent / "origin.git", remote.parent / "second")


@pytest.fixture(scope="session")
def remote_template(tmp_path_factory: pytest.TempPathFactory) -> Path:
    """What `remote` copies: a bare repository and a clone of it, in one folder.

    Git makes them once a session, and no test changes them.
    """
    base = tmp_path_factory.mktemp("remote-template").resolve()
    origin = base / "origin.git"
    git(base, "init", "-q", "--bare", "-b", "main", str(origin))
    seed = base / "seed"
    git(base, "init", "-q", "-b", "main", str(seed))
    commit_files(seed, ACCEPTED, "claims, accepted")
    git(seed, "push", "-q", str(origin), "main")
    shutil.rmtree(seed)
    clone_of(origin, base / "clone")
    return base


@pytest.fixture
def remote(remote_template: Path, tmp_path_factory: pytest.TempPathFactory) -> Path:
    """A clone whose `origin` is a bare repository beside it, on disk.

    The remote's main holds `ACCEPTED`, in one commit, and the clone is on main at
    that commit. Nothing here reaches the network.

    Both are a copy of what git made earlier in the session, file for file, so
    making them starts no process. The one thing a copy gets wrong is a path
    written into the clone's configuration: its `origin` and its `asdlc.gh` name
    the folder they were made in, so they are pointed at the copy.
    """
    base = tmp_path_factory.mktemp("remote").resolve()
    shutil.copytree(remote_template, base, dirs_exist_ok=True)
    settings = base / "clone" / ".git" / "config"
    settings.write_text(settings.read_text().replace(str(remote_template), str(base)))
    return base / "clone"


# A stand-in for `gh`, as a shell script: it answers the `pr` calls asdlc makes
# and no others. It is plain sh with sed, grep and sort, so that a copy can go
# into an eval case's scaffold, where no Python can be started.
GH_STAND_IN = r"""#!/bin/sh
# A stand-in for gh. Its files are beside it:
#   pulls.json  the open pull requests, as a JSON array with one row to a line
#   calls       one line for each call: its arguments, tab-separated, and for a
#               comment read from stdin, the comment as one more field
#   fail        when it holds the name of a subcommand (list, create, comment
#               or ready), that subcommand fails
case $0 in
*/*) here=${0%/*} ;;
*) here=. ;;
esac
pulls="$here/pulls.json"
tab=$(printf '\t')
newline='
'

flat() {
    # Put any text on one line, in $flat: a backslash, a tab and a newline each
    # become two characters. Most arguments hold none of the three, and one
    # that holds none starts no process.
    case $1 in
    *\\* | *"$tab"* | *"$newline"*)
        flat=$(printf '%s\n' "$1" |
            sed -e 's/\\/\\\\/g' -e "s/$tab/\\\\t/g" |
            sed -e ':a' -e '$!N' -e '$!ba' -e 's/\n/\\n/g')
        ;;
    *) flat=$1 ;;
    esac
}

rows() {
    [ -f "$pulls" ] || return 0
    sed -n -e 's/,$//' -e '/^{/p' "$pulls"
}

save() {
    {
        printf '[\n'
        sed -e '$!s/$/,/'
        printf ']\n'
    } >"$pulls.new" && mv "$pulls.new" "$pulls"
}

refuse() {
    echo "gh stand-in: $1" >&2
    exit 1
}

line=
for argument in "$@"; do
    flat "$argument"
    line="${line:+$line$tab}$flat"
done
if [ "$1 $2" = "pr comment" ]; then
    case " $* " in
    *" --body-file - "*)
        flat "$(cat)"
        line="$line$tab$flat"
        ;;
    esac
fi
printf '%s\n' "$line" >>"$here/calls"

if [ -f "$here/fail" ] && [ "$(cat "$here/fail")" = "$2" ]; then
    refuse "told to fail on $2"
fi
[ "$1" = pr ] || refuse "no answer for: $*"

case "$2" in
list)
    cat "$pulls"
    ;;
create)
    shift 2
    draft=false
    head=
    while [ $# -gt 0 ]; do
        case "$1" in
        --draft) draft=true ;;
        --head)
            head=$2
            shift
            ;;
        --base | --title | --body) shift ;;
        esac
        shift
    done
    [ -n "$head" ] || refuse "pr create needs --head"
    if rows | grep -F -q "\"headRefName\": \"$head\""; then
        refuse "a pull request for $head is already open"
    fi
    last=$(rows | sed -n 's/.*"number": \([0-9][0-9]*\).*/\1/p' | sort -n | tail -1)
    number=$((${last:-0} + 1))
    link="https://example.invalid/pull/$number"
    {
        rows
        printf '{"headRefName": "%s", "isDraft": %s, "number": %s, "url": "%s"}\n' \
            "$head" "$draft" "$number" "$link"
    } | save
    printf '%s\n' "$link"
    ;;
comment | ready)
    number=$3
    mine="\"number\": ${number}[,}]"
    rows | grep -q "$mine" || refuse "no open pull request $number"
    if [ "$2" = ready ]; then
        draft=false
        case " $* " in
        *" --undo "*) draft=true ;;
        esac
        rows | sed -e "/$mine/s/\"isDraft\": [a-z]*/\"isDraft\": $draft/" | save
    fi
    ;;
*)
    refuse "no answer for: $*"
    ;;
esac
"""


@dataclass(frozen=True)
class Gh:
    """Where the stand-in for `gh` keeps its files: all beside the clone."""

    program: Path
    pulls: Path  # the open pull requests, as JSON
    calls: Path  # one line for each call it took
    fail: Path  # names the subcommand that is to fail, when there is one


def pull_row(branch: str, number: int, draft: bool = False) -> dict[str, object]:
    """Give an open pull request as `gh pr list --json` gives one."""
    link = f"https://example.invalid/pull/{number}"
    return {"headRefName": branch, "isDraft": draft, "number": number, "url": link}


def write_pulls(gh: Gh, *rows: dict[str, object]) -> None:
    """Set the open pull requests the stand-in holds, one row to a line."""
    lines = ",\n".join(json.dumps(row) for row in rows)
    gh.pulls.write_text(f"[\n{lines}\n]\n" if rows else "[\n]\n")


def held_pulls(gh: Gh) -> list[dict[str, object]]:
    """Read the open pull requests the stand-in holds."""
    return json.loads(gh.pulls.read_text())


_PLAIN = {"\\\\": "\\", "\\t": "\t", "\\n": "\n"}


def calls(gh: Gh) -> list[list[str]]:
    """Give each call the stand-in took, oldest first: its arguments as given.

    A comment read from stdin is one more argument at the end, without the
    newlines it ended with.
    """
    lines = gh.calls.read_bytes().decode().split("\n")[:-1]
    return [
        [
            re.sub(r"\\[\\tn]", lambda found: _PLAIN[found[0]], field)
            for field in line.split("\t")
        ]
        for line in lines
    ]


@pytest.fixture
def gh(remote: Path) -> Gh:
    """A stand-in for `gh` that the `remote` clone runs, through `asdlc.gh`.

    It holds no pull request to begin with. Its script, its JSON file and its
    record are in a folder beside the clone, so the clone's working tree stays
    clean. The clone's `asdlc.gh` names the script already, and so does that of
    a clone `second_clone` makes: without this fixture nothing is at that path.
    """
    folder = remote.parent / "gh"
    folder.mkdir()
    stand_in = Gh(
        program=folder / "gh",
        pulls=folder / "pulls.json",
        calls=folder / "calls",
        fail=folder / "fail",
    )
    stand_in.program.write_text(GH_STAND_IN)
    stand_in.program.chmod(0o755)
    stand_in.calls.write_text("")
    write_pulls(stand_in)
    return stand_in
