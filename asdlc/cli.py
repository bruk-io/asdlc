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

from asdlc.domain.documents import Document, Finding
from asdlc.domain.guard import Verdict, guard, waiting
from asdlc.domain.lint import library
from asdlc.domain.requirements import Requirement, Standing, lineage, requirements
from asdlc.domain.shell import push_folder
from asdlc.io import files, git
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


def _requirements(options: Options) -> tuple[Requirement, ...]:
    documents, found = _library(options)
    if found:
        click.echo(
            f"Warning: {len(found)} finding(s) in the documents, so this may be "
            "wrong. Run: asdlc document check",
            err=True,
        )
    return requirements(documents)


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
