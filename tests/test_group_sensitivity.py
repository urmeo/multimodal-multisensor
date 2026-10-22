from __future__ import annotations

import json
import os
from itertools import combinations

import numpy as np
import pandas as pd
import pytest
from scipy import stats

from mms import io, paths
from scripts import build_group_sensitivity as sensitivity


@pytest.fixture(scope="module")
def result():
    return sensitivity.calculate()


def test_scenarios_change_copies_and_omit_the_same_participant():
    frames = {
        metric: io.load_group_summary(metric).set_index("Participant")
        for metric in paths.GROUP_METRICS
    }
    before = {metric: frame.copy(deep=True) for metric, frame in frames.items()}
    scenarios = sensitivity.scenarios(frames)
    for metric, source in frames.items():
        pd.testing.assert_frame_equal(source, before[metric])
        pd.testing.assert_frame_equal(scenarios["released"][metric], source)
        pd.testing.assert_frame_equal(scenarios["omit_p01"][metric], source.drop("P01"))
        candidate = scenarios["report_candidate"][metric]
        changed = candidate.ne(source)
        assert changed.to_numpy().sum() == (1 if metric == sensitivity.METRIC else 0)
    assert scenarios["report_candidate"][sensitivity.METRIC].loc["P01", "Session 03"] == 1012.69
    scenarios["report_candidate"][sensitivity.METRIC].iloc[0, 0] = -1
    assert (
        scenarios["released"][sensitivity.METRIC].iloc[0, 0]
        == before[sensitivity.METRIC].iloc[0, 0]
    )
    pd.testing.assert_frame_equal(frames[sensitivity.METRIC], before[sensitivity.METRIC])


@pytest.mark.parametrize(
    "scenario, expected",
    [
        ("released", (0.22086877598148408, -0.13106918452370253, 0.6585242879821892)),
        ("report_candidate", (0.0383526954985559, -0.2527550683217968, 0.5086509578797136)),
        ("omit_p01", (0.21609837947646235, -0.15033525063366285, 0.6798198848650101)),
    ],
)
def test_interval_icc_matches_independent_one_way_anova(result, scenario, expected):
    source = io.load_group_summary(sensitivity.METRIC).set_index("Participant")
    if scenario == "report_candidate":
        source.loc["P01", "Session 03"] = 1012.69
    elif scenario == "omit_p01":
        source = source.drop("P01")
    values = source.to_numpy(float)
    n, k = values.shape
    means = values.mean(axis=1)
    between = k * np.square(means - values.mean()).sum() / (n - 1)
    within = np.square(values - means[:, None]).sum() / (n * (k - 1))
    ratio = between / within
    bounds = ratio / stats.f.ppf([0.975, 0.025], n - 1, n * (k - 1))
    reference = [(ratio - 1) / (ratio + k - 1), *((bounds - 1) / (bounds + k - 1))]
    estimates = result["tables"]["icc.csv"]
    row = estimates.loc[
        (estimates["scenario"] == scenario) & (estimates["metric"] == sensitivity.METRIC)
    ].iloc[0]
    assert row[["icc", "lower", "upper"]].to_numpy(float) == pytest.approx(reference, abs=1e-12)
    assert reference == pytest.approx(expected, abs=1e-12)


def test_all_unique_correlations_and_test_families_are_retained(result):
    table = result["tables"]["correlations.csv"]
    assert table.groupby("scenario").size().to_dict() == dict.fromkeys(
        sensitivity.SCENARIO_LABELS, 36
    )
    features = [
        f"{metric}: {session}"
        for metric in paths.GROUP_METRICS
        for session in paths.SESSION_COLUMNS
    ]
    expected_pairs = set(combinations(features, 2))
    for _, scenario in table.groupby("scenario"):
        assert set(
            scenario[["feature_a", "feature_b"]].itertuples(index=False, name=None)
        ) == expected_pairs
    assert table.groupby("scenario")["n_pairs"].unique().map(list).to_dict() == {
        "released": [10], "report_candidate": [10], "omit_p01": [9]
    }
    assert table[["p_raw", "p_fdr"]].ge(0).all().all()
    assert table[["p_raw", "p_fdr"]].le(1).all().all()
    indexed = table.set_index(["scenario", "feature_a", "feature_b"]).sort_index()
    delta = indexed.loc["report_candidate", "rho"] - indexed.loc["released", "rho"]
    assert (delta.abs() > 1e-12).sum() == 8
    assert delta.abs().max() == pytest.approx(0.10909090909090909)
    assert result["tables"]["omnibus.csv"].groupby("scenario").size().eq(3).all()
    paired = result["tables"]["paired.csv"]
    assert paired.groupby("scenario").size().eq(9).all()
    assert paired.groupby("scenario")["p_holm"].min().to_dict() == pytest.approx({
        "released": 1, "report_candidate": 1, "omit_p01": 0.87890625
    })


def test_export_and_verification_leave_sources_and_outputs_unchanged(
    tmp_path, monkeypatch, result
):
    sources = {name: (paths.ROOT / name).read_bytes() for name in result["source_sha256"]}
    output = tmp_path / "outputs/sensitivity"
    sensitivity.build(output, result)
    saved = {name: (output / name).read_bytes() for name in sensitivity.OUTPUT_NAMES}
    monkeypatch.setattr(sensitivity, "ROOT", tmp_path)
    monkeypatch.setattr(sensitivity, "calculate", lambda data_root=None: result)
    assert sensitivity.main([]) == 0
    assert saved == {name: (output / name).read_bytes() for name in saved}
    assert sources == {name: (paths.ROOT / name).read_bytes() for name in sources}


@pytest.mark.parametrize("corruption", ["sources", "settings", "figure", "results"])
def test_verification_rejects_stale_results_or_provenance(tmp_path, result, corruption):
    sensitivity.build(tmp_path, result)
    provenance_path = tmp_path / "provenance.json"
    provenance = json.loads(provenance_path.read_text())
    if corruption == "sources":
        provenance["source_sha256"] = {}
    elif corruption == "settings":
        provenance["settings"]["report_candidate"] = 65.39
    elif corruption == "figure":
        (tmp_path / "sensitivity.png").write_bytes(b"changed")
    else:
        table = pd.read_csv(tmp_path / "icc.csv")
        table.loc[0, "icc"] = 0.99
        table.to_csv(tmp_path / "icc.csv", index=False)
    provenance_path.write_text(json.dumps(provenance))
    with pytest.raises(ValueError):
        sensitivity.verify(tmp_path, result)


def test_all_destinations_are_guarded_before_writing(tmp_path, result):
    data_root = tmp_path / "data"
    source = data_root / "group_results/HRV_SDNN.csv"
    source.parent.mkdir(parents=True)
    source.write_bytes(b"preserved source observation\n")
    before = source.read_bytes()
    output = tmp_path / "sensitivity"
    output.mkdir()
    os.link(source, output / "provenance.json")
    with pytest.raises(ValueError, match="aliases a source"):
        sensitivity.build(output, result, data_root=data_root)
    assert not (output / "icc.csv").exists()
    assert source.read_bytes() == before
