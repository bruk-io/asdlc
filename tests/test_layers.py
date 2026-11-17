"""The layers hold: domain decides alone, io and presentation never meet."""

import ast
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "src" / "asdlc"

# What each layer must not import. Only cli may import all three.
FORBIDDEN = {
    "domain": (
        "asdlc.io",
        "asdlc.presentation",
        "asdlc.cli",
        "click",
        "subprocess",
        "sys",
    ),
    "io": ("asdlc.presentation", "asdlc.cli", "click"),
    "presentation": ("asdlc.io", "asdlc.cli", "click", "subprocess"),
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


MODULES = [
    (layer, file)
    for layer in FORBIDDEN
    for file in sorted((PACKAGE / layer).glob("*.py"))
]


@pytest.mark.parametrize(
    ("layer", "file"), MODULES, ids=lambda value: getattr(value, "name", value)
)
def test_a_layer_imports_only_what_it_may(layer, file):
    crossed = sorted(
        name
        for name in imports(file)
        for banned in FORBIDDEN[layer]
        if name == banned or name.startswith(f"{banned}.")
    )
    assert not crossed, f"src/asdlc/{layer}/{file.name} must not import {crossed}"


def test_every_layer_has_modules_to_judge():
    assert {layer for layer, _ in MODULES} == set(FORBIDDEN)
