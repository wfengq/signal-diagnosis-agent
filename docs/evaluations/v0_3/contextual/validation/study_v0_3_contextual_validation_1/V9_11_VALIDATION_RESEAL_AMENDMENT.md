# Amendment: v9.9/v3 → v9.11/v4 validation reseal (Phase 7)

Date: 2026-09-06 (Asia/Shanghai)  
Scope: Phase 7 only — create unexecuted `validation_seal_v4` and rebind campaign preflight.  
**validation_passed = false**. Phase 8 (real-model one-shot) needs separate authorization.

## Old (v9.9 / validation_seal_v3) vs new (v9.11 / validation_seal_v4)

| Field | Old (v9.9 / v3) | New (v9.11 / v4) |
| --- | --- | --- |
| Prompt version | `v0.3-s1-planner-9.9` | `v0.3-s1-planner-9.11` |
| Prompt SHA-256 | `27a9315ad85a035c9cc9cbfe5f15ea26c49383d7fb23207989315ae0adb78dc9` | `ecd10554beef79afcf505bf788509f660eb933eaef72ed89693514009fe1134b` |
| Causal policy | `v9_9_paired_reference_recovery` | `v9_11_mode_aware_no_fault_recovery` |
| product_tree SHA-256 | `2eff9095d256c726b52f0a24397a5fb2afa8944381b84d776eb5cdb531f1473f` | `626824f6bd2c4c04da566d77914648f2e2d629241d910cb56bcd086bd279c799` |
| profile_s1 SHA-256 | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` | `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` (unchanged) |
| profile_contextual file | `s1_contextual_comparison_v1.yaml` | `s1_contextual_comparison_v9_10.yaml` |
| profile_contextual SHA-256 | `c79865caf913b2a1a5f6f50fccd8c37d6f2828e72feb1f80d9c9c7b4b7d9eb58` | `02df1a7df05354035451a6f079e919f72ccbf558e23ae2be34f54664a6445e01` |
| evaluation harness SHA-256 | `9c3844a2b73e8ba060c9bdbeff75434a91feb111f12a8d23c57f6ff2dee7bc94` | `f4bdf9b2adefbe7e610b2687e8313aa81406604d73cbbcd9db3c9019947a8618` |
| product_code / frozen implementation | `5bc2a3375d5fb5be5c7c77cb0ddba140c240635d549662c9d3221e64acb81ae2` | `f4bdf9b2adefbe7e610b2687e8313aa81406604d73cbbcd9db3c9019947a8618` (campaign frozen mapping = live harness) |
| Active seal directory | was pending after v3 historical stop; v3 = `historical_infrastructure_stopped` | `validation_seal_v4` / `active_model_not_run` |
| Active seal index SHA-256 | n/a (active was null / pending v9.10 confirmation) | `67683f67ca6b0635392d58714adb0d43a136d2c5b933dee42b3b82f99f06b053` |
| Development meets pointer | v9.9 era evidence | conf_2 at `caabd87306be3912af361925e3c112c211132a9f` (Spec ⚪) |

## Immutable assets (byte-identical v3 → v4)

- `manifest.json`
- `wav_checksums.json`
- `source_decisions.json`
- `slot_plan.json`
- `execution_inputs.json`

## Authorization boundary

| Gate | Value |
| --- | --- |
| real_model_run_authorized | false |
| final_test_authorized | false |
| push_authorized | false |
| validation_passed | false |
| one_shot_validation_complete | false |
| Phase 8 | **not authorized** — separate auth required |

## Drift note (conf_2)

`agent_v9_11_dev_confirmation_2` STATUS fields correctly record policy
`v9_11_mode_aware_no_fault_recovery`. Authorization *prose* in
`preflight.json` / `run_summary.json` wrongly says
`v9_10_contextual_clipping_recovery`. Historical conf_2 artifacts are **not**
rewritten; this amendment and the new seal/docs carry the corrected identity.

## Forbidden claims

Do not claim validation_passed, unblock, RealLLM run, V0.2/final access, or push.
