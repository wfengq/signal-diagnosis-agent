# Validation seal status

- Status: `validation_resealed_model_not_run`
- Protocol commit: `e6ea5fbec3cecdb47a317054d201a44ec74233af`
- Active seal directory: `validation_seal_v2/`
- Active seal index SHA-256: `32db0f484ad29d60c41814f44ecca7a74602e3d0d15090fcecefabfed681c4ac`
- Evaluation harness SHA-256: `9d45558384ab44d5077d9826dab8f3b35f5333d949d773755d67f54124c4f017`
- Historical seal directory: `validation_seal/`
- Historical seal index SHA-256: `cfaf101b3117d028ce9f5e80462ab5aad8b150702774fbf8f811cec6a7458b0f`
- Historical seal status: `superseded_unexecuted_historical_seal`
- Planned cases: 20
- Planned arm executions: 60
- Executed cases/arms: 0/0
- Real model: not run
- Final test: not entered
- Commit/push: not performed

The original seal was not modified and had zero executed arms/model calls when
the fixed-pipeline label leak was found. The append-only supersession record is
`VALIDATION_SEAL_SUPERSESSION.json`. Both the historical seal and active
replacement seal verify with the contextual bundle verifier. Manifest, WAV,
source, slot, product, prompt, profile, and scoring identities are unchanged;
the replacement additionally binds the repaired evaluation-harness identity.
