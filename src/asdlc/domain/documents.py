"""A document: one Markdown file under `intent/<slug>/`, parsed.

Each document starts with flat frontmatter and marks the things other documents cite
with a heading and a short list of properties:

    ### R1: Status updates within 2 seconds of a change
    - replaces: claims-status.R3

A document holds what a person declared. State is worked out elsewhere and has no
place to be written here: an unknown key or property is a finding.
"""

import re
from collections.abc import Iterable, Sequence
from dataclasses import dataclass
from enum import StrEnum
from pathlib import PurePosixPath


class Kind(StrEnum):
    INTENT = "intent"
    SPEC = "spec"
    PLAN = "plan"
    TASK = "task"


class Mark(StrEnum):
    """The prefix of a heading that other documents cite."""

    REQUIREMENT = "R"
    QUESTION = "Q"
    CONCERN = "C"
    STEP = "Step"


@dataclass(frozen=True)
class Finding:
    """One thing wrong with a document, and the rule it breaks."""

    path: str
    rule: str
    message: str


@dataclass(frozen=True)
class Item:
    """A cited heading: `### R1: title` and the `- key: value` lines under it."""

    mark: Mark
    number: int
    title: str
    props: frozendict[str, str]
    repeated: tuple[str, ...] = ()  # the keys written more than once; the last won


@dataclass(frozen=True)
class Document:
    path: str
    kind: Kind
    slug: str
    task: str | None  # the task folder, for a task.md or a task's own plan.md
    title: str  # the first heading, without its 'Intent:' or 'Task:' prefix
    meta: frozendict[str, str | tuple[str, ...]]
    items: tuple[Item, ...]
    sections: frozendict[str, tuple[str, ...]]  # each '## heading', its lines


# The sections a rule reads. The names are the course's.
FILES = "Files that change"
CONSTRAINTS = "Constraints"
CONSTRAINTS_MET = "How each constraint in the intent is met"

_FILES = frozendict(
    {"intent.md": Kind.INTENT, "spec.md": Kind.SPEC, "plan.md": Kind.PLAN}
)
_REQUIRED = frozendict(
    {
        Kind.INTENT: ("author",),
        Kind.SPEC: (),
        Kind.PLAN: (),
        Kind.TASK: ("step", "delivers"),
    }
)
_OPTIONAL = frozendict(
    {
        Kind.INTENT: ("parent",),
        Kind.SPEC: ("policies", "retires"),
        Kind.PLAN: (),
        Kind.TASK: ("depends", "size"),
    }
)
_LISTS = frozenset({"policies", "retires", "delivers", "depends"})
_MARKS = frozendict(
    {
        Kind.INTENT: (Mark.QUESTION,),
        Kind.SPEC: (Mark.REQUIREMENT, Mark.QUESTION, Mark.CONCERN),
        Kind.PLAN: (Mark.STEP,),
        Kind.TASK: (),
    }
)
_PROPS = frozendict(
    {
        Mark.REQUIREMENT: ("replaces",),
        Mark.QUESTION: ("answer",),
        Mark.CONCERN: ("owner",),
        Mark.STEP: ("delivers", "intent"),
    }
)

# What to do in place of a second line, for the properties that tempt one.
_ONCE = frozendict(
    {
        "replaces": ": to end two requirements, write a requirement for each",
        "delivers": ": list what a step delivers on one line, as 'R1, R2'",
    }
)

_KEY = re.compile(r"([a-z][a-z-]*): (\S.*)")
_ITEM = re.compile(r"### (Step |[RQC])(\d+): (\S.*)")
_NEARLY_ITEM = re.compile(r"### (Step |[RQC]) ?\d")
_PROP = re.compile(r"- ([a-z][a-z-]*): (\S.*)")
_TITLE = re.compile(r"# (?:(?:Intent|Spec|Plan|Task): )?(\S.*)")
_SECTION = re.compile(r"## (\S.*)")
_CELL = re.compile(r"(?<!\\)\|")
_RULE = re.compile(r":?-+:?")


def label(item: Item) -> str:
    """Give the item's id inside its own intent: `R3`, `Q1`, `Step 2`."""
    if item.mark is Mark.STEP:
        return f"{item.mark} {item.number}"
    return f"{item.mark}{item.number}"


def qualify(slug: str, ref: str) -> str:
    """Name the intent in a requirement id: `R3` inside `claims` is `claims.R3`."""
    return ref if "." in ref else f"{slug}.{ref}"


def place(path: str) -> tuple[Kind, str, str | None] | None:
    """Say what a path makes a document: its kind, intent slug and task folder.

    Return None when the path is not a document's.
    """
    match PurePosixPath(path).parts:
        case ("intent", slug, name) if name in _FILES:
            return _FILES[name], slug, None
        case ("intent", slug, "tasks", task, "task.md"):
            return Kind.TASK, slug, task
        case ("intent", slug, "tasks", task, "plan.md"):
            return Kind.PLAN, slug, task
    return None


def frontmatter(
    text: str,
) -> tuple[dict[str, str | tuple[str, ...]], str, tuple[str, ...]]:
    """Split a file into its frontmatter keys, the text after them, and what was wrong.

    Frontmatter is flat on purpose: `key: value` or `key: [a, b]`, nothing nested.
    """
    lines = text.split("\n")
    end = next((i for i in range(1, len(lines)) if lines[i] == "---"), None)
    if lines[0] != "---" or end is None:
        problem = "the file must start with frontmatter between two '---' lines"
        return {}, text, (problem,)
    meta: dict[str, str | tuple[str, ...]] = {}
    problems = []
    for line in lines[1:end]:
        if not line.strip():
            continue
        found = _KEY.fullmatch(line)
        if found is None:
            problems.append(
                f"'{line}' is not 'key: value'; frontmatter is flat keys with a "
                "plain value or an inline list"
            )
            continue
        key, raw = found[1], found[2].strip()
        if key in meta:
            problems.append(f"'{key}' is given twice")
        if raw.startswith("[") and raw.endswith("]"):
            meta[key] = tuple(p.strip() for p in raw[1:-1].split(",") if p.strip())
        else:
            meta[key] = raw
    return meta, "\n".join(lines[end + 1 :]), tuple(problems)


def items(body: str) -> tuple[tuple[Item, ...], tuple[str, ...]]:
    """Find the cited headings in a body, and the headings that nearly were one."""
    lines = body.split("\n")
    found = []
    problems = []
    fenced = False
    for index, line in enumerate(lines):
        if line.startswith("```"):
            fenced = not fenced
        if fenced:
            continue
        heading = _ITEM.fullmatch(line)
        if heading is None:
            if _NEARLY_ITEM.match(line):
                problems.append(
                    f"'{line}' looks like a cited heading but is not "
                    "'### R1: title' (or Q, C, Step)"
                )
            continue
        at = index + 1
        while at < len(lines) and not lines[at].strip():
            at += 1
        props = {}
        repeated = []
        while at < len(lines) and (prop := _PROP.fullmatch(lines[at])):
            if prop[1] in props and prop[1] not in repeated:
                repeated.append(prop[1])
            props[prop[1]] = prop[2].strip()
            at += 1
        mark = Mark(heading[1].strip())
        found.append(
            Item(
                mark,
                int(heading[2]),
                heading[3].strip(),
                frozendict(props),
                tuple(repeated),
            )
        )
    return tuple(found), tuple(problems)


def sections(body: str) -> frozendict[str, tuple[str, ...]]:
    """Split a body into its `## ` sections: each heading, and the lines under it.

    Blank lines are dropped. A heading inside a code fence is text.
    """
    found: dict[str, list[str]] = {}
    current: list[str] | None = None
    fenced = False
    for line in body.split("\n"):
        if line.startswith("```"):
            fenced = not fenced
        heading = None if fenced else _SECTION.fullmatch(line)
        if heading is not None:
            current = found.setdefault(heading[1].strip(), [])
        elif current is not None and line.strip():
            current.append(line)
    return frozendict({name: tuple(lines) for name, lines in found.items()})


def bullets(lines: Sequence[str]) -> tuple[str, ...]:
    """Give the list items among a section's lines, a wrapped item as one line."""
    found: list[str] = []
    for line in lines:
        if line.startswith("- "):
            found.append(line[2:].strip())
        elif found and line.startswith((" ", "\t")):
            found[-1] = f"{found[-1]} {line.strip()}"
    return tuple(found)


def filled(entries: Iterable[str]) -> tuple[str, ...]:
    """Drop the entries that are still a template's `<placeholder>`."""
    return tuple(
        entry
        for entry in entries
        if not (entry.startswith("<") and entry.endswith(">"))
    )


def table_rows(lines: Sequence[str]) -> tuple[tuple[str, ...], ...]:
    """Give the rows of a Markdown table among a section's lines, as cells.

    The header, which is the row above the rule of dashes, is left out.
    """
    rows: list[tuple[str, ...]] = []
    for line in lines:
        text = line.strip()
        if not text.startswith("|"):
            continue
        cells = tuple(
            cell.strip().replace("\\|", "|") for cell in _CELL.split(text.strip("|"))
        )
        if all(_RULE.fullmatch(cell) for cell in cells):
            del rows[-1:]
            continue
        rows.append(cells)
    return tuple(rows)


def title(body: str) -> str:
    """Give a document's first heading without its kind; empty when it has none."""
    for line in body.split("\n"):
        if found := _TITLE.fullmatch(line):
            return found[1].strip()
    return ""


def parse(path: str, text: str) -> tuple[Document | None, tuple[Finding, ...]]:
    """Read one document from its path and text, with everything wrong inside it.

    Return no document when the path is not a document's.
    """
    where = place(path)
    if where is None:
        message = (
            "not a document: expected intent/<slug>/intent.md, spec.md or plan.md, "
            "or tasks/<task>/task.md or plan.md under it"
        )
        return None, (Finding(path, "place", message),)
    kind, slug, task = where
    meta, body, problems = frontmatter(text)
    findings = [Finding(path, "frontmatter", problem) for problem in problems]

    def wrong(rule: str, message: str) -> None:
        findings.append(Finding(path, rule, message))

    if meta.get("kind") != kind:
        wrong("kind", f"frontmatter must say 'kind: {kind}', as the file's name does")
    allowed = ("kind", *_REQUIRED[kind], *_OPTIONAL[kind])
    for key in _REQUIRED[kind]:
        if key not in meta:
            wrong("frontmatter", f"'{key}' is missing; a {kind} must give it")
    for key, value in list(meta.items()):
        if key not in allowed:
            keys = ", ".join(allowed)
            wrong("frontmatter", f"'{key}' is not a key a {kind} has; they are {keys}")
        elif key in _LISTS and isinstance(value, str):
            meta[key] = (value,)
        elif key not in _LISTS and not isinstance(value, str):
            wrong("frontmatter", f"'{key}' takes one value, not a list")
    found, problems = items(body)
    findings += [Finding(path, "heading", problem) for problem in problems]
    for mark in Mark:
        numbers = [item.number for item in found if item.mark is mark]
        if numbers and mark not in _MARKS[kind]:
            wrong("heading", f"a {kind} has no '{mark}' headings")
        elif numbers != list(range(1, len(numbers) + 1)):
            wrong(
                "numbering",
                f"'{mark}' headings must be numbered 1, 2, 3 in order, with none "
                f"repeated or skipped; found {numbers}",
            )
    for item in found:
        for key in item.props:
            if key not in _PROPS[item.mark]:
                known = ", ".join(_PROPS[item.mark])
                wrong(
                    "property",
                    f"{label(item)} has '- {key}:', which is not a property of "
                    f"'{item.mark}'; the properties are {known}",
                )
        for key in item.repeated:
            wrong(
                "property",
                f"{label(item)} has '- {key}:' more than once, and only the last "
                f"would count. A heading takes a property once{_ONCE.get(key, '')}",
            )
    parts = sections(body)
    if kind is Kind.PLAN and not filled(bullets(parts.get(FILES, ()))):
        wrong(
            "files",
            f"a plan names the files it changes, so a review can compare the "
            f"change with it: add '## {FILES}' with one '- path' line for each",
        )
    document = Document(
        path, kind, slug, task, title(body), frozendict(meta), found, parts
    )
    return document, tuple(findings)


def listed(document: Document, key: str) -> tuple[str, ...]:
    """Give a frontmatter list, empty when the key is absent."""
    value = document.meta.get(key, ())
    return (value,) if isinstance(value, str) else value


def step_delivers(plan: Document, step: Item) -> tuple[str, ...]:
    """Give the requirement ids a plan step delivers, each naming its intent."""
    refs = step.props.get("delivers", "").split(",")
    return tuple(qualify(plan.slug, ref.strip()) for ref in refs if ref.strip())


def of_kind(
    documents: Iterable[Document], kind: Kind, *, own_plan: bool = False
) -> tuple[Document, ...]:
    """Pick the documents of one kind.

    An intent's plan has no task; `own_plan` asks for the tasks' plans instead.
    """
    return tuple(
        d
        for d in documents
        if d.kind is kind
        and (kind is not Kind.PLAN or (d.task is not None) == own_plan)
    )
