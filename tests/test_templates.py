"""The templates that ship with the package are documents the domain can read.

`io` hands a template's text over and `domain` parses it, so this is a test of
the two together and sits with the tests of the app layer.
"""

import pytest

from asdlc.domain.documents import Kind, parse
from asdlc.io import files


@pytest.mark.parametrize("kind", list(Kind))
def test_every_kind_has_a_template_that_ships_with_the_package(kind):
    text = files.template(kind)
    assert text.startswith(f"---\nkind: {kind}\n")


def test_a_template_is_a_document_once_its_frontmatter_is_filled():
    document, _ = parse("intent/claims/intent.md", files.template(Kind.INTENT))
    assert document.kind is Kind.INTENT
