# Validation seal status

- Status: `active_model_not_run`
- Active seal: `validation_seal_v4/`
- Active seal index SHA-256: `67683f67ca6b0635392d58714adb0d43a136d2c5b933dee42b3b82f99f06b053`
- Historical v9.9 seal directory: `validation_seal_v3/` (preserved unchanged)
- Historical v9.9 seal index SHA-256: `8e69f19343466c4222581b1326c9560217847bdb2d37bbd8e6c51edfd196d3a9`
- Historical v9.9 original campaign: 47/60 terminal slots, including 27 model slots, stopped by infrastructure failure
- Diagnostic continuation: `agent_v9_9_validation_diagnostic_continuation_1/`, 13 slots, diagnostic-only
- One-shot validation complete: `false`
- Validation passed: `false`
- Development meets-target anchor: `agent_v9_11_dev_confirmation_2` at commit `caabd87306be3912af361925e3c112c211132a9f` (code `ef4f66e`; Spec review ⚪ scoped ✅)
- conf_2 authorization prose drift: STATUS fields are correct (`v9_11_mode_aware_no_fault_recovery`); authorization *prose* wrongly says `v9_10_contextual_clipping_recovery` — not rewritten in historical conf_2 artifacts
- Real model: not authorized (Phase 8 separately authorized)
- Final test: not entered / not authorized
- Commit/push: local commit authorized for Phase 7 docs+code reseal; push not authorized

Phase 7 creates an unexecuted v9.11 validation seal only. The append-only
lifecycle record is `VALIDATION_SEAL_SUPERSESSION.json`. Historical seal
directories under `validation_seal/`, `validation_seal_v2/`, `validation_seal_v3/`,
and historical drafts remain byte-preserved.
