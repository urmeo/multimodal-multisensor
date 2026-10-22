"""Numerical results and dataset-loader contracts."""

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from mms import fixation, hrv, io, stats


@pytest.mark.parametrize(
    "ratings",
    [
        np.array([1.0, 2.0, 3.0]),
        np.array([[1.0], [2.0]]),
        np.array([[1.0, 2.0]]),
    ],
)
def test_icc1_degenerate_input_returns_nan(ratings):
    result = stats.icc1(ratings)
    assert math.isnan(result["icc"])


def test_sdnn_filters_artifacts_and_zeros():
    beats = pd.Series([800, 810, 0, 790, 5000, 805])
    assert hrv.sdnn(beats) == pytest.approx(np.sqrt(875 / 12))


def test_time_windows_compute_variability_from_their_own_samples():
    frame = pd.DataFrame(
        {"reltime": [0, 1, 30, 31], "ibi": [800, 810, 1000, 1020]}
    )
    windows = hrv.hrv_over_time(frame, window_s=30)
    assert windows["window_start_s"].tolist() == [0, 30]
    assert windows["n_samples"].tolist() == windows["n_beats"].tolist() == [2, 2]
    assert windows["n_pairs"].tolist() == [1, 1]
    assert windows["sdnn"].tolist() == pytest.approx([np.sqrt(50), np.sqrt(200)])
    assert windows["rmssd"].tolist() == pytest.approx([10, 20])


def test_benjamini_hochberg_restores_input_order():
    raw = np.array([0.9, 0.001, 0.5, 0.01, 0.04])
    adjusted = stats.benjamini_hochberg(raw)
    assert adjusted == pytest.approx([0.9, 0.005, 0.625, 0.025, 1 / 15])


def test_benjamini_hochberg_is_nan_safe():
    adjusted = stats.benjamini_hochberg([0.001, 0.5, np.nan, 0.02])
    assert np.isnan(adjusted[2])
    assert adjusted[[0, 1, 3]] == pytest.approx([0.003, 0.5, 0.03])


@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_correlation_matrix_adjusts_each_unique_pair_once(method):
    measurements = pd.DataFrame(
        {
            "a": [1, 2, 3, 4, 5, 6],
            "b": [1, 3, 2, 6, 4, 5],
            "c": [6, 1, 4, 2, 5, 3],
        }
    )
    pairs = [("a", "b"), ("a", "c"), ("b", "c")]
    correlate = scipy_stats.pearsonr if method == "pearson" else scipy_stats.spearmanr
    references = [
        correlate(measurements[left], measurements[right]) for left, right in pairs
    ]
    adjusted = scipy_stats.false_discovery_control(
        [reference.pvalue for reference in references], method="bh"
    )
    result = stats.corr_matrix_fdr(measurements, method=method)
    assert result["n_tests"] == len(pairs)
    assert result["n_pairs"].eq(6).all().all()
    for (left, right), reference, p_fdr in zip(pairs, references, adjusted):
        assert result["r"].loc[left, right] == pytest.approx(reference.statistic)
        assert result["p_raw"].loc[left, right] == pytest.approx(reference.pvalue)
        assert result["p_fdr"].loc[left, right] == pytest.approx(p_fdr)
    for name in ("r", "p_raw", "p_fdr", "n_pairs"):
        pd.testing.assert_frame_equal(result[name], result[name].T)
    assert np.diag(result["r"]).tolist() == [1, 1, 1]
    assert np.isnan(np.diag(result["p_raw"])).all()
    assert np.isnan(np.diag(result["p_fdr"])).all()


def test_pupil_std_quality_gates_and_matches_std():
    frame = pd.DataFrame(
        {"pupil": [3.0, 4.0, 100.0, 5.0], "pupilQ": [1.0, 1.0, 0.1, 1.0]}
    )
    assert fixation.pupil_std(frame, quality_min=0.5) == pytest.approx(1)


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


@pytest.mark.parametrize(
    "window_s, step_s",
    [
        (0, None),
        (-1, None),
        (float("nan"), None),
        (float("inf"), None),
        (30, 0),
        (30, -1),
        (30, float("nan")),
        (30, float("inf")),
    ],
)
def test_hrv_over_time_rejects_invalid_windows(window_s, step_s):
    frame = pd.DataFrame({"reltime": [0, 1], "ibi": [800, 810]})
    with pytest.raises(ValueError, match="finite and positive"):
        hrv.hrv_over_time(frame, window_s=window_s, step_s=step_s)


def test_hrv_rolling_differences_stay_inside_beat_window():
    frame = pd.DataFrame({"ibi": [700, 800, 800, 800]})
    result = hrv.hrv_rolling(frame, window_beats=3)
    assert result["rmssd"].iloc[2] == pytest.approx(np.sqrt(5000))
    assert result["rmssd"].iloc[3] == 0
