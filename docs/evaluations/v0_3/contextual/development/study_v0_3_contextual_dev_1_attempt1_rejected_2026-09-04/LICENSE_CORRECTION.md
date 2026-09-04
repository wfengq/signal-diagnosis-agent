# Attempt-1 license correction (append-only)

This file corrects false license claims in the rejected attempt-1 study.
It does not rehabilitate attempt-1 as a Task 11 freeze.

## Erroneous original claims

| Asset | Erroneous source_id | Erroneous license_id | Erroneous label notes |
|---|---|---|---|
| `1-100038-A-14.wav` | `esc10_100038_a14` | `CC-BY-4.0` | treated as ESC-10 |
| `1-101336-A-30.wav` | `esc10_101336_a30` | `CC-BY-4.0` | mislabeled as rain / ESC-10 |

## Correct classification

| Asset | Official category (`esc50.csv`) | `esc10` | Correct license |
|---|---|---|---|
| `1-100038-A-14.wav` | chirping_birds | `False` | **CC BY-NC 3.0** (`CC-BY-NC-3.0`) |
| `1-101336-A-30.wav` | door_wood_knock (not rain) | `False` | **CC BY-NC 3.0** (`CC-BY-NC-3.0`) |

ESC-10 is a CC BY 3.0 subset. These two files are **not** in ESC-10.
ESC-50 overall (non-ESC-10) is licensed under Creative Commons
Attribution-NonCommercial 3.0 Unported.

Official references:

- Metadata: https://raw.githubusercontent.com/karolpiczak/ESC-50/master/meta/esc50.csv
- License: https://raw.githubusercontent.com/karolpiczak/ESC-50/master/LICENSE
- Audio: https://raw.githubusercontent.com/karolpiczak/ESC-50/master/audio/1-100038-A-14.wav
- Audio: https://raw.githubusercontent.com/karolpiczak/ESC-50/master/audio/1-101336-A-30.wav

## Attribution

ESC-50: Dataset for Environmental Sound Classification  
Author: Karol J. Piczak  
Citation: Piczak, K. J. (2015). ESC: Dataset for Environmental Sound Classification.
In Proceedings of the 23rd ACM International Conference on Multimedia (pp. 1015–1018).

Used here only as preserved rejected-development evidence under the corrected
**CC BY-NC 3.0** terms. Do not redistribute or re-register these two assets as
ESC-10 or as CC-BY-4.0 / CC BY 3.0.

## On-disk correction

`contextual_manifest.json` and `case_build_record.json` in this directory now
store `license_id: "CC-BY-NC-3.0"` for the two cases above. Historical
erroneous claims remain documented in this file and in `REJECTION_NOTICE.md`.
