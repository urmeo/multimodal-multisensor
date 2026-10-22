# Data dictionary

The data comes from one participant. Raw sensor readings and questionnaire responses cover Session 1; supplied eye summaries cover three sessions. The tables below describe stored fields and constraints. [Data rights and consent](../DATA_ETHICS.md) apply to every resource.

| Resource | Rows | Scope |
|---|---:|---|
| `hr.csv` | 4,032 | Sampled heart-rate readings |
| `ibi.csv` | 2,394 | Quantized interval readings |
| `sed.csv` | 34,171 | Eye-tracking export |
| `sed_fix.csv` | 34,171 | Original eye columns plus legacy segmentation |
| `eye_metrics.csv` | 264 | 88 question summaries × 3 sessions |
| `Psychometric_Test_Results.csv` | 88 | Session 1 item responses |

## Recording provenance

[RECORDING_PROVENANCE.json](RECORDING_PROVENANCE.json) records each resource's session, observed channels and source SHA-256 hash. It marks acquisition facts unknown where evidence is missing.

| Recording | Supplied resources / selectors | Acquisition evidence |
|---|---|---|
| `session-1` | `hr`, `ibi`: channels 0–5; `sed`, derived `sed_fix`: channel 0; `eye_metrics`: `Test 01`; `psych` | Device mappings and calibration unknown; summary lineage/aggregation unknown |
| `session-2` | `eye_metrics`: `Test 02` | Raw streams and acquisition/calibration logs absent; aggregation unknown |
| `session-3` | `eye_metrics`: `Test 03` | Raw streams and acquisition/calibration logs absent; aggregation unknown |

Calendar dates are withheld from the current publication. Session labels preserve recording grouping and do not establish shared clocks. Each `iSensor` identifier is local to its file; matching numbers in HR and IBI do not identify the same physical unit. Summary rows have no channel identifier. Their `source_data` is null, including Session 1, because their relationship to available raw streams has not been reproduced.

Each stream has device, calibration, clock and aggregation records. Metadata states describe the available evidence:

- `unknown` uses null fields and explains what evidence is missing.
- `not_applicable` is used for sensor calibration of questionnaire responses.
- `reproduced` records the known historical `sed` → `sed_fix` transformation and parameters. It does not establish how the original file was produced or validate fixation events.
- `verified` requires recording-specific evidence and identifying details.

## Clocks

| Resource | Current elapsed fields | Origin | Original calendar zone |
|---|---|---|---|
| `hr`, `ibi`, `sed`, `sed_fix` | `reltime` | Existing recording-relative seconds, unchanged | Naive; unspecified |
| `eye_metrics` | `Start (s)`, `End (s)` | Earliest start within each `Test`; separate zero per session | Naive; unspecified |
| `psych` | `Question Start (s)`, `Question Answer (s)` | Earliest questionnaire start | Aware; UTC |

- All six current CSVs contain relative time only. No calendar origin, calendar date or between-session gap is published in the current data or recording metadata.
- Sensor streams span about 535 seconds. Their existing offsets and every non-calendar cell are retained. Summary and questionnaire intervals retain their original precision; no cross-resource offset is inferred.
- Origins differ by resource and session. Equal elapsed readings do not establish synchronization, and the original timezone and acquisition clock mappings remain unverified.
- The schema's `timeRepresentation`, `timeZone`, `timestampAwareness`, `timestampFields`, `relativeTimeFields`, `relativeTimeOrigin` and `sourceTimeZone` are custom descriptive metadata. Relative seconds have no timezone; `sourceTimeZone` describes the former calendar clock only.
- The manifest records current hashes and `original_sha256` hashes of byte-exact originals retained privately outside the repository. The conversion preserves all non-calendar cells, row order and row counts. The exporter also accepts already-relative samples without changing their values.
- Current relative-only publication does not remove calendar values from existing Git history, forks, clones or earlier downloads. It does not make sensitive responses or physiological patterns anonymous. See [data ethics](../DATA_ETHICS.md).

## Heart rate and interval readings

| File | Column | Type | Stored range / meaning |
|---|---|---|---|
| Both | `reltime` | number | 0.001–534.892 s from recording start |
| Both | `iSensor` | integer | Anonymous channel 0–5; device mapping unavailable |
| `hr` | `confidence` | number | 0 or 1; `valid_hr` retains 1 |
| `hr` | `heart_rate` | number | 0–73 BPM; zero represents no lock in supplied metadata |
| `ibi` | `ibi` | integer | 0–1,093 ms; zero initialization values retained |

| Channel observation | Meaning |
|---|---|
| 3 and 5 | Active HR/interval channels; hardware identities unrecorded |
| 0, 1, 2, 4 | Initialization rows without valid HR signal |
| Interval counts | Channel 5: 1,809; channel 3: 581; four initialization rows |

The repeated, quantized interval readings are not a verified NN or R-R beat sequence. They do not support reliable RMSSD or SDNN estimates. Reviewing Polar and Moofit devices does not establish channel identities; HW401 is an optical PPG device.

## Eye stream: `sed.csv`

The historical filename means “Smart Eye Data”. Recorded device, adapter, sampling configuration, coordinate units and calibration are undocumented.

| Column | Type | Stored range / meaning |
|---|---|---|
| `reltime` | number | 0.001–534.979 s from recording start |
| `iSensor` | integer | 0 |
| `headPos.x`, `headPos.y`, `headPos.z` | number | All zero; coordinate units unknown |
| `headPosQ` | number | All zero |
| `headYaw`, `headPitch`, `headRoll` | number | All zero; angle units unknown |
| `headRotQ` | number | All zero |
| `gazeSrc.x`, `gazeSrc.y`, `gazeSrc.z` | number | Approximately −0.02 to 0.01; coordinate units unknown |
| `gazeDir.x`, `gazeDir.y`, `gazeDir.z` | number | Reported gaze-direction components, approximately −0.3 to 1 |
| `gazeQ` | number | Reported tracking quality, 0.11–1 |
| `leftEyeOpen`, `rightEyeOpen` | number | Reported openness scale, 0–10 |
| `leftEyeOpenQ`, `rightEyeOpenQ` | number | Reported quality, 0–1 |
| `pupil` | number | 0–3.88; reported mm, calibration unavailable |
| `pupilQ` | number | Reported measurement quality, 0–1 |

The cause of the all-zero head fields is unknown. `valid_pupil` keeps finite, positive pupil readings and finite quality values with `0.5 < pupilQ <= 1` by default. Its configurable cutoff must be finite and within 0–1. This is a descriptive filter, not a validated anxiety rule.

Boolean, datetime/date and timedelta values in either measurement column raise `ValueError` before numeric conversion. This includes values in mixed object columns and temporal `NaT` values. Numeric strings are converted as before. Ordinary missing values (`None`, `pd.NA`, `np.nan`) and nonnumeric strings are excluded.

## Legacy runs: `sed_fix.csv`

All 23 current eye-source columns are retained; the calendar column has been removed from both eye CSVs.

| Added column | Type | Definition |
|---|---|---|
| `gaze_diff` | number | Euclidean displacement between consecutive direction vectors; first row null; dimensionless |
| `fixation` | boolean | `gaze_diff < 0.01`; first row false |
| `fixation_id` | integer | 1-based ID for every contiguous true **or** false run |
| `duration` | number | Last-minus-first `reltime` in a true run, repeated on its rows; null for false runs |

- Existing observations: 30,289 true samples; 2,479 true runs; 4,958 total runs; true-run spans 0–1.938 s.
- This low-movement heuristic has no quality, gap or minimum-duration rule. False samples are not measured saccades.
- Reproduction compares derived numbers with `rtol=0`, `atol=1e-9`. The source CSV remains unchanged.

## Supplied summaries: `eye_metrics.csv`

Previously named `HRV.csv`; these are eye summaries. Aggregation code, baseline intervals, blink-event rules and calibrated pupil scale are unavailable.

| Column | Type | Supplied meaning |
|---|---|---|
| `Test` | string | `Test 01`, `Test 02`, `Test 03` |
| `Type` | string | `HADS`, `STAI-S`, `STAI-T`, `BFI`, `FQ` |
| `Start (s)`, `End (s)` | number | Supplied question boundaries in elapsed seconds from each session's earliest start |
| `Score` | integer | Stored item code, 0–6 |
| `Average Pupil Dilation` | number | 1.22–3.13; reported mm; diameter versus baseline change unverified |
| `Average Left Blink Rate` | number | 0–254.05; reported blinks/min |
| `Average Right Blink Rate` | number | 0–458.43; reported blinks/min |
| `Pupil Dilation Increase` | string | Supplied `Yes`/`No` flag |
| `Left Blink Rate Increase`, `Right Blink Rate Increase` | string | Supplied `Yes`/`No` flags |

Session 1 has 88 “Yes” pupil flags. Their cause is unknown. Large blink values and all flags remain as supplied; no clinical threshold or silent cleaning is applied. Raw Sessions 2–3 are unavailable. Matching clock readings alone do not reproduce the summaries.

## Responses: `Psychometric_Test_Results.csv`

| Column | Type | Stored meaning |
|---|---|---|
| `Test` | string | HADS 14; STAI-S 20; STAI-T 20; BFI 10; FQ 24 rows |
| `Question` | string | Original instrument wording; third-party rights |
| `Answer` | string | Selected wording; third-party answer-option rights remain |
| `Score` | integer | Stored item code, 1–6; keyed scoring unestablished |
| `Time(s)` | number | Response duration, 2.016–22.737 s |
| `Question Start (s)`, `Question Answer (s)` | number | Elapsed seconds from the earliest questionnaire start |

The instrument variant, reverse-keying and aggregate scoring are undocumented. These codes are not validated scale totals. Time fields are checked against `Time(s)` within 0.001 s. Longer responses do not establish deliberation, avoidance or anxiety.
