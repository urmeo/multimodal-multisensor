# Contributing

Use Python 3.11 or 3.12. Run these commands from the repository root:

```sh
python -m pip install -e '.[dev,docs]'
python -m pytest tests -q
python -m scripts.build_group_summaries --check
python -m scripts.build_figures --check
python -m scripts.build_recording_figures --check
```

Describe the method you changed, the command you ran and the expected result. Keep units, clock assumptions, [material rights](NOTICE.md) and [consent limits](DATA_ETHICS.md) explicit. Preserve source observations and historical reports. Use synthetic data for regression tests and public issue reports.

## Notebooks and outputs

Run `python scripts/verify_notebooks.py` to execute all 33 notebooks. It copies the notebooks and data to a temporary workspace, directs exports to a separate directory and checks that both copies and original inputs stay unchanged.

For interactive use, install `python -m pip install -e '.[notebooks]'` and run `jupyter lab notebooks`.

The notebook helpers use these environment variables:

| Variable | Purpose |
| :--- | :--- |
| `MMS_DATA_ROOT` | Directory containing `case-study`, `individual` and `group_results`; defaults to the checkout's `data/` directory |
| `MMS_OUTPUT_ROOT` | Separate directory for generated tables and figures; without it, notebook helpers skip exports |
| `MMS_SENSOR_TIMEZONE` | Documented acquisition timezone for sensor timestamps without an offset; required before joining them to UTC question times |
| `MMS_CLOCKS_SYNCHRONIZED` | Set to `1` only when acquisition metadata confirms clock synchronization; also required for cross-sensor clustering |

Command-line scripts use their explicit `--data-root` and `--output-root` options. Output directories must be separate from source data. A timezone declaration alone does not establish synchronized clocks.

## Hashed environment

The lock file targets CPython 3.11 on x86_64 GNU/Linux. It pins distributions and their hashes; runtime behavior may still vary across platforms.

```sh
python -m pip install --require-hashes -r requirements.lock
python -m pip install -e . --no-deps
```

## Documentation site

The site uses the repository's Markdown files, figures and reports. Build it locally with:

```sh
python -m pip install -e '.[docs]'
python scripts/build_docs.py
python -m http.server 8000 --directory build/docs
```

Open `http://localhost:8000`. The build checks local page and asset links. Notebooks, code and data links open their source files on GitHub. The Verify workflow publishes to GitHub Pages after all checks pass on `main`.
