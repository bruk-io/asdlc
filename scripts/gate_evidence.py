#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""Gate evidence: did the eval suite pass on the configuration that steers the agent?

`scripts/eval gate` runs the suite and writes a report keyed by a digest of the steering
paths (CLAUDE.md, skills, hooks, agents, commands) and of the eval suite. Everything that
enforces the gate, the hooks, `./scripts/check` and CI later, asks `verify` and never reads
a report itself. A hook never runs the suite, which costs tokens and minutes; it asks
whether passing evidence exists for what is on disk now, and refuses when it does not.

    gate_evidence.py verify [--base <ref>]   exit 0 for pass or not needed, 1 otherwise

The logic (what counts as steering, digests, the verdict) takes data and returns data; git
and files stay in the shell below it.
"""

import hashlib
import json
import subprocess
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from enum import StrEnum
from pathlib import Path

from protected_paths import is_suite

SCHEMA = 1
STEERING = ("CLAUDE.md", "skills", "hooks", "agents", "commands")
EVIDENCE_FOLDER = Path(".eval-results") / "gate"
EVIDENCE_ROOTS = frozenset({".eval-results", ".asdlc"})  # written by scripts/eval and the hooks; never a change to the plugin
COMMAND = "scripts/eval gate"


class State(StrEnum):
    PASS = "pass"
    FAIL = "fail"
    MISSING = "missing"
    STALE = "stale"
    NOT_NEEDED = "not needed"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class Verdict:
    state: State
    reason: str

    @property
    def holds(self) -> bool:
        return self.state in (State.PASS, State.NOT_NEEDED)

    def line(self) -> str:
        return f"gate evidence {self.state}: {self.reason}"


def is_steering(path: str) -> bool:
    """Whether a path is configuration the agent reads: CLAUDE.md, or anything under skills, hooks, agents or commands."""
    return any(path == name or path.startswith(f"{name}/") for name in STEERING)


def needs_evidence(changed: Iterable[str]) -> bool:
    """A change needs gate evidence when it touches steering paths."""
    return any(is_steering(path) for path in changed)


def digest(entries: Iterable[tuple[str, str]]) -> str:
    """One digest over (path, content digest) pairs, whatever order they come in."""
    whole = hashlib.sha256()
    for path, content in sorted(entries):
        whole.update(f"{path}\0{content}\n".encode())
    return whole.hexdigest()


def key(steering: Mapping[str, str], suite: str) -> str:
    """What a report is filed under: the steering digests and the suite's, together."""
    return digest([*steering.items(), ("<suite>", suite)])


def verify(report: Mapping[str, object] | None, steering: Mapping[str, str], suite: str,
           transcripts: Mapping[str, str | None], where: str = COMMAND) -> Verdict:
    """Whether a report is passing evidence for the steering paths and suite as they are now.

    `transcripts` is the current digest of each transcript the report lists, None for one
    that is gone, so a report whose transcripts were removed or edited does not count.
    """
    if report is None:
        return Verdict(State.MISSING, f"no passing report for the current steering paths and eval suite; a person runs `{where}`, which spends tokens")
    if report.get("schema") != SCHEMA:
        return Verdict(State.STALE, f"the report has schema {report.get('schema')!r}, this version reads {SCHEMA}; run `{where}` again")
    recorded = report.get("steering")
    recorded = recorded if isinstance(recorded, dict) else {}
    if recorded != dict(steering):
        changed = sorted(name for name in {*steering, *recorded} if recorded.get(name) != steering.get(name))
        return Verdict(State.STALE, f"{', '.join(changed)} changed since the report; run `{where}` again")
    if report.get("suite") != suite:
        return Verdict(State.STALE, f"the eval suite changed since the report; run `{where}` again")
    listed = report.get("transcripts")
    if not isinstance(listed, dict):
        return Verdict(State.STALE, f"the report lists no transcripts to check it against; run `{where}` again")
    for name, expected in sorted(listed.items()):
        if transcripts.get(name) != expected:
            what = "is gone" if transcripts.get(name) is None else "was edited"
            return Verdict(State.FAIL, f"transcript {name} {what}, so the report cannot be trusted; run `{where}` again")
    if report.get("verdict") != "pass":
        return Verdict(State.FAIL, f"the last gate run did not pass: {report.get('summary', 'no summary recorded')}")
    return Verdict(State.PASS, f"passed for these steering paths and this suite ({report.get('created', 'time unrecorded')})")


# --- the shell: git and files ------------------------------------------------------------


def _git(root: Path, *args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True)


def _file_digests(root: Path, pathspecs: Iterable[str]) -> list[tuple[str, str]]:
    """(path, content digest) for each file tracked, staged or untracked-but-not-ignored under the pathspecs, as it is on disk now."""
    listed = _git(root, "ls-files", "-z", "--cached", "--others", "--exclude-standard", "--", *pathspecs).stdout
    found = []
    for name in sorted(set(filter(None, listed.split("\0")))):
        path = root / name
        if path.is_file():
            found.append((name, hashlib.sha256(path.read_bytes()).hexdigest()))
    return found


def current(root: Path) -> tuple[dict[str, str], str]:
    """The steering digests (one per steering path) and the suite's digest, as the files are on disk now."""
    steering = {name: digest(_file_digests(root, [name])) for name in STEERING}
    suite = digest(_file_digests(root, ["evals", ":(glob)spec/*-evals.md"]))
    return steering, suite


def report_file(root: Path, evidence_key: str) -> Path:
    return root / EVIDENCE_FOLDER / f"{evidence_key[:16]}.json"


def read_report(path: Path) -> Mapping[str, object] | None:
    try:
        found = json.loads(path.read_text())
    except (OSError, ValueError):
        return None
    return found if isinstance(found, dict) else None


def transcript_digests(root: Path, report: Mapping[str, object] | None) -> dict[str, str | None]:
    listed = report.get("transcripts") if report else None
    if not isinstance(listed, dict):
        return {}
    digests: dict[str, str | None] = {}
    for name in listed:
        path = root / ".eval-results" / name
        digests[name] = hashlib.sha256(path.read_bytes()).hexdigest() if path.is_file() else None
    return digests


def check(root: Path) -> Verdict:
    """The verdict for what is on disk in `root` now, whatever changed."""
    steering, suite = current(root)
    report = read_report(report_file(root, key(steering, suite)))
    return verify(report, steering, suite, transcript_digests(root, report))


def root_of(path: Path) -> Path | None:
    """The repository holding a path, from its nearest folder that exists."""
    folder = path if path.is_dir() else path.parent
    while not folder.is_dir() and folder != folder.parent:
        folder = folder.parent
    top = _git(folder, "rev-parse", "--show-toplevel").stdout.strip() if folder.is_dir() else ""
    return Path(top) if top else None


def has_gate(root: Path) -> bool:
    """Whether a repository holds the plugin's eval suite and its runner: the repositories the gate is for."""
    return (root / "scripts" / "eval").is_file() and (root / "evals" / "cases").is_dir()


def resolve_base(root: Path, requested: str | None = None) -> str | None:
    """The commit a change is measured from: the merge base of HEAD with the requested ref, else origin/main, else main."""
    for ref in ([requested] if requested else []) + ["origin/main", "main"]:
        done = _git(root, "merge-base", "HEAD", ref)
        if done.returncode == 0 and done.stdout.strip():
            return done.stdout.strip()
    return None


def changed_since(root: Path, base: str) -> list[str]:
    """Every path that differs from `base`: committed, staged, unstaged, and untracked files that are not ignored.
    Gate evidence and the hook log are left out, whether or not the repository ignores them."""
    tracked = _git(root, "diff", "--name-only", "--no-renames", base).stdout.splitlines()
    new = _git(root, "ls-files", "--others", "--exclude-standard").stdout.splitlines()
    return sorted(path for path in {*filter(None, tracked), *filter(None, new)} if path.split("/", 1)[0] not in EVIDENCE_ROOTS)


def check_change(root: Path, base: str | None = None) -> Verdict:
    """Whether this change needs evidence, and if so whether it has it.

    A change that touches no steering path needs none. When the base can't be found the
    verdict is UNKNOWN and says so, never a silent pass.
    """
    start = resolve_base(root, base)
    if start is None:
        return Verdict(State.UNKNOWN, "no base to measure the change from (no origin/main or main); pass --base <ref>")
    if not needs_evidence(changed_since(root, start)):
        return Verdict(State.NOT_NEEDED, f"no steering path changed since {start[:12]}")
    return check(root)


def main(argv: list[str]) -> int:
    if not argv or argv[0] != "verify" or len(argv) not in (1, 3) or (len(argv) == 3 and argv[1] != "--base"):
        print(__doc__, file=sys.stderr)
        return 2
    verdict = check_change(Path.cwd(), argv[2] if len(argv) == 3 else None)
    print(verdict.line())
    return 0 if verdict.holds else 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
