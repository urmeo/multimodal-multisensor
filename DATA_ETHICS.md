# Data and consent

## Recorded consent

The author states that all 10 adults gave written informed consent. This account includes later open sharing for research and education and withdrawal without penalty. Not every consent or review record is independently verified.

The thesis describes an earlier protocol limited to the research team. The poster proposes a CER submission; it does not document approval. No approval identifier is recorded here. The author names GDPR and French data-protection law as the governing framework. That statement does not establish institutional approval or independently verified compliance.

The thesis describes explicit consent for recognizable session photographs in Annexes E/F, PDF page 46, printed page 49. Photo consent is separate from the use of participant codes in tables and from questionnaire copyright.

## Actual release scope

| Material | Residual information |
| :--- | :--- |
| CSVs and raw TXT | Responses, physiological data, calendar timestamps and channel/device labels |
| QQ and modified CSVs | Historical dates, derived flags and responses |
| Notebooks, PDFs and screenshots | Dates, device labels and context |
| Session photographs | Consented recognizable people |

Tables use participant codes instead of names. The release still contains identifying information and is not anonymous. The two raw-data folders contain distinct files; the individual folder's participant mapping is undocumented. Eye and cardiac records are available. GSR and facial outputs are absent.

## Timestamp copies

```sh
python -m scripts.deidentify_timestamps
python -m scripts.deidentify_timestamps --output-root /tmp/mms-time-copies
```

The first command validates all 51 CSVs without writing files. Adding `--output-root` writes copies of CSVs that contain calendar timestamps. Dates shift to a fixed calendar anchor separately for each file and compatible clock domain. Raw TXT, notebooks, reports, media and CSVs without calendar timestamps are not copied or changed.

The tool validates every CSV before writing any copies. It never overwrites source files and rejects malformed nonempty dates. Logs omit original dates and offsets.

Shifting dates within a file preserves differences between compatible timestamps in that file. It does not establish synchronization across streams. The copies still contain sensitive responses and measurements; they are not anonymous.

## Use and contact

- Retain attribution and comply with [data terms](DATA_LICENSE.md), consent limits and [instrument rights](NOTICE.md). Do not reidentify participants or make individual decisions from these records.
- Report identifying evidence privately through [Security](https://github.com/urmeo/multimodal-multisensor/security/advisories/new). Public reproducibility issues should use synthetic examples.
- Send data-subject access, correction, erasure and objection requests to the recorded controller, urme ([@urmeo](https://github.com/urmeo)), through a private channel.
