"""The asdlc command. It reads through `io`, decides in `domain`, and speaks
through `presentation`. Nothing else imports all three.

The grammar is `asdlc <noun> <verb> [target] [flags]`: singular nouns, verbs from
a closed set, at most one positional, and everything else a flag.

Exit statuses: 0 success; 1 the command ran and found something wrong; 2 bad
usage; 3 the target matched nothing; 4 there is no repository or no main to
compare with; 130 interrupted.
"""

import json
import sys
from collections.abc import Callable
from dataclasses import dataclass
from importlib.metadata import version as package_version
from pathlib import Path

import click

from asdlc.domain import scaffold
from asdlc.domain.documents import Document, Finding, Kind, Mark, step_delivers
from asdlc.domain.guard import Verdict, guard, waiting
from asdlc.domain.lint import library
from asdlc.domain.requirements import Requirement, Standing, lineage, requirements
from asdlc.domain.shell import push_folder
from asdlc.domain.tasks import Task, done, intents, merged_branches, tasks
from asdlc.io import files, git, github
from asdlc.io.hook import read_file_write, read_shell_command
from asdlc.presentation import data, output, text
from asdlc.presentation import hook as hook_text

FAILED = 1
NO_TARGET = 3
NO_REPOSITORY = 4
INTERRUPTED = 130

_SETTINGS = {"help_option_names": ["-h", "--help"]}


@dataclass(frozen=True)
class Options:
    """The flags every command has."""

    root: Path
    json: bool
    quiet: bool
    verbose: bool


def universal[**P, R](command: Callable[P, R]) -> Callable[P, R]:
    """Add the flags every command has, and hand them over as one `Options`."""
    flags = [
        click.option(
            "--root",
            type=click.Path(file_okay=False, path_type=Path),
            default=".",
            help="The repository to act on. Defaults to the current folder.",
        ),
        click.option("--json", "as_json", is_flag=True, help="Machine-readable."),
        click.option("-q", "--quiet", is_flag=True, help="Identifiers only."),
        click.option("-v", "--verbose", is_flag=True, help="Diagnostics on stderr."),
        click.option("--color/--no-color", default=False, help="Colour. Off."),
        click.option("--input/--no-input", "reads", default=False, help="Never asks."),
    ]

    def wrapped(root, as_json, quiet, verbose, color, reads, **rest):
        return command(Options(root, as_json, quiet, verbose), **rest)

    wrapped.__name__ = command.__name__
    wrapped.__doc__ = command.__doc__
    for flag in reversed(flags):
        wrapped = flag(wrapped)
    return wrapped


def _fail(message: str, status: int) -> click.exceptions.Exit:
    click.echo(text.error(message), err=True)
    return click.exceptions.Exit(status)


def _note(options: Options, message: str) -> None:
    if options.verbose:
        click.echo(message, err=True)


def _emit(rendered: str) -> None:
    if rendered:
        click.echo(rendered)


def _library(options: Options) -> tuple[tuple[Document, ...], tuple[Finding, ...]]:
    documents, found = library(files.document_texts(options.root))
    _note(options, f"read {len(documents)} documents under {options.root}/intent")
    return documents, found


def _warn_of(found: tuple[Finding, ...]) -> None:
    if found:
        click.echo(
            f"Warning: {len(found)} finding(s) in the documents, so this may be "
            "wrong. Run: asdlc document check",
            err=True,
        )


def _main(options: Options) -> tuple[Path, str] | None:
    """Give the repository and the ref that stands for main; None without them."""
    root = git.repository(options.root)
    ref = git.base(root) if root else None
    return (root, ref) if root and ref else None


def _repository(options: Options) -> tuple[Path, str]:
    found = _main(options)
    if found is None:
        raise _fail(
            f"{options.root} is not a git repository with a main branch",
            NO_REPOSITORY,
        )
    return found


def _merged(options: Options) -> frozenset[str]:
    found = _main(options)
    if found is None:
        _note(options, "no git repository with a main branch, so nothing reads as done")
        return frozenset()
    return merged_branches(git.merge_subjects(*found))


def _tasks(options: Options, documents: tuple[Document, ...]) -> tuple[Task, ...]:
    """Every task with its state, from the branches, pull requests and merges."""
    found = _main(options)
    if found is None:
        return tasks(documents, merged=_merged(options))
    pulls = github.open_pull_branches(found[0])
    if pulls is None:
        _note(options, "gh listed no pull requests, so no task reads as in review")
    return tasks(
        documents,
        branches=git.branches(found[0]),
        open_pulls=pulls or frozenset(),
        merged=_merged(options),
    )


def _requirements(options: Options) -> tuple[Requirement, ...]:
    documents, found = _library(options)
    _warn_of(found)
    return requirements(documents, done(tasks(documents, merged=_merged(options))))


def _split(target: str) -> tuple[str, str | None]:
    """Read a target as an intent's slug, or as <slug>/<task>."""
    parts = target.split("/")
    if len(parts) > 2 or not all(scaffold.well_named(part) for part in parts):
        raise click.UsageError(
            f"'{target}' is not <slug> or <slug>/<task>: lowercase words, digits "
            "and hyphens"
        )
    return parts[0], parts[1] if len(parts) == 2 else None


def _start(
    options: Options,
    kind: Kind,
    slug: str,
    task: str | None,
    branch: str,
    fields: dict[str, str | tuple[str, ...]],
    title: str,
) -> None:
    """Get onto the document's branch, write the document, and print its path."""
    root, ref = _repository(options)
    _on_branch(root, ref, branch)
    relative = scaffold.path(kind, slug, task)
    text_ = scaffold.document(kind, files.template(kind), fields, title)
    if not files.write_new(root / relative, text_):
        raise _fail(f"{relative} already exists", FAILED)
    _note(options, f"wrote {relative} on '{branch}'")
    click.echo(json.dumps(relative) if options.json else relative)


def _on_branch(root: Path, ref: str, branch: str) -> None:
    """Switch to a branch, making it from main once what it builds on is merged."""
    if git.current_branch(root) == branch:
        return
    if git.has_branch(root, branch):
        if not git.switch(root, branch):
            raise _fail(f"git would not switch to '{branch}'", FAILED)
        return
    reason = waiting(branch, git.documents_on(root, ref))
    if reason is not None:
        raise _fail(f"cannot start '{branch}': {reason}", FAILED)
    if not git.create_branch(root, branch, ref):
        raise _fail(f"git would not create '{branch}'", FAILED)


def _title_of(root: Path, slug: str) -> str:
    """Give the title of an intent in the working tree; empty when it has none."""
    documents, _ = library(files.document_texts(root))
    return next(
        (d.title for d in documents if d.slug == slug and d.kind is Kind.INTENT), ""
    )


@click.group(context_settings=_SETTINGS)
def cli() -> None:
    """asdlc <noun> <verb> [target] [flags]"""


@cli.command("version", context_settings=_SETTINGS)
def show_version() -> None:
    """Print the version."""
    click.echo(package_version("asdlc"))


@cli.group(context_settings=_SETTINGS)
def document() -> None:
    """An intent, spec, plan or task file under intent/."""


@document.command("check", context_settings=_SETTINGS)
@click.argument("intent", required=False)
@universal
def document_check(options: Options, intent: str | None) -> None:
    """Find everything wrong in and between the documents.

    The target is one intent's slug. Without it, every document is checked.
    Prints one finding per line: path, rule, message. Prints nothing when clean.
    """
    documents, found = _library(options)
    if intent is not None:
        slugs = sorted({d.slug for d in documents})
        if intent not in slugs:
            raise _fail(
                f"no intent '{intent}'. The intents are: {', '.join(slugs)}", NO_TARGET
            )
        found = tuple(f for f in found if f.path.startswith(f"intent/{intent}/"))
    _emit(
        output.listing(
            found,
            line=text.finding_line,
            identifier=lambda f: f.path,
            document=data.finding,
            as_json=options.json,
            quiet=options.quiet,
        )
    )
    if found:
        raise click.exceptions.Exit(FAILED)


@cli.group(context_settings=_SETTINGS)
def intent() -> None:
    """What someone wants, in their words: the first document of a change."""


@intent.command("list", context_settings=_SETTINGS)
@universal
def intent_list(options: Options) -> None:
    """List the intents: slug, stage, parent, title."""
    documents, found = _library(options)
    _warn_of(found)
    _emit(
        output.listing(
            intents(documents, _tasks(options, documents)),
            line=text.intent_line,
            identifier=lambda i: i.slug,
            document=data.intent,
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@intent.command("show", context_settings=_SETTINGS)
@click.argument("slug")
@universal
def intent_show(options: Options, slug: str) -> None:
    """Show one intent in full, with the tasks under it and their states."""
    documents, found = _library(options)
    _warn_of(found)
    known = intents(documents, _tasks(options, documents))
    match = next((i for i in known if i.slug == slug), None)
    if match is None:
        slugs = ", ".join(i.slug for i in known)
        raise _fail(f"no intent '{slug}'. The intents are: {slugs}", NO_TARGET)
    _emit(
        output.single(
            text=text.intent_record(match),
            identifier=match.slug,
            document=data.intent(match),
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@intent.command("new", context_settings=_SETTINGS)
@click.argument("slug")
@click.option("--author", help="Who asked for this. Defaults to git's user.name.")
@click.option("--parent", help="The intent this one was handed over from.")
@click.option("--title", default="", help="What is wanted, in a few words.")
@universal
def intent_new(
    options: Options, slug: str, author: str | None, parent: str | None, title: str
) -> None:
    """Start an intent on its own branch. Prints the file it wrote.

    The target is the new intent's slug: lowercase words joined by hyphens.
    """
    slug, task = _split(slug)
    if task is not None:
        raise click.UsageError("an intent is named by a slug alone")
    root, _ = _repository(options)
    author = author or git.user_name(root)
    if not author:
        raise click.UsageError("no --author given, and git has no user.name")
    fields: dict[str, str | tuple[str, ...]] = {"author": author}
    if parent:
        fields["parent"] = parent
    _start(options, Kind.INTENT, slug, None, f"intent/{slug}", fields, title)


@cli.group(context_settings=_SETTINGS)
def spec() -> None:
    """An intent's requirements and design."""


@spec.command("new", context_settings=_SETTINGS)
@click.argument("slug")
@click.option("--title", default="", help="Defaults to the intent's title.")
@universal
def spec_new(options: Options, slug: str, title: str) -> None:
    """Start an intent's spec on its own branch. Prints the file it wrote.

    The target is the intent's slug. Its intent must be on main.
    """
    slug, task = _split(slug)
    if task is not None:
        raise click.UsageError("a spec belongs to an intent: give its slug alone")
    root, ref = _repository(options)
    _on_branch(root, ref, f"spec/{slug}")
    title = title or _title_of(root, slug)
    _start(options, Kind.SPEC, slug, None, f"spec/{slug}", {}, title)


@cli.group(context_settings=_SETTINGS)
def plan() -> None:
    """How an intent, or one of its tasks, gets built."""


@plan.command("new", context_settings=_SETTINGS)
@click.argument("target")
@click.option("--title", default="", help="Defaults to the intent's title.")
@universal
def plan_new(options: Options, target: str, title: str) -> None:
    """Start a plan. Prints the file it wrote.

    The target is an intent's slug, for the intent's plan on its own branch; or
    <slug>/<task>, for a task's own plan on that task's branch.
    """
    slug, task = _split(target)
    branch = f"plan/{slug}" if task is None else f"task/{slug}/{task}"
    root, ref = _repository(options)
    _on_branch(root, ref, branch)
    if not title and task is None:
        title = _title_of(root, slug)
    _start(options, Kind.PLAN, slug, task, branch, {}, title)


@cli.group(context_settings=_SETTINGS)
def task() -> None:
    """One piece of an intent's plan, built on its own branch."""


@task.command("list", context_settings=_SETTINGS)
@click.argument("intent", required=False)
@universal
def task_list(options: Options, intent: str | None) -> None:
    """List the tasks: id, state, size, step, title.

    The target is one intent's slug. Without it, every intent's tasks are listed.
    """
    documents, found = _library(options)
    _warn_of(found)
    rows = _tasks(options, documents)
    if intent is not None:
        slugs = sorted({d.slug for d in documents})
        if intent not in slugs:
            raise _fail(
                f"no intent '{intent}'. The intents are: {', '.join(slugs)}", NO_TARGET
            )
        rows = tuple(row for row in rows if row.slug == intent)
    _emit(
        output.listing(
            rows,
            line=text.task_line,
            identifier=lambda t: t.id,
            document=data.task,
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@task.command("show", context_settings=_SETTINGS)
@click.argument("id")
@universal
def task_show(options: Options, id: str) -> None:
    """Show one task in full. The target is <slug>/<task>."""
    documents, found = _library(options)
    _warn_of(found)
    match = next((row for row in _tasks(options, documents) if row.id == id), None)
    if match is None:
        raise _fail(
            f"no task '{id}'. Ids look like <slug>/<task>. List them: asdlc task list",
            NO_TARGET,
        )
    _emit(
        output.single(
            text=text.task_record(match),
            identifier=match.id,
            document=data.task(match),
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@task.command("new", context_settings=_SETTINGS)
@click.argument("id")
@click.option(
    "--step", required=True, help="The number of the plan step it is cut from."
)
@click.option("--size", help="By complexity, unknowns and risk: 1, 2, 3, 5 or 8.")
@click.option(
    "--depends", multiple=True, help="Another task of this intent. Repeatable."
)
@click.option("--title", default="", help="What gets built.")
@universal
def task_new(
    options: Options,
    id: str,
    step: str,
    size: str | None,
    depends: tuple[str, ...],
    title: str,
) -> None:
    """Cut a task from a plan step, on the intent's tasks branch. Prints the file.

    The target is <slug>/<task>. What the task delivers is copied from the step.
    """
    slug, name = _split(id)
    if name is None:
        raise click.UsageError("a task is named <slug>/<task>")
    root, ref = _repository(options)
    branch = f"tasks/{slug}"
    _on_branch(root, ref, branch)
    documents, _ = library(files.document_texts(root))
    cut_from = next(
        (
            (document, item)
            for document in documents
            if document.slug == slug
            and document.kind is Kind.PLAN
            and not document.task
            for item in document.items
            if item.mark is Mark.STEP and str(item.number) == step
        ),
        None,
    )
    if cut_from is None:
        raise click.UsageError(f"--step {step} is not a step of intent/{slug}/plan.md")
    delivers = tuple(ref_.removeprefix(f"{slug}.") for ref_ in step_delivers(*cut_from))
    fields: dict[str, str | tuple[str, ...]] = {"step": step, "delivers": delivers}
    if depends:
        fields["depends"] = depends
    if size:
        fields["size"] = size
    _start(options, Kind.TASK, slug, name, branch, fields, title or cut_from[1].title)


@cli.group(context_settings=_SETTINGS)
def requirement() -> None:
    """One numbered requirement of a spec, as it stands now."""


@requirement.command("list", context_settings=_SETTINGS)
@click.option("--all", "everything", is_flag=True, help="Replaced and retired too.")
@universal
def requirement_list(options: Options, everything: bool) -> None:
    """List the requirements in force: id, state, area, title."""
    rows = [
        row
        for row in _requirements(options)
        if everything or row.standing is Standing.IN_FORCE
    ]
    _emit(
        output.listing(
            rows,
            line=text.requirement_line,
            identifier=lambda r: r.id,
            document=data.requirement,
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@requirement.command("show", context_settings=_SETTINGS)
@click.argument("id")
@universal
def requirement_show(options: Options, id: str) -> None:
    """Show one requirement in full, with what it replaced and what replaced it.

    The target is a requirement id, such as claims-status.R3.
    """
    known = _requirements(options)
    chain = lineage(known, id)
    if not chain:
        raise _fail(
            f"no requirement '{id}'. Ids look like <intent>.R<number>. "
            "List them: asdlc requirement list --all",
            NO_TARGET,
        )
    found = next(row for row in chain if row.id == id)
    _emit(
        output.single(
            text=text.requirement_record(found, chain),
            identifier=found.id,
            document=data.requirement_in_full(found, chain),
            as_json=options.json,
            quiet=options.quiet,
        )
    )


@cli.group(context_settings=_SETTINGS)
def branch() -> None:
    """A git branch, named for what it adds or builds."""


@branch.command("check", context_settings=_SETTINGS)
@click.argument("name", required=False)
@universal
def branch_check(options: Options, name: str | None) -> None:
    """Judge whether a branch changed only what its documents on main allow.

    The target is a branch. Without it, the current branch is judged.
    Prints one line per file it should not change freely: verdict, path, reason.
    """
    root = git.repository(options.root)
    ref = git.base(root) if root else None
    if root is None or ref is None:
        raise _fail(
            f"{options.root} is not a git repository with a main branch",
            NO_REPOSITORY,
        )
    name = name or git.current_branch(root)
    if not name:
        raise click.UsageError("no branch given, and HEAD is not on one")
    if not git.has_branch(root, name):
        raise _fail(f"no branch '{name}'", NO_TARGET)
    _note(options, f"judging '{name}' against {ref}")
    changed = git.changed_since(root, ref, name)
    found = guard(name, changed, git.documents_on(root, ref))
    _emit(
        output.listing(
            found,
            line=text.ruling_line,
            identifier=lambda r: r.path,
            document=data.ruling,
            as_json=options.json,
            quiet=options.quiet,
        )
    )
    if any(ruling.verdict is Verdict.DENY for ruling in found):
        raise click.exceptions.Exit(FAILED)


@branch.command("new", context_settings=_SETTINGS)
@click.argument("name")
@universal
def branch_new(options: Options, name: str) -> None:
    """Start a branch from main, once the document it builds on is merged.

    The target is the new branch's name, such as spec/claims-status. Prints it.
    """
    root = git.repository(options.root)
    ref = git.base(root) if root else None
    if root is None or ref is None:
        raise _fail(
            f"{options.root} is not a git repository with a main branch",
            NO_REPOSITORY,
        )
    reason = waiting(name, git.documents_on(root, ref))
    if reason is not None:
        raise _fail(f"cannot start '{name}': {reason}", FAILED)
    if not git.create_branch(root, name, ref):
        raise _fail(f"git would not create '{name}'. Does it already exist?", FAILED)
    _note(options, f"created '{name}' from {ref}")
    click.echo(json.dumps(name) if options.json else name)


def _lint_hook() -> None:
    call = read_file_write(sys.stdin)
    if call is None:
        return
    root = git.repository(files.nearest_folder(call.path))
    relative = files.inside(call.path, root) if root else None
    if root is None or relative is None or not relative.startswith("intent/"):
        return  # not a document, so there is nothing to lint
    _, found = library(files.document_texts(root))
    slug = relative.split("/")[1]
    mine = [f for f in found if f.path.startswith(f"intent/{slug}/")]
    _emit(hook_text.lint_feedback(mine))


def _guard_hook() -> None:
    call = read_shell_command(sys.stdin)
    folder = push_folder(call.text) if call else None
    if call is None or folder is None:
        return  # not a git push, so there is nothing to guard
    root = git.repository(call.cwd / folder)
    ref = git.base(root) if root else None
    if root is None or ref is None:
        return  # no repository or no main, so nothing has been accepted yet
    name = git.current_branch(root)
    found = guard(name, git.changed_since(root, ref), git.documents_on(root, ref))
    denied = [ruling for ruling in found if ruling.verdict is Verdict.DENY]
    if denied:
        click.echo(hook_text.push_denial(name, denied))


_HOOKS = {"guard": _guard_hook, "lint": _lint_hook}


@cli.group(context_settings=_SETTINGS)
def hook() -> None:
    """Something Claude Code runs before or after a tool call."""


@hook.command("run", context_settings=_SETTINGS)
@click.argument("name")
@universal
def hook_run(options: Options, name: str) -> None:
    """Run one hook. It reads the tool call as JSON on standard input.

    The target is the hook's name. The hooks are: guard, lint.
    """
    if name not in _HOOKS:
        raise _fail(f"no hook '{name}'. The hooks are: {', '.join(_HOOKS)}", NO_TARGET)
    _HOOKS[name]()


@hook.command("new", context_settings=_SETTINGS)
@click.argument("name")
@click.option("--force", is_flag=True, help="Replace a hook asdlc did not write.")
@universal
def hook_new(options: Options, name: str, force: bool) -> None:
    """Install a git hook in this repository. Prints the file it wrote.

    The target is the git hook's name. The git hooks are: pre-push.
    """
    if name not in hook_text.GIT_HOOKS:
        known = ", ".join(hook_text.GIT_HOOKS)
        raise _fail(f"no git hook '{name}'. The git hooks are: {known}", NO_TARGET)
    root = git.repository(options.root)
    if root is None:
        raise _fail(f"{options.root} is not a git repository", NO_REPOSITORY)
    path = git.hooks_folder(root) / name
    existing = files.read_text(path)
    if existing is not None and not hook_text.ours(existing) and not force:
        raise _fail(
            f"{path} exists and asdlc did not write it. Replace it with --force", FAILED
        )
    files.write_program(path, hook_text.git_hook(name))
    click.echo(json.dumps(str(path)) if options.json else str(path))


def main() -> None:
    """Run the command and turn how it ended into an exit status."""
    try:
        status = cli.main(standalone_mode=False)
    except click.exceptions.Abort:
        sys.exit(INTERRUPTED)
    except click.ClickException as failure:
        failure.show()
        sys.exit(failure.exit_code)
    sys.exit(status if isinstance(status, int) else 0)
