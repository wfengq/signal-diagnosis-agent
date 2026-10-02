# Independent offline label review: `study_s1_planner_ablation_dev_2`

| Field | Value |
|-------|-------|
| reviewer | `independent_offline_reviewer` (subagent) |
| date | 2026-10-01 |
| study_id | `study_s1_planner_ablation_dev_2` |
| proposal | unsealed `design_inputs.md` (design §5) |
| independence | Reviewer did **not** implement the harness. **Arm outputs were not used as truth** — neither `product_agent` nor `fixed_pipeline` diagnoses. Labels judged from construction, WAV identity, documented transforms, and versioned gates only. |
| prior-output exposure | Remains disclosed in `design_inputs.md` (Wave 5 / `dev_1` motivation). Exposure does not authorize treating those outputs as oracle. |
| overall | **approve** (`approved=true`) |
| blockers | **none** |
| seal | **Not created.** This review does not authorize `protocol_seal/`, RealLLM, threshold relaxation, or product changes. |

Demonstration thresholds used for gate checks: **1% clipping ratio**, **5% THD**, **5% even-harmonic growth** (`profile_s1_distortion` / contextual comparison). Not industry standards or SLAs.

## Scenario table

| Scenario ID | Role | Single oracle | Paired oracle | U | C | G | Upgrade target | Verdict | Rationale |
|-------------|------|---------------|---------------|:-:|:-:|:-:|----------------|---------|-----------|
| `825a759a0ea47bb7` | clean | `no_supported_fault` | `no_supported_fault` | | | | — | **approve** | Identity transform; test==ref; DSP no clip, THD≈0.11%≪5%. Clean gates both modes. |
| `857fac53e4d2e57e` | clipping | `supported_fault` `{clipping}` | `supported_fault` `{clipping}` | | | | — | **approve** | Hard-clip; mech=true, ratio≈23.8%≫1%; paired even-g≈0.15%≪5% → clipping only. §16 Option C / §8. |
| `abd9010438d4ad93` | clipping | `supported_fault` `{clipping}` | `supported_fault` `{clipping}` | | | | — | **approve** | Hard-clip bass; mech=true, ratio≈13.4%≫1%; even-g≈0 → clipping only both modes. |
| `a4a0853be9983f8c` | harmonic | `inconclusive` | `supported_fault` `{harmonic_distortion}` | ✓ | ✓ | ✓ | harmonic attribution | **approve** | H2 ampnorm. Single THD≈7.48%>5% but §8 blocks single-file causal harmonic → `inconclusive`. Paired even-g≈7.23%>5% → exact harmonic set. |
| `2be730b9113701de` | harmonic | `inconclusive` | `supported_fault` `{harmonic_distortion}` | ✓ | ✓ | ✓ | harmonic attribution | **approve** | Same transform; single THD≈10.34% → `inconclusive`; paired even-g≈9.91%>5%. |
| `6fb80bbda391c26c` | combined | `supported_fault` `{clipping}` | `supported_fault` `{clipping, harmonic_distortion}` | ✓ | ✓ | | additional harmonic coverage beyond clipping | **approve** | Harmonic-then-clip. Single ratio≈2.56%>1% → clipping only. Paired adds even-g≈8.81%>5%. |
| `aa9b4a91b0253c33` | combined | `supported_fault` `{clipping}` | `supported_fault` `{clipping, harmonic_distortion}` | ✓ | ✓ | | additional harmonic coverage beyond clipping | **approve** | Same order; single ratio≈6.53%; paired even-g≈6.41%>5%. |
| `393940e92c58cf0b` | natural_even_control | `inconclusive` | `no_supported_fault` | ✓ | ✓ | ✓ | supported no-fault for natural controls | **approve** | Adjacent windows; single THD≈12.63%>5% → cannot single `no_supported_fault` → `inconclusive` (revises sealed `dev_1` single). Paired growth≈0.09%≪5% → `no_supported_fault`. |
| `04f4068ec91d2621` | natural_even_control | `inconclusive` | `no_supported_fault` | ✓ | ✓ | ✓ | supported no-fault for natural controls | **approve** | Twin control; single THD≈8.47%>5% → `inconclusive`; paired growth≈0.01% → `no_supported_fault`. |
| `163185980dc8f7a4` | invalid_comparison | `no_supported_fault` | `inconclusive` | ✓ | | | **none** (negative control) | **approve** | Test SHA identical to `825a…` → single oracle must match clean (`no_supported_fault`); paired `fundamental_incompatible` → `inconclusive`. Outside C. |

Empty fault sets accompany `no_supported_fault` and `inconclusive`. Positive sets are exact sets.

## Alias, mapping, U/C/G

| Check | Proposed | Verdict | Rationale |
|-------|----------|---------|-----------|
| Single-mode alias | `163185980dc8f7a4` → `825a759a0ea47bb7` | **approve** | Shared test-byte hash `ea04bd30…`; equal request identity ⇒ equal oracle. Paired keys remain distinct (different refs). |
| Unique schedule | 9 single + 10 paired = 19 keys/arm/round; 114 slots | **approve** | Consistent with alias collapsing one single duplicate. |
| Source/master | seven parent masters per `design_inputs.md` table | **approve** | Matches sealed `dev_1` `case_sources` / contextual build; no fresh-source generalization. |
| \|U\|=7 | harmonics + combined + naturals + invalid | **approve** | Design §5.3 construction labels; registered before execution; arms never receive them. |
| \|C\|=6 | U minus `163185…` | **approve** | Invalid reference obtainable but not valid/sufficient. |
| \|G\|=4 | two harmonic + two natural singles | **approve** | §17 guidance-eligible inconclusive singles; combined singles finish clipping so excluded. |
| Upgrade targets | as in `design_inputs.md` | **approve** | Match §5.3 purposes; invalid target none. |

## Evidence basis (not arm truth)

- Construction / roles / transforms: `study_v0_3_contextual_dev_1/case_build_record.json`, `contextual_manifest.json`
- Sealed source paths and historical (defective) single labels: `study_s1_planner_ablation_dev_1/protocol_seal/manifest.json`
- Mode-aware gates: `CONTRACTS_V0_3_CONTEXTUAL.md` §§8, 15, 16 (Option C), 17; design `2026-10-01-s1-planner-ablation-protocol-revision-design.md` §5
- Independent DSP re-measure on on-disk WAVs (clipping mechanism/ratio/flat-top; absolute THD; paired `even_harmonic_growth_percent` / validity) — measurements only, not diagnosis outcomes

## Overall summary

**Approve all ten proposed oracle rows**, alias scheme, source/master mapping, U/C/G membership (7/6/4), and upgrade targets. **approved=true; blockers=none.**

Corrections relative to sealed `dev_1` singles for natural controls and the invalid/clean collision are **required by construction and gates**, not by arm score chasing. Do not relax thresholds. Do not seal from this file alone.

## Structured label approval (machine-readable)

```json
{
  "schema": "planner_ablation_label_approval_v1",
  "reviewer": "independent_offline_reviewer",
  "study_id": "study_s1_planner_ablation_dev_2",
  "approved": true,
  "review_status": "approved",
  "review_provenance": ["independent_offline_reviewer"],
  "upgrade_population": [
    "2be730b9113701de",
    "393940e92c58cf0b",
    "6fb80bbda391c26c",
    "a4a0853be9983f8c"
  ],
  "conditional_population": [
    "04f4068ec91d2621",
    "163185980dc8f7a4",
    "2be730b9113701de",
    "393940e92c58cf0b",
    "6fb80bbda391c26c",
    "a4a0853be9983f8c",
    "aa9b4a91b0253c33"
  ],
  "guidance_population": [
    "04f4068ec91d2621",
    "2be730b9113701de",
    "393940e92c58cf0b",
    "a4a0853be9983f8c"
  ]
}
```
