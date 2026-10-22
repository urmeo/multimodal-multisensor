"""CLI help, current figure drift and prevalidated output regressions."""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from scripts import build_figures, verify_notebooks

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def notebook_checkout(tmp_path):
    root = tmp_path / "checkout"
    (root / "data").mkdir(parents=True)
    (root / "data" / "source.csv").write_text("value\n1\n")
    for folder in verify_notebooks.FOLDERS:
        destination = root / folder
        destination.mkdir(parents=True)
        (destination / "example.ipynb").write_text("{}")
    return root


@pytest.mark.parametrize("missing", verify_notebooks.FOLDERS)
def test_notebook_verifier_rejects_an_empty_analysis_folder(
    notebook_checkout, monkeypatch, missing
):
    (notebook_checkout / missing / "example.ipynb").unlink()
    monkeypatch.setattr(verify_notebooks, "ROOT", notebook_checkout)
    with pytest.raises(ValueError, match="no source notebooks"):
        verify_notebooks.main([])


@pytest.mark.parametrize("existing_path", [None, "another-project"])
def test_notebook_verifier_imports_checkout_without_site_packages(
    notebook_checkout, monkeypatch, existing_path
):
    shutil.copytree(
        ROOT / "mms",
        notebook_checkout / "mms",
        ignore=shutil.ignore_patterns("__pycache__"),
    )
    if existing_path is None:
        monkeypatch.delenv("PYTHONPATH", raising=False)
    else:
        monkeypatch.setenv("PYTHONPATH", existing_path)
    monkeypatch.setattr(verify_notebooks, "ROOT", notebook_checkout)
    run = subprocess.run

    def check_import(command, *, cwd, env, check):
        if existing_path:
            assert env["PYTHONPATH"].endswith(os.pathsep + existing_path)
        result = run(
            [sys.executable, "-S", "-c", "from mms.paths import ROOT; print(ROOT)"],
            cwd=cwd / "notebooks/case-study",
            env=env,
            check=True,
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.stdout.strip() == str(notebook_checkout)
        return result

    monkeypatch.setattr(verify_notebooks.subprocess, "run", check_import)
    assert verify_notebooks.main([]) == 0


def test_notebook_verifier_propagates_execution_failure(notebook_checkout, monkeypatch):
    monkeypatch.setattr(verify_notebooks, "ROOT", notebook_checkout)

    def fail_execution(command, *, cwd, env, check):
        assert "--nbmake" in command
        return subprocess.CompletedProcess(command, returncode=7)

    monkeypatch.setattr(verify_notebooks.subprocess, "run", fail_execution)
    assert verify_notebooks.main([]) == 7


@pytest.mark.parametrize("changed_copy", [False, True], ids=["original", "copy"])
def test_notebook_verifier_rejects_input_mutation(
    notebook_checkout, monkeypatch, changed_copy
):
    monkeypatch.setattr(verify_notebooks, "ROOT", notebook_checkout)

    def mutate_input(command, *, cwd, env, check):
        root = cwd if changed_copy else notebook_checkout
        (root / "data" / "source.csv").write_text("value\n2\n")
        return subprocess.CompletedProcess(command, returncode=0)

    monkeypatch.setattr(verify_notebooks.subprocess, "run", mutate_input)
    with pytest.raises(ValueError, match="notebook execution changed source inputs"):
        verify_notebooks.main([])


@pytest.mark.parametrize(
    "script", ["build_figures", "verify_notebooks", "normalize_kernelspec"]
)
def test_cli_help_and_unknown_argument(script):
    command = [sys.executable, str(ROOT / "scripts" / f"{script}.py")]
    help_result = subprocess.run(
        command + ["--help"], capture_output=True, text=True, timeout=30
    )
    invalid = subprocess.run(
        command + ["--unknown-option"], capture_output=True, text=True, timeout=30
    )
    assert help_result.returncode == 0 and "usage:" in help_result.stdout
    assert invalid.returncode == 2 and "unrecognized arguments" in invalid.stderr


@pytest.mark.parametrize(
    "corruption", ["empty hashes", "truncated hashes", "changed metric"]
)
def test_figure_check_rejects_incomplete_or_stale_artifacts(tmp_path, corruption):
    for name in ("figures.csv", "figures.toml", "reliability.png", "correlation.png"):
        shutil.copy2(ROOT / "outputs" / name, tmp_path / name)
    path = tmp_path / (
        "figures.csv" if corruption == "changed metric" else "figures.toml"
    )
    text = path.read_text()
    if corruption == "empty hashes":
        text = text[: text.index("[figure]")] + "[figure]\n"
    elif corruption == "truncated hashes":
        text = "\n".join(
            line
            for line in text.splitlines()
            if not line.startswith('"correlation.png"')
        )
    else:
        lines = text.splitlines()
        fields = lines[1].split(",")
        fields[-1] = "0.99"
        lines[1] = ",".join(fields)
        text = "\n".join(lines)
    path.write_text(text)
    rows, corr, hashes = build_figures.calculate()
    with pytest.raises(ValueError):
        build_figures.verify(tmp_path, rows, corr, hashes)


@pytest.mark.parametrize("alias", ["source hardlink", "contained nested symlink"])
def test_all_figure_destinations_validated_before_first_write(tmp_path, capsys, alias):
    data_root = tmp_path / "data"
    shutil.copytree(ROOT / "data" / "group_results", data_root / "group_results")
    output = tmp_path / "figures"
    output.mkdir()
    if alias == "source hardlink":
        source = data_root / "group_results" / "HRV_SDNN.csv"
        before = source.read_bytes()
        os.link(source, output / "figures.toml")
        expected_error = "aliases a source observation"
    else:
        (output / "nested").mkdir()
        (output / "reliability.png").symlink_to(
            output / "nested" / "reliability.png"
        )
        expected_error = "one flat output directory"
    assert build_figures.main(
        ["--data-root", str(data_root), "--output-root", str(output)]
    ) == 1
    assert expected_error in capsys.readouterr().err
    assert not (output / "correlation.png").exists()
    assert not (output / "figures.csv").exists()
    if alias == "source hardlink":
        assert source.read_bytes() == before
    else:
        assert not (output / "nested" / "reliability.png").exists()
