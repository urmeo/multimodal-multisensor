#!/usr/bin/env python3
"""Assess the unresolved P01 S3 interval-SD discrepancy without changing sources."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from itertools import combinations
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import scipy

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mms import exploration, io, paths, stats  # noqa: E402

REPORT = ROOT / "docs/reports/Multimodal Multisensor Technical Report.pdf"
METRIC = "HRV_SDNN"
REPORT_VALUE = 1012.69
SCENARIO_LABELS = {
    "released": "Released CSV · n = 10",
    "report_candidate": "Report 1012.69, unverified · n = 10",
    "omit_p01": "Omit P01 · n = 9",
}
TABLE_NAMES = ("icc.csv", "correlations.csv", "omnibus.csv", "paired.csv")
OUTPUT_NAMES = (*TABLE_NAMES, "provenance.json", "sensitivity.png")


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def scenarios(frames: dict[str, pd.DataFrame]) -> dict:
    copies = {
        name: {metric: frame.copy(deep=True) for metric, frame in frames.items()}
        for name in ("released", "report_candidate")
    }
    copies["report_candidate"][METRIC].loc["P01", "Session 03"] = REPORT_VALUE
    copies["omit_p01"] = {
        metric: frame.drop(index="P01") for metric, frame in frames.items()
    }
    return copies


def calculate(data_root: str | Path | None = None) -> dict:
    source = paths.resolve_data_root(data_root)
    frames = {
        metric: io.load_group_summary(metric, data_root=source).set_index("Participant")
        for metric in paths.GROUP_METRICS
    }
    rows = {name: [] for name in TABLE_NAMES}
    for scenario, selected in scenarios(frames).items():
        for metric, frame in selected.items():
            estimate = stats.icc1(frame.to_numpy(float))
            rows["icc.csv"].append(
                {
                    "scenario": scenario,
                    "metric": metric,
                    "n": estimate["n"],
                    "k": estimate["k"],
                    "icc": estimate["icc"],
                    "lower": estimate["ci95"][0],
                    "upper": estimate["ci95"][1],
                }
            )
        combined = pd.concat(
            [
                frame.rename(columns=lambda name: f"{metric}: {name}")
                for metric, frame in selected.items()
            ],
            axis=1,
        )
        correlation = stats.corr_matrix_fdr(combined, method="spearman")
        for first, second in combinations(combined.columns, 2):
            rows["correlations.csv"].append(
                {
                    "scenario": scenario,
                    "feature_a": first,
                    "feature_b": second,
                    "rho": correlation["r"].loc[first, second],
                    "n_pairs": correlation["n_pairs"].loc[first, second],
                    "p_raw": correlation["p_raw"].loc[first, second],
                    "p_fdr": correlation["p_fdr"].loc[first, second],
                }
            )
        omnibus, paired = exploration.paired_group_tests(selected)
        for name, table in (("omnibus.csv", omnibus), ("paired.csv", paired)):
            rows[name].extend(
                table.assign(scenario=scenario)[["scenario", *table.columns]].to_dict(
                    "records"
                )
            )
    hashes = {
        f"data/group_results/{metric}.csv": digest(
            source / "group_results" / f"{metric}.csv"
        )
        for metric in paths.GROUP_METRICS
    }
    hashes[REPORT.relative_to(ROOT).as_posix()] = digest(REPORT)
    return {
        "tables": {name: pd.DataFrame(records) for name, records in rows.items()},
        "source_sha256": hashes,
        "settings": {
            "candidate_cell": {
                "metric": METRIC,
                "participant": "P01",
                "session": "Session 03",
            },
            "report_candidate": REPORT_VALUE,
            "report_pdf_page_1based": 6,
            "candidate_status": "unverified rounded report value; not a source correction",
            "scenarios": {
                "released": "all released values, n=10",
                "report_candidate": "change only the candidate cell in a copy, n=10",
                "omit_p01": "omit P01 from all three tables, n=9",
            },
            "icc": "ICC(1,1), finite complete rows, 95% F interval",
            "correlations": "Spearman; BH across all 36 unique pairs per scenario",
            "omnibus": "Friedman; Holm across all three metrics per scenario",
            "paired": "two-sided Wilcoxon; Holm across all nine session pairs per scenario",
            "change_intervals": "paired t 95% intervals in source units; d_z uses difference SD",
            "limits": (
                "Sensitivity only; original export and verified NN-beat provenance unavailable"
            ),
        },
    }


def figure(output: Path, result: dict) -> None:
    fig, axes = plt.subplots(1, 2, figsize=(12, 4.8), layout="constrained")
    colors = ("#2263a6", "#b85130", "#45836d")
    markers = ("o", "s", "^")
    icc = result["tables"]["icc.csv"].query("metric == @METRIC").set_index("scenario")
    correlation = result["tables"]["correlations.csv"]
    for index, (scenario, label) in enumerate(SCENARIO_LABELS.items()):
        row = icc.loc[scenario]
        axes[0].errorbar(
            row["icc"],
            index,
            xerr=[[row["icc"] - row["lower"]], [row["upper"] - row["icc"]]],
            fmt=markers[index],
            color=colors[index],
            capsize=5,
            markersize=7,
        )
        pairs = []
        for first, second in combinations(paths.SESSION_COLUMNS, 2):
            match = correlation.loc[
                (correlation["scenario"] == scenario)
                & (correlation["feature_a"] == f"{METRIC}: {first}")
                & (correlation["feature_b"] == f"{METRIC}: {second}"),
                "rho",
            ]
            pairs.append(float(match.iloc[0]))
        axes[1].scatter(
            np.arange(3) + (index - 1) * 0.16,
            pairs,
            color=colors[index],
            marker=markers[index],
            label=label,
            s=45,
        )
    axes[0].set(
        yticks=range(3),
        yticklabels=list(SCENARIO_LABELS.values()),
        xlabel="ICC(1,1) and 95% F interval",
        title="Interval-sample SD: reliability",
        xlim=(-0.5, 1),
        ylim=(2.5, -0.5),
    )
    axes[1].set(
        xticks=range(3),
        xticklabels=("S1–S2", "S1–S3", "S2–S3"),
        ylabel="Spearman ρ",
        title="Interval-sample SD: session correlations",
        ylim=(-1, 1),
    )
    axes[1].legend(fontsize=8, loc="lower left")
    axes[0].axvline(0, color="#9aa6b2", linestyle=":")
    axes[1].axhline(0, color="#9aa6b2", linestyle=":")
    for ax in axes:
        ax.spines[["top", "right"]].set_visible(False)
    fig.suptitle(
        "P01 session 3: sensitivity to the unresolved interval-SD value", fontsize=13
    )
    fig.savefig(output, dpi=150)
    plt.close(fig)


def build(output: Path, result: dict, *, data_root: str | Path | None = None) -> None:
    destinations = paths.output_paths(
        output, OUTPUT_NAMES, data_root=data_root, flat=True
    )
    root = paths.resolve_output_root(output, data_root=data_root)
    root.mkdir(parents=True, exist_ok=True)
    for name, table in result["tables"].items():
        table.to_csv(destinations[name], index=False)
    figure(destinations["sensitivity.png"], result)
    provenance = {
        "source_sha256": result["source_sha256"],
        "settings": result["settings"],
        "environment": {
            "python": sys.version.split()[0],
            "numpy": np.__version__,
            "pandas": pd.__version__,
            "scipy": scipy.__version__,
            "matplotlib": matplotlib.__version__,
        },
        "source_modified": False,
        "figure_sha256": {"sensitivity.png": digest(destinations["sensitivity.png"])},
    }
    destinations["provenance.json"].write_text(
        json.dumps(provenance, indent=2, allow_nan=False) + "\n"
    )


def verify(output: Path, result: dict) -> None:
    provenance = json.loads((output / "provenance.json").read_text())
    if (
        provenance.get("source_sha256") != result["source_sha256"]
        or provenance.get("settings") != result["settings"]
        or provenance.get("source_modified") is not False
    ):
        raise ValueError("sensitivity provenance differs from current sources or settings")
    if provenance.get("figure_sha256") != {"sensitivity.png": digest(output / "sensitivity.png")}:
        raise ValueError("sensitivity figure bytes differ from provenance")
    for name, expected in result["tables"].items():
        actual = pd.read_csv(output / name)
        try:
            pd.testing.assert_frame_equal(
                actual, expected, check_dtype=False, check_exact=False,
                rtol=1e-9, atol=1e-12,
            )
        except AssertionError as error:
            raise ValueError(f"sensitivity results differ: {name}") from error


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--data-root", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="check committed sensitivity results (default)",
    )
    mode.add_argument(
        "--output-root", type=Path, help="write sensitivity outputs outside source data"
    )
    args = parser.parse_args(argv)
    try:
        result = calculate(args.data_root)
        if args.output_root is None:
            verify(ROOT / "outputs/sensitivity", result)
            action = "Verified"
        else:
            build(args.output_root, result, data_root=args.data_root)
            action = "Wrote"
        print(f"{action} three sensitivity scenarios; source inputs unchanged.")
        return 0
    except (OSError, ValueError, KeyError, TypeError, pd.errors.ParserError) as error:
        print(f"Sensitivity failed: {error}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
