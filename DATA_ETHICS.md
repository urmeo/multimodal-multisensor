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
| PDFs and screenshots | Dates, device labels and context |
| Session photographs | Consented recognizable people |

Tables use participant codes instead of names. The release still contains identifying information and is not anonymous. Earlier notebooks remain in Git history. The two raw-data folders contain distinct files; the individual folder's participant mapping is undocumented. Eye and cardiac records are available. GSR and facial outputs are absent.

## Historical timestamp-copy tool

The [archived timestamp-copy tool](https://github.com/urmeo/multimodal-multisensor/blob/0f2b1cc55409b1b68bc9ee52341382263fa4559e/scripts/deidentify_timestamps.py) is no longer included in this checkout. That version validates its 51-file inventory in `case-study/`, `individual/` and `group_results/` without writing files by default. Its `--output-root` option writes copies of CSVs that contain calendar timestamps. Dates shift to a fixed calendar anchor separately for each file and compatible clock domain. Raw TXT, notebooks, reports, media and CSVs without calendar timestamps are not copied or changed.

The tool validates every CSV before writing any copies. It never overwrites source files and rejects malformed nonempty dates. Logs omit original dates and offsets.

Shifting dates within a file preserves differences between compatible timestamps in that file. It does not establish synchronization across streams. The copies still contain sensitive responses and measurements; they are not anonymous.

## Rights and attribution

| Material | Terms |
| :--- | :--- |
| Code | [MIT](LICENSE) |
| Author-owned data and figures | Recorded [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/legalcode.en) grant; retain attribution, cite [CITATION.cff](CITATION.cff) and identify changes |
| HADS wording and screenshots | GL Assessment; [permission process](https://www.gl-assessment.co.uk/policies/permissions/) |
| STAI-S/STAI-T wording, translations and screenshots | Mind Garden; [publication permission](https://www.mindgarden.com/271-mind-garden-forms) and [licensed scope](https://www.mindgarden.com/state-trait-anxiety-inventory-for-adults/28-staiad-transform-survey-hosting.html) |
| BFI-10/Fear Questionnaire items | Rights depend on the original authors and versions; redistribution permission is not recorded here |
| Illustrative photos and report graphics | Author or source rights; recognizable session photographs have the consent account described above |

The recorded CC BY 4.0 copyright grant allows sharing and adaptation, including commercial use. It does not grant all privacy or personality rights. The author's recorded research and education intent and consent account remain separate from copyright permission; they are not additional CC BY copyright restrictions.

Repository licenses do not grant permission to republish protected questionnaire wording, translations or answer options. Historical questionnaire versions and response coding remain unverified; establish them before scoring.

## Use and contact

- Retain attribution and respect consent and third-party rights. Do not reidentify participants or make individual decisions from these records.
- Report identifying evidence privately through [Security](https://github.com/urmeo/multimodal-multisensor/security/advisories/new). Public reproducibility issues should use synthetic examples.
- Send data-subject access, correction, erasure and objection requests to the recorded controller, urme ([@urmeo](https://github.com/urmeo)), through a private channel.
