# Group Analysis

Group-level analysis of physiological data from 10 participants across 3 sessions. Focuses on HRV, pupil dilation, and psychometric test timing — pulling out summary statistics and looking at correlations between modalities.

## What's measured

| Metric | Source | What it captures |
|--------|--------|------------------|
| HRV SDNN | Polar H10+ (inter-beat intervals) | Cardiac autonomic regulation — standard deviation of NN intervals |
| Pupil Dilation STD | Pupil Labs Core | Variability in pupil diameter, indexes cognitive load and arousal |
| Test Duration STD | Psychometric app timestamps | Response time variability across test items |

## Notebooks

```
├── Group_Analysis.ipynb               # Full cohort psychometric + physiology analysis
├── Group Correlation Matrix.ipynb     # Cross-modal correlation analysis
├── Group HRV.ipynb                    # Heart rate variability across sessions
├── Group Eye.ipynb                    # Pupil dilation across sessions
├── Group Duration.ipynb               # Test completion time analysis
├── Group SD.ipynb                     # Standard deviation metrics
├── Group Time.ipynb                   # Response timing analysis
└── Duration.ipynb                     # Per-session duration breakdowns
```

Summary CSVs live in `../data/group_results/`.

## Analysis approach

1. **Aggregation** — Each notebook reads per-participant summary CSVs from `data/group_results/`
2. **Group statistics** — Compute means, standard deviations, and ranges across all participants and sessions
3. **Correlation** — Cross-modal analysis looking at relationships between HRV, pupil dilation, and response timing
