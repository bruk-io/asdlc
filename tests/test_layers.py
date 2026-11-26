"""The layers hold.

`domain` and `io` know nothing of each other. `presentation` knows `domain` and
never `io`. Only the app layer, `cli.py`, brings `domain` and `io` together.
The tests of a layer keep to the same lines.
"""

import ast
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "src" / "asdlc"
TESTS = ROOT / "tests"

# The one module that may import from both `domain` and `io`.
APP = "cli.py"

# What each layer must not import.
FORBIDDEN = {
    "domain": (
        "asdlc.io",
        "asdlc.presentation",
        "asdlc.cli",
        "click",
        "subprocess",
        "sys",
    ),
    "io": ("asdlc.domain", "asdlc.presentation", "asdlc.cli", "click"),
    "presentation": ("asdlc.io", "asdlc.cli", "click", "subprocess"),
}

# What the tests of each layer must not import: a test that needs two layers
# is a test of the app layer, and belongs beside `tests/test_cli.py`.
FORBIDDEN_IN_TESTS = {
    "domain": ("asdlc.io", "asdlc.presentation", "asdlc.cli", "subprocess"),
    "io": ("asdlc.domain", "asdlc.presentation", "asdlc.cli"),
    "presentation": ("asdlc.io", "asdlc.cli", "subprocess"),
}


def imports(file: Path) -> set[str]:
    found = set()
    for node in ast.walk(ast.parse(file.read_text())):
        if isinstance(node, ast.Import):
            found |= {alias.name for alias in node.names}
        elif isinstance(node, ast.ImportFrom) and node.module:
            found.add(node.module)
            found |= {f"{node.module}.{alias.name}" for alias in node.names}
    return found


def relative_imports(file: Path) -> list[int]:
    """Give the lines of a module's relative imports, which `imports` cannot name."""
    tree = ast.walk(ast.parse(file.read_text()))
    return [n.lineno for n in tree if isinstance(n, ast.ImportFrom) and n.level]


def crossed(file: Path, banned: tuple[str, ...]) -> list[str]:
    return sorted(
        name
        for name in imports(file)
        for ban in banned
        if name == ban or name.startswith(f"{ban}.")
    )


def modules(folder: Path, rules: dict[str, tuple[str, ...]]) -> list:
    return [
        pytest.param(layer, file, id=f"{layer}/{file.relative_to(folder / layer)}")
        for layer in rules
        for file in sorted((folder / layer).rglob("*.py"))
    ]


MODULES = modules(PACKAGE, FORBIDDEN)
EVERY_MODULE = sorted(PACKAGE.rglob("*.py"))


@pytest.mark.parametrize(("layer", "file"), MODULES)
def test_a_layer_imports_only_what_it_may(layer, file):
    found = crossed(file, FORBIDDEN[layer])
    assert not found, f"src/asdlc/{layer}/{file.name} must not import {found}"


@pytest.mark.parametrize(("layer", "file"), modules(TESTS, FORBIDDEN_IN_TESTS))
def test_the_tests_of_a_layer_import_only_what_they_may(layer, file):
    found = crossed(file, FORBIDDEN_IN_TESTS[layer])
    assert not found, f"tests/{layer}/{file.name} must not import {found}"


def test_only_the_app_layer_imports_from_both_domain_and_io():
    both = [
        file.relative_to(PACKAGE).as_posix()
        for file in EVERY_MODULE
        if crossed(file, ("asdlc.domain",)) and crossed(file, ("asdlc.io",))
    ]
    assert both == [APP]


def test_every_module_is_in_a_layer_or_is_the_app_layer():
    """A module anywhere else would be judged by no rule above."""
    unjudged = [
        file.relative_to(PACKAGE).as_posix()
        for file in EVERY_MODULE
        if file.relative_to(PACKAGE).parts[0] not in (*FORBIDDEN, APP, "__init__.py")
    ]
    assert unjudged == []


def test_every_import_names_its_module_in_full():
    """A relative import would name no layer, and so slip past every rule above."""
    relative = {
        file.relative_to(PACKAGE).as_posix(): lines
        for file in EVERY_MODULE
        if (lines := relative_imports(file))
    }
    assert relative == {}


def test_every_layer_has_modules_to_judge():
    assert {param.values[0] for param in MODULES} == set(FORBIDDEN)
    assert len(EVERY_MODULE) > len(MODULES)
