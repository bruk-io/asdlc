"""The shape of the plugin's eval cases, read from files. No model runs here.

A skill is judged by the cases under `plugins/asdlc/evals/`. `just check` fails
when a skill is missing a kind of case, or when a case rests on a judge alone.
Running the cases is `just eval`, which is not part of `just check`.
"""

import subprocess
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest
import yaml
from click.testing import CliRunner

from asdlc.cli import cli
from tests.conftest import ROOT

PLUGIN = ROOT / "plugins" / "asdlc"

# A skill needs a case where it must act and a case where it must stay out.
KINDS = ("acts", "stays-out")

# The graders that give the same verdict on the same run every time.
PATTERNS = frozenset({"regex", "file_exists"})

type Case = Mapping[str, Any]


def problems(skills: Sequence[str], cases: Sequence[Case]) -> tuple[str, ...]:
    """Say what is wrong with the eval cases, given the skills they are for.

    A case is for a skill when its tags hold the skill's name.
    """
    tagged = [frozenset(case.get("tags") or ()) for case in cases]
    missing = tuple(
        f"skill '{skill}' has no case tagged '{skill}' and '{kind}'"
        for skill in skills
        for kind in KINDS
        if not any({skill, kind} <= tags for tags in tagged)
    )
    judged_only = tuple(
        f"case '{case.get('name')}' has no grader of type regex or file_exists"
        for case in cases
        if not any(
            grader.get("type") in PATTERNS for grader in case.get("graders") or ()
        )
    )
    return missing + judged_only


def case(name: str, *tags: str, graders: Sequence[str] = ("regex",)) -> Case:
    return {
        "name": name,
        "tags": list(tags),
        "graders": [{"name": f"g{n}", "type": kind} for n, kind in enumerate(graders)],
    }


COMPLETE = (
    case("in-their-words", "capturing-intent", "acts", graders=("regex", "llm")),
    case("small-request", "capturing-intent", "stays-out", graders=("file_exists",)),
)


def test_a_skill_with_both_kinds_of_case_has_no_problems():
    assert problems(["capturing-intent"], COMPLETE) == ()


def test_no_skills_and_no_cases_is_no_problem():
    assert problems([], []) == ()


def test_a_skill_with_no_case_where_it_stays_out_is_named():
    assert problems(["capturing-intent"], COMPLETE[:1]) == (
        "skill 'capturing-intent' has no case tagged 'capturing-intent' "
        "and 'stays-out'",
    )


def test_a_skill_with_no_case_where_it_acts_is_named():
    assert problems(["capturing-intent"], COMPLETE[1:]) == (
        "skill 'capturing-intent' has no case tagged 'capturing-intent' and 'acts'",
    )


def test_another_skills_cases_do_not_count():
    found = problems(["capturing-intent", "generating-a-spec"], COMPLETE)
    assert found == (
        "skill 'generating-a-spec' has no case tagged 'generating-a-spec' and 'acts'",
        "skill 'generating-a-spec' has no case tagged 'generating-a-spec' "
        "and 'stays-out'",
    )


def test_a_case_that_rests_on_a_judge_alone_is_named():
    judged = case("in-their-words", "capturing-intent", "acts", graders=("llm",))
    assert problems(["capturing-intent"], (judged, COMPLETE[1])) == (
        "case 'in-their-words' has no grader of type regex or file_exists",
    )


def test_a_case_with_no_graders_at_all_is_named():
    empty = case("in-their-words", "capturing-intent", "acts", graders=())
    assert problems(["capturing-intent"], (empty, COMPLETE[1])) == (
        "case 'in-their-words' has no grader of type regex or file_exists",
    )


def skills_in_the_plugin() -> tuple[str, ...]:
    return tuple(sorted(p.parent.name for p in PLUGIN.glob("skills/*/SKILL.md")))


def cases_in_the_plugin() -> tuple[Case, ...]:
    files = sorted(PLUGIN.glob("evals/*/case.yaml"))
    return tuple(yaml.safe_load(file.read_text()) for file in files)


def test_every_skill_in_the_plugin_has_both_kinds_and_no_case_is_judge_only():
    assert problems(skills_in_the_plugin(), cases_in_the_plugin()) == ()


SCAFFOLDS = sorted(PLUGIN.glob("evals/*/scaffold.sh"))


@pytest.mark.parametrize("scaffold", SCAFFOLDS, ids=lambda path: path.parent.name)
def test_a_scaffold_builds_a_repository_whose_documents_lint_clean(
    scaffold: Path, tmp_path: Path
):
    """A scaffold writes its documents by hand, so they can drift from the format.

    Finding that here costs nothing. Finding it in a run costs a run.
    """
    built = subprocess.run(
        ["sh", str(scaffold)], cwd=tmp_path, capture_output=True, text=True
    )
    assert built.returncode == 0, built.stderr
    checked = CliRunner().invoke(cli, ["document", "check", "--root", str(tmp_path)])
    assert (checked.exit_code, checked.stdout) == (0, "")
