# Attempt 1 rejected (Bugbot / human review 2026-09-04)

Preserved as failure evidence. Do not treat as frozen Task 11 success.

P1: clipping_mechanism not gated; quantile hard_clip lacked mechanism=true
P1: non-ESC-10 files mislabeled as ESC-10 / CC BY; see `LICENSE_CORRECTION.md`
P1: natural_even_control used low-THD adjacent windows
P2: code_sha256 was fixed-string digest
P2: weak catalog/lineage provenance

## License correction (authoritative for the two ESC-50 assets)

Attempt-1 wrongly labeled `1-100038-A-14.wav` and `1-101336-A-30.wav` as
ESC-10 under `CC-BY-4.0`. Official `esc50.csv` marks both `esc10=False`.
ESC-50 non-ESC-10 material is **CC BY-NC 3.0**, not CC BY / CC-BY-4.0.
Corrected `license_id` values in this rejected study are `CC-BY-NC-3.0`.
Full attribution and source URLs: `LICENSE_CORRECTION.md`.
