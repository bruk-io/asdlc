# everything: asdlc lint on the example, formatting, ruff and the tests
check:
    uv run asdlc document check --root examples/claims
    uv run ruff format --check .
    uv run ruff check .
    uv run pytest -q

# the tests alone
test *args:
    uv run pytest {{args}}

# reformat in place
format:
    uv run ruff format .
    uv run ruff check --fix .
