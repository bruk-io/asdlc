---
paths:
  - "**/tests/**/*.py"
  - "**/test/**/*.py"
  - "**/test_*.py"
  - "**/*_test.py"
  - "**/conftest.py"
---
# Testing in Python

Applies to Python tests. These are the techniques for the team's testing policy (`rules/testing.md`, the `team:testing` skill); where a repository's existing tests do it differently, they govern.

## Layout

- A folder per kind of test, named for what it proves: `tests/unit/`, `tests/functional/`, `tests/adapter/`, `tests/e2e/`. Only `tests/functional/` uses doubles.
- A repository that already has one flat `tests/` folder keeps it; new tests follow its layout.

## Logic

- Put the decision in a function that takes plain data and returns a value saying what should happen next (an Enum, or a frozen dataclass when the step carries data). The function that does the I/O calls it and acts on the result. Then a unit test is one line:

  ```python
  assert next_step(status=503, attempt=1) is Step.RETRY
  assert next_step(status=503, attempt=3) is Step.FAIL
  ```

- `now`, `rng` and id generators are parameters with production defaults at the edge. A test passes a fixed `datetime` or `random.Random(0)`. Never `unittest.mock.patch` the clock, `random` or `uuid`.
- Use `subTest` (unittest) or `pytest.mark.parametrize` for a table of cases, so one failing case names itself.

## Fakes

- A fake is a small class implementing the same `Protocol` as the real gateway, holding its state in plain collections: an in-memory repository, a recording outbox. Assert on that state after the act.
- `unittest.mock.Mock`, `MagicMock` and `patch` are not fakes. Don't use them on code inside the boundary, and don't assert on `called_with`.
- Real files, git repositories and SQLite databases in a temporary folder (`tempfile.TemporaryDirectory`, pytest's `tmp_path`) are cheap and are not doubles: prefer them to faking the filesystem.

## Running

- Run the tests the way the repository's verified test command does (`commands.toml` in its plugin), not with a bare `pytest` or `python -m unittest` that may pick up the wrong interpreter or settings.
- Run the functional suite twice in one process when you change shared fixtures or module-level state, to catch state that leaks between tests.
- A test that is slow or needs the network belongs in the adapter or end-to-end folder, marked so the fast tier can leave it out.
