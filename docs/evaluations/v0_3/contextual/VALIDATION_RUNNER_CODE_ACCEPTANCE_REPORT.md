# Contextual Validation Runner Code Acceptance

## Conclusion

`validation_runner_harness_complete`

This conclusion covers only the deterministic campaign runner, guarded product
adapter, truth-free fixed baseline, scoring handoff, and active zero-execution
seal. It does not mean validation passed, performance improved, or final-test
access was authorized.

## Frozen identities

- Product prompt: `v0.3-s1-planner-9.9`
- Prompt SHA-256: `27a9315ad85a035c9cc9cbfe5f15ea26c49383d7fb23207989315ae0adb78dc9`
- Causal policy: `v9_9_paired_reference_recovery`
- Product implementation SHA-256: `5bc2a3375d5fb5be5c7c77cb0ddba140c240635d549662c9d3221e64acb81ae2`
- Evaluation harness SHA-256: `9c3844a2b73e8ba060c9bdbeff75434a91feb111f12a8d23c57f6ff2dee7bc94`
- Live product-tree SHA-256: `2eff9095d256c726b52f0a24397a5fb2afa8944381b84d776eb5cdb531f1473f`
- Scoring identity: `signal_diag.contextual_scoring@1.0.0-dev.1`
- Active seal: `validation_seal_v3/`
- Active seal index SHA-256: `8e69f19343466c4222581b1326c9560217847bdb2d37bbd8e6c51edfd196d3a9`

## Implemented gates

- Sealed truth-free execution inputs for exactly 20 cases and 60 arm slots.
- Sealed runtime identity plus recomputation of live product, prompt, profile,
  scoring, and provider-facing runner bytes.
- Canonical active-seal path, supersession status, and seal-index SHA pinning.
- Provider, model, base URL, RealLLMPlanner, prompt, and causal-policy checks
  before execution.
- Frozen arm-major order: contextual Agent, fixed pipeline, no-context ablation.
- One-attempt append-only slot artifacts and live atomic execution ledger.
- Copied seal identity at startup and required `run_summary.json` at completion.
- Behavioral failure continues; sanitized infrastructure failure stops.
- Evaluation core has no dependency on `app`; the RealLLMPlanner adapter and
  explicitly authorized live-run CLI are under `app`.
- Fixed pipeline uses only local WAV, declared stimulus context, deterministic
  DSP/Tools, and frozen profiles.
- Manifest truth is loaded only after all 60 execution slots are terminal.
- Aggregate, causal macro-F1, role hard gates, and ablation gates are applied
  without shrinking frozen denominators.

## Verification evidence

- Runner/sealing/freeze-identity focused: `34 passed`.
- Architecture and preservation: `70 passed`.
- Full deterministic pytest: `1432 passed`, one pre-existing Pydantic serializer
  warning, zero skip/xfail reported.
- Ruff: passed.
- mypy `src`: passed for 100 source files.
- Wheel build/install smoke: passed; new runner modules are packaged and no
  private validation audio is included.
- Architecture boundaries: passed after moving the product adapter to `app`.
- `git diff --check 605c8a8`: passed (line-ending warnings only).
- v1, v2, all four preserved v3 construction/review drafts, and active v3
  seals verify.
- Active preflight: `preflight_passed_model_not_run`, 20 cases / 60 slots.
- Credential-pattern scan: zero findings in new runner/seal artifacts.
- New seal directories contain no WAV/MP3/FLAC payloads.
- Source execution ledger remains zero for all three arms.

## Preservation and execution status

The original seal, v2 seal, and four unexecuted v3 construction/review drafts remain
byte-preserved with their identities recorded in
`VALIDATION_SEAL_SUPERSESSION.json`. No historical official bundle, Demo,
prompt, rule, threshold, label, scoring identity, or V0.2 tag was rewritten.

Real-model calls: **0**. Validation results: **not evaluated**. Final test: **not
entered**. Push: **not performed**.
