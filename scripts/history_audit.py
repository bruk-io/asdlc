#!/usr/bin/env -S uv run --script
# /// script
# requires-python = ">=3.15"
# ///
"""An audit of this repository's own history against its own rules: every pull request that changed the plugin carried a plan,
the plan came first and was not a draft, the suite and the plugin never changed together, scripts and hooks shipped with tests,
and the change was announced.

Git is a proxy for what happened: a plan file in a pull request is not proof that a person approved it. The audit says what the
history shows. Each finding names the pull request, the rule and why the rule exists. A known departure is waived in
scripts/history_waivers.toml with a reason; a waived finding is still listed.

Usage: history_audit.py [<repository root>] [--ref <ref>] [--range <base>..<head>] [--pulls <json>] [--report]
  --ref     the history to read (default HEAD): every merge commit on its first-parent line is a pull request
  --range   audit one branch as if it were a pull request, before it merges
  --pulls   check runs per pull request, exported from the GitHub API: [{"number": 5, "checks": [{"name": "check", "conclusion": "success"}]}]
  --report  also print the indicators for every pull request
"""

import json
import re
import subprocess
import sys
import tomllib
from collections.abc import Callable, Iterable, Mapping, Sequence
from dataclasses import dataclass, field
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from protected_paths import is_suite  # noqa: E402

FIRST_JUDGED = 4  # pull requests before the v0 bootstrap built the loop itself and are listed, not judged
PLUGIN_PREFIXES = ("skills/", "commands/", "hooks/", "agents/", "scripts/", "templates/", ".github/workflows/", ".claude-plugin/")
REQUIRED_CHECKS = ("check", "protected-paths")
RULES = {
    "H1": "a plan travels with the change (R20): a pull request that changes the plugin adds or edits a file under plan/",
    "H2": "the plan comes first (R9): a plan the pull request adds is committed no later than the first commit touching the plugin",
    "H3": "an approved plan ships with code (R9): a plan the pull request adds is not 'draft' when the pull request also changes the plugin",
    "H4": "suite and plugin never together (R23): no pull request changes both the eval suite and the plugin",
    "H5": "tests ship with scripts and hooks: a pull request that changes a script or hook changes something under tests/",
    "H6": "the change is announced: a pull request that changes the plugin changes CHANGELOG.md",
    "H7": "the required checks passed at merge",
}


@dataclass(frozen=True)
class Commit:
    sha: str
    time: int
    files: tuple[str, ...]


@dataclass(frozen=True)
class Pull:
    number: int
    title: str
    merged: int  # unix time of the merge
    commits: tuple[Commit, ...]  # oldest first, merges of main into the branch left out
    files: Mapping[str, str]  # path -> A, M or D, the pull request's whole contribution
    plan_status: Mapping[str, str]  # each plan file it changed -> its Status line at the merge
    plan_text: str  # those plans' text at the merge
    changelog_existed: bool
    checks: tuple[tuple[str, str], ...] | None = None  # (name, conclusion), None when no export covers it


@dataclass(frozen=True)
class Finding:
    pull: int
    rule: str
    message: str
    waived: str = ""  # the reason, when a waiver covers it
    judged: bool = True  # False for a pull request before the loop existed

    def __str__(self) -> str:
        tag = "" if self.judged else " (before the loop; not judged)"
        waiver = f" [waived: {self.waived}]" if self.waived else ""
        return f"#{self.pull} {self.rule}: {self.message}{tag}{waiver}"


def is_plugin(path: str) -> bool:
    return path.startswith(PLUGIN_PREFIXES) and "__pycache__" not in path


def is_code(path: str) -> bool:
    """A script or hook that needs a test: under scripts/ or hooks/, and not data or prose."""
    return path.startswith(("scripts/", "hooks/")) and "__pycache__" not in path and not path.endswith((".json", ".md", ".toml"))


def _first(commits: Sequence[Commit], wanted: Callable[[str], bool]) -> int | None:
    return next((i for i, c in enumerate(commits) if any(wanted(f) for f in c.files)), None)


def audit_pull(pull: Pull) -> list[Finding]:
    """What one pull request departs from."""
    found: list[Finding] = []
    paths = [p for p, status in pull.files.items()]
    plugin = [p for p in paths if is_plugin(p)]
    suite = [p for p in paths if is_suite(p)]
    plans = [p for p in paths if p.startswith("plan/") and pull.files[p] != "D"]
    if plugin and not plans:
        found.append(Finding(pull.number, "H1", f"changes {len(plugin)} plugin files ({', '.join(plugin[:3])}{', ...' if len(plugin) > 3 else ''}) and carries no plan"))
    new_plans = [p for p in plans if pull.files[p] == "A"]  # a plan already on main was approved by the pull request that merged it
    if plugin and new_plans:
        plan_at = _first(pull.commits, lambda f: f in new_plans)
        code_at = _first(pull.commits, is_plugin)
        if plan_at is not None and code_at is not None and plan_at > code_at:
            found.append(Finding(pull.number, "H2", f"the first plugin commit ({pull.commits[code_at].sha[:7]}) is before the first plan commit ({pull.commits[plan_at].sha[:7]})"))
        for path in sorted(new_plans):
            status = pull.plan_status.get(path, "")
            if re.match(r"\s*draft", status, re.I):
                found.append(Finding(pull.number, "H3", f"{path} is still '{status.strip()[:60]}' at the merge, with code in the same pull request"))
    if plugin and suite:
        found.append(Finding(pull.number, "H4", f"changes the plugin ({plugin[0]}) and the suite ({suite[0]}) together"))
    code = [p for p in paths if is_code(p) and pull.files[p] != "D"]
    if code and not any(p.startswith("tests/") for p in paths):
        found.append(Finding(pull.number, "H5", f"changes {', '.join(code[:3])}{', ...' if len(code) > 3 else ''} with no change under tests/"))
    if plugin and pull.changelog_existed and "CHANGELOG.md" not in pull.files:
        found.append(Finding(pull.number, "H6", "changes the plugin and not CHANGELOG.md"))
    if pull.checks is not None:
        by_name = dict(pull.checks)
        bad = [f"{name} {by_name.get(name, 'missing')}" for name in REQUIRED_CHECKS if by_name.get(name) != "success"]
        if pull.checks and bad:
            found.append(Finding(pull.number, "H7", f"required checks not green at merge: {', '.join(bad)}"))
    return [Finding(f.pull, f.rule, f.message, judged=pull.number >= FIRST_JUDGED or pull.number == 0) for f in found]


def apply_waivers(findings: Iterable[Finding], waivers: Iterable[Mapping[str, object]]) -> list[Finding]:
    reasons = {(int(w["pr"]), str(w["rule"])): f"{w['reason']} (accepted by {w['accepted_by']})" for w in waivers}
    return [Finding(f.pull, f.rule, f.message, reasons.get((f.pull, f.rule), ""), f.judged) for f in findings]


def audit(pulls: Iterable[Pull], waivers: Iterable[Mapping[str, object]] = ()) -> list[Finding]:
    return apply_waivers([f for pull in pulls for f in audit_pull(pull)], waivers)


def failing(findings: Iterable[Finding]) -> list[Finding]:
    return [f for f in findings if f.judged and not f.waived]


@dataclass(frozen=True)
class Indicators:
    pull: int
    title: str
    commits: int
    lead_hours: float
    plan_after_code: int  # commits touching the plan after the first plugin commit
    plan_match: float | None  # the share of changed plugin files the plan names, None without a plan


def indicators(pull: Pull) -> Indicators:
    code_at = _first(pull.commits, is_plugin)
    after = 0 if code_at is None else sum(1 for c in pull.commits[code_at + 1:] if any(f.startswith("plan/") for f in c.files))
    plugin = [p for p, s in pull.files.items() if is_plugin(p) and s != "D"]
    named = [p for p in plugin if p in pull.plan_text or p.rsplit("/", 1)[-1] in pull.plan_text]
    start = pull.commits[0].time if pull.commits else pull.merged
    return Indicators(pull.number, pull.title, len(pull.commits), max(0, pull.merged - start) / 3600,
                      after, (len(named) / len(plugin)) if plugin and pull.plan_status else None)


def render(findings: Sequence[Finding], pulls: Sequence[Pull], report: bool) -> str:
    lines = [f"history audit: {len(pulls)} pull requests, judged from #{FIRST_JUDGED}"]
    open_ = failing(findings)
    waived = [f for f in findings if f.judged and f.waived]
    early = [f for f in findings if not f.judged]
    lines += ["", f"{len(open_)} findings", *(f"  {f}" for f in open_)] if open_ else ["", "0 findings"]
    if waived:
        lines += ["", f"{len(waived)} waived", *(f"  {f}" for f in waived)]
    if early:
        lines += ["", f"{len(early)} before the loop (listed, not judged)", *(f"  {f}" for f in early)]
    if report:
        lines += ["", "| PR | Title | Commits | Lead (h) | Plan edits after code | Plan names the files |", "|---|---|---|---|---|---|"]
        for pull in pulls:
            i = indicators(pull)
            match = "-" if i.plan_match is None else f"{i.plan_match:.0%}"
            lines.append(f"| #{i.pull} | {i.title[:48]} | {i.commits} | {i.lead_hours:.1f} | {i.plan_after_code} | {match} |")
    return "\n".join(lines)


# --- the shell: the only code that touches git and the filesystem -------------------------


def _git(root: Path, *args: str) -> str:
    return subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, check=True).stdout


def _files(root: Path, *args: str) -> dict[str, str]:
    found = {}
    for line in _git(root, "diff", "--name-status", "--no-renames", *args).splitlines():
        status, _, path = line.partition("\t")
        found[path] = status[0]
    return found


def _commits(root: Path, rev_range: str) -> tuple[Commit, ...]:
    out = []
    for sha in _git(root, "rev-list", "--reverse", "--no-merges", rev_range).split():
        names = _git(root, "diff-tree", "--no-commit-id", "--name-only", "-r", "--root", sha).split("\n")
        out.append(Commit(sha, int(_git(root, "show", "-s", "--format=%at", sha)), tuple(n for n in names if n)))
    return tuple(out)


def _plans(root: Path, at: str, files: Mapping[str, str]) -> tuple[dict[str, str], str]:
    status, text = {}, []
    for path, change in sorted(files.items()):
        if path.startswith("plan/") and change != "D":
            body = _git(root, "show", f"{at}:{path}")
            found = re.search(r"^- Status:\s*(.*)$", body, re.M)
            status[path] = found.group(1) if found else ""
            text.append(body)
    return status, "\n".join(text)


def read_pull(root: Path, base: str, head: str, number: int, title: str, merged: int, checks: tuple[tuple[str, str], ...] | None) -> Pull:
    files = _files(root, base, head)
    status, text = _plans(root, head, files)
    changelog = subprocess.run(["git", "-C", str(root), "cat-file", "-e", f"{base}:CHANGELOG.md"], capture_output=True).returncode == 0
    return Pull(number, title, merged, _commits(root, f"{base}..{head}"), files, status, text, changelog, checks)


def _title(subject: str) -> str:
    """The words after 'Merge pull request #N' : or from <owner>/<branch>."""
    if " from " in subject:
        return subject.split(" from ", 1)[1].split("/", 1)[-1].strip()
    return subject.split(":", 1)[-1].strip() if ":" in subject else subject


def read_history(root: Path, ref: str, exported: Mapping[int, tuple[tuple[str, str], ...]]) -> list[Pull]:
    pulls = []
    for sha in reversed(_git(root, "rev-list", "--first-parent", "--merges", ref).split()):
        parents = _git(root, "show", "-s", "--format=%P", sha).split()
        subject = _git(root, "show", "-s", "--format=%s", sha)
        if len(parents) < 2 or not (number := re.search(r"#(\d+)", subject)):
            continue
        n = int(number.group(1))
        pulls.append(read_pull(root, parents[0], sha, n, _title(subject),
                               int(_git(root, "show", "-s", "--format=%at", sha)), exported.get(n)))
    return pulls


def main(argv: list[str]) -> int:
    args = argv[1:]
    options = {"--ref": "HEAD", "--range": "", "--pulls": ""}
    root = Path.cwd()
    report = False
    i = 0
    while i < len(args):
        if args[i] in options:
            options[args[i]] = args[i + 1]
            i += 2
        elif args[i] == "--report":
            report, i = True, i + 1
        else:
            root, i = Path(args[i]), i + 1
    if _git(root, "rev-parse", "--is-shallow-repository").strip() == "true":
        print("history audit: this clone is shallow, so the pull requests' parents are missing; fetch the full history (git fetch --unshallow) and run again")
        return 2
    exported = {int(p["number"]): tuple((c["name"], c["conclusion"]) for c in p["checks"]) for p in json.loads(Path(options["--pulls"]).read_text())} if options["--pulls"] else {}
    waiver_file = root / "scripts" / "history_waivers.toml"
    waivers = tomllib.loads(waiver_file.read_text()).get("waiver", []) if waiver_file.is_file() else []
    if options["--range"]:
        base, _, head = options["--range"].partition("..")
        pulls = [read_pull(root, base, head or "HEAD", 0, f"branch {options['--range']}", int(_git(root, "show", "-s", "--format=%at", head or "HEAD")), None)]
    else:
        pulls = read_history(root, options["--ref"], exported)
    findings = audit(pulls, waivers)
    print(render(findings, pulls, report))
    return 1 if failing(findings) else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
