"""Data contracts, file safety, notebook execution and documentation."""

from __future__ import annotations

import ast
import hashlib
import json
import os
import shutil
import stat
import subprocess
import sys
from pathlib import Path

import nbformat
import numpy as np
import pandas as pd
import pytest

from mms import io, paths
from scripts import (
    build_docs,
    build_figures,
    build_group_summaries,
    deidentify_timestamps,
    normalize_kernelspec,
    verify_notebooks,
)

ROOT = Path(__file__).resolve().parents[1]
SOURCE_CSVS = tuple(ROOT / "data" / name for name in paths.SOURCE_CSV_RELATIVE)
NOTEBOOKS = sorted(
    path
    for folder in ("case-study", "individual", "group")
    for path in (ROOT / "notebooks" / folder).glob("*.ipynb")
)


def file_hashes(root):
    return {
        path.relative_to(root).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


@pytest.fixture
def source_dataset(tmp_path):
    root = tmp_path / "source"
    for name in paths.SOURCE_CSV_RELATIVE:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        pd.DataFrame(
            {
                "datetime": ["2001/02/03 04:05:00.000", "2001/02/03 04:05:01.000"],
                "value": [1, 2],
            }
        ).to_csv(destination, index=False)
    for name in paths.SOURCE_RAW_RELATIVE:
        destination = root / name
        destination.parent.mkdir(parents=True, exist_ok=True)
        destination.write_text("reltime;ibi;iSensor\n0;800;3\n1;810;3\n")
    expected = {metric: [] for metric in paths.GROUP_METRICS}
    for session in (1, 2, 3):
        ibi = pd.DataFrame(
            {
                "iSensor": [3, 3, 5, 5],
                "ibi": [800, 800 + 10 * session, 900, 900 + 20 * session],
            }
        )
        eye = pd.DataFrame(
            {
                "iSensor": [0] * 4,
                "pupilQ": [0.8] * 4,
                "pupil": [2, 2 + 0.1 * session, 2 + 0.4 * session, 2 + 0.7 * session],
            }
        )
        durations = np.array([1, 2 * session, 3 * session, 4 * session], dtype=float)
        starts = pd.date_range("2001-02-03T04:05:00Z", periods=4, freq="1min")
        psych = pd.DataFrame(
            {
                "Type": ["synthetic"] * 4,
                "Test": ["synthetic"] * 4,
                "Question": ["fixture"] * 4,
                "Answer": [1] * 4,
                "Time(s)": durations,
                "Question Start Time": starts.astype(str),
                "Question Answer Time": (
                    starts + pd.to_timedelta(durations, unit="s")
                ).astype(str),
            }
        )
        for name, frame in (
            (f"processed/ibi_{session:02d}.csv", ibi),
            (f"processed/sed_fix_{session:02d}.csv", eye),
            (f"psychometric/Psychometric_Test_Results_{session:02d}.csv", psych),
        ):
            frame.to_csv(root / "case-study" / name, index=False)
        expected["HRV_SDNN"].append(ibi["ibi"].std(ddof=1))
        expected["Pupil_Dilation_STD"].append(eye["pupil"].std(ddof=1))
        expected["Psychometric_Test_Duration_STD"].append(psych["Time(s)"].std(ddof=1))
    for metric, values in expected.items():
        frame = pd.DataFrame(
            {
                "Participant": paths.PARTICIPANTS,
                "Session 01": np.arange(100.0, 110),
                "Session 02": np.arange(200.0, 210),
                "Session 03": np.arange(300.0, 310),
            }
        )
        frame.loc[1, list(paths.SESSION_COLUMNS)] = values
        if metric == "Psychometric_Test_Duration_STD":
            frame.loc[1, "Session 01"] += 2e-5
        frame.to_csv(root / "group_results" / f"{metric}.csv", index=False)
    return root


def run_cli(module, *args):
    environment = dict(os.environ, PYTHONDONTWRITEBYTECODE="1")
    return subprocess.run(
        [sys.executable, "-m", module, *map(str, args)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        env=environment,
        timeout=30,
    )


def test_explicit_dataset_root_and_missing_checkout_data(
    source_dataset, monkeypatch, tmp_path
):
    assert len(io.load_ibi(1, data_root=source_dataset)) == 4
    assert io.load_raw("ibi", data_root=source_dataset)["ibi"].tolist() == [800, 810]
    monkeypatch.setattr(paths, "DATA", tmp_path / "missing-data")
    with pytest.raises(
        FileNotFoundError, match="Dataset directory is absent.*data_root"
    ):
        io.load_ibi(1)


@pytest.mark.parametrize("session", [0, 4, -1, True, 1.2, "01"])
def test_invalid_stream_session_rejected(session, source_dataset):
    with pytest.raises(ValueError, match="session"):
        io.load_ibi(session, data_root=source_dataset)


def test_malformed_legacy_psychometric_rejected(source_dataset):
    with pytest.raises(ValueError, match="legacy.*malformed"):
        io.load_psychometric(0, source="individual", data_root=source_dataset)
    malformed = pd.DataFrame({"Score": [3.0], "Time(s)": ["2001-02-03T04:05:00Z"]})
    with pytest.raises(ValueError, match="noncanonical.*Score holds duration"):
        io.validate_psychometric(malformed)


def test_datetime_preserves_awareness_and_requires_declared_naive_zone():
    aware = io.parse_datetime(pd.Series(["2001-02-03T04:05:00+02:00"], dtype="string"))
    assert aware.dt.tz is not None and aware.iloc[0].utcoffset().total_seconds() == 7200
    naive = io.parse_datetime(pd.Series(["2001/02/03 04:05:00.000"]))
    assert naive.dt.tz is None
    mapped = io.parse_datetime(
        pd.Series(["2001/02/03 04:05:00.000"]), naive_timezone="UTC"
    )
    assert str(mapped.dt.tz) == "UTC"


@pytest.mark.parametrize(
    "values",
    [
        ["2001-01-01", "bad"],
        ["2001-01-01", None],
        ["2001-01-01", "2001-01-01T00:00:00Z"],
        [1000, 2000],
    ],
)
def test_datetime_rejects_incomplete_ambiguous_or_mixed_columns(values):
    with pytest.raises(ValueError):
        io.parse_datetime(pd.Series(values))


def test_explicit_missing_datetime_keeps_original_position():
    parsed = io.parse_datetime(
        pd.Series([None, "2001-01-01T00:00:00Z"], index=[4, 9]), allow_missing=True
    )
    assert parsed.index.tolist() == [4, 9] and pd.isna(parsed.iloc[0])
    assert parsed.dt.tz is not None


@pytest.mark.parametrize(
    "kind", ["third_identity", "changed_value", "wrong_identity", "within_value"]
)
def test_duplicate_allowlist_exact_values_identities_and_multiplicity(kind):
    metric = "HRV_SDNN" if kind == "within_value" else "Psychometric_Test_Duration_STD"
    frame = io.load_group_summary(metric).copy()
    if kind == "third_identity":
        frame.loc[frame.Participant == "P09", "Session 01"] = 4.409281089248826
    elif kind == "changed_value":
        frame.loc[frame.Participant.isin(["P07", "P08"]), "Session 01"] = 9.123
    elif kind == "wrong_identity":
        frame.loc[frame.Participant == "P08", "Session 01"] = 8.123
        frame.loc[frame.Participant == "P09", "Session 01"] = 4.409281089248826
    else:
        frame.loc[frame.Participant == "P01", ["Session 02", "Session 03"]] = 9.123
    with pytest.raises(ValueError, match="duplicate"):
        io.validate_group_summary(frame, metric)


@pytest.mark.parametrize(
    "kind", ["missing", "duplicated", "wrong_columns", "nonfinite"]
)
def test_group_summary_canonical_schema_required(kind, source_dataset):
    frame = io.load_group_summary("HRV_SDNN", data_root=source_dataset)
    if kind == "missing":
        frame = frame.iloc[:-1]
    elif kind == "duplicated":
        frame.loc[1, "Participant"] = "P01"
    elif kind == "wrong_columns":
        frame = frame.rename(columns={"Session 01": "Session 1"})
    else:
        frame.loc[0, "Session 01"] = np.inf
    with pytest.raises(ValueError):
        io.validate_group_summary(frame, "HRV_SDNN")


def test_complex_summary_and_interval_values_are_rejected(source_dataset):
    frame = io.load_group_summary("HRV_SDNN", data_root=source_dataset)
    frame["Session 01"] = frame["Session 01"].astype(complex) + 1j
    with pytest.raises(ValueError, match="real"):
        io.validate_group_summary(frame, "HRV_SDNN")
    with pytest.raises(ValueError, match="real"):
        build_group_summaries._numeric(
            pd.DataFrame({"ibi": [800 + 1j, 810 + 2j]}), "ibi"
        )


def test_summary_check_metric_tolerances_and_no_writes(source_dataset, tmp_path):
    before = file_hashes(source_dataset)
    result = run_cli(
        "scripts.build_group_summaries", "--check", "--data-root", source_dataset
    )
    assert result.returncode == 0, result.stderr
    assert "within tolerance" in result.stdout and file_hashes(source_dataset) == before
    assert not (tmp_path / "review").exists()
    target = source_dataset / "group_results/Psychometric_Test_Duration_STD.csv"
    frame = pd.read_csv(target)
    frame.loc[1, "Session 01"] += 4e-5
    frame.to_csv(target, index=False)
    before = file_hashes(source_dataset)
    result = run_cli(
        "scripts.build_group_summaries", "--check", "--data-root", source_dataset
    )
    assert result.returncode == 1 and "DRIFT" in result.stdout
    assert file_hashes(source_dataset) == before


def test_summary_explicit_output_and_both_duplicate_flags(source_dataset, tmp_path):
    for metric, identities, columns, value in (
        ("HRV_SDNN", ["P01"], ["Session 02", "Session 03"], 65.39381048265373),
        (
            "Psychometric_Test_Duration_STD",
            ["P07", "P08"],
            ["Session 01"],
            4.409281089248826,
        ),
    ):
        target = source_dataset / "group_results" / f"{metric}.csv"
        frame = pd.read_csv(target)
        frame.loc[frame.Participant.isin(identities), columns] = value
        frame.to_csv(target, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "review"
    assert (
        build_group_summaries.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 0
    )
    assert (output / "MANIFEST.json").is_file()
    manifest = json.loads((output / "MANIFEST.json").read_text())
    assert len(manifest["known_equal_value_issues"]) == 2
    assert manifest["participant_identity_independently_established"] is False
    assert len(list(output.glob("*.csv"))) == 4
    assert file_hashes(source_dataset) == before


def test_summary_full_prevalidation_prevents_partial_output(source_dataset, tmp_path):
    target = source_dataset / "case-study/psychometric/Psychometric_Test_Results_03.csv"
    frame = pd.read_csv(target).drop(columns="Question Answer Time")
    frame.to_csv(target, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "review"
    assert (
        build_group_summaries.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert not output.exists() and file_hashes(source_dataset) == before


@pytest.mark.parametrize("kind", ["ibi", "sed_fix"])
def test_summary_fractional_channels_fail_before_output(
    kind, source_dataset, tmp_path, capsys
):
    target = source_dataset / "case-study/processed" / f"{kind}_03.csv"
    frame = pd.read_csv(target)
    frame["iSensor"] = [1.1, 1.1, 1.9, 1.9]
    frame.to_csv(target, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "review"
    assert (
        build_group_summaries.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert "integer channel identifiers" in capsys.readouterr().err
    assert not output.exists() and file_hashes(source_dataset) == before
    streams = {
        3: (
            io.load_ibi(3, data_root=source_dataset),
            io.load_fixation(3, data_root=source_dataset),
            pd.DataFrame(),
        )
    }
    with pytest.raises(ValueError, match="integer channel identifiers"):
        build_group_summaries.filtered_sample_metrics(streams)


@pytest.mark.parametrize(
    "module", ["scripts.build_group_summaries", "scripts.deidentify_timestamps"]
)
def test_help_and_parser_errors_never_write_sources(module, source_dataset):
    before = file_hashes(source_dataset)
    assert run_cli(module, "--help").returncode == 0
    assert run_cli(module, "--typo").returncode == 2
    assert file_hashes(source_dataset) == before


def test_output_roots_reject_source_parent_symlink_and_hardlink(
    source_dataset, tmp_path
):
    for destination in (
        source_dataset,
        source_dataset / "generated",
        source_dataset.parent,
    ):
        with pytest.raises(ValueError, match="separate"):
            paths.resolve_output_root(destination, data_root=source_dataset)
    link = tmp_path / "link"
    link.symlink_to(source_dataset, target_is_directory=True)
    with pytest.raises(ValueError, match="separate"):
        paths.resolve_output_root(link, data_root=source_dataset)
    output = tmp_path / "review"
    output.mkdir()
    alias = output / "HRV_SDNN_P02_consistency.csv"
    os.link(source_dataset / "group_results/HRV_SDNN.csv", alias)
    before = file_hashes(source_dataset)
    assert (
        build_group_summaries.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert (
        not (output / "MANIFEST.json").exists()
        and file_hashes(source_dataset) == before
    )
    with pytest.raises(ValueError):
        paths.output_path(
            output, "../source/group_results/HRV_SDNN.csv", data_root=source_dataset
        )


def test_calendar_shift_stringdtype_renamed_columns_and_aware_elapsed_time():
    frame = pd.DataFrame(
        {
            "renamed clock": pd.Series(
                ["2001-02-03T04:05:00+02:00", "2001-02-03T04:05:01+02:00"],
                dtype="string",
            ),
            "value": [2, 3],
        }
    )
    before = frame.copy(deep=True)
    shifted, columns = deidentify_timestamps.shift_frame(frame)
    assert columns == ["renamed clock"]
    parsed = io.parse_datetime(shifted["renamed clock"])
    assert parsed.iloc[0].year == 2000 and parsed.dt.tz is not None
    assert (parsed.iloc[1] - parsed.iloc[0]).total_seconds() == 1
    pd.testing.assert_frame_equal(frame, before)


def test_calendar_detection_checks_later_rows_and_refuses_parse_loss():
    frame = pd.DataFrame(
        {
            "renamed clock": pd.Series(
                ["bad"] * 60 + ["2001-02-03T04:05:00Z"], dtype="string"
            )
        }
    )
    with pytest.raises(ValueError, match="invalid"):
        deidentify_timestamps.shift_frame(frame)


def test_shift_validates_full_inventory_before_write_without_offsets_in_logs(
    source_dataset, tmp_path, capsys
):
    legacy = source_dataset / "individual/psychometric/Psychometric_Test_Results_00.csv"
    pd.DataFrame(
        {
            "Time(s)": ["2001-02-03T04:05:00Z"],
            "Question Start Time": ["2001-02-03T04:05:03Z"],
            "Answer Time": [None],
            "Score": [3.0],
        }
    ).to_csv(legacy, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "shifted"
    assert (
        deidentify_timestamps.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 0
    )
    assert file_hashes(source_dataset) == before
    text = capsys.readouterr().out
    assert "2001" not in text and "offset" not in text and "04:05" not in text
    assert "Raw TXT" in text and "awareness-specific" in text
    assert (output / legacy.relative_to(source_dataset)).is_file()
    assert not list(output.rglob("*.txt"))
    shifted = pd.read_csv(output / legacy.relative_to(source_dataset))
    assert pd.isna(shifted["Answer Time"].iloc[0])
    assert (
        io.parse_datetime(shifted["Question Start Time"])
        - io.parse_datetime(shifted["Time(s)"])
    ).dt.total_seconds().iloc[0] == 3


@pytest.mark.parametrize(
    "relative",
    [
        f"case-study/psychometric/Psychometric_Test_Results_{session:02d}_modified.csv"
        for session in (1, 2, 3)
    ]
    + ["individual/psychometric/Psychometric_Test_Results_00.csv"],
)
def test_shift_preserves_leading_field_with_missing_header(
    source_dataset, tmp_path, relative
):
    source = source_dataset / relative
    source.write_text(
        "Question,Score,datetime\n"
        "HADS,first,2,2001-02-03T04:05:00Z\n"
        "STAI,second,3,2001-02-03T04:05:01Z\n"
    )
    before = file_hashes(source_dataset)
    output = tmp_path / "shifted"
    assert deidentify_timestamps.run(source_dataset, output_root=output) == 0
    result = pd.read_csv(output / relative)
    assert result.columns.tolist() == ["source_index", "Question", "Score", "datetime"]
    assert result["source_index"].tolist() == ["HADS", "STAI"]
    assert result["Question"].tolist() == ["first", "second"]
    assert result["Score"].tolist() == [2, 3]
    stamps = io.parse_datetime(result["datetime"])
    assert stamps.iloc[0] == pd.Timestamp("2000-01-01T00:00:00Z")
    assert (stamps.iloc[1] - stamps.iloc[0]).total_seconds() == 1
    assert file_hashes(source_dataset) == before


def test_shift_parse_failure_and_missing_inventory_never_create_output(
    source_dataset, tmp_path
):
    path = source_dataset / "individual/processed/sed_03.csv"
    frame = pd.read_csv(path)
    frame.loc[1, "datetime"] = "bad"
    frame.to_csv(path, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "shifted"
    assert (
        deidentify_timestamps.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert not output.exists() and file_hashes(source_dataset) == before
    path.unlink()
    assert (
        deidentify_timestamps.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert not output.exists()


@pytest.mark.parametrize(
    "csv",
    [
        "source_index,datetime\nHADS,first,2001-02-03T04:05:00Z\n",
        "Question,datetime\nHADS,first,2,2001-02-03T04:05:00Z\n",
    ],
)
def test_shift_ambiguous_inferred_index_fails_before_writing(
    source_dataset, tmp_path, csv
):
    source = (
        source_dataset
        / "case-study/psychometric/Psychometric_Test_Results_01_modified.csv"
    )
    source.write_text(csv)
    before = file_hashes(source_dataset)
    output = tmp_path / "shifted"
    assert (
        deidentify_timestamps.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert not output.exists() and file_hashes(source_dataset) == before


def test_shift_in_place_flag_rejected_and_dry_run_immutable(source_dataset):
    before = file_hashes(source_dataset)
    result = run_cli("scripts.deidentify_timestamps", "--data-root", source_dataset)
    assert result.returncode == 0, result.stderr
    assert file_hashes(source_dataset) == before
    result = run_cli(
        "scripts.deidentify_timestamps", "--apply", "--data-root", source_dataset
    )
    assert result.returncode == 2 and file_hashes(source_dataset) == before


def test_generated_csv_is_excluded_from_inventory(source_dataset):
    generated = source_dataset / "group_results/reconstructed"
    generated.mkdir()
    (generated / "bad.csv").write_text("corrupt")
    assert len(deidentify_timestamps.collect(source_dataset)) == 51
    assert generated / "bad.csv" not in paths.source_files(source_dataset)


def test_shift_source_hardlink_and_directory_destination_fail_before_any_write(
    source_dataset, tmp_path
):
    output = tmp_path / "review"
    relative = Path("individual/processed/sed_03.csv")
    destination = output / relative
    destination.parent.mkdir(parents=True)
    os.link(source_dataset / relative, destination)
    before = file_hashes(source_dataset)
    output_before = file_hashes(output)
    assert (
        deidentify_timestamps.main(
            ["--data-root", str(source_dataset), "--output-root", str(output)]
        )
        == 1
    )
    assert (
        file_hashes(output) == output_before and file_hashes(source_dataset) == before
    )
    destination.unlink()
    destination.mkdir()
    with pytest.raises(ValueError, match="must be a file"):
        paths.output_path(output, relative, data_root=source_dataset)


def test_filtered_metrics_keep_channels_separate_and_share_pupil_quality():
    streams = {
        1: (
            pd.DataFrame({"iSensor": [3, 5, 3, 5], "ibi": [800, 1000, 810, 1020]}),
            pd.DataFrame(
                {
                    "iSensor": [0] * 4,
                    "pupil": [2, 3, 99, 99],
                    "pupilQ": [0.5, 0.5, 0.4, 1.1],
                }
            ),
            pd.DataFrame(),
        )
    }
    records = build_group_summaries.filtered_sample_metrics(streams)
    assert len(records) == 3
    intervals = [
        record for record in records if record["metric"] == "interval_sample_sd_ms"
    ]
    assert [record["channel"] for record in intervals] == [3, 5]
    assert [record["value"] for record in intervals] == pytest.approx(
        [10 / 2**0.5, 20 / 2**0.5]
    )
    pupil = next(
        record
        for record in records
        if record["metric"] == "pupil_sample_sd_reported_mm"
    )
    assert pupil["n_samples"] == 2 and pupil["value"] == pytest.approx(1 / 2**0.5)


def test_output_hardlink_to_other_dataset_artifact_is_rejected(
    source_dataset, tmp_path
):
    artifact = source_dataset / "group_results/historical.png"
    artifact.write_bytes(b"historical image bytes")
    output = tmp_path / "review"
    output.mkdir()
    os.link(artifact, output / "result.csv")
    with pytest.raises(ValueError, match="aliases"):
        paths.output_path(output, "result.csv", data_root=source_dataset)
    assert artifact.read_bytes() == b"historical image bytes"


@pytest.mark.parametrize(
    "module", ["scripts.build_group_summaries", "scripts.deidentify_timestamps"]
)
@pytest.mark.parametrize("kind", ["input", "output"])
def test_cyclic_roots_fail_helpfully_without_traceback_or_writes(
    module, kind, source_dataset, tmp_path
):
    loop = tmp_path / "loop"
    loop.symlink_to("loop")
    before = file_hashes(source_dataset)
    arguments = (
        ["--data-root", loop]
        if kind == "input"
        else ["--data-root", source_dataset, "--output-root", loop]
    )
    result = run_cli(module, *arguments)
    assert result.returncode == 1
    assert "cyclic symlink" in result.stderr and "Traceback" not in result.stderr
    assert file_hashes(source_dataset) == before


@pytest.mark.parametrize(
    "module", ["scripts.build_group_summaries", "scripts.deidentify_timestamps"]
)
def test_cli_flags_cannot_be_abbreviated(module, source_dataset):
    before = file_hashes(source_dataset)
    assert run_cli(module, "--data-r", source_dataset).returncode == 2
    assert run_cli(module, "--output-r", source_dataset).returncode == 2
    assert file_hashes(source_dataset) == before


def test_custom_dataset_outputs_still_protect_canonical_dataset(
    source_dataset, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    canonical = project / "data"
    canonical.mkdir(parents=True)
    source = canonical / "observation.csv"
    source.write_text("value\n1\n")
    monkeypatch.setattr(paths, "DATA", canonical)
    monkeypatch.setattr(paths, "ROOT", project)
    for destination in (canonical, canonical / "generated", project):
        with pytest.raises(ValueError, match="separate"):
            paths.resolve_output_root(destination, data_root=source_dataset)
    output = project / "outputs"
    output.mkdir()
    os.link(source, output / "result.csv")
    before = source.read_bytes()
    with pytest.raises(ValueError, match="aliases"):
        paths.output_path(output, "result.csv", data_root=source_dataset)
    assert source.read_bytes() == before


@pytest.mark.parametrize(
    "relative",
    [
        "docs/reports/snapshot.pdf",
        "images/photo.jpg",
        "outputs/silhouette_score.png",
        "LICENSE",
    ],
)
def test_outputs_protect_declared_preserved_artifacts(
    relative, source_dataset, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    canonical = project / "data"
    canonical.mkdir(parents=True)
    original = project / relative
    original.parent.mkdir(parents=True, exist_ok=True)
    original.write_bytes(b"preserved evidence")
    monkeypatch.setattr(paths, "DATA", canonical)
    monkeypatch.setattr(paths, "ROOT", project)
    output = project / "outputs"
    output.mkdir(exist_ok=True)
    os.link(original, output / "reliability.png")
    with pytest.raises(ValueError, match="aliases"):
        paths.output_path(output, "reliability.png", data_root=source_dataset)
    assert original.read_bytes() == b"preserved evidence"


def test_current_outputs_can_be_regenerated_without_protecting_unrelated_files(
    source_dataset, tmp_path, monkeypatch
):
    project = tmp_path / "project"
    canonical = project / "data"
    canonical.mkdir(parents=True)
    monkeypatch.setattr(paths, "DATA", canonical)
    monkeypatch.setattr(paths, "ROOT", project)
    output = project / "outputs"
    output.mkdir()
    for name in ("reliability.png", "correlation.png", "figures.csv", "figures.toml"):
        target = output / name
        target.write_bytes(b"current generated artifact")
        assert paths.output_path(output, name, data_root=source_dataset) == target


def test_canonical_question_clock_awareness_cannot_be_silently_removed(source_dataset):
    frame = io.load_psychometric(1, data_root=source_dataset)
    for name in ("Question Start Time", "Question Answer Time"):
        frame[name] = io.parse_datetime(frame[name]).dt.tz_convert(None).astype(str)
    with pytest.raises(ValueError, match="timezone-aware"):
        io.validate_psychometric(frame)


@pytest.mark.parametrize("kind", ["bool", "complex"])
def test_canonical_duration_rejects_nonreal_values_instead_of_casting(
    source_dataset, kind
):
    frame = io.load_psychometric(1, data_root=source_dataset)
    starts = io.parse_datetime(frame["Question Start Time"])
    frame["Question Answer Time"] = (starts + pd.Timedelta(1, unit="s")).astype(str)
    frame["Time(s)"] = (
        pd.Series([True] * len(frame))
        if kind == "bool"
        else pd.Series([1 + 2j] * len(frame), dtype=object)
    )
    with pytest.raises(ValueError, match="real"):
        io.validate_psychometric(frame)


def test_group_and_pipeline_reject_boolean_numbers(source_dataset):
    frame = io.load_group_summary("HRV_SDNN", data_root=source_dataset)
    frame["Session 01"] = frame["Session 01"].astype(object)
    frame.loc[0, "Session 01"] = True
    with pytest.raises(ValueError, match="real"):
        io.validate_group_summary(frame, "HRV_SDNN")
    with pytest.raises(ValueError, match="real"):
        build_group_summaries._numeric(pd.DataFrame({"ibi": [True, False]}), "ibi")


def test_case_insensitive_directory_alias_cannot_write_into_source(source_dataset):
    alias = source_dataset.with_name(source_dataset.name.upper())
    if not alias.exists() or not os.path.samefile(source_dataset, alias):
        pytest.skip("filesystem is case-sensitive")
    for destination in (alias, alias / "generated"):
        with pytest.raises(ValueError, match="separate"):
            paths.resolve_output_root(destination, data_root=source_dataset)


@pytest.mark.parametrize("timestamp", ["2024-10-27T02:30:00", "2024-03-31T02:30:00"])
def test_declared_dst_zone_rejects_ambiguous_or_nonexistent_times_without_calendar_logs(
    timestamp, source_dataset, tmp_path
):
    with pytest.raises(ValueError, match="declared naive timezone"):
        io.parse_datetime(pd.Series([timestamp]), naive_timezone="Europe/Paris")
    source = source_dataset / "case-study/processed/hr.csv"
    pd.DataFrame({"datetime": [timestamp], "value": [1]}).to_csv(source, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "review"
    result = run_cli(
        "scripts.deidentify_timestamps",
        "--data-root",
        source_dataset,
        "--naive-timezone",
        "Europe/Paris",
        "--output-root",
        output,
    )
    assert result.returncode == 1 and "declared naive timezone" in result.stderr
    assert "Traceback" not in result.stderr and timestamp not in result.stderr
    assert not output.exists() and file_hashes(source_dataset) == before


def test_load_hr_keeps_only_declared_high_confidence_rows(tmp_path):
    source = tmp_path / "individual" / "processed"
    source.mkdir(parents=True)
    frame = pd.DataFrame(
        {"heart_rate": [80, 90, 100, 110], "confidence": [1, 0, 0.5, 1]}
    )
    path = source / "hr_01.csv"
    frame.to_csv(path, index=False)
    pd.testing.assert_frame_equal(
        io.load_hr(1, source="individual", data_root=tmp_path), frame.iloc[[0, 3]]
    )
    pd.testing.assert_frame_equal(
        io.load_hr(
            1, source="individual", data_root=tmp_path, high_confidence_only=False
        ),
        frame,
    )
    frame.drop(columns="confidence").to_csv(path, index=False)
    with pytest.raises(ValueError, match="confidence"):
        io.load_hr(1, source="individual", data_root=tmp_path)
    pd.testing.assert_frame_equal(
        io.load_hr(
            1, source="individual", data_root=tmp_path, high_confidence_only=False
        ),
        frame.drop(columns="confidence"),
    )


def test_unknown_source_raises():
    with pytest.raises(ValueError):
        io.load_ibi(1, source="casestudy")


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
        (output / "reliability.png").symlink_to(output / "nested" / "reliability.png")
        expected_error = "one flat output directory"
    assert (
        build_figures.main(
            ["--data-root", str(data_root), "--output-root", str(output)]
        )
        == 1
    )
    assert expected_error in capsys.readouterr().err
    assert not (output / "correlation.png").exists()
    assert not (output / "figures.csv").exists()
    if alias == "source hardlink":
        assert source.read_bytes() == before
    else:
        assert not (output / "nested" / "reliability.png").exists()


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


def test_exact_source_inventory():
    assert len(SOURCE_CSVS) == 51
    assert len(set(SOURCE_CSVS)) == 51
    assert all(path.is_file() for path in SOURCE_CSVS)
    for source in paths.SOURCES:
        for folder in ("processed", "psychometric"):
            found = {
                path.relative_to(ROOT / "data").as_posix()
                for path in (ROOT / "data" / source / folder).glob("*.csv")
            }
            expected = {
                name
                for name in paths.SOURCE_CSV_RELATIVE
                if name.startswith(f"{source}/{folder}/")
            }
            assert found == expected
    assert {path.name for path in (ROOT / "data/group_results").glob("*.csv")} == {
        f"{metric}.csv" for metric in paths.GROUP_METRICS
    }


@pytest.mark.parametrize(
    "path", SOURCE_CSVS, ids=[str(path.relative_to(ROOT)) for path in SOURCE_CSVS]
)
def test_csv_loads_and_is_non_trivial(path):
    assert path.stat().st_size > 0
    frame = pd.read_csv(path)
    assert len(frame) > 0 and len(frame.columns) > 0


@pytest.mark.parametrize("metric", paths.GROUP_METRICS)
def test_group_summary_schema_and_exact_duplicate_cases(metric):
    frame = pd.read_csv(ROOT / "data" / "group_results" / f"{metric}.csv")
    io.validate_group_summary(frame, metric, require_known_duplicates=True)


def test_exact_raw_inventory_and_distinct_sources():
    assert len(paths.SOURCE_RAW_RELATIVE) == 24
    assert all((ROOT / "data" / name).is_file() for name in paths.SOURCE_RAW_RELATIVE)
    for source in paths.SOURCES:
        assert {
            path.relative_to(ROOT / "data").as_posix()
            for path in (ROOT / "data" / source / "raw").glob("*.txt")
        } == {
            name for name in paths.SOURCE_RAW_RELATIVE if name.startswith(f"{source}/")
        }
    for metric in ("hr", "ibi", "sed"):
        for suffix in ("", "_01", "_02", "_03"):
            name = f"raw/{metric}{suffix}.txt"
            assert (ROOT / "data/case-study" / name).read_bytes() != (
                ROOT / "data/individual" / name
            ).read_bytes()


def test_notebooks_present():
    assert {
        folder: sum(path.parent.name == folder for path in NOTEBOOKS)
        for folder in ("case-study", "individual", "group")
    } == {"case-study": 7, "individual": 9, "group": 6}


@pytest.mark.parametrize(
    "path", NOTEBOOKS, ids=[str(p.relative_to(ROOT)) for p in NOTEBOOKS]
)
def test_notebook_contract(path):
    notebook = nbformat.read(path, as_version=4)
    nbformat.validate(notebook)
    assert notebook.cells
    first_code = next(
        cell.source for cell in notebook.cells if cell.cell_type == "code"
    )
    assert "from mms import exploration as ex" in first_code
    for cell in notebook.cells:
        if cell.cell_type == "code":
            tree = ast.parse(cell.source)
            assert cell.execution_count is None
            assert not cell.outputs, (
                "Source notebooks must not embed participant-derived outputs"
            )
            for node in ast.walk(tree):
                if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                    assert node.func.attr not in {"to_csv", "savefig"}, (
                        "Notebook writes must use validated scratch helpers"
                    )
            assert "utc=True" not in cell.source
            assert "tz_localize(None)" not in cell.source
    assert "MMS_OUTPUT_ROOT" in notebook.cells[0].source


@pytest.mark.parametrize(
    "names",
    [
        ("result.csv", "result.csv"),
        ("result.csv", "./result.csv"),
        ("result", "result/nested.csv"),
        ("result/nested.csv", "result"),
    ],
)
def test_output_batch_rejects_colliding_planned_paths(source_dataset, tmp_path, names):
    output = tmp_path / "export"
    with pytest.raises(ValueError, match="distinct files"):
        paths.output_paths(output, names, data_root=source_dataset)
    assert not output.exists()


@pytest.mark.parametrize("alias", ["symlink", "hardlink"])
def test_output_batch_rejects_aliases_between_outputs(source_dataset, tmp_path, alias):
    output = tmp_path / "export"
    output.mkdir()
    original = output / "first.csv"
    original.write_text("previous results\n")
    duplicate = output / "second.csv"
    if alias == "symlink":
        duplicate.symlink_to(original)
    else:
        os.link(original, duplicate)
    before = file_hashes(output)
    with pytest.raises(ValueError, match="distinct files"):
        paths.output_paths(
            output, ("first.csv", "second.csv"), data_root=source_dataset
        )
    assert file_hashes(output) == before


@pytest.mark.parametrize("relative", ["", "."])
def test_output_path_requires_a_filename(source_dataset, tmp_path, relative):
    with pytest.raises(ValueError, match="relative and contained"):
        paths.output_path(tmp_path / "export", relative, data_root=source_dataset)


def test_output_batch_rejects_a_bare_filename(source_dataset, tmp_path):
    with pytest.raises(ValueError, match="iterable"):
        paths.output_paths(tmp_path / "export", "result.csv", data_root=source_dataset)


@pytest.mark.parametrize("alias", ["hardlink", "nested symlink"])
def test_summary_output_alias_fails_before_replacing_results(
    source_dataset, tmp_path, alias
):
    output = tmp_path / "summary"
    output.mkdir()
    first = output / "HRV_SDNN_P02_consistency.csv"
    first.write_text("previous results\n")
    if alias == "hardlink":
        os.link(first, output / "Pupil_Dilation_STD_P02_consistency.csv")
        expected = "distinct files"
    else:
        (output / "MANIFEST.json").symlink_to(output / "nested" / "MANIFEST.json")
        expected = "one flat output directory"
    before = file_hashes(tmp_path)
    with pytest.raises(ValueError, match=expected):
        build_group_summaries.run(source_dataset, output)
    assert file_hashes(tmp_path) == before


def test_shift_file_valued_late_parent_fails_before_writing(source_dataset, tmp_path):
    output = tmp_path / "shifted"
    output.mkdir()
    (output / "individual").write_text("previous results\n")
    before = file_hashes(tmp_path)
    with pytest.raises(ValueError, match="parent must be a directory"):
        deidentify_timestamps.run(source_dataset, output_root=output)
    assert file_hashes(tmp_path) == before


def test_output_root_rejects_a_file_valued_parent(source_dataset, tmp_path):
    parent = tmp_path / "file"
    parent.write_text("preserved\n")
    with pytest.raises(ValueError, match="parent must be a directory"):
        paths.resolve_output_root(parent / "export", data_root=source_dataset)
    assert parent.read_text() == "preserved\n"


def test_notebook_verifier_ignores_host_pytest_and_clock_overrides(
    notebook_checkout, monkeypatch
):
    monkeypatch.setattr(verify_notebooks, "ROOT", notebook_checkout)
    overrides = {
        "PYTEST_ADDOPTS": "--collect-only",
        "PYTEST_PLUGINS": "a_missing_host_plugin",
        "MMS_SENSOR_TIMEZONE": "UTC",
        "MMS_CLOCKS_SYNCHRONIZED": "1",
    }
    for name, value in overrides.items():
        monkeypatch.setenv(name, value)

    def execute(command, *, cwd, env, check):
        assert not set(overrides).intersection(env)
        assert command[:3] == [sys.executable, "-m", "pytest"]
        assert "--nbmake" in command and "--collect-only" not in command
        assert (
            len([argument for argument in command if argument.endswith(".ipynb")]) == 3
        )
        return subprocess.CompletedProcess(command, returncode=0)

    monkeypatch.setattr(verify_notebooks.subprocess, "run", execute)
    assert verify_notebooks.main([]) == 0
    assert all(os.environ[name] == value for name, value in overrides.items())


def test_shift_preserves_every_noncalendar_csv_field(source_dataset, tmp_path):
    relative = Path("case-study/processed/hr.csv")
    original = pd.DataFrame(
        {
            "datetime": ["2001-02-03T04:05:00Z", "2001-02-03T04:05:01Z"],
            "identifier": ["001", "002"],
            "status": ["NA", "null"],
            "amount": ["01.00", "-0"],
            "empty": ["", ""],
            "text": ["a,b", 'He said "yes"'],
        }
    )
    original.to_csv(source_dataset / relative, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "shifted"
    assert deidentify_timestamps.run(source_dataset, output_root=output) == 0
    result = pd.read_csv(output / relative, dtype=str, keep_default_na=False)
    pd.testing.assert_frame_equal(
        result.drop(columns="datetime"), original.drop(columns="datetime")
    )
    assert io.parse_datetime(result["datetime"]).tolist() == [
        pd.Timestamp("2000-01-01T00:00:00Z"),
        pd.Timestamp("2000-01-01T00:00:01Z"),
    ]
    assert file_hashes(source_dataset) == before


def test_shift_keeps_slash_calendar_format_with_empty_clock_cells():
    original = pd.DataFrame(
        {"datetime": ["2001/02/03 04:05:00.000", ""], "identifier": ["001", "NA"]}
    )
    result, columns = deidentify_timestamps.shift_frame(original)
    assert columns == ["datetime"]
    assert result["datetime"].iloc[0] == "2000/01/01 00:00:00.000000"
    assert pd.isna(result["datetime"].iloc[1])
    assert result["identifier"].tolist() == ["001", "NA"]


def _kernel_notebooks(checkout):
    for folder in verify_notebooks.FOLDERS:
        path = checkout / folder / "example.ipynb"
        nbformat.write(
            nbformat.v4.new_notebook(
                cells=[nbformat.v4.new_code_cell("value = 1")],
                metadata={
                    "kernelspec": {
                        **normalize_kernelspec.PORTABLE,
                        "name": "old-kernel",
                    }
                },
            ),
            path,
        )


@pytest.mark.parametrize(
    "alias", ["file symlink", "folder symlink", "root symlink", "hardlink"]
)
def test_kernel_normalizer_rejects_aliases_before_writing(
    notebook_checkout, monkeypatch, tmp_path, alias
):
    _kernel_notebooks(notebook_checkout)
    source = notebook_checkout / "notebooks/group/example.ipynb"
    external = tmp_path / "external.ipynb"
    if alias == "file symlink":
        source.rename(external)
        source.symlink_to(external)
    elif alias == "folder symlink":
        directory = source.parent
        external = tmp_path / "external-group"
        directory.rename(external)
        directory.symlink_to(external, target_is_directory=True)
    elif alias == "root symlink":
        directory = notebook_checkout / "notebooks"
        external = tmp_path / "external-notebooks"
        directory.rename(external)
        directory.symlink_to(external, target_is_directory=True)
    else:
        os.link(source, external)
    before = file_hashes(tmp_path)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)
    with pytest.raises(ValueError, match="symlink|hard links"):
        normalize_kernelspec.main(["--write"])
    assert file_hashes(tmp_path) == before


@pytest.mark.parametrize("folder", verify_notebooks.FOLDERS)
def test_kernel_normalizer_requires_every_notebook_folder(
    notebook_checkout, monkeypatch, folder
):
    _kernel_notebooks(notebook_checkout)
    shutil.rmtree(notebook_checkout / folder)
    before = file_hashes(notebook_checkout)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)
    with pytest.raises(ValueError, match="No source notebooks"):
        normalize_kernelspec.main(["--write"])
    assert file_hashes(notebook_checkout) == before


def test_kernel_normalizer_corrects_language_without_changing_cells(
    notebook_checkout, monkeypatch
):
    _kernel_notebooks(notebook_checkout)
    path = notebook_checkout / "notebooks/case-study/example.ipynb"
    notebook = nbformat.read(path, as_version=4)
    notebook.metadata["kernelspec"] = dict(normalize_kernelspec.PORTABLE)
    notebook.metadata["language_info"] = {"name": "julia"}
    nbformat.write(notebook, path)
    path.chmod(0o640)
    before = file_hashes(notebook_checkout)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)
    assert normalize_kernelspec.main([]) == 1
    assert file_hashes(notebook_checkout) == before
    assert normalize_kernelspec.main(["--write"]) == 0
    updated = nbformat.read(path, as_version=4)
    assert updated.metadata["kernelspec"] == normalize_kernelspec.PORTABLE
    assert updated.metadata["language_info"]["name"] == "python"
    assert updated.cells == notebook.cells
    assert stat.S_IMODE(path.stat().st_mode) == 0o640
    after = file_hashes(notebook_checkout)
    assert normalize_kernelspec.main([]) == 0
    assert file_hashes(notebook_checkout) == after
    assert not list((notebook_checkout / "notebooks").rglob(".*.ipynb"))


def test_kernel_normalizer_validates_all_sources_before_writing(
    notebook_checkout, monkeypatch
):
    _kernel_notebooks(notebook_checkout)
    (notebook_checkout / "notebooks/group/example.ipynb").write_text("invalid JSON")
    before = file_hashes(notebook_checkout)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)
    with pytest.raises(ValueError):
        normalize_kernelspec.main(["--write"])
    assert file_hashes(notebook_checkout) == before


@pytest.mark.parametrize("failure", ["serialization", "replacement"])
def test_kernel_normalizer_preserves_sources_when_writes_fail(
    notebook_checkout, monkeypatch, failure
):
    _kernel_notebooks(notebook_checkout)
    before = file_hashes(notebook_checkout)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)

    def fail_write(notebook, stream):
        stream.write("partial JSON")
        raise OSError("simulated write failure")

    def fail_replace(source, destination):
        raise PermissionError("simulated replacement failure")

    if failure == "serialization":
        monkeypatch.setattr(normalize_kernelspec.nbformat, "write", fail_write)
    else:
        monkeypatch.setattr(normalize_kernelspec.os, "replace", fail_replace)
    with pytest.raises(OSError, match="simulated"):
        normalize_kernelspec.main(["--write"])
    assert file_hashes(notebook_checkout) == before
    assert not list((notebook_checkout / "notebooks").rglob(".*.ipynb"))


@pytest.mark.parametrize(
    "contents",
    [
        "[]",
        "null",
        "42",
        '{"nbformat": 4, "nbformat_minor": 5, "metadata": {}, "cells": null}',
    ],
)
def test_kernel_normalizer_rejects_invalid_json_structure(
    notebook_checkout, monkeypatch, contents
):
    _kernel_notebooks(notebook_checkout)
    invalid = notebook_checkout / "notebooks/group/example.ipynb"
    invalid.write_text(contents)
    before = file_hashes(notebook_checkout)
    monkeypatch.setattr(normalize_kernelspec, "ROOT", notebook_checkout)
    with pytest.raises(ValueError, match="Invalid notebook structure") as error:
        normalize_kernelspec.main(["--write"])
    assert str(invalid) in str(error.value)
    assert file_hashes(notebook_checkout) == before


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


def test_summary_without_retained_samples_writes_readable_empty_csv(
    source_dataset, tmp_path
):
    for session in (1, 2, 3):
        intervals = pd.DataFrame(
            {
                "ibi": [100 + 10 * session * index for index in range(4)],
                "iSensor": [3] * 4,
            }
        )
        intervals.to_csv(
            source_dataset / f"case-study/processed/ibi_{session:02d}.csv", index=False
        )
        eye_path = source_dataset / f"case-study/processed/sed_fix_{session:02d}.csv"
        eye = pd.read_csv(eye_path)
        eye["pupilQ"] = 0.0
        eye.to_csv(eye_path, index=False)
    group_path = source_dataset / "group_results/HRV_SDNN.csv"
    group = pd.read_csv(group_path)
    group.loc[group["Participant"] == "P02", list(paths.SESSION_COLUMNS)] = [
        np.std([100 + 10 * session * index for index in range(4)], ddof=1)
        for session in (1, 2, 3)
    ]
    group.to_csv(group_path, index=False)
    before = file_hashes(source_dataset)
    output = tmp_path / "review"
    assert build_group_summaries.run(source_dataset, output) is True
    result = pd.read_csv(output / "filtered_channel_sample_variability.csv")
    assert result.empty
    assert result.columns.tolist() == [
        "session",
        "channel",
        "metric",
        "n_samples",
        "value",
    ]
    assert (output / "MANIFEST.json").is_file()
    assert file_hashes(source_dataset) == before
