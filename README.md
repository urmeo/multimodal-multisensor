# Multimodal-Multisensor

Longitudinal study where 10 adults completed standardized psychology tests across three weekly sessions while wearing multiple biometric sensors. Combines self-report psychometric data with real-time physiological recordings.

## Study design

| Parameter | Detail |
|-----------|--------|
| Participants | 10 adults |
| Sessions | 3 per participant (weekly intervals) |
| Design | Longitudinal, within-subjects |
| Key finding | People differed a lot from each other, but each person's pattern stayed consistent across sessions |

## Psychometric instruments

- **HADS** — Hospital Anxiety and Depression Scale
- **STAI-S** — State-Trait Anxiety Inventory (State subscale)
- **BFI-10** — Big Five Inventory (10-item short form)
- **Fear Questionnaire** — Marks-Mathews phobia assessment

<p align="center">
  <img src="images/scoring-results.png" width="45%" />
</p>

## Sensors used

| Modality | Sensor | What it measures |
|----------|--------|------------------|
| Eye tracking | Pupil Labs Core | Gaze position, pupil dilation, fixations, saccades |
| Cardiac | Polar H10+ | Heart rate, HRV (SDNN, RMSSD), inter-beat intervals |
| Electrodermal | TEA GSR | Galvanic skin response, skin conductance level |
| Facial analysis | OpenFace | Action units, head pose, gaze direction |

## Experimental setup

<p align="center">
  <img src="images/Thales Human Performance Monitoring for Data Collection.png" width="85%" />
</p>
<p align="center">
  <img src="images/experimental_setup.jpg" width="36%" />
  &nbsp;&nbsp;
  <img src="images/Eye-Tracking calibration.png" width="56%" />
</p>
<p align="center">
  <img src="images/data_collection_session.jpg" width="48%" />
  &nbsp;
  <img src="images/participant_testing.jpg" width="48%" />
</p>

## How it was done

1. **Recruitment** — Adult participants screened and enrolled
2. **Baseline** — Resting-state sensor calibration before each session
3. **Assessment** — Psychometric tests administered while all sensors record simultaneously
4. **Data collection** — Synchronized multimodal streams captured per participant per session
5. **Analysis** — Individual and group-level correlations between self-report and physiological data

## Key findings

There's high variability between people (everyone responds quite differently during testing) but low variability within each person across sessions (each individual's physiological pattern stays pretty consistent). This suggests these responses reflect stable individual traits rather than just random fluctuation.

<p align="center">
  <img src="images/correlation_heatmap_with_values_final.png" width="70%" />
</p>

## Results

<p align="center">
  <img src="images/Standard Deviation of HRV (SDNN).png" width="85%" />
</p>
<p align="center">
  <img src="images/Standard Deviation of Pupil Dilation.png" width="70%" />
</p>
<p align="center">
  <img src="images/Group Duration.png" width="85%" />
</p>
<p align="center">
  <img src="images/pca_kmeans_clusters.png" width="52%" />
  &nbsp;
  <img src="images/silhouette_score.png" width="44%" />
</p>

## Tech Stack

Python · Jupyter · pandas · NumPy · SciPy · Matplotlib · Seaborn · scikit-learn

## Keywords

IoT · Machine Learning · Multimodal · Neurophysiological · Multi-Sensors · Psychometrics

## Related repos

- [Sensor](https://github.com/urmeo/sensor) — Review of the biometric sensors used here
- [Psychometric](https://github.com/urmeo/psychometric) — Web app for the psychometric tests used in this study
- [CalmSense](https://github.com/urmeo/calm-sense) — ML/DL stress detection from physiological signals

## License

[MIT](LICENSE)
