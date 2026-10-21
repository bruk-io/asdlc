#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""Shape checks for the loop's artefacts: intents, specs, plans and CLAUDE.md.

Each finding names the file, the rule, and why the rule exists, so the fix is clear
without reading this script.

Usage: artefacts.py [<repository root> [<file> ...]]
Every artefact is read so links resolve, but when files are named only their findings
are reported, so checking a new intent never reports on someone else's CLAUDE.md.
"""

import re
import sys
from collections.abc import Iterable, Mapping
from dataclasses import dataclass
from pathlib import Path

INTENT_SECTIONS = ("Problem", "Proposed outcome", "Affected users and systems", "Constraints", "Open questions")
SPEC_SECTIONS = ("Requirements", "Design", "Areas of concern", "Out of scope")
PLAN_SECTIONS = ("Files that change", "Order of work", "Risks", "Proof")
CLAUDE_MD_MAX_LINES = 60

_LINK = re.compile(r"\]\(([^)\s]+)\)")
_REQUIREMENT = re.compile(r"^- \*\*R(\d+)\.", re.MULTILINE)
_REQUIREMENT_REF = re.compile(r"\bR(\d+)\b")
_CHECKBOX = re.compile(r"^- \[( |x|X)\] ")


@dataclass(frozen=True)
class Finding:
    path: str
    rule: str
    message: str

    def __str__(self) -> str:
        return f"{self.path}: {self.rule}: {self.message}"


@dataclass(frozen=True)
class Document:
    title: str
    header: frozendict[str, str]
    sections: frozendict[str, str]


# --- the logic: text in, findings out ---------------------------------------------


def parse(text: str) -> Document:
    """Split a Markdown artefact into its title, header bullets and `##` sections."""
    title = ""
    header: dict[str, str] = {}
    sections: dict[str, list[str]] = {}
    current: str | None = None
    for line in text.splitlines():
        if not title and line.startswith("# "):
            title = line[2:].strip()
        elif line.startswith("## "):
            current = line[3:].strip()
            sections[current] = []
        elif current is not None:
            sections[current].append(line)
        elif line.startswith("- ") and ":" in line:
            key, _, value = line[2:].partition(":")
            header[key.strip()] = value.strip()
    return Document(
        title=title,
        header=frozendict(header),
        sections=frozendict({name: "\n".join(lines).strip() for name, lines in sections.items()}),
    )


def _missing(path: str, doc: Document, prefix: str, header_keys: Iterable[str], sections: Iterable[str]) -> list[Finding]:
    findings = []
    if not doc.title.startswith(prefix):
        findings.append(Finding(path, "title", f"the first heading must start with '# {prefix}' so tools can tell what kind of artefact this is"))
    for key in header_keys:
        if key not in doc.header:
            findings.append(Finding(path, "header", f"missing '- {key}:' under the title; the next stage reads it"))
    for name in sections:
        if not doc.sections.get(name):
            findings.append(Finding(path, "section", f"missing or empty '## {name}'; every artefact of this kind carries it so the gate can judge it"))
    return findings


def _question_lines(doc: Document) -> list[str]:
    """The open-question lines, or none when the section says there are none."""
    lines = [line for line in doc.sections.get("Open questions", "").splitlines() if line.strip()]
    return [] if [line.strip().rstrip(".").lower() for line in lines] == ["none"] else lines


def open_questions(doc: Document) -> tuple[tuple[int, bool], ...]:
    """Number each open question from 1 and say whether it is ticked."""
    lines = _question_lines(doc)
    return tuple(
        (number, match.group(1) != " ")
        for number, line in enumerate(lines, start=1)
        if (match := _CHECKBOX.match(line))
    )


def check_intent(path: str, doc: Document) -> list[Finding]:
    findings = _missing(path, doc, "Intent: ", ("Author", "Status"), INTENT_SECTIONS)
    for line in _question_lines(doc):
        if not _CHECKBOX.match(line):
            findings.append(Finding(path, "open-questions", f"'{line.strip()}' is not a checkbox; each open question is one '- [ ]' line so the spec can settle it by number, or the section says 'None.'"))
    return findings


def linked(header_value: str | None) -> str | None:
    """The first Markdown link target in a header value."""
    if header_value is None:
        return None
    match = _LINK.search(header_value)
    return match.group(1) if match else None


def requirement_numbers(doc: Document) -> tuple[int, ...]:
    return tuple(int(n) for n in _REQUIREMENT.findall(doc.sections.get("Requirements", "")))


def check_spec(path: str, doc: Document, intent: Document | None, full_text: str) -> list[Finding]:
    findings = _missing(path, doc, "Spec: ", ("Intent", "Status"), SPEC_SECTIONS)
    if intent is None:
        findings.append(Finding(path, "intent-link", "'- Intent:' must link to an intent file in this repository; a spec answers one intent"))
    numbers = requirement_numbers(doc)
    if doc.sections.get("Requirements") and not numbers:
        findings.append(Finding(path, "requirements", "no requirement written as '**R1.**'; plans cite requirements by number"))
    if numbers and numbers != tuple(range(1, len(numbers))):
        findings.append(Finding(path, "requirements", f"requirements are numbered {list(numbers)}; number them R1 upwards without gaps or repeats so citations stay unambiguous"))
    if intent is not None:
        lowered = full_text.lower()
        for number, ticked in open_questions(intent):
            if not ticked and not re.search(rf"\bintent question {number}\b", lowered):
                findings.append(Finding(path, "open-questions", f"intent question {number} is neither ticked in the intent nor answered or carried forward here as 'intent question {number}'"))
    return findings


def check_plan(path: str, doc: Document, spec: Document | None) -> list[Finding]:
    findings = _missing(path, doc, "Plan: ", ("Spec", "Status", "Delivers"), PLAN_SECTIONS)
    if spec is None:
        findings.append(Finding(path, "spec-link", "'- Spec:' must link to a spec file in this repository; a plan delivers part of one spec"))
    else:
        known = set(requirement_numbers(spec))
        cited = [int(n) for n in _REQUIREMENT_REF.findall(doc.header.get("Delivers", ""))]
        if "Delivers" in doc.header and not cited:
            findings.append(Finding(path, "delivers", "'- Delivers:' names no requirement such as R1; a plan says which requirements it delivers"))
        for number in cited:
            if number not in known:
                findings.append(Finding(path, "delivers", f"R{number} is not a requirement in the linked spec"))
    if doc.sections.get("Files that change") and "`" not in doc.sections["Files that change"]:
        findings.append(Finding(path, "files", "'## Files that change' names no file in backticks; the plan's file list is what drift is measured against"))
    if doc.sections.get("Order of work") and not re.search(r"^1\. ", doc.sections["Order of work"], re.MULTILINE):
        findings.append(Finding(path, "order", "'## Order of work' has no numbered steps; the order is part of what gets approved"))
    return findings


def check_claude_md(path: str, text: str) -> list[Finding]:
    lines = len(text.splitlines())
    if lines > CLAUDE_MD_MAX_LINES:
        return [Finding(path, "length", f"{lines} lines; keep it to at most {CLAUDE_MD_MAX_LINES}, because every session reads all of it")]
    return []


def check_all(files: Mapping[str, str]) -> list[Finding]:
    """Check every artefact. `files` maps a repository-relative POSIX path to its text."""
    docs = {path: parse(text) for path, text in files.items() if path.endswith(".md")}

    def normalised(path: str, target: str) -> str:
        parts: list[str] = []
        for part in (Path(path).parent / target).as_posix().split("/"):
            if part == "..":
                if parts:
                    parts.pop()
            elif part not in ("", "."):
                parts.append(part)
        return "/".join(parts)

    def resolve(path: str, target: str | None) -> Document | None:
        return docs.get(normalised(path, target)) if target else None

    # A file in spec/ that a spec links from its header (an evals file, say) supports that
    # spec; every other file in spec/ is a spec and gets every spec check.
    supporting = {
        normalised(path, target)
        for path, doc in docs.items()
        if path.startswith("spec/")
        for value in doc.header.values()
        if (target := linked(value))
    } - {path for path in docs if not path.startswith("spec/")}

    findings: list[Finding] = []
    for path, doc in sorted(docs.items()):
        folder = path.split("/", 1)[0] if "/" in path else ""
        match folder:
            case "intent":
                findings += check_intent(path, doc)
            case "spec" if path not in supporting:
                findings += check_spec(path, doc, resolve(path, linked(doc.header.get("Intent"))), files[path])
            case "plan":
                findings += check_plan(path, doc, resolve(path, linked(doc.header.get("Spec"))))
            case _:
                pass
    if "CLAUDE.md" in files:
        findings += check_claude_md("CLAUDE.md", files["CLAUDE.md"])
    return findings


# --- the shell: the only code that touches the filesystem -------------------------


def _read(root: Path) -> dict[str, str]:
    paths = [p for folder in ("intent", "spec", "plan") for p in sorted((root / folder).glob("*.md"))]
    if (root / "CLAUDE.md").exists():
        paths.append(root / "CLAUDE.md")
    return {p.relative_to(root).as_posix(): p.read_text() for p in paths}


def main(argv: list[str]) -> int:
    root = Path(argv[1]) if len(argv) > 1 else Path.cwd()
    only = {(root / name).resolve().relative_to(root.resolve()).as_posix() for name in argv[2:]}
    findings = [f for f in check_all(_read(root)) if not only or f.path in only]
    for finding in findings:
        print(finding)
    if not findings:
        print("artefacts: all clean")
    return 1 if findings else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
