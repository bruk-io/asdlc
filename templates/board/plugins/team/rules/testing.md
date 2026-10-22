---
paths:
  - "**/{test,tests,Tests,__tests__,spec,specs,androidTest,testFixtures}/**"
  - "**/*{Test,Tests,Spec}.{swift,kt,kts,java}"
  - "**/*.{test,spec}.{ts,tsx,js,jsx,mjs,cjs}"
  - "**/{test_*,*_test}.{py,go,rb,ts,js}"
  - "**/conftest.py"
---
# Testing

Applies to tests in any language. The procedure, and how to record evidence, is the `team:testing` skill: load it before writing tests, fixing a bug, or saying a task is done.

- Name a test by what it proves: unit (logic, no doubles), functional (behaviour, with the outside world faked at the boundary), adapter (one gateway against the real thing), end to end. Not "integration".
- Doubles only at the boundary with the outside world, and only as fakes. Assert on the fake's state, not on calls made. Never mock the code under test.
- A test that needs a page of setup and mocks is telling you about the code: move the decision out of the I/O and test the decision.
- Time, randomness and ids are parameters. Never patch them.
- A bug is reproduced as a failing test, committed, before the fix; the fix doesn't edit that test.
- Never weaken, skip or loosen a test or check to make a change pass. A wrong check is a finding on the task.
- The repository's existing test conventions govern where they differ from this.
