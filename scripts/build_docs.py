#!/usr/bin/env python3
"""Build the documentation site without publishing source recordings."""

from __future__ import annotations

import argparse
from html import escape, unescape
from html.parser import HTMLParser
from pathlib import Path
import posixpath
import re
import shutil
from string import Template
import tempfile
from urllib.parse import quote, unquote, urlsplit, urlunsplit

import mistune


REPOSITORY_URL = "https://github.com/urmeo/multimodal-multisensor"
PAGES = (
    "README.md",
    "CONTRIBUTING.md",
    "SECURITY.md",
    "DATA_PROVENANCE.md",
    "DATA_ETHICS.md",
    "DATA_LICENSE.md",
    "NOTICE.md",
    "docs/FIGURES.md",
    "docs/REPORT_STATUS.md",
)
ASSET_SUFFIXES = {".svg", ".png", ".jpg", ".jpeg", ".pdf"}
BUILD_MARKER = ".mms-docs-build"
MARKER_CONTENT = "multimodal-multisensor documentation\n"


def page_path(source: Path) -> Path:
    return Path("index.html") if source == Path("README.md") else source.with_suffix(".html")


def source_file(repository: Path, relative: Path) -> Path:
    path = (repository / relative).resolve()
    if not path.is_relative_to(repository):
        raise ValueError(f"Source escapes the repository: {relative}")
    if not path.is_file():
        raise ValueError(f"Missing source file: {relative}")
    return path


class SiteRenderer(mistune.HTMLRenderer):
    def __init__(self, repository: Path, source: Path, ref: str, assets: set[Path]):
        super().__init__(escape=True)
        self.repository = repository
        self.source = source
        self.ref = ref
        self.assets = assets
        self.heading_ids: set[str] = set()

    def local_url(self, url: str) -> str:
        parts = urlsplit(url)
        if parts.scheme or parts.netloc or not parts.path:
            return url
        decoded = unquote(parts.path)
        target = (
            self.repository / decoded.lstrip("/")
            if decoded.startswith("/")
            else self.repository / self.source.parent / decoded
        ).resolve()
        if not target.is_relative_to(self.repository):
            raise ValueError(f"Link escapes the repository in {self.source}: {url}")
        if not target.exists():
            raise ValueError(f"Missing target in {self.source}: {url}")
        relative = target.relative_to(self.repository)
        if relative.as_posix() in PAGES:
            output = page_path(relative)
        elif target.is_file() and target.suffix.lower() in ASSET_SUFFIXES:
            self.assets.add(relative)
            output = relative
        else:
            kind = "tree" if target.is_dir() else "blob"
            github_path = (
                f"{REPOSITORY_URL}/{kind}/{quote(self.ref, safe='')}/"
                f"{quote(relative.as_posix(), safe='/')}"
            )
            return urlunsplit((*urlsplit(github_path)[:3], parts.query, parts.fragment))
        path = posixpath.relpath(output.as_posix(), page_path(self.source).parent.as_posix())
        return urlunsplit(("", "", quote(path, safe="/"), parts.query, parts.fragment))

    def link(self, text: str, url: str, title: str | None = None) -> str:
        return super().link(text, self.local_url(url), title)

    def image(self, text: str, url: str, title: str | None = None) -> str:
        url = self.local_url(url)
        return super().link(super().image(text, url, title), url, title)

    def heading(self, text: str, level: int, **attrs: object) -> str:
        plain = unescape(re.sub(r"<[^>]*>", "", text)).lower()
        slug = "".join(char for char in plain if char.isalnum() or char in " _-")
        slug = re.sub(r"\s+", "-", slug.strip()) or "section"
        identifier = slug
        suffix = 1
        while identifier in self.heading_ids:
            identifier = f"{slug}-{suffix}"
            suffix += 1
        self.heading_ids.add(identifier)
        return super().heading(text, level, id=identifier)


class PageLinks(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.ids: set[str] = set()
        self.links: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        for name, value in attrs:
            if value is None:
                continue
            if name == "id":
                self.ids.add(value)
            elif name in {"href", "src"}:
                self.links.append(value)


def validate_site(directory: Path) -> None:
    pages: dict[Path, PageLinks] = {}
    for path in directory.rglob("*.html"):
        parser = PageLinks()
        parser.feed(path.read_text(encoding="utf-8"))
        pages[path] = parser
    for page, parser in pages.items():
        for url in parser.links:
            parts = urlsplit(url)
            if parts.scheme or parts.netloc:
                continue
            if parts.path.startswith("/"):
                raise ValueError(f"Site link needs a relative path in {page.name}: {url}")
            target = (page.parent / unquote(parts.path)).resolve() if parts.path else page
            if not target.is_relative_to(directory) or not target.is_file():
                raise ValueError(f"Missing site target in {page.name}: {url}")
            if (
                parts.fragment
                and target in pages
                and unquote(parts.fragment) not in pages[target].ids
            ):
                raise ValueError(f"Missing heading in {page.name}: {url}")


def build_site(repository: Path, output: Path | None = None, ref: str = "main") -> Path:
    repository = repository.resolve()
    destination = (output or repository / "build" / "docs").resolve()
    managed_output = repository / "build" / "docs"
    if destination == repository or repository.is_relative_to(destination):
        raise ValueError("The output must not contain the repository.")
    if destination.is_relative_to(repository) and not destination.is_relative_to(repository / "build"):
        raise ValueError("An output inside the repository must be under build/.")
    if destination.exists() and not destination.is_dir():
        raise ValueError(f"The output is not a directory: {destination}")
    if destination.exists() and any(destination.iterdir()):
        marker = destination / BUILD_MARKER
        if (
            destination != managed_output
            or not marker.is_file()
            or marker.read_text(encoding="utf-8") != MARKER_CONTENT
        ):
            raise ValueError(f"Refusing to replace an unknown nonempty output: {destination}")
    if not ref or any(char.isspace() for char in ref):
        raise ValueError("The GitHub ref must be nonempty and contain no whitespace.")
    template_file = source_file(repository, Path("docs/site/template.html"))
    stylesheet = source_file(repository, Path("docs/site/style.css"))
    template = Template(template_file.read_text(encoding="utf-8"))
    assets: set[Path] = set()
    destination.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix=".mms-docs-", dir=destination.parent) as temporary:
        staging = Path(temporary).resolve()
        for filename in PAGES:
            source = Path(filename)
            markdown = source_file(repository, source).read_text(encoding="utf-8")
            renderer = SiteRenderer(repository, source, ref, assets)
            content = mistune.create_markdown(renderer=renderer, plugins=["table"])(markdown)
            title = next(
                (line[2:].strip() for line in markdown.splitlines() if line.startswith("# ")),
                source.stem,
            )
            relative = page_path(source)
            target = staging / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            root = posixpath.relpath(".", relative.parent.as_posix())
            html = template.substitute(
                title=escape(title), content=content, root=root, repository_url=REPOSITORY_URL
            )
            target.write_text(html, encoding="utf-8")
        for asset in sorted(assets):
            target = staging / asset
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copyfile(source_file(repository, asset), target)
        shutil.copyfile(stylesheet, staging / "style.css")
        (staging / ".nojekyll").touch()
        (staging / BUILD_MARKER).write_text(MARKER_CONTENT, encoding="utf-8")
        validate_site(staging)
        if destination.exists():
            shutil.rmtree(destination)
        staging.rename(destination)
    return destination


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, help="Output directory (default: build/docs)")
    parser.add_argument("--ref", default="main", help="GitHub revision for source links (default: main)")
    args = parser.parse_args()
    repository = Path(__file__).resolve().parents[1]
    try:
        output = build_site(repository, args.output, args.ref)
    except (OSError, ValueError, KeyError) as error:
        parser.exit(1, f"Documentation build failed: {error}\n")
    print(f"Built {len(PAGES)} documentation pages in {output}")


if __name__ == "__main__":
    main()
