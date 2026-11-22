# everything: asdlc lint on the example, formatting, ruff and the tests
check:
    uv run asdlc document check --root examples/claims
    uv run ruff format --check .
    uv run ruff check .
    uv run pytest -q -n auto

# the tests alone, one at a time unless told otherwise: `just test -n auto`
test *args:
    uv run pytest {{args}}

# reformat in place
format:
    uv run ruff format .
    uv run ruff check --fix .

# run the plugin's eval cases with claude, with the plugin and without it; this spends money
eval *args:
    claude plugin eval plugins/asdlc --scaffold --no-publish --judge-model sonnet --allow-tools Bash Write Edit {{args}}
