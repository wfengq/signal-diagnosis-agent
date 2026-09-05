# Validation seal status

- Status: `validation_runner_resealed_model_not_run`
- Protocol commit: `e6ea5fbec3cecdb47a317054d201a44ec74233af`
- Active seal directory: `validation_seal_v3/`
- Active seal index SHA-256: `8e69f19343466c4222581b1326c9560217847bdb2d37bbd8e6c51edfd196d3a9`
- Evaluation harness SHA-256: `9c3844a2b73e8ba060c9bdbeff75434a91feb111f12a8d23c57f6ff2dee7bc94`
- Live product-tree SHA-256: `2eff9095d256c726b52f0a24397a5fb2afa8944381b84d776eb5cdb531f1473f`
- Historical pre-review draft directory: `validation_seal_v3_historical_draft_pre_bugbot_review/`
- Historical pre-review draft index SHA-256: `61628d7584c6c797ee551c76bce39fb63e49a30f90d4cd39074089e2b29934c1`
- Historical pre-review draft status: `superseded_unexecuted_historical_draft`
- Historical pre-lint draft directory: `validation_seal_v3_historical_draft_pre_lint_fix/`
- Historical pre-lint draft index SHA-256: `8efeb8fe7b32d68043a9b1d99da1128ab352db2cb4d519e86d6ed6767ae91dbc`
- Historical pre-lint draft status: `superseded_unexecuted_historical_draft`
- Historical architecture-draft directory: `validation_seal_v3_historical_draft_pre_architecture_fix/`
- Historical architecture-draft index SHA-256: `a51846294ca5f58e3ccb725b1ddfcf31710ae3cfc98ccc336f24a416518ef5ae`
- Historical architecture-draft status: `superseded_unexecuted_historical_draft`
- Historical runner-draft directory: `validation_seal_v3_historical_draft/`
- Historical runner-draft index SHA-256: `05bcdf1a8c387b1ef123ee01956718d54a850fbefcb55ded739cff206d542b16`
- Historical runner-draft status: `superseded_unexecuted_historical_draft`
- Historical truth-free seal directory: `validation_seal_v2/`
- Historical truth-free seal index SHA-256: `32db0f484ad29d60c41814f44ecca7a74602e3d0d15090fcecefabfed681c4ac`
- Historical seal directory: `validation_seal/`
- Historical seal index SHA-256: `cfaf101b3117d028ce9f5e80462ab5aad8b150702774fbf8f811cec6a7458b0f`
- Historical seal status: `superseded_unexecuted_historical_seal`
- Planned cases: 20
- Planned arm executions: 60
- Executed cases/arms: 0/0
- Real model: not run
- Final test: not entered
- Commit/push: not performed

All earlier seals remain byte-preserved and had zero executed arms/model calls
when superseded. The runner draft was preserved after its checksum-key defect
was found before activation. The append-only supersession record is
`VALIDATION_SEAL_SUPERSESSION.json`. Historical seals and the active v3 seal
verify with the contextual bundle verifier. Manifest, WAV, source, slot,
product, prompt, profile, and scoring identities are unchanged; active v3 also
binds the final runner identity and truth-free execution inputs.
