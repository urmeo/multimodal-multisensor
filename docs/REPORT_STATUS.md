# Report status

The PDFs retain their bytes from release baseline `a369ee0dc2dcac24feaa9e2e1faf160c39d5a3de`, which revised the thesis and poster. Locations use PDF pages, with printed page numbers where they differ. The result tables are retained; their [analysis code](https://github.com/urmeo/multimodal-multisensor/tree/0f2b1cc55409b1b68bc9ee52341382263fa4559e) is no longer included in this checkout. The source gaps below limit interpretation of the historical reports.

| Report | Status |
| :--- | :--- |
| [Technical report](reports/Multimodal%20Multisensor%20Technical%20Report.pdf), 12 pages | Historical methods and results |
| [Thesis](reports/Thesis%20Report.pdf), 53 pages | Protocol, analyses and consent appendices |
| [Poster](reports/CYPSY_Poster.pdf), 1 page | Proposed protocol and expected results |

## Corrections and source gaps

| Location | Correction or unresolved issue |
| :--- | :--- |
| Technical p3 | The report counts openness values above 1 as closed; the archived analysis uses values at or below 1 for candidate closure. Units and polarity are unverified. Its event rules require observed reopening and handle gaps. Gaze distance was not angular velocity. |
| Technical p6 | P01 S3 interval SD is 1012.69 in the report and 65.39 in the CSV. The original raw source is unavailable. Both values are preserved; the discrepancy is unresolved. |
| Technical p8 to 11 | Claims about agreement at k = 3, PCA before clustering, HADS validation and stable traits exceed the code evidence. The case study clusters timestamp samples from one person. It does not validate clinical or participant categories. |
| Thesis p25, printed 28 | Some p values exceed 1; values shown as 0.00 are rounded. Recovering lost exponents and precision requires the original statistical output. No replacement values are supplied. |
| Thesis p37 to 38, printed 40 to 41 | Available eye and cardiac analyses differ from the planned GSR and facial integration. Diagnostic and stable-trait conclusions exceed the evidence from the uncertain ten-person estimates. |
| Thesis p4 to 5, printed 7 to 8 | The protocol limits access to the research team. It differs from the author's later account of consent for sharing. No review identifier is independently established. |
| Thesis p46, printed 49 | Annexes E/F explicitly record photo consent. |
| Poster | The poster gives a target of 10 participants, expected results and a planned CER submission. Its Tobii/Empatica equipment, PHQ/ACEs instruments and age range of 18 to 30 differ from later methods. It does not document approval or measured results. |

## Cardiac sensitivity

The original P01 S3 export is absent from the released files and Git history. The preserved sensitivity results compare the released value, the report's printed value and omission of P01 from all three group tables.

| Scenario | Participants | ICC(1,1) of interval-sample SD | 95% interval |
| :--- | ---: | ---: | :--- |
| Released CSV: P01 S3 = 65.3938 | 10 | 0.221 | −0.131 to 0.659 |
| Report candidate: P01 S3 = 1012.69 | 10 | 0.038 | −0.253 to 0.509 |
| Omit P01 from all metrics | 9 | 0.216 | −0.150 to 0.680 |

![Cardiac ICC intervals and session correlations for the three sensitivity scenarios](../outputs/sensitivity/sensitivity.png)

The report value is rounded and unverified. Neither alternative establishes the correct value. Released tables remain unchanged. Substitution changes eight of 36 Spearman correlations, with a maximum absolute change of 0.109. Pupil and response-duration ICCs remain unchanged in that scenario. Participant omission changes all three metrics' estimates.

[ICC results](../outputs/sensitivity/icc.csv) · [Correlations](../outputs/sensitivity/correlations.csv) · [Omnibus tests](../outputs/sensitivity/omnibus.csv) · [Paired tests](../outputs/sensitivity/paired.csv)

The [archived sensitivity script](https://github.com/urmeo/multimodal-multisensor/blob/0f2b1cc55409b1b68bc9ee52341382263fa4559e/scripts/build_group_sensitivity.py) records the three scenarios and calculations.

## Bibliography

The Green/Harlow eye-tracking attribution to *Journal of Anxiety Disorders 73:102233* is incorrect. That identifier belongs to McKay, Yang, Elhai and Asmundson's 2020 study of COVID-related disgust and anxiety, DOI [10.1016/j.janxdis.2020.102233](https://pmc.ncbi.nlm.nih.gov/articles/PMC7194061/). It does not support the attributed eye-tracking claim. The historical Johnson/Bennett titles remain unverified.

## Current evidence

- **Interpretation:** the group estimates have wide confidence intervals. They do not validate anxiety diagnoses or stable traits.
- **Sample units:** cardiac records contain repeated interval samples without timing for verified unique normal heartbeats. Group response-duration values are within-session standard deviations in seconds.
- **Source gaps:** equal-value patterns, missing clock metadata and undocumented participant mapping limit independent reconstruction.

[Data and consent](../DATA_ETHICS.md) · [Figures](FIGURES.md)
