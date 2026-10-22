# Data dictionary

This dictionary covers only the six CSVs directly under `data/`. It does not cover `case-study/`, `individual/` or `group_results/`. These six files describe one participant. Sensor readings and questionnaire responses cover Session 1; supplied eye summaries cover three sessions. The tables below describe stored fields and constraints. [Data rights and consent](../DATA_ETHICS.md) apply to every resource.

| Resource | Rows | Scope |
|---|---:|---|
| `hr.csv` | 4,032 | Sampled heart-rate readings |
| `ibi.csv` | 2,394 | Quantized interval readings |
| `sed.csv` | 34,171 | Eye-tracking export |
| `sed_fix.csv` | 34,171 | Original eye columns plus legacy segmentation |
| `eye_metrics.csv` | 264 | 88 question summaries × 3 sessions |
| `Psychometric_Test_Results.csv` | 88 | Session 1 item responses |

## Recording provenance

| Recording | Supplied resources / selectors | Acquisition evidence |
|---|---|---|
| `session-1` | `hr`, `ibi`: channels 0–5; `sed`, derived `sed_fix`: channel 0; `eye_metrics`: `Test 01`; `psych` | Device mappings and calibration unknown; summary lineage/aggregation unknown |
| `session-2` | `eye_metrics`: `Test 02` | Raw streams and acquisition/calibration logs absent; aggregation unknown |
| `session-3` | `eye_metrics`: `Test 03` | Raw streams and acquisition/calibration logs absent; aggregation unknown |

Calendar dates are withheld from these six files. Other dataset directories retain calendar timestamps. Session labels preserve recording grouping and do not establish shared clocks. Each `iSensor` identifier is local to its file; matching numbers in HR and IBI do not identify the same physical unit. Summary rows have no channel identifier. Their relationship to the available raw streams remains unverified, including Session 1.

## Clocks

| Resource | Current elapsed fields | Origin | Original calendar zone |
|---|---|---|---|
| `hr`, `ibi`, `sed`, `sed_fix` | `reltime` | Existing recording-relative seconds, unchanged | Naive; unspecified |
| `eye_metrics` | `Start (s)`, `End (s)` | Earliest start within each `Test`; separate zero per session | Naive; unspecified |
| `psych` | `Question Start (s)`, `Question Answer (s)` | Earliest questionnaire start | Aware; UTC |

- These six CSVs contain relative time only. They do not provide a calendar origin, calendar date or between-session gap.
- Sensor streams span about 535 seconds. Their existing offsets and every non-calendar cell are retained. Summary and questionnaire intervals retain their original precision; no cross-resource offset is inferred.
- Origins differ by resource and session. Equal elapsed readings do not establish synchronization, and the original timezone and acquisition clock mappings remain unverified.
- The six-file conversion does not remove calendar values from other dataset directories, existing Git history, forks, clones or earlier downloads. It does not make sensitive responses or physiological patterns anonymous. See [data ethics](../DATA_ETHICS.md).

## Heart rate and interval readings

| File | Column | Type | Stored range / meaning |
|---|---|---|---|
| Both | `reltime` | number | 0.001–534.892 s from recording start |
| Both | `iSensor` | integer | Anonymous channel 0–5; device mapping unavailable |
| `hr` | `confidence` | number | 0 or 1; historical filtering retained 1 |
| `hr` | `heart_rate` | number | 0–73 BPM; zero values retained from the export |
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

The cause of the all-zero head fields is unknown. Historical filtering notes retain finite, positive pupil readings with finite quality values satisfying `0.5 < pupilQ <= 1`. This is a descriptive filter, not a validated anxiety rule. The filtering implementation is not included in this checkout.

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
- A historical comparison used `rtol=0` and `atol=1e-9`. Its implementation is not included in this checkout.

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

The instrument variant, reverse-keying and aggregate scoring are undocumented. These codes are not validated scale totals. The elapsed question intervals match `Time(s)` within 0.001 s. Longer responses do not establish deliberation, avoidance or anxiety.
