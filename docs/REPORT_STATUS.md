# Report status

Original PDFs are preserved byte for byte. Locations below refer to PDF pages, with printed page numbers where they differ. Use the current code and tables for reproducible calculations, and read the source gaps below alongside the historical reports.

| Report | Status |
| :--- | :--- |
| [Technical report](reports/Multimodal%20Multisensor%20Technical%20Report.pdf), 12 pages | Historical methods and results |
| [Thesis](reports/Thesis%20Report.pdf), 53 pages | Protocol, analyses and consent appendices |
| [Poster](reports/CYPSY_Poster.pdf), 1 page | Proposed protocol and expected results |

## Corrections and source gaps

| Location | Correction or unresolved issue |
| :--- | :--- |
| Technical p3 | The report's eye-open threshold above 1 conflicts with the old code's closure threshold at or below 1. Units and polarity need confirmation. Current blink output uses a stated heuristic that requires observed reopening and handles gaps. Gaze distance was not angular velocity. |
| Technical p6 | P01 S3 interval SD is 1012.69 in the report and 65.39 in the CSV. The original raw source is unavailable. Both values are preserved; the discrepancy is unresolved. |
| Technical p8 to 11 | Claims about agreement at k = 3, PCA before clustering, HADS validation and stable traits exceed the code evidence. The case study clusters timestamp samples from one person. It does not validate clinical or participant categories. |
| Thesis p25, printed 28 | Some p values exceed 1; values shown as 0.00 are rounded. Recovering lost exponents and precision requires the original statistical output. No replacement values are supplied. |
| Thesis p37 to 38, printed 40 to 41 | Available eye and cardiac analyses differ from the planned GSR and facial integration. Diagnostic and stable-trait conclusions exceed the evidence from the uncertain ten-person estimates. |
| Thesis p4 to 5, printed 7 to 8 | The protocol limits access to the research team. It differs from the author's later account of consent for sharing. No review identifier is independently established. |
| Thesis p46, printed 49 | Annexes E/F explicitly record photo consent. |
| Poster | The poster gives a target of 10 participants, expected results and a planned CER submission. Its Tobii/Empatica equipment, PHQ/ACEs instruments and age range of 18 to 30 differ from later methods. It does not document approval or measured results. |

## Bibliography

The Green/Harlow eye-tracking attribution to *Journal of Anxiety Disorders 73:102233* is incorrect. That identifier belongs to McKay, Yang, Elhai and Asmundson's 2020 study of COVID-related disgust and anxiety, DOI [10.1016/j.janxdis.2020.102233](https://pmc.ncbi.nlm.nih.gov/articles/PMC7194061/). It does not support the attributed eye-tracking claim. The historical Johnson/Bennett titles remain unverified.

## Current evidence

- **ICC(1,1):** the group tables give estimates of 0.22, 0.45 and 0.61, with wide 95% confidence intervals. They do not validate anxiety diagnoses or stable traits.
- **Sample units:** cardiac records contain repeated interval samples without timing for verified unique normal heartbeats. Group response-duration values are within-session standard deviations in seconds.
- **Source gaps:** equal-value patterns, missing clock metadata and undocumented participant mapping limit independent reconstruction.

[Data contract](../DATA_PROVENANCE.md) · [Figures](FIGURES.md)
