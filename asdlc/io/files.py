"""Files on disk: the documents' text, and where a path sits in a repository."""

from importlib import resources
from pathlib import Path


def document_texts(root: Path) -> tuple[tuple[str, str], ...]:
    """Read every Markdown file under `root/intent` as `(path from root, text)`."""
    files = sorted((root / "intent").rglob("*.md"))
    return tuple(
        (file.relative_to(root).as_posix(), file.read_text()) for file in files
    )


def template(kind: str) -> str:
    """Give the template that ships with asdlc for a kind of document."""
    return resources.files("asdlc").joinpath("templates", f"{kind}.md").read_text()


def write_new(path: Path, text: str) -> bool:
    """Write a file that must not exist yet; False, writing nothing, when it does."""
    if path.exists():
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    return True


def read_text(path: Path) -> str | None:
    """Give a file's text; None when there is no such file."""
    return path.read_text() if path.is_file() else None


def write_program(path: Path, text: str) -> None:
    """Write a file a person or git can run."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text)
    path.chmod(0o755)


def nearest_folder(path: Path) -> Path:
    """Give the closest folder above a path that exists; the file may not yet."""
    return next(parent for parent in path.parents if parent.is_dir())


def inside(path: Path, root: Path) -> str | None:
    """Give a path relative to `root` with forward slashes; None when it is outside."""
    resolved, top = path.resolve(), root.resolve()
    if not resolved.is_relative_to(top):
        return None
    return resolved.relative_to(top).as_posix()
