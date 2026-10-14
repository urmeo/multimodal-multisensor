# Multimodal-Multisensor

Python analysis of eye, cardiac and questionnaire data from 10 adults across three weekly sessions. The code checks recordings, measures within-session variation and compares session summaries.

![Project pipeline: recordings and released group tables are checked and analysed separately, producing plots and tables. Clock-dependent recording analysis is optional.](images/pipeline.svg)

The repository contains 51 CSV files, 24 raw sensor streams and 33 Jupyter notebooks. Eye and cardiac recordings are available. GSR collection was attempted; facial integration was unfinished.

The shared `mms` package uses NumPy, pandas and SciPy for analysis, Matplotlib for plots and scikit-learn for exploratory clustering. The questionnaires include HADS, STAI-S, STAI-T, BFI-10 and the Fear Questionnaire.

## Run the analysis

Use Python 3.11 or 3.12. From a clone of this repository:

```sh
python -m venv .venv
source .venv/bin/activate
python -m pip install -e '.[dev,notebooks,docs]'
python -m pytest tests -q
python -m scripts.build_group_summaries --check
python -m scripts.build_figures --check
python -m scripts.build_recording_figures --check
```

The `--check` commands read the source data without writing files. To inspect the notebooks, run `jupyter lab notebooks`. They are organized into [case study](notebooks/case-study), [group](notebooks/group) and [individual](notebooks/individual) analyses. Run `python scripts/verify_notebooks.py` to execute all 33 in a temporary workspace and check that their inputs stay unchanged.

See [CONTRIBUTING.md](CONTRIBUTING.md) for output settings and the hashed Linux environment. Installed wheels contain code only; use a repository checkout for the included data and notebooks.

## Results and limitations

The released group tables give the following ICC(1,1) estimates for the consistency of within-session standard deviations across three sessions. Each estimate uses 10 participant rows and a 95% confidence interval.

| Within-session standard deviation | ICC | 95% interval |
| :--- | ---: | :--- |
| Interval samples | 0.22 | −0.13 to 0.66 |
| Pupil diameter | 0.45 | 0.07 to 0.79 |
| Response duration | 0.61 | 0.25 to 0.87 |

![ICC estimates and 95 percent confidence intervals](outputs/reliability.png)

These calculations describe the released tables. The small sample and wide intervals do not establish diagnostic accuracy or stable traits. The [Spearman correlation plot](outputs/correlation.png) is also descriptive.

- Repeated cardiac interval samples are not verified unique beats. Cross-stream clock alignment is unverified.
- Two equality patterns in the group tables are suspected duplicates. Most participant rows cannot be reconstructed from the available raw recordings.
- The case-study summaries numerically match group row P02. That match does not independently confirm participant identity.

The [data provenance](DATA_PROVENANCE.md) describes schemas, units, source gaps and reconciliation tolerances. The [figure notes](docs/FIGURES.md) record source hashes, filters and historical images, including photographs of the experimental setup.

## Documentation and data use

Read the [documentation site](https://urmeo.github.io/multimodal-multisensor/) for the workflow, figures and data notes.

The original [technical report](docs/reports/Multimodal%20Multisensor%20Technical%20Report.pdf), [thesis](docs/reports/Thesis%20Report.pdf) and [proposed protocol](docs/reports/CYPSY_Poster.pdf) are preserved. Read the [report corrections](docs/REPORT_STATUS.md) alongside them.

The author records consent for sharing and session photographs. Dates, device labels, responses and recognizable photos remain in the release; participant codes do not make it anonymous. Review the [consent account](DATA_ETHICS.md), [data terms](DATA_LICENSE.md) and [questionnaire rights](NOTICE.md) before reuse. Code and notebooks use the [MIT license](LICENSE). Cite the data using [CITATION.cff](CITATION.cff).

Related repositories: [Sensor](https://github.com/urmeo/sensor), [Psychometric](https://github.com/urmeo/psychometric) and [CalmSense](https://github.com/urmeo/calm-sense).
