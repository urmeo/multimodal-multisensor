# Analysis pipeline

The six current relative-time source files stay in `data/`. Calendar originals are retained privately outside the repository; existing history and earlier copies are unaffected. The notebook
produces six descriptive charts; it does not train a classifier.

```mermaid
flowchart LR
    A[Six supplied CSVs] --> B[Schema and provenance checks]
    B --> C[Exploration notebook]
    C --> D[Six charts and figure hashes]
    D --> E[Static visual report]
    F[sed.csv] --> G[Legacy reproduction]
    G --> H[Compare supplied sed_fix.csv]
    F --> I[Configured candidate detection]
    I --> J[Separate event CSV and parameter JSON]
```

`sed_fix.csv` supplies the notebook's historical run histogram. Reproducing its
flags does not validate fixation accuracy. Candidate events use a separate
command and are not included in the six charts. Supplied eye summaries and
questionnaire timing are independent inputs; clock alignment and summary
aggregation remain unverified.

See [Run the analysis](../README.md#run-the-analysis) for setup, checks and figure commands.

| Folder | Contents |
| --- | --- |
| `data/` | Six source CSVs, field dictionary and recording manifest |
| `notebooks/` | Descriptive analysis and chart definitions |
| `scripts/` | Summary checks, sensitivity analysis, timestamp copies, figure generation and documentation |
| `tests/` | Source contracts and synthetic regression cases |
| `docs/figures/` | Versioned chart previews and their hash manifest |
| `docs/reviews/` | Original historical PDFs |
| `docs/images/` | Reviewed product images and their credits |
| `docs/index.html` | Static visual report |
| `outputs/` | Local exports, including candidate events and relative-time copies |
