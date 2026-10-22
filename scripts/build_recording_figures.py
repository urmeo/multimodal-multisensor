#!/usr/bin/env python3
"""Check or draw channel-separated figures from case-study Session 1 raw exports."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import tomllib
from itertools import cycle
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from matplotlib import font_manager

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from mms import io, paths  # noqa: E402

NAMES = ("hr", "ibi", "sed")
COLORS = ("#183b62", "#16888c", "#b05d38")
FIGURE_NAMES = ("recorded-heart.png", "recorded-interval.png", "recorded-pupil.png")
OUTPUT_NAMES = (*FIGURE_NAMES, "recording-figures.toml")


def samples(frame: pd.DataFrame, column: str, *, quality: str | None = None) -> dict:
    fields = ["reltime", "iSensor", column]
    if quality:
        fields.append(quality)
    numeric = frame[fields].apply(pd.to_numeric, errors="raise")
    channels = numeric["iSensor"].to_numpy(float)
    if not np.isfinite(channels).all() or np.any(channels % 1):
        raise ValueError("iSensor must contain finite integer channel identifiers")
    keep = np.isfinite(numeric.to_numpy(float)).all(axis=1)
    keep &= numeric["reltime"].ge(0) & numeric[column].gt(0)
    if quality == "confidence":
        keep &= numeric[quality].eq(1)
    elif quality:
        keep &= numeric[quality].gt(0.5) & numeric[quality].le(1)
    result = {}
    for channel, group in numeric.loc[keep].groupby("iSensor", sort=True):
        time = group["reltime"].to_numpy(float)
        if np.any(np.diff(time) < 0):
            raise ValueError("channel recording-relative times must be nondecreasing")
        result[str(int(channel))] = {
            "time_s": time.tolist(),
            "values": group[column].tolist(),
        }
    if not result:
        raise ValueError(f"no valid recorded samples for {column}")
    return result


def payload(data_root: Path | None = None) -> dict:
    raw = {name: io.load_raw(name, 1, data_root=data_root) for name in NAMES}
    return {
        "heart": samples(raw["hr"], "heart_rate", quality="confidence"),
        "interval": samples(raw["ibi"], "ibi"),
        "pupil": samples(raw["sed"], "pupil", quality="pupilQ"),
    }


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def provenance(data: dict, data_root: Path) -> dict:
    return {
        "source": {
            f"data/case-study/raw/{name}_01.txt": digest(
                data_root / "case-study" / "raw" / f"{name}_01.txt"
            )
            for name in NAMES
        },
        "selection_sha256": hashlib.sha256(
            json.dumps(data, sort_keys=True, allow_nan=False).encode()
        ).hexdigest(),
        "scope": "case-study Session 1 only; independent recording clocks; device mapping and beat provenance unverified",
        "filters": {
            "heart": "finite positive heart_rate; confidence == 1",
            "interval": "finite positive ibi; repeated samples retained",
            "pupil": "finite positive pupil; 0.5 < pupilQ <= 1",
        },
        "units": {
            "time": "recording-relative seconds",
            "heart": "reported bpm",
            "interval": "reported ms",
            "pupil": "reported mm",
        },
        "counts": {
            name: {channel: len(values["values"]) for channel, values in groups.items()}
            for name, groups in data.items()
        },
    }


def render(
    output: Path,
    data: dict,
    info: dict,
    *,
    data_root: str | Path | None = None,
) -> None:
    destinations = paths.output_paths(
        output, OUTPUT_NAMES, data_root=data_root, flat=True
    )
    output = paths.resolve_output_root(output, data_root=data_root)
    output.mkdir(parents=True, exist_ok=True)
    font_directory = Path("/System/Library/Fonts/Supplemental")
    for filename in ("Times New Roman.ttf", "Times New Roman Bold.ttf"):
        font = font_directory / filename
        if font.is_file():
            font_manager.fontManager.addfont(str(font))
    plt.rcParams.update(
        {
            "font.family": "serif",
            "font.serif": ["Times New Roman", "DejaVu Serif"],
            "font.size": 17,
            "axes.spines.top": False,
            "axes.spines.right": False,
        }
    )
    specs = {
        "heart": (
            "Heart rate | recorded samples",
            "Confidence = 1 · no smoothing",
            "Reported heart rate (bpm)",
        ),
        "interval": (
            "Intervals | recorded sample distribution",
            "Positive readings · repeated samples retained",
            "Reported interval (ms)",
        ),
        "pupil": (
            "Pupil | recorded samples",
            "Positive readings · 0.5 < quality ≤ 1",
            "Reported pupil size (mm)",
        ),
    }
    hashes = {}
    for name, groups in data.items():
        title, subtitle, unit = specs[name]
        fig, ax = plt.subplots(figsize=(12, 7.6), facecolor="#f7f9fc")
        fig.subplots_adjust(left=0.16, right=0.95, top=0.76, bottom=0.21)
        fig.text(0.055, 0.94, title, fontsize=26, weight="bold", va="top")
        fig.text(
            0.055,
            0.86,
            f"Released case-study Session 1 · {subtitle}",
            fontsize=17,
            va="top",
        )
        fig.text(
            0.055,
            0.065,
            "Available raw export; channel/device mapping and clock alignment unverified.",
            fontsize=16,
        )
        ax.set_facecolor("#f7f9fc")
        ax.grid(alpha=0.2)
        ax.set_axisbelow(True)
        for color, (channel, values) in zip(
            cycle(COLORS), groups.items(), strict=False
        ):
            readings = np.asarray(values["values"], dtype=float)
            label = f"Channel {channel} · {len(readings):,} readings"
            if name == "interval":
                readings = np.sort(readings)
                ax.step(
                    np.r_[readings[0], readings],
                    np.r_[0, np.arange(1, len(readings) + 1) / len(readings)],
                    where="post",
                    color=color,
                    label=label,
                    linewidth=2.4,
                )
            elif name == "pupil":
                ax.scatter(
                    values["time_s"],
                    readings,
                    s=3,
                    alpha=0.45,
                    color=color,
                    label=label,
                )
            else:
                ax.plot(
                    values["time_s"], readings, linewidth=1.3, color=color, label=label
                )
        ax.set(
            xlabel=unit if name == "interval" else "Recording-relative time (s)",
            ylabel="Cumulative fraction of readings" if name == "interval" else unit,
        )
        if name == "interval":
            ax.set_ylim(0, 1.03)
        ax.legend(frameon=False, fontsize=14)
        filename = f"recorded-{name}.png"
        fig.savefig(
            destinations[filename],
            dpi=100,
            metadata={
                "Description": json.dumps({**info, "panel": name}, sort_keys=True)
            },
        )
        plt.close(fig)
        hashes[filename] = digest(destinations[filename])
    destinations["recording-figures.toml"].write_text(
        metadata_text({**info, "figures": hashes})
    )


def metadata_text(info: dict) -> str:
    lines = []

    def table(values: dict, prefix: tuple[str, ...] = ()) -> None:
        if prefix:
            lines.append("[" + ".".join(json.dumps(key) for key in prefix) + "]")
        lines.extend(
            f"{json.dumps(key)} = {json.dumps(value, ensure_ascii=False)}"
            for key, value in values.items()
            if not isinstance(value, dict)
        )
        lines.append("")
        for key, value in values.items():
            if isinstance(value, dict):
                table(value, (*prefix, key))

    table(info)
    return "\n".join(lines)


def verify(output: Path, info: dict) -> None:
    actual = tomllib.loads((output / "recording-figures.toml").read_text())
    expected = {
        **info,
        "figures": {name: digest(output / name) for name in FIGURE_NAMES},
    }
    if actual != expected:
        raise ValueError("recording figure sources, selections or image bytes differ")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--data-root", type=Path)
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument(
        "--check",
        action="store_true",
        help="check saved figures without writing (default)",
    )
    mode.add_argument(
        "--output-root",
        type=Path,
        help="write figures to a directory outside source data",
    )
    args = parser.parse_args(argv)
    root = paths.resolve_data_root(args.data_root)
    data = payload(root)
    info = provenance(data, root)
    if args.output_root is None:
        verify(ROOT / "outputs", info)
        action = "Verified"
    else:
        render(args.output_root, data, info, data_root=root)
        action = "Wrote"
    print(f"{action} {len(data)} recording panels for case-study Session 1.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError, KeyError, TypeError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
