# Multimodal-Multisensor

Eye, cardiac and questionnaire data from a study of 10 adults across three weekly sessions. The release includes available recordings, group tables, saved plots and reports.

![Historical analysis workflow. The analysis code has been removed; recordings and saved results remain.](images/pipeline.svg)

[View full size](images/pipeline.svg) · [Historical Figma design](https://www.figma.com/board/hexcUfwWED4MIu7wjxmWrU/) · [Design files](design/README.md)

The release includes 24 raw sensor streams. GSR collection was attempted; facial integration was unfinished. The questionnaires include HADS, STAI-S, STAI-T, BFI-10 and the Fear Questionnaire.

The shared analysis package and its scripts have been removed. Saved results remain available, but this checkout cannot recalculate them. The [last version with analysis code](https://github.com/urmeo/multimodal-multisensor/tree/0f2b1cc55409b1b68bc9ee52341382263fa4559e) remains in Git history.

## Build the documentation

Use Python 3.11 or 3.12. Run from the repository root:

```bash
python -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest tests -q
python scripts/build_docs.py
python -m http.server 8000 --directory build/docs
```

Open `http://localhost:8000`. The build uses Mistune to render Markdown into `build/docs`. The tests check documentation links, output boundaries and recovery from failed builds.

## Saved results and limitations

The released group tables gave the following ICC(1,1) estimates for the session-to-session reliability of within-session standard deviations. Each estimate used 10 participant rows across three sessions and a 95% confidence interval.

| Within-session standard deviation | ICC | 95% interval |
| :--- | ---: | :--- |
| Interval samples | 0.22 | −0.13 to 0.66 |
| Pupil diameter | 0.45 | 0.07 to 0.79 |
| Response duration | 0.61 | 0.25 to 0.87 |

![Saved ICC estimates and 95 percent confidence intervals](outputs/reliability.png)

These calculations describe the released tables. The small sample and wide intervals do not establish diagnostic accuracy or stable traits. The [saved Spearman correlation plot](outputs/correlation.png) is also descriptive.

- Repeated cardiac interval samples are not verified unique beats. Cross-stream clock alignment is unverified.
- Two equality patterns in the group tables are suspected duplicates. Most participant rows cannot be reconstructed from the available raw recordings.
- The case-study summaries numerically match group row P02. That match does not independently confirm participant identity.

The [figure notes](docs/FIGURES.md) record source hashes, filters and historical images, including photographs of the experimental setup.

## Documentation and data use

[Browse the published documentation](https://urmeo.github.io/multimodal-multisensor/).

The original [technical report](docs/reports/Multimodal%20Multisensor%20Technical%20Report.pdf), [thesis](docs/reports/Thesis%20Report.pdf) and [proposed protocol](docs/reports/CYPSY_Poster.pdf) are preserved. Read the [report corrections](docs/REPORT_STATUS.md) alongside them.

The author records consent for sharing and session photographs. Dates, device labels, responses and recognizable photos remain in the release; participant codes do not make it anonymous. Review the [data use and consent notes](DATA_ETHICS.md) before reuse. Code uses the [MIT license](LICENSE). Cite the data using [CITATION.cff](CITATION.cff).
