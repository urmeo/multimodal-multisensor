#!/usr/bin/env python3
"""Execute notebooks on copied inputs and verify source bytes stay unchanged."""

from __future__ import annotations

import argparse
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FOLDERS = ("notebooks/case-study", "notebooks/group", "notebooks/individual")


def hashes(root: Path) -> dict[str, str]:
    return {
        str(path.relative_to(root)): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in root.rglob("*")
        if path.is_file()
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.parse_args(argv)
    before = hashes(ROOT / "data")
    with tempfile.TemporaryDirectory(prefix="mms-notebooks-") as name:
        scratch = Path(name)
        shutil.copytree(ROOT / "data", scratch / "data")
        notebooks = []
        for folder in FOLDERS:
            sources = sorted((ROOT / folder).glob("*.ipynb"))
            if not sources:
                raise ValueError(f"no source notebooks in {folder}")
            destination = scratch / folder
            destination.mkdir(parents=True)
            for source in sources:
                target = destination / source.name
                shutil.copy2(source, target)
                notebooks.append(target)
        environment = os.environ.copy()
        python_path = [str(ROOT)]
        if environment.get("PYTHONPATH"):
            python_path.append(environment["PYTHONPATH"])
        environment.update(
            PYTHONPATH=os.pathsep.join(python_path),
            MMS_DATA_ROOT=str(scratch / "data"),
            MMS_OUTPUT_ROOT=str(scratch / "outputs"),
            IPYTHONDIR=str(scratch / "ipython"),
            JUPYTER_DATA_DIR=str(scratch / "jupyter-data"),
            JUPYTER_CONFIG_DIR=str(scratch / "jupyter-config"),
            JUPYTER_RUNTIME_DIR=str(scratch / "jupyter-runtime"),
            MPLCONFIGDIR=str(scratch / "matplotlib"),
            OPENBLAS_NUM_THREADS="1",
            OMP_NUM_THREADS="1",
        )
        environment.pop("MMS_SENSOR_TIMEZONE", None)
        command = [
            sys.executable,
            "-m",
            "pytest",
            "--nbmake",
            "--nbmake-kernel=python3",
            "--nbmake-timeout=900",
            "-q",
            *map(str, notebooks),
        ]
        result = subprocess.run(command, cwd=scratch, env=environment, check=False)
        if hashes(ROOT / "data") != before or hashes(scratch / "data") != before:
            raise ValueError("notebook execution changed source inputs")
        if result.returncode:
            return result.returncode
        print(f"All {len(notebooks)} notebooks executed; original and copied inputs unchanged.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (OSError, ValueError) as error:
        print(f"Error: {error}", file=sys.stderr)
        raise SystemExit(1)
