"""Documentation builds, links and output preservation."""

import hashlib
from pathlib import Path

import pytest

from scripts import build_docs


def file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def site_repository(tmp_path):
    root = tmp_path / "repository"
    for filename in build_docs.PAGES:
        path = root / filename
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(f"# {path.stem}\n", encoding="utf-8")
    site = root / "docs" / "site"
    site.mkdir()
    (site / "template.html").write_text(
        "<!doctype html><html><head><title>$title</title>"
        '<link rel="stylesheet" href="$root/style.css"></head><body>'
        '<a href="$root/index.html">Home</a><a href="$repository_url">Source</a>'
        '<main id="content">$content</main></body></html>',
        encoding="utf-8",
    )
    (site / "style.css").write_text("body { color: black; }\n", encoding="utf-8")
    return root


def write_site_file(site_repository, name, content):
    path = site_repository / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(content)
    return path


def test_nested_pages_assets_and_encoded_links(site_repository):
    image = write_site_file(site_repository, "images/curve 100%.png", b"image bytes")
    report = write_site_file(
        site_repository, "docs/reports/Study Report.pdf", b"report bytes"
    )
    (site_repository / "README.md").write_text(
        "# Study\n\n[Figures](docs/FIGURES.md#same-title-1)\n\n"
        "| Metric | Value |\n| --- | --- |\n| Sample | 10 |\n",
        encoding="utf-8",
    )
    (site_repository / "docs/FIGURES.md").write_text(
        "# Figures\n\n## Same *title*\n\n## Same title\n\n"
        "[Home](../README.md#study)\n\n"
        "![Curve](../images/curve%20100%25.png?download=1&size=2)\n\n"
        "[Report](reports/Study%20Report.pdf?download=1#page=2)\n",
        encoding="utf-8",
    )

    output = build_docs.build_site(site_repository, ref="abc123")
    figures = (output / "docs/FIGURES.html").read_text()
    assert 'href="../index.html#study"' in figures
    assert 'src="../images/curve%20100%25.png?download=1&amp;size=2"' in figures
    assert 'href="../images/curve%20100%25.png?download=1&amp;size=2"' in figures
    assert 'href="reports/Study%20Report.pdf?download=1#page=2"' in figures
    assert 'href="../style.css"' in figures
    assert 'id="same-title-1"' in figures
    assert "<table>" in (output / "index.html").read_text()
    assert (
        output / image.relative_to(site_repository)
    ).read_bytes() == image.read_bytes()
    assert (
        output / report.relative_to(site_repository)
    ).read_bytes() == report.read_bytes()
    assert len(list(output.rglob("*.html"))) == 4
    build_docs.validate_site(output)


def test_source_links_use_exact_ref_without_publishing_data(site_repository):
    source_files = {
        "data/raw.csv": b"private source rows\n",
        "notebooks/example.ipynb": b"{}\n",
        "scripts/analysis.py": b"print('source')\n",
        "LICENSE": b"MIT license\n",
        "CITATION.cff": b"cff-version: 1.2.0\n",
    }
    for name, content in source_files.items():
        write_site_file(site_repository, name, content)
    write_site_file(site_repository, "images/unlinked.png", b"unused asset")
    links = "\n".join(f"[{name}]({name})" for name in source_files)
    (site_repository / "README.md").write_text(
        f"# Study\n\n{links}\n\n[Notebooks](notebooks)\n", encoding="utf-8"
    )
    before = {
        path: path.read_bytes() for path in site_repository.rglob("*") if path.is_file()
    }

    output = build_docs.build_site(site_repository, ref="a1b2c3")

    page = (output / "index.html").read_text()
    for name in source_files:
        assert f'href="{build_docs.REPOSITORY_URL}/blob/a1b2c3/{name}"' in page
        assert not (output / name).exists()
    assert f'href="{build_docs.REPOSITORY_URL}/tree/a1b2c3/notebooks"' in page
    assert not (output / "images/unlinked.png").exists()
    assert all(path.read_bytes() == content for path, content in before.items())
    assert not (output / "data").exists()


@pytest.mark.parametrize(
    ("link", "message"),
    [
        ("missing.csv", "Missing target"),
        ("../outside.txt", "escapes the repository"),
        ("docs/FIGURES.md#missing-heading", "Missing heading"),
    ],
)
def test_invalid_links_do_not_replace_a_working_site(site_repository, link, message):
    output = build_docs.build_site(site_repository)
    previous = (output / "index.html").read_bytes()
    (site_repository / "README.md").write_text(f"# Study\n\n[Broken]({link})\n")

    with pytest.raises(ValueError, match=message):
        build_docs.build_site(site_repository)

    assert (output / "index.html").read_bytes() == previous
    assert not list(output.parent.glob(".mms-docs-*"))


def test_unknown_output_is_preserved_and_repository_cannot_be_output(
    site_repository, tmp_path
):
    output = tmp_path / "existing"
    output.mkdir()
    retained = output / "important.txt"
    retained.write_text("keep this")
    with pytest.raises(ValueError, match="unknown nonempty output"):
        build_docs.build_site(site_repository, output)
    assert retained.read_text() == "keep this"
    with pytest.raises(ValueError, match="must not contain the repository"):
        build_docs.build_site(site_repository, site_repository)
    with pytest.raises(ValueError, match="must be under build"):
        build_docs.build_site(site_repository, site_repository / "docs/published")


def test_managed_site_rebuild_removes_obsolete_assets(site_repository):
    write_site_file(site_repository, "images/old.png", b"old image")
    readme = site_repository / "README.md"
    readme.write_text("# Study\n\n![Old](images/old.png)\n")
    output = build_docs.build_site(site_repository)
    assert (output / "images/old.png").exists()

    readme.write_text("# Updated study\n")
    assert build_docs.build_site(site_repository) == output
    assert not (output / "images/old.png").exists()
    assert "Updated study" in (output / "index.html").read_text()


def test_symlink_target_cannot_publish_files_outside_repository(
    site_repository, tmp_path
):
    external = tmp_path / "outside.pdf"
    external.write_bytes(b"outside document")
    (site_repository / "report.pdf").symlink_to(external)
    (site_repository / "README.md").write_text("# Study\n\n[Report](report.pdf)\n")

    with pytest.raises(ValueError, match="escapes the repository"):
        build_docs.build_site(site_repository)


def test_source_page_cannot_be_a_symlink_outside_repository(site_repository, tmp_path):
    external = tmp_path / "outside.md"
    external.write_text("# Outside document\n")
    page = site_repository / "README.md"
    page.unlink()
    page.symlink_to(external)

    with pytest.raises(ValueError, match="Source escapes the repository"):
        build_docs.build_site(site_repository)


def test_site_installation_failure_restores_previous_build(
    site_repository, monkeypatch
):
    output = build_docs.build_site(site_repository)
    before = file_hashes(output)
    (site_repository / "README.md").write_text("# Updated study\n")
    rename = Path.rename

    def fail_install(path, target):
        if path.name.startswith(".mms-docs-") and not path.name.startswith(
            ".mms-docs-backup-"
        ):
            raise PermissionError("simulated installation failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_install)
    with pytest.raises(PermissionError, match="installation failure"):
        build_docs.build_site(site_repository)
    assert file_hashes(output) == before
    assert not list(output.parent.glob(".mms-docs-*"))


def test_site_failed_rollback_preserves_previous_build_in_backup(
    site_repository, monkeypatch
):
    output = build_docs.build_site(site_repository)
    before = file_hashes(output)
    (site_repository / "README.md").write_text("# Updated study\n")
    rename = Path.rename

    def fail_install_and_restore(path, target):
        if path.name.startswith(".mms-docs-"):
            raise PermissionError("simulated rename failure")
        return rename(path, target)

    monkeypatch.setattr(Path, "rename", fail_install_and_restore)
    with pytest.raises(OSError, match="previous build is preserved") as error:
        build_docs.build_site(site_repository)
    backups = list(output.parent.glob(".mms-docs-backup-*"))
    assert len(backups) == 1 and str(backups[0]) in str(error.value)
    assert file_hashes(backups[0]) == before
    assert not output.exists()
    assert set(output.parent.glob(".mms-docs-*")) == set(backups)
