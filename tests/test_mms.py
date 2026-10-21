"""Numerical regressions and checks against the preserved study summaries."""

import math

import numpy as np
import pandas as pd
import pytest

from mms import fixation, hrv, io, stats


def test_icc1_reproduces_readme_hrv_value():
    summary = io.load_group_summary("HRV_SDNN")
    ratings = summary[["Session 01", "Session 02", "Session 03"]].to_numpy(float)
    result = stats.icc1(ratings)
    assert result["icc"] == pytest.approx(0.22, abs=0.02)
    ci_low, ci_high = result["ci95"]
    assert ci_low < 0 < ci_high


def test_icc1_perfect_agreement_is_one():
    data = np.array([[1.0, 1.0], [2.0, 2.0], [3.0, 3.0], [4.0, 4.0]])
    result = stats.icc1(data)
    assert result["icc"] == pytest.approx(1.0, abs=1e-9)
    ci_low, ci_high = result["ci95"]
    assert math.isnan(ci_low)
    assert math.isnan(ci_high)
    assert math.isinf(result["F"])


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
    expected = pd.Series([800, 810, 790, 805]).std(ddof=1)
    assert hrv.sdnn(beats) == pytest.approx(expected)


def test_rmssd_preserves_invalid_interval_gaps():
    beats = pd.Series([800, 810, 0, 5000, 790, 805])
    expected = float(np.sqrt((10**2 + 15**2) / 2))
    assert hrv.rmssd(beats) == pytest.approx(expected)


def test_hrv_over_time_is_not_a_broadcast_scalar():
    random = np.random.default_rng(0)
    times = np.arange(0, 300, 0.8)
    frame = pd.DataFrame(
        {"reltime": times, "ibi": 800 + random.normal(0, 40, len(times))}
    )
    windows = hrv.hrv_over_time(frame, window_s=30)
    assert len(windows) > 1
    assert windows["sdnn"].nunique() > 1


def test_hrv_over_time_conserves_beats():
    frame = pd.DataFrame({"reltime": [0, 10, 20, 30, 59.9, 60.0], "ibi": [800] * 6})
    windows = hrv.hrv_over_time(frame, window_s=30)
    assert windows["n_beats"].sum() == 6


def test_benjamini_hochberg_bounds_and_dominates_raw():
    raw = np.array([0.9, 0.001, 0.5, 0.01, 0.04])
    adjusted = stats.benjamini_hochberg(raw)
    assert np.all((adjusted >= 0) & (adjusted <= 1))
    assert np.all(adjusted >= raw - 1e-12)
    assert np.array_equal(np.argsort(adjusted), np.argsort(raw))


def test_benjamini_hochberg_is_nan_safe():
    adjusted = stats.benjamini_hochberg([0.001, 0.5, np.nan, 0.02])
    assert np.isnan(adjusted[2])
    assert np.all(np.isfinite(adjusted[[0, 1, 3]]))


def test_corr_matrix_fdr_does_not_add_significant_pairs():
    measurements = pd.concat(
        [
            io.load_group_summary("HRV_SDNN")
            .set_index("Participant")
            .add_suffix("_HRV"),
            io.load_group_summary("Pupil_Dilation_STD")
            .set_index("Participant")
            .add_suffix("_Pupil"),
        ],
        axis=1,
    )
    result = stats.corr_matrix_fdr(measurements)
    upper_triangle = np.triu_indices(len(result["r"]), k=1)
    raw_significant = (result["p_raw"].to_numpy()[upper_triangle] < 0.05).sum()
    adjusted_significant = (result["p_fdr"].to_numpy()[upper_triangle] < 0.05).sum()
    assert raw_significant > 0
    assert adjusted_significant <= raw_significant


def test_pupil_std_quality_gates_and_matches_std():
    frame = pd.DataFrame(
        {"pupil": [3.0, 4.0, 100.0, 5.0], "pupilQ": [1.0, 1.0, 0.1, 1.0]}
    )
    expected = pd.Series([3.0, 4.0, 5.0]).std(ddof=1)
    assert fixation.pupil_std(frame, quality_min=0.5) == pytest.approx(expected)


def test_parse_datetime_preserves_explicit_zone():
    parsed = io.parse_datetime(pd.Series(["2024-05-28T15:37:00.695Z"]))
    assert str(parsed.dt.tz) == "UTC"
    assert parsed.iloc[0].year == 2024


def test_load_hr_individual_source_and_raw_confidence():
    filtered = io.load_hr(1, source="individual")
    unfiltered = io.load_hr(1, source="individual", high_confidence_only=False)
    assert len(unfiltered) >= len(filtered)


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


def test_hrv_over_time_rejects_nonfinite_timestamps():
    frame = pd.DataFrame(
        {
            "reltime": [0, np.inf, -np.inf, np.nan, 1],
            "ibi": [800, 1900, 1900, 1900, 810],
        }
    )
    with pytest.raises(ValueError, match="finite nonnegative"):
        hrv.hrv_over_time(frame)
