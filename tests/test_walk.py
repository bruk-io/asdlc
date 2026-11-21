"""One intent through the whole chain, by the commands, in a real repository.

Each document is scaffolded on its own branch, filled in, and accepted by a merge.
Task state and requirement progress are then read back from git alone.
"""

import json

from click.testing import CliRunner

from asdlc.cli import cli
from asdlc.io import files
from tests.conftest import git


def run(repository, *args: str):
    done = CliRunner().invoke(cli, [*args, "--root", str(repository)])
    assert done.exit_code == 0, done.output
    return done.stdout.strip()


def fill(repository, relative: str, body: str) -> None:
    """Keep the frontmatter the command wrote and replace the template's body."""
    path = repository / relative
    front = path.read_text().split("---\n")[1]
    path.write_text(f"---\n{front}---\n{body}")


def accept(repository, branch: str, number: int) -> None:
    """Commit the branch and merge it the way GitHub merges a pull request."""
    git(repository, "add", "-A")
    git(repository, "commit", "-q", "-m", f"work on {branch}")
    git(repository, "switch", "-q", "main")
    subject = f"Merge pull request #{number} from owner/{branch}"
    git(repository, "merge", "-q", "--no-ff", "-m", subject, branch)
    git(repository, "branch", "-q", "-D", branch)


def task_states(repository) -> dict[str, str]:
    rows = json.loads(run(repository, "task", "list", "--json"))
    return {row["id"]: row["state"] for row in rows}


def progress(repository) -> dict[str, str]:
    rows = json.loads(run(repository, "requirement", "list", "--json"))
    return {row["id"]: row["state"] for row in rows}


def test_an_intent_goes_from_a_spec_to_built(repository, tmp_path_factory, monkeypatch):
    assert run(repository, "spec", "new", "claims") == "intent/claims/spec.md"
    assert git(repository, "branch", "--show-current").strip() == "spec/claims"
    fill(
        repository,
        "intent/claims/spec.md",
        "# Spec: claims\n### R1: one\n### R2: two\n",
    )
    accept(repository, "spec/claims", 1)
    assert progress(repository) == {"claims.R1": "approved", "claims.R2": "approved"}

    assert run(repository, "plan", "new", "claims") == "intent/claims/plan.md"
    steps = (
        "### Step 1: the endpoint\n- delivers: R1\n"
        "### Step 2: the panel\n- delivers: R2\n"
    )
    files_ = "## Files that change\n- api/status.py (new)\n## Order of work\n"
    fill(repository, "intent/claims/plan.md", f"# Plan: claims\n{files_}{steps}")
    accept(repository, "plan/claims", 2)
    assert progress(repository) == {"claims.R1": "planned", "claims.R2": "planned"}

    first = run(
        repository, "task", "new", "claims/01-endpoint", "--step", "1", "--size", "3"
    )
    assert first == "intent/claims/tasks/01-endpoint/task.md"
    run(
        repository,
        "task",
        "new",
        "claims/02-panel",
        "--step",
        "2",
        "--depends",
        "01-endpoint",
    )
    assert git(repository, "branch", "--show-current").strip() == "tasks/claims"
    cut = (repository / first).read_text()
    assert "step: 1\ndelivers: [R1]\nsize: 3\n" in cut
    assert "# Task: the endpoint" in cut
    accept(repository, "tasks/claims", 3)

    assert run(repository, "document", "check") == ""
    assert task_states(repository) == {
        "claims/01-endpoint": "ready",
        "claims/02-panel": "waiting",
    }
    assert progress(repository) == {"claims.R1": "in tasks", "claims.R2": "in tasks"}
    assert run(repository, "intent", "list").split("\t")[:2] == ["claims", "tasks"]

    assert (
        run(repository, "branch", "new", "task/claims/01-endpoint")
        == "task/claims/01-endpoint"
    )
    assert task_states(repository)["claims/01-endpoint"] == "claimed"

    with monkeypatch.context() as patched:
        folder = tmp_path_factory.mktemp("bin")
        patched.setenv(
            "PATH", f"{folder}:/usr/bin:/bin:/usr/local/bin:/opt/homebrew/bin"
        )
        for draft, state in (("true", "claimed"), ("false", "in review")):
            row = (
                '{"headRefName": "task/claims/01-endpoint", '
                f'"isDraft": {draft}, "number": 4, "url": "https://example.invalid/4"}}'
            )
            files.write_program(folder / "gh", f"#!/bin/sh\necho '[{row}]'\n")
            assert task_states(repository)["claims/01-endpoint"] == state
            shown = json.loads(
                run(repository, "task", "show", "claims/01-endpoint", "--json")
            )
            assert shown["pull_request"] == "https://example.invalid/4"

    (repository / "endpoint.py").write_text("status = 'received'\n")
    accept(repository, "task/claims/01-endpoint", 4)
    assert task_states(repository) == {
        "claims/01-endpoint": "done",
        "claims/02-panel": "ready",
    }
    assert progress(repository) == {"claims.R1": "built", "claims.R2": "in tasks"}

    run(repository, "branch", "new", "task/claims/02-panel")
    (repository / "panel.py").write_text("refresh = 60\n")
    accept(repository, "task/claims/02-panel", 5)
    assert progress(repository) == {"claims.R1": "built", "claims.R2": "built"}
    assert run(repository, "intent", "list").split("\t")[1] == "built"
