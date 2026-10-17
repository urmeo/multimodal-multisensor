# Data provenance

## Inventory

| Source | Contents | Status |
| :--- | :--- | :--- |
| `data/case-study/raw` | 12 semicolon-delimited streams | One recording set; its summaries numerically match group row P02 |
| `data/individual/raw` | 12 different streams | Participant mapping is undocumented; files differ from the case-study streams |
| `data/*/processed` | Cardiac, eye and historical derived CSVs | Sampled channels; schemas and units are described below |
| `data/*/psychometric` | Item responses and question timestamps | 88 items per current session; original wording is retained |
| `data/group_results` | 3 tables, P01 to P10, 3 sessions | Released values; raw source mappings are unavailable for most rows |

The dataset contains 51 CSV files and 24 raw TXT files. Suffixes `01`, `02` and `03` identify sessions. Unsuffixed streams supply one baseline per modality, which analyses reuse. Three independent baselines are not documented.

## Schemas and units

| Fields | Meaning and limits |
| :--- | :--- |
| `reltime` | Seconds from that recording's origin; streams have independent origins |
| `datetime` | Calendar time; sensor exports have no timezone offset, while question times explicitly use UTC |
| `iSensor` | Channel identifier; current sample metrics keep channels separate |
| `ibi` | Reported interval in ms; repeated sampled values are not verified intervals between unique normal heartbeats (NN intervals) |
| `heart_rate`, `confidence` | Reported bpm and source confidence |
| `pupil`, `pupilQ`, `gazeQ` | Reported pupil diameter in mm and quality from 0 to 1; current metrics require finite positive readings and stated quality bounds |
| `gazeDir.*`, `gaze_*` | Original/renamed gaze components; legacy 0.01 rule is vector distance per sample, not angular velocity |
| `fixation`, `fixation_id`, `duration` | Historical sample annotations; current event tables give one row per run, duration in seconds, gap/quality handling and censoring status |
| `sdnn`, `rmssd` | Historical names; current interval-sample calculations use 30-sample windows and 29 internal adjacent differences |
| `Time(s)` | Response duration in seconds for current question exports |
| `Question Start Time`, `Question Answer Time` | Question interval boundaries; joins use these intervals rather than the nearest start time and require a documented timezone and confirmed clock synchronization |

Current questionnaire exports contain 14 HADS items, 20 STAI-S items, 20 STAI-T items, 10 BFI items and 24 FQ items. Scoring requires a separate specification of `Answer` coding, reverse-scored items and the historical questionnaire versions. The notebooks do not assign diagnostic categories.

`individual/psychometric/Psychometric_Test_Results_00.csv` is a malformed 88-row legacy export. `Time(s)` holds a start timestamp, `Question Start Time` holds a later timestamp, `Score` holds a duration and `Answer Time` is blank. The file is retained as source evidence and inspected explicitly. The canonical question loader rejects it.

`*_modified.csv`, `QQ.csv`, `QQ2.csv` and `QQHRV.csv` are historical derivatives. Their dates and anxiety/decrease flags remain as source evidence. Those flags are not validated diagnoses.

The three `*_modified.csv` files and the legacy `*_00.csv` omit a leading header. Copies with shifted dates retain the inferred leading field as `source_index`. Source bytes and historical column labels stay unchanged.

## Reconciliation

```sh
python -m scripts.build_group_summaries --check
python -m scripts.build_group_summaries --output-root /tmp/mms-review
```

The legacy calculation takes standard deviations of pooled, unfiltered raw samples. Its numerical match to P02 does not establish participant identity. With `rtol=0`, absolute tolerances of `1e-9` for interval/pupil SD and `3e-5` seconds for duration SD allow known rounding drift. A mismatch returns exit code 1. Check mode writes nothing.

Review outputs include filtered sample metrics for each channel and hashes of the sources and settings. They do not replace the group values or establish unique-beat provenance. Invalid readings affect legacy variance. A variance spike alone does not establish clinical meaning.

## Known equality patterns

| Pattern | Released value | Status |
| :--- | ---: | :--- |
| P01 interval SD, S2=S3 | 65.39 | Suspected duplicate; report lists 1012.69 for S3 |
| P07=P08 duration SD, S1 | 4.409281… | Suspected duplicate; underlying raw records unavailable |

Equal values do not prove copying. Tests check the exact participant IDs, values and number of occurrences for these patterns. New duplicates fail validation. Original cells remain unchanged.

## Clocks and outputs

- Preserve whether timestamps include a timezone. Question-aligned summaries and cross-sensor features require both a documented acquisition timezone (`MMS_SENSOR_TIMEZONE`) and synchronization confirmed by acquisition records (`MMS_CLOCKS_SYNCHRONIZED=1`). Neither is available for the released recordings, so these steps remain skipped.
- Notebook helpers use `MMS_OUTPUT_ROOT` for exports outside source data. Without it, they skip exports. `MMS_DATA_ROOT` selects a directory containing `case-study`, `individual` and `group_results`; command-line scripts use explicit root options.
- Wheels contain code only. Loaders accept `data_root=` for a separately obtained dataset and report an error when required files are missing.

[Report status](docs/REPORT_STATUS.md) · [Figure provenance](docs/FIGURES.md) · [Consent and residual identifiers](DATA_ETHICS.md)
