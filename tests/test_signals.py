"""Interval, gaze-event and statistical calculations."""

from __future__ import annotations

import math

import numpy as np
import pandas as pd
import pytest
from scipy import stats as scipy_stats

from mms import fixation, hrv, stats
from mms.fixation import (
    blink_events,
    contiguous_events,
    fixation_events,
    pupil_samples,
    pupil_std,
)


@pytest.mark.parametrize(
    "values",
    [[800, 0, 1000], [800, 5000, 1000], [800, np.nan, 1000], [800, np.inf, 1000], []],
)
def test_rmssd_never_joins_invalid_intervals(values):
    assert math.isnan(hrv.rmssd(values))


def test_rmssd_uses_only_real_adjacent_pairs_after_gap():
    assert hrv.rmssd([800, 810, 0, 1000, 1020]) == pytest.approx(np.sqrt(250))


@pytest.mark.parametrize("bad", [True, 1.5, 1, 0, -1, np.nan, np.inf, "3", 2**100])
def test_rolling_window_must_be_integer_at_least_two(bad):
    with pytest.raises(ValueError, match="window_beats"):
        hrv.hrv_rolling(pd.DataFrame({"ibi": [800, 810]}), window_beats=bad)


@pytest.mark.parametrize(
    "lo,hi", [(np.nan, 2000), (300, np.inf), (900, 800), (True, 2000), (300, "2000")]
)
@pytest.mark.parametrize("function", [hrv.clean_nn, hrv.sdnn, hrv.rmssd])
def test_interval_bounds_rejected(lo, hi, function):
    with pytest.raises(ValueError):
        function([800, 810], lo, hi)


@pytest.mark.parametrize(
    "values",
    [[True, False], [800, 1j], pd.Series([800, 2 + 3j], dtype=object), [800, "bad"]],
)
@pytest.mark.parametrize("function", [hrv.clean_nn, hrv.sdnn, hrv.rmssd])
def test_interval_input_must_be_real(values, function):
    with pytest.raises(ValueError, match="real"):
        function(values)


def test_two_sample_rolling_and_gap_keep_index_and_rows():
    frame = pd.DataFrame({"ibi": [800, 810, 0, 1000, 1020]}, index=[4, 4, 2, 8, 9])
    result = hrv.hrv_rolling(frame, window_beats=2)
    pd.testing.assert_frame_equal(result[frame.columns], frame)
    assert result.rmssd.iloc[1] == pytest.approx(10)
    assert result.rmssd.isna().tolist() == [True, False, True, True, False]
    assert result.rmssd.iloc[4] == pytest.approx(20)


def test_rolling_separates_sample_channels():
    frame = pd.DataFrame(
        {
            "reltime": [0, 0, 1, 1],
            "iSensor": [1, 2, 1, 2],
            "ibi": [800, 1500, 810, 1520],
        }
    )
    result = hrv.hrv_rolling(frame, window_beats=2)
    assert result.rmssd.iloc[2:].tolist() == pytest.approx([10, 20])
    windows = hrv.hrv_over_time(frame)
    assert windows.iSensor.tolist() == [1, 2]
    assert windows.n_samples.tolist() == [2, 2]
    assert windows.n_pairs.tolist() == [1, 1]
    assert windows.rmssd.tolist() == pytest.approx([10, 20])


def test_elapsed_gap_excludes_pairs():
    frame = pd.DataFrame({"reltime": [0, 1, 9, 10], "ibi": [800, 810, 1000, 1020]})
    windows = hrv.hrv_over_time(frame, max_gap_s=2)
    assert windows.n_pairs.tolist() == [2]
    assert windows.rmssd.iloc[0] == pytest.approx(np.sqrt(250))
    rolling = hrv.hrv_rolling(frame, window_beats=2, max_gap_s=2)
    assert math.isnan(rolling.rmssd.iloc[2])


def test_gap_filter_keeps_empty_windows_between_channel_samples():
    frame = pd.DataFrame({"reltime": [0, 4], "iSensor": [1, 2], "ibi": [800, 810]})
    windows = hrv.hrv_over_time(frame, window_s=2, step_s=3, max_gap_s=0.3)
    assert len(windows) == 4
    assert windows.n_samples.tolist() == [1, 0, 0, 1]
    assert windows.n_pairs.tolist() == [0, 0, 0, 0]
    assert windows[["sdnn", "rmssd"]].isna().all().all()


def test_rolling_gap_filter_accepts_empty_stream_without_channels():
    frame = pd.DataFrame({"reltime": [], "ibi": []})
    result = hrv.hrv_rolling(frame, max_gap_s=1)
    assert result.empty
    pd.testing.assert_frame_equal(result[frame.columns], frame)
    assert {"sdnn", "rmssd"} <= set(result)


@pytest.mark.parametrize(
    "times",
    [[1, 0], [0, np.inf], [0, -np.inf], [0, np.nan], [-1, 0], [False, True], [0, 1j]],
)
@pytest.mark.parametrize("function", [hrv.hrv_rolling, hrv.hrv_over_time])
def test_elapsed_times_must_be_real_finite_and_ordered(times, function):
    with pytest.raises(ValueError):
        function(pd.DataFrame({"reltime": times, "ibi": [800, 810]}))


def test_integer_order_and_resolution_preserved_before_float_conversion():
    times = np.array([2**60, 2**60 + 1, 2**60 + 2], dtype=np.uint64)
    result = hrv.hrv_over_time(
        pd.DataFrame({"reltime": times, "ibi": [800, 810, 820]}), window_s=1
    )
    assert result.window_start_s.tolist() == [0, 1]
    assert result.n_samples.tolist() == [1, 2]
    times[-1] = 2**60
    with pytest.raises(ValueError, match="chronological"):
        hrv.hrv_over_time(pd.DataFrame({"reltime": times, "ibi": [800, 810, 820]}))


def test_large_absolute_float_time_uses_elapsed_origin_without_looping():
    frame = pd.DataFrame({"reltime": [1e16, 1e16 + 2], "ibi": [800, 810]})
    result = hrv.hrv_over_time(frame, window_s=0.1, step_s=0.1)
    assert len(result) == 20
    assert result.n_samples.sum() == 2


def test_gap_checks_preserve_small_integer_steps_after_large_span():
    times = np.array([0, 2**60, 2**60 + 10], dtype=np.uint64)
    frame = pd.DataFrame({"reltime": times, "ibi": [800, 810, 820]})
    assert hrv.hrv_over_time(frame, window_s=2**61, max_gap_s=1).n_pairs.tolist() == [0]
    assert hrv.hrv_rolling(frame, window_beats=2, max_gap_s=1).rmssd.isna().all()


@pytest.mark.parametrize(
    "kwargs",
    [
        {"step_s": 1e-320},
        {"max_windows": 1},
        {"max_windows": True},
        {"max_windows": 0},
        {"max_windows": 1000001},
        {"window_s": True},
        {"step_s": "1"},
    ],
)
def test_window_limits_reject_unbounded_or_invalid_requests(kwargs):
    frame = pd.DataFrame({"reltime": [0, 100], "ibi": [800, 810]})
    with pytest.raises(ValueError):
        hrv.hrv_over_time(frame, **kwargs)


def test_window_top_overflow_rejected_without_warnings():
    frame = pd.DataFrame({"reltime": [0, 1.7e308], "ibi": [800, 810]})
    with pytest.raises(ValueError, match="finite and advance"):
        hrv.hrv_over_time(frame, window_s=1.5e308, step_s=1e308)


def test_empty_single_and_exact_final_boundary_windows():
    empty = hrv.hrv_over_time(pd.DataFrame({"reltime": [], "ibi": []}))
    assert empty.empty and {"n_samples", "n_pairs", "rmssd"} <= set(empty)
    single = hrv.hrv_over_time(pd.DataFrame({"reltime": [0], "ibi": [800]}))
    assert single.n_samples.tolist() == [1]
    assert math.isnan(single.rmssd.iloc[0])
    final = hrv.hrv_over_time(pd.DataFrame({"reltime": [0, 30, 60], "ibi": [800] * 3}))
    assert final.n_samples.tolist() == [1, 2]


def test_large_interval_arithmetic_matches_analytic_variability():
    values = [1e307, 5e307, 1e308]
    frame = pd.DataFrame({"reltime": [0, 1, 2], "ibi": values})
    expected_sd = np.sqrt(61 / 3) * 1e307
    expected_rmssd = np.sqrt(41 / 2) * 1e307
    assert hrv.sdnn(values, lo=0, hi=1e308) == pytest.approx(expected_sd)
    assert hrv.rmssd(values, lo=0, hi=1e308) == pytest.approx(expected_rmssd)
    rolling = hrv.hrv_rolling(frame, window_beats=3, lo=0, hi=1e308)
    assert rolling.sdnn.iloc[-1] == pytest.approx(expected_sd)
    assert rolling.rmssd.iloc[-1] == pytest.approx(expected_rmssd)


def test_sdnn_filters_artifacts_and_zeros():
    beats = pd.Series([800, 810, 0, 790, 5000, 805])
    assert hrv.sdnn(beats) == pytest.approx(np.sqrt(875 / 12))


def test_time_windows_compute_variability_from_their_own_samples():
    frame = pd.DataFrame({"reltime": [0, 1, 30, 31], "ibi": [800, 810, 1000, 1020]})
    windows = hrv.hrv_over_time(frame, window_s=30)
    assert windows["window_start_s"].tolist() == [0, 30]
    assert windows["n_samples"].tolist() == windows["n_beats"].tolist() == [2, 2]
    assert windows["n_pairs"].tolist() == [1, 1]
    assert windows["sdnn"].tolist() == pytest.approx([np.sqrt(50), np.sqrt(200)])
    assert windows["rmssd"].tolist() == pytest.approx([10, 20])


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


def test_holm_and_bh_exact_unsorted_vectors_and_unrun_tests():
    assert stats.holm([0.04, 0.041, 0.042]) == pytest.approx([0.12] * 3)
    assert stats.benjamini_hochberg([0.04, 0.001, 0.03]) == pytest.approx(
        [0.04, 0.003, 0.04]
    )
    result = stats.holm([0.041, np.nan, 0.04, 0.042])
    assert result[[0, 2, 3]] == pytest.approx([0.12] * 3)
    assert math.isnan(result[1])
    assert stats.holm([]).size == 0


@pytest.mark.parametrize(
    "values",
    [
        [-0.1],
        [1.1],
        [np.inf],
        [-np.inf],
        [True],
        [True, 0.1],
        [1j],
        [[0.1, 0.2]],
        [0.1, "bad"],
    ],
)
@pytest.mark.parametrize("adjust", [stats.holm, stats.benjamini_hochberg])
def test_invalid_pvalues_fail_clearly(values, adjust):
    with pytest.raises(ValueError):
        adjust(values)


@pytest.mark.parametrize("method", ["pearson", "spearman"])
def test_correlation_joint_finite_masks_constants_and_family(method):
    frame = pd.DataFrame(
        {
            "a": [1, 2, 3, np.inf, 5],
            "b": [1, 4, 2, 8, np.nan],
            "constant": [2] * 5,
            "sparse": [1, 2, np.nan, np.nan, np.nan],
        }
    )
    result = stats.corr_matrix_fdr(frame, method=method)
    correlate = scipy_stats.pearsonr if method == "pearson" else scipy_stats.spearmanr
    expected_r, expected_p = correlate([1, 2, 3], [1, 4, 2])
    assert result["r"].loc["a", "b"] == pytest.approx(expected_r)
    assert result["p_raw"].loc["a", "b"] == pytest.approx(expected_p)
    assert result["n_pairs"].loc["a", "b"] == 3
    assert result["n_tests"] == 1
    assert result["method"] == method
    assert result["adjustment"] == "Benjamini-Hochberg"
    assert result["p_raw"].loc["constant"].isna().all()
    assert result["p_fdr"].loc["sparse"].isna().all()
    assert math.isnan(result["r"].loc["constant", "constant"])


def test_spearman_preserves_tiny_distinct_ranks():
    frame = pd.DataFrame({"a": [1e-300, 2e-300, 1e308], "b": [1, 2, 3]})
    result = stats.corr_matrix_fdr(frame, method="spearman")
    assert result["r"].iloc[0, 1] == pytest.approx(1)


@pytest.mark.parametrize(
    "frame,kwargs",
    [
        (pd.DataFrame({"x": [1, 2, 3]}), {"method": "kendall"}),
        (pd.DataFrame([[1, 2]], columns=["x", "x"]), {}),
        (pd.DataFrame({"x": [1j, 2, 3], "y": [1, 2, 3]}), {}),
    ],
)
def test_correlation_contract_rejected(frame, kwargs):
    with pytest.raises(ValueError):
        stats.corr_matrix_fdr(frame, **kwargs)


def test_icc_complete_finite_rows_match_explicit_subset():
    valid = np.array([[1, 2], [2, 4], [4, 3]], dtype=float)
    actual = stats.icc1(np.vstack([valid, [np.inf, 1], [2, np.nan]]))
    expected = stats.icc1(valid)
    assert actual == expected
    assert actual["n"] == 3


def test_icc_all_constant_undefined_and_large_finite_scale_invariant():
    result = stats.icc1(np.ones((4, 3)))
    assert math.isnan(result["icc"]) and math.isnan(result["F"])
    values = np.array([[1, 2], [3, 2], [4, 5]], dtype=float)
    assert stats.icc1(values * 1e307)["icc"] == pytest.approx(stats.icc1(values)["icc"])


@pytest.mark.parametrize("n,k", [(4, 2), (3, 5)])
def test_identical_ratings_stay_perfect_without_rounding_variance(n, k):
    values = np.repeat(np.arange(1.0, n + 1)[:, None], k, axis=1)
    result = stats.icc1(values)
    assert result["icc"] == 1.0
    assert math.isinf(result["F"])
    assert all(math.isnan(bound) for bound in result["ci95"])


@pytest.mark.parametrize(
    "values",
    [
        [[1j, 2], [2, 3]],
        [[True, False], [False, True]],
        [[True, 2], [3, 4]],
        [["bad", 2], [2, 3]],
    ],
)
def test_icc_rejects_nonreal_values(values):
    with pytest.raises(ValueError, match="real"):
        stats.icc1(values)


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


def test_runs_are_one_row_each_with_observed_duration():
    result = contiguous_events(
        [0, 1, 2, 3, 4, 5], [False, True, True, False, True, False]
    )
    assert result.n_samples.tolist() == [2, 1]
    assert result.duration_s.tolist() == [1, 0]
    assert result.start_pos.tolist() == [1, 4]
    assert not result.left_censored.any() and not result.right_censored.any()


def test_recording_boundaries_and_all_run_are_censored():
    result = contiguous_events([0, 1, 2], [True] * 3)
    assert result.n_samples.tolist() == [3]
    assert result.duration_s.tolist() == [2]
    assert result.left_censored.tolist() == [True]
    assert result.right_censored.tolist() == [True]
    assert result.end_reason.tolist() == ["recording_end"]


def test_invalid_quality_and_gaps_split_runs():
    result = contiguous_events(
        [0, 1, 2, 3, 8, 9],
        [True] * 6,
        valid=[True, True, False, True, True, True],
        max_gap_s=2,
    )
    assert result.n_samples.tolist() == [2, 1, 2]
    assert result.end_reason.tolist() == ["invalid", "gap", "recording_end"]
    assert result.left_censored.all() and result.right_censored.all()


def test_missing_mask_cannot_join_runs():
    result = contiguous_events(
        [0, 1, 2], pd.Series([True, pd.NA, True], dtype="boolean")
    )
    assert result.n_samples.tolist() == [1, 1]
    assert result.end_reason.tolist() == ["invalid", "recording_end"]


def test_uint64_event_times_keep_exact_durations_and_gap_boundaries():
    times = np.array([2**60, 2**60 + 1, 2**60 + 4], dtype=np.uint64)
    result = contiguous_events(times, [True] * 3, max_gap_s=2)
    assert result.n_samples.tolist() == [2, 1]
    assert result.duration_s.tolist() == [1, 0]


@pytest.mark.parametrize(
    "time,mask,kwargs",
    [
        ([1, 0], [True, True], {}),
        ([0, np.inf], [True, True], {}),
        ([0, 1], [1, 0], {}),
        ([0, 1], [True], {}),
        ([0, 1], [True, True], {"valid": [True]}),
        ([0, 1], [True, True], {"max_gap_s": 0}),
    ],
)
def test_invalid_event_contract_rejected(time, mask, kwargs):
    with pytest.raises(ValueError):
        contiguous_events(time, mask, **kwargs)


def test_empty_events_have_stable_columns():
    result = contiguous_events([], [])
    assert result.empty
    assert {"duration_s", "left_censored", "right_censored"} <= set(result)
    blink = blink_events(
        [], [], valid=[], min_duration_s=0.1, max_duration_s=0.5, max_gap_s=0.1
    )
    assert blink.empty and blink.columns.equals(result.columns)
    assert result.left_censored.dtype == bool
    assert result.duration_s.dtype == float
    raw = pd.DataFrame(
        columns=["reltime", "gazeQ", "gazeDir.x", "gazeDir.y", "gazeDir.z"]
    )
    fixation = fixation_events(raw)
    assert fixation.empty and fixation.columns.equals(result.columns)


def test_blink_requires_valid_opening_closure_reopening_and_elapsed_bounds():
    times = [0, 0.05, 0.13, 0.2, 0.3, 0.35, 0.5, 0.55]
    closed = [False, True, True, False, False, True, True, False]
    result = blink_events(
        times,
        closed,
        valid=[True] * 8,
        min_duration_s=0.1,
        max_duration_s=0.3,
        max_gap_s=0.1,
    )
    assert result.start_s.tolist() == [0.05]
    assert result.end_s.tolist() == [0.2]
    assert result.duration_s.tolist() == pytest.approx([0.15])
    assert result.n_samples.tolist() == [2]


@pytest.mark.parametrize(
    "closed,valid",
    [
        ([True, True, False], [True] * 3),
        ([False, True, True], [True] * 3),
        ([False, True, False], [True, True, False]),
        ([False, True, False], [False, True, True]),
    ],
)
def test_tracking_loss_or_boundary_closure_is_not_blink(closed, valid):
    assert blink_events(
        [0, 0.05, 0.1],
        closed,
        valid=valid,
        min_duration_s=0.01,
        max_duration_s=0.5,
        max_gap_s=0.1,
    ).empty


def test_blink_duration_bounds_rejected():
    with pytest.raises(ValueError, match="bounds"):
        blink_events(
            [0],
            [False],
            valid=[True],
            min_duration_s=0.5,
            max_duration_s=0.1,
            max_gap_s=0.1,
        )


@pytest.mark.parametrize(
    "duration,accepted",
    [
        pytest.param(1 / 16, False, id="below-minimum"),
        pytest.param(1 / 8, True, id="minimum"),
        pytest.param(1 / 4, True, id="inside"),
        pytest.param(3 / 8, True, id="maximum"),
        pytest.param(1 / 2, False, id="above-maximum"),
    ],
)
def test_blink_duration_filter_includes_both_bounds(duration, accepted):
    result = blink_events(
        [0, 1, 1 + duration],
        [False, True, False],
        valid=[True] * 3,
        min_duration_s=1 / 8,
        max_duration_s=3 / 8,
        max_gap_s=1,
    )
    assert result.duration_s.tolist() == pytest.approx([duration] if accepted else [])
    if accepted:
        assert result.start_s.tolist() == [1]
        assert result.end_s.tolist() == [1 + duration]
        assert result.n_samples.tolist() == [1]


def test_pupil_samples_keep_index_and_exclude_nonfinite_nonpositive_quality():
    frame = pd.DataFrame(
        {
            "pupil": [3, 4, 0, np.inf, 5, 6, 7],
            "pupilQ": [1, 0.8, 1, 1, np.inf, 1.1, -0.1],
        },
        index=list("abcdefg"),
    )
    result = pupil_samples(frame)
    assert result.index.equals(frame.index)
    assert result.dropna().tolist() == [3, 4]
    assert pupil_std(frame) == pytest.approx(np.sqrt(0.5))


def test_missing_quality_requires_explicit_policy():
    frame = pd.DataFrame({"pupil": [3, 4]})
    with pytest.raises(ValueError, match="pupilQ"):
        pupil_samples(frame)
    assert pupil_samples(frame, missing_quality="allow").tolist() == [3, 4]
    assert math.isnan(pupil_std(pd.DataFrame({"pupil": [3], "pupilQ": [1]})))


@pytest.mark.parametrize("column", ["pupil", "pupilQ"])
@pytest.mark.parametrize("bad", [True, 2 + 3j, "bad"])
def test_pupil_rejects_nonreal_values_without_casting(column, bad):
    frame = pd.DataFrame({"pupil": [3, 4], "pupilQ": [1, 1]})
    frame[column] = pd.Series([1, bad], dtype=object)
    with pytest.raises(ValueError, match="real"):
        pupil_samples(frame)


@pytest.mark.parametrize("quality", [True, np.nan, np.inf, -1, 1.1])
def test_quality_threshold_rejected(quality):
    with pytest.raises(ValueError, match="quality_min"):
        pupil_std(
            pd.DataFrame({"pupil": [3, 4], "pupilQ": [1, 1]}), quality_min=quality
        )


def test_fixation_source_mask_quality_and_coordinates_gate_events():
    frame = pd.DataFrame(
        {
            "reltime": [0, 0.1, 0.2, 0.3, 0.4],
            "fixation": [False, True, True, True, False],
            "gazeQ": [1, 1, 0.1, 1, 1],
        }
    )
    result = fixation_events(frame, max_gap_s=0.2)
    assert result.n_samples.tolist() == [1, 1]
    assert result.right_censored.tolist() == [True, False]
    assert result.left_censored.tolist() == [False, True]


def test_raw_euclidean_fixation_rule_never_compacts_invalid_gaze():
    frame = pd.DataFrame(
        {
            "reltime": [0, 0.1, 0.2, 0.3, 0.4],
            "gazeDir.x": [1] * 5,
            "gazeDir.y": [0, 0.001, np.nan, 0.002, 0.003],
            "gazeDir.z": [0] * 5,
            "gazeQ": [1] * 5,
        }
    )
    result = fixation_events(frame, max_gap_s=0.2)
    assert result.n_samples.tolist() == [1, 1]
    assert result.start_pos.tolist() == [1, 4]


def test_fixation_requires_quality_and_mask_or_coordinates():
    with pytest.raises(ValueError, match="gazeQ"):
        fixation_events(pd.DataFrame({"reltime": [0], "fixation": [True]}))
    with pytest.raises(ValueError, match="mask or complete"):
        fixation_events(pd.DataFrame({"reltime": [0], "gazeQ": [1]}))


def test_pupil_std_quality_gates_and_matches_std():
    frame = pd.DataFrame(
        {"pupil": [3.0, 4.0, 100.0, 5.0], "pupilQ": [1.0, 1.0, 0.1, 1.0]}
    )
    assert fixation.pupil_std(frame, quality_min=0.5) == pytest.approx(1)
