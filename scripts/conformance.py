#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""The playbook conformance check: every claim in spec/playbook-conformance.md says what builds it and what tests it,
every target it names exists, and every requirement of the spec serves a claim or is listed as beyond the playbook.

Each finding names the claim or requirement and why the rule exists, so the fix is clear without reading this script.

Usage: conformance.py [<repository root>]
"""

import re
import sys
from collections.abc import Callable, Iterable
from dataclasses import dataclass
from pathlib import Path

CONFORMANCE = "spec/playbook-conformance.md"
SPEC = "spec/agentic-sdlc-plugin.md"

# Where each kind of target lives, relative to the repository root. `none` is not a kind: it stands alone in a field.
LOCATIONS: dict[str, Callable[[str], str]] = {
    "skill": lambda name: f"skills/{name}/SKILL.md",
    "agent": lambda name: f"agents/{name}.md",
    "command": lambda name: f"commands/{name}.md",
    "hook": lambda name: f"hooks/{name}",
    "script": lambda name: f"scripts/{name}",
    "template": lambda name: f"templates/{name}",
    "workflow": lambda name: f".github/workflows/{name}",
    "doc": lambda name: f"docs/{name}",
    "file": lambda name: name,
    "eval": lambda name: f"evals/cases/{name}/case.toml",
    "test": lambda name: f"tests/{name}",
}

_CLAIM = re.compile(r"^- \*\*(P\d+\.\d+)\*\* \| (.+?) \| (.+?) \| built: (.+?) \| tested: (.+)$")
_CLAIM_START = re.compile(r"^- \*\*P\d")
_REQUIREMENT = re.compile(r"^- \*\*R(\d+)\b", re.MULTILINE)
_REQUIREMENT_REF = re.compile(r"R(\d+)")
_BEYOND = re.compile(r"^- R(\d+): (\S.*)$")


@dataclass(frozen=True)
class Finding:
    where: str
    message: str

    def __str__(self) -> str:
        return f"{self.where}: {self.message}"


@dataclass(frozen=True)
class Claim:
    id: str
    text: str
    requirements: tuple[str, ...]
    built: str
    tested: str


def parse(text: str) -> tuple[list[Claim], dict[str, str], list[Finding]]:
    """The claims, the requirements listed as beyond the playbook with their reasons, and the lines that could not be read."""
    claims: list[Claim] = []
    beyond: dict[str, str] = {}
    findings: list[Finding] = []
    in_beyond = False
    for number, line in enumerate(text.splitlines(), 1):
        if line.startswith("## "):
            in_beyond = line.strip() == "## Beyond the playbook"
        elif in_beyond and (found := _BEYOND.match(line)):
            beyond[f"R{found.group(1)}"] = found.group(2)
        elif _CLAIM_START.match(line):
            if not (found := _CLAIM.match(line)):
                findings.append(Finding(f"line {number}", "a claim must read `- **P<play>.<n>** | claim | requirements | built: ... | tested: ...`, so the check can read it"))
                continue
            claim_id, claim_text, refs, built, tested = found.groups()
            requirements = tuple(f"R{n}" for n in _REQUIREMENT_REF.findall(refs))
            claims.append(Claim(claim_id, claim_text, requirements, built.strip(), tested.strip()))
    return claims, beyond, findings


def targets(field: str) -> tuple[list[tuple[str, str]], str | None]:
    """The (kind, name) targets of a built or tested field, or the reason when the field is `none: <reason>`."""
    if field.startswith("none:"):
        return [], field[len("none:"):].strip()
    found = []
    for part in (p.strip() for p in field.split(",")):
        kind, _, name = part.partition(":")
        found.append((kind.strip(), name.strip()))
    return found, None


def check_field(claim: Claim, label: str, field: str, exists: Callable[[str], bool]) -> list[Finding]:
    found, reason = targets(field)
    if reason is not None:
        if reason:
            return []
        return [Finding(claim.id, f"{label}: `none:` needs a reason; a gap written down without one is not a finding anyone can act on")]
    findings = []
    for kind, name in found:
        if kind not in LOCATIONS:
            findings.append(Finding(claim.id, f"{label}: '{kind}:{name}' is not a kind of target ({', '.join(LOCATIONS)}), so the check cannot find it"))
        elif not name or not exists(LOCATIONS[kind](name)):
            path = LOCATIONS[kind](name) if name else kind
            findings.append(Finding(claim.id, f"{label}: {kind}:{name} does not exist (looked for {path}); a mapping to nothing claims coverage there is none"))
    return findings


def check(conformance: str, requirements: Iterable[str], exists: Callable[[str], bool]) -> list[Finding]:
    """Every finding about the conformance file against the spec's requirement numbers and the files that exist."""
    claims, beyond, findings = parse(conformance)
    known = set(requirements)
    seen: set[str] = set()
    served: set[str] = set()
    for claim in claims:
        if claim.id in seen:
            findings.append(Finding(claim.id, "repeated; each claim has its own id so a gap can be named"))
        seen.add(claim.id)
        findings += check_field(claim, "built", claim.built, exists) + check_field(claim, "tested", claim.tested, exists)
        for requirement in claim.requirements:
            if requirement not in known:
                findings.append(Finding(claim.id, f"{requirement} is not a requirement of the spec"))
            served.add(requirement)
    for requirement, _ in sorted(beyond.items(), key=lambda item: int(item[0][1:])):
        if requirement not in known:
            findings.append(Finding("Beyond the playbook", f"{requirement} is not a requirement of the spec"))
        elif requirement in served:
            findings.append(Finding("Beyond the playbook", f"{requirement} also serves a claim; it is either the playbook's or beyond it"))
    for requirement in sorted(known - served - set(beyond), key=lambda r: int(r[1:])):
        findings.append(Finding(requirement, "serves no claim and is not listed under 'Beyond the playbook'; place it, or say why the plugin has it"))
    if not claims:
        findings.append(Finding(CONFORMANCE, "has no claims"))
    return findings


def requirement_ids(spec: str) -> list[str]:
    return [f"R{n}" for n in _REQUIREMENT.findall(spec)]


# --- the shell: the only code that touches the filesystem -------------------------


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    if not (root / CONFORMANCE).is_file():
        print(f"conformance: no {CONFORMANCE}, nothing to check")
        return 0
    spec = (root / SPEC).read_text() if (root / SPEC).is_file() else ""
    findings = check((root / CONFORMANCE).read_text(), requirement_ids(spec), lambda path: (root / path).exists())
    for finding in findings:
        print(finding)
    if not findings:
        print("conformance: all clean")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
