# Regression workbench browser proof (Task 6 / T-CX339)

Date: 2026-10-04
Tip driven: `4972100` (Phase B revise4 Codex-accept docs tip; code tip `d66f346`)
Origin: `http://127.0.0.1:8765/regression`
Driver: headed Playwright on `DISPLAY=:1` (`drive_regression_browser.py`).
`computerUse` subagent was unavailable (spend limit); Playwright drove the real Chromium UI.

## Mapping correction

| ID | Spec meaning | This proof |
|---|---|---|
| Design **AC14** | 方案准入：不适用方案或未批准参数不能由模型输出绕过 | **Not claimed here** (Task 7+ / T-CX340+) |
| **T-CX339** | Web dual-file path supports manual retest; late responses and missing keys do not forge success | **Covered** by this browser drive |
| Prior acceptance rows that labeled browser GUI as “AC14” | Mis-mapped | Corrected to T-CX339 |

HTTP proof (`docs/REGRESSION_WORKBENCH_HTTP_PROOF_2026-10-04.md`) remains complementary API evidence and does not replace this browser path.

## Steps executed (measured)

Case `case_6d2fd56bed2c4d1994c09f43f0dc6817`:

1. Page load with measurement-only notice; no pass badge
2. Create case with goal “Browser acceptance: 1kHz harmonic compare”
3. Dual-file compare (`baseline.wav` / `candidate.wav`) → 1 comparison; clipping `descriptive_only`; THD `not_comparable` / `harmonic_applicability_not_configured` (expected with `profile=None`)
4. Manual **Repeat** → 2 comparisons; second `link_kind=repeat`
5. Manual **Repair** with `candidate_repair.wav` → 3 comparisons; third `link_kind=repair`
6. Download JSON + HTML reports (sources preserved; measurement-only notice present)
7. Missing-file compare shows `missing file for baseline-file`; prior 3 comparisons preserved

`browser_drive_report.json`: **overall_pass=true** (7/7 steps).

## Evidence pack

Directory:

```text
.cursor/skills/verify-signal-diagnosis-agent/evidence/regression-browser-tcx339/
```

Artifacts also mirrored under `/opt/cursor/artifacts/regression-browser-tcx339/` and recording:

```text
/opt/cursor/artifacts/regression-browser-tcx339-task6.mp4
```

Key files: `01_page_load.png` … `07_missing_file_error.png`, `case.report.json`, `case.report.html`, `final_case_snapshot.json`, `browser_drive_report.json`, `drive.log`.

## Out of scope

Tasks 7–8, merge, seal, RealLLM, product tolerances, design AC14 scheme admission.
