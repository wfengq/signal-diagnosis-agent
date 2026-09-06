# Contextual validation construction status

Status: `validation_sealed_model_not_run`

- Active seal: `validation_seal_v4/`
- Bound cases: 20 (17 scoreable; 3 unscored pressure cases)
- Unique derived WAV files: 24
- Deterministic qualification: 20/20 passed
- Planned arm executions: 60
- Executed arm attempts: 0
- One-shot validation complete: `false`
- Validation passed: `false`
- Frozen prompt: `v0.3-s1-planner-9.11` / `ecd10554beef79afcf505bf788509f660eb933eaef72ed89693514009fe1134b`
- Frozen causal policy: `v9_11_mode_aware_no_fault_recovery`
- Frozen product_tree: `626824f6bd2c4c04da566d77914648f2e2d629241d910cb56bcd086bd279c799`
- Frozen evaluation harness / product_code: `f4bdf9b2adefbe7e610b2687e8313aa81406604d73cbbcd9db3c9019947a8618`
- Profile S1: `1e02d0dabe74ae1327fa3418d4ce546c53e8a8d06b175b5c508edb8b512f5ed1` (unchanged)
- Profile contextual live file: `s1_contextual_comparison_v9_10.yaml` / `02df1a7df05354035451a6f079e919f72ccbf558e23ae2be34f54664a6445e01`
- Scoring: `signal_diag.contextual_scoring@1.0.0-dev.1`
- Development meets anchor: conf_2 at `caabd87` (Spec ⚪)
- Real-model validation: not run; Phase 8 requires separate authorization
- Final test: not entered

Immutable case assets (manifest, WAV checksums, source decisions, slot plan,
execution inputs) are byte-identical to `validation_seal_v3/`. Runtime identity
and seal meta bind v9.11. A real-model validation run still requires separate
Phase 8 authorization. Do not claim validation_passed or unblock.
