#!/usr/bin/env python3
"""Check notebook kernel metadata for Python 3; update it with --write."""

from __future__ import annotations

import argparse
import os
import shutil
import sys
import tempfile
from pathlib import Path

import nbformat

ROOT = Path(__file__).resolve().parents[1]
PORTABLE = {"name": "python3", "display_name": "Python 3", "language": "python"}


def notebook_paths() -> list[Path]:
    root = ROOT.resolve()
    notebooks = []
    for folder in ("case-study", "individual", "group"):
        directory = ROOT / "notebooks" / folder
        if (ROOT / "notebooks").is_symlink() or directory.is_symlink():
            raise ValueError(f"Notebook directories must not be symlinks: {directory}")
        if not directory.resolve().is_relative_to(root):
            raise ValueError(f"Notebook directory escapes the repository: {directory}")
        sources = sorted(directory.glob("*.ipynb"))
        if not sources:
            raise ValueError(f"No source notebooks in {directory}")
        for path in sources:
            if path.is_symlink() or not path.resolve().is_relative_to(root):
                raise ValueError(
                    f"Notebook must be a repository file, not a symlink: {path}"
                )
            if not path.is_file() or path.stat().st_nlink != 1:
                raise ValueError(
                    f"Notebook must be a regular file without hard links: {path}"
                )
            notebooks.append(path)
    return notebooks


def write_notebooks(pending: list[tuple[Path, nbformat.NotebookNode]]) -> None:
    replacements = []
    try:
        for path, notebook in pending:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                dir=path.parent,
                prefix=f".{path.stem}-",
                suffix=".ipynb",
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                replacements.append((temporary, path))
                nbformat.write(notebook, stream)
            shutil.copymode(path, temporary)
        for temporary, path in replacements:
            os.replace(temporary, path)
    finally:
        for temporary, _ in replacements:
            temporary.unlink(missing_ok=True)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument(
        "--write",
        action="store_true",
        help="save Python 3 kernel metadata in notebooks",
    )
    args = parser.parse_args(argv)
    pending = []
    for path in notebook_paths():
        try:
            notebook = nbformat.read(path, as_version=4)
            nbformat.validate(notebook)
        except (AttributeError, TypeError) as error:
            raise ValueError(f"Invalid notebook structure: {path}") from error
        if (
            notebook.metadata.get("kernelspec") != PORTABLE
            or notebook.metadata.get("language_info", {}).get("name") != "python"
        ):
            notebook.metadata["kernelspec"] = dict(PORTABLE)
            notebook.metadata.setdefault("language_info", {})["name"] = "python"
            pending.append((path, notebook))
    if args.write:
        write_notebooks(pending)
    print(
        f"Python 3 kernel metadata: {len(pending)} notebooks "
        f"{'updated' if args.write else 'need changes'}."
    )
    return 1 if pending and not args.write else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, nbformat.ValidationError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
