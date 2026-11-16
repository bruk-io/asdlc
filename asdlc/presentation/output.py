"""One result, in the form the flags asked for: lines, identifiers or JSON."""

import json
from collections.abc import Callable, Sequence


def listing[T](
    records: Sequence[T],
    *,
    line: Callable[[T], str],
    identifier: Callable[[T], str],
    document: Callable[[T], object],
    as_json: bool,
    quiet: bool,
) -> str:
    """Render records: one per line, or identifiers only, or one JSON array.

    An empty listing is the empty string, or `[]` as JSON.
    """
    if as_json:
        chosen = [identifier(r) if quiet else document(r) for r in records]
        return json.dumps(chosen)
    return "\n".join(identifier(r) if quiet else line(r) for r in records)


def single(
    *, text: str, identifier: str, document: object, as_json: bool, quiet: bool
) -> str:
    """Render one record: in full, or its identifier, or one JSON object."""
    if as_json:
        return json.dumps(identifier if quiet else document)
    return identifier if quiet else text
