# V0.2 Real-World WAV Validation Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build and execute an additive, reproducible 52-WAV external-validity
study for V0.2 Scenario S1 without changing any accepted V0.2 product,
prompt, rule, scoring, Demo, bundle, or release identity.

**Architecture:** Add an isolated `signal_diag.evaluation.external` package
which consumes public PCM WAV assets, creates provenance-complete derivatives,
performs evaluator-only reference checks, seals group-isolated manifests, runs
the frozen Agent and fixed pipeline, scores only eligible labels, and writes
new append-only study bundles. Existing `signal_diag.evaluation` and product
modules are dependencies, not edit targets.

**Tech Stack:** Python 3.11/3.12, NumPy, Pydantic 2, PyYAML, standard-library
`wave`/`hashlib`/`urllib`/`csv`/`json`, pytest, Ruff, mypy.

**Spec:** `docs/superpowers/specs/2026-09-01-v0-2-real-world-validation-design.md`

## Global Constraints

- Work only on branch `codex/v0.2-real-world-validation` based on `605c8a8`.
- Tag `v0.2.0` remains unchanged; its peeled commit is `ff16e2a`.
- Never modify or overwrite `docs/evaluations/phase4_3_1/development/`,
  `docs/evaluations/phase4_3_1/official/`, or
  `docs/demo/phase5/v0_2_acceptance/`.
- Never change prompt `v0.2-s1-planner-8.1` or SHA-256
  `f2f0a81cc8f36f0301ee67c43e692886e86f9aa9136adeea4d592707133423ca`.
- Never change `signal_diag.scoring` `2.0.0` or any historical scoring output.
- Never change `profile_s1_distortion` `1.0.0-demo`, including 1% clipping and
  5% THD demonstration settings.
- Do not add a dependency. Public sources selected for V1 of this study must be
  integer PCM at a V0.2-supported sample rate; unsupported/compressed material
  is excluded before sealing rather than adding a codec or resampler.
- Raw downloads and ambiguous-license audio live under
  `private/external_wav/`, which is already ignored by Git.
- No ordinary import, test, or validation command may access the network.
- Downloading requires a separate user authorization and an explicit
  `--allow-network` flag.
- Final data access and the 28-slot real-model campaign require separate user
  authorizations.
- Final Agent slots use `RealLLMPlanner` only, one attempt each, concurrency
  one, zero infrastructure retries, and no `ScriptedPlanner` fallback.
- Files are split by source recording, instrument, parent master, capture
  configuration, and environment—not by random WAV file.
- Only `strong_ground_truth` and `reference_supported` enter correctness
  metrics.
- Every failed, unscored, or below-target final attempt remains in the bundle.
- Do not commit unless the user separately authorizes commits. Commit commands
  below are prepared checkpoints, not current authority.

---

## File Structure

Create the following focused implementation units:

```text
src/signal_diag/evaluation/external/
  __init__.py       public external-study interfaces only
  __main__.py       explicit, gated study CLI
  models.py         immutable provenance, case, review, score, and report models
  manifest.py       canonical JSON load/dump and identity fingerprints
  source.py         source catalog validation and opt-in bounded acquisition
  pcm.py            bounded multichannel PCM channel/crop derivation and encoding
  transforms.py     canonical base, clipping, harmonic, and combined transforms
  reference.py      evaluator-only deterministic measurements
  validation.py     counts, labels, provenance, leakage, and eligibility checks
  review.py         delayed blinded re-review packages and agreement statistics
  sealing.py        final write-once seal and protected-asset audit
  scoring.py        signal_diag.external_scoring 1.0.0
  runner.py         identical-WAV Agent/fixed execution without fallback
  reporting.py      append-only external bundle and stratified reports

tests/evaluation/external/
  conftest.py
  test_models.py
  test_manifest.py
  test_source.py
  test_pcm.py
  test_transforms.py
  test_reference.py
  test_validation.py
  test_review.py
  test_sealing.py
  test_scoring.py
  test_runner.py
  test_reporting.py
  test_cli.py
  test_preservation.py

docs/
  EXTERNAL_VALIDATION_CONTRACTS_V0_2.md
  EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md
  evaluations/v0_2_external_wav/
    README.md
    protocol/
      source_catalog.json
      protected_assets.sha256
      label_manual.md
      source_decision_record.md
```

Later authorized data phases add write-once directories below
`docs/evaluations/v0_2_external_wav/development/`,
`validation/`, and `final_external_test/`. They never reuse the word
`official`.

---

### Task 1: Freeze Additive Contracts, Test IDs, and Preservation Baseline

**Files:**
- Create: `docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md`
- Create: `docs/EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md`
- Create: `docs/evaluations/v0_2_external_wav/README.md`
- Create: `docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256`
- Create: `tests/evaluation/external/test_preservation.py`

**Interfaces:**
- Consumes: approved design and Git baseline `605c8a8`.
- Produces: contracts `EV-C001`–`EV-C024`, tests `EV-T001`–`EV-T048`,
  and `verify_protected_assets(repo_root: Path, checksum_file: Path) -> None`.

- [ ] **Step 1: Write the additive contract document**

Define these exact contract families:

```text
EV-C001-C004  immutable V0.2 assets, identities, paths, and tag
EV-C005-C008  source terms, provenance, checksums, and redistribution
EV-C009-C012  PCM derivation, pairing, transforms, and reference analysis
EV-C013-C016  confidence, scoreability, delayed review, and disagreement
EV-C017-C020  grouped splits, final sealing, attempt consumption, no fallback
EV-C021-C024  external scoring, bundle immutability, status, and public claims
```

State that these contracts are additive and cannot amend frozen
`CONTRACTS_V0_2.md`.

- [ ] **Step 2: Write the external test plan**

Allocate exact IDs:

```text
EV-T001-T004 preservation and architecture
EV-T005-T010 immutable model and manifest validation
EV-T011-T014 bounded source acquisition
EV-T015-T020 PCM derivation and WAV loader compatibility
EV-T021-T026 transforms and pairing
EV-T027-T030 reference analysis
EV-T031-T035 grouping, confidence, and final sealing
EV-T036-T039 delayed blind review
EV-T040-T043 scoring and stratification
EV-T044-T046 Agent/fixed execution and no fallback
EV-T047-T048 append-only reporting and cumulative gate
```

- [ ] **Step 3: Generate the protected checksum list**

Hash every tracked file under the three protected directories plus
`src/signal_diag/agent/prompts.py`,
`src/signal_diag/evaluation/scoring.py`,
`src/signal_diag/rules/profiles/s1_distortion_v1.yaml`, and the annotated tag
object/peeled commit. Sort paths ordinally and use forward slashes.

Run:

```powershell
$externalProtectedRoots = @(
  'docs/evaluations/phase4_3_1/development',
  'docs/evaluations/phase4_3_1/official',
  'docs/demo/phase5/v0_2_acceptance'
)
$externalProtectedFiles = @(
  'src/signal_diag/agent/prompts.py',
  'src/signal_diag/evaluation/scoring.py',
  'src/signal_diag/rules/profiles/s1_distortion_v1.yaml'
)
$externalProtectedTargets = @(
  $externalProtectedRoots | ForEach-Object {
    Get-ChildItem -LiteralPath $_ -File -Recurse | Select-Object -ExpandProperty FullName
  }
) + $externalProtectedFiles
$externalProtectedTargets | Sort-Object | Get-FileHash -Algorithm SHA256
git rev-parse v0.2.0
git rev-parse 'v0.2.0^{}'
```

Expected: the new checksum file contains no external-study artifact and does
not alter a protected source.

- [ ] **Step 4: Write the failing preservation test**

```python
def test_ev_t001_protected_v02_assets_match_frozen_hashes(repo_root: Path) -> None:
    verify_protected_assets(
        repo_root,
        repo_root
        / "docs/evaluations/v0_2_external_wav/protocol/protected_assets.sha256",
    )
```

- [ ] **Step 5: Run the test and confirm the missing verifier failure**

Run: `pytest tests/evaluation/external/test_preservation.py -v`

Expected: FAIL because `signal_diag.evaluation.external.sealing` does not exist.

- [ ] **Step 6: Implement the minimal verifier**

Parse each file record as 64 lowercase hexadecimal characters, two ASCII
spaces, then a forward-slash repository-relative path. Reject duplicates,
absolute paths, `..`, missing files, mismatches, and paths outside the
repository. Verify the tag object and peeled commit from separately named
records.

- [ ] **Step 7: Run focused checks**

Run:

```powershell
pytest tests/evaluation/external/test_preservation.py -v
git diff --check 605c8a8
```

Expected: PASS and no protected drift.

- [ ] **Step 8: Review checkpoint**

If commit authority is later granted:

```powershell
git add docs/EXTERNAL_VALIDATION_CONTRACTS_V0_2.md docs/EXTERNAL_VALIDATION_TEST_PLAN_V0_2.md docs/evaluations/v0_2_external_wav tests/evaluation/external/test_preservation.py src/signal_diag/evaluation/external/sealing.py
git commit -m "docs: freeze external WAV validation contracts"
```

Without commit authority, stop with the task diff uncommitted.

---

### Task 2: Add Immutable External Study Models and Canonical Manifests

**Files:**
- Create: `src/signal_diag/evaluation/external/__init__.py`
- Create: `src/signal_diag/evaluation/external/models.py`
- Create: `src/signal_diag/evaluation/external/manifest.py`
- Create: `tests/evaluation/external/conftest.py`
- Create: `tests/evaluation/external/test_models.py`
- Create: `tests/evaluation/external/test_manifest.py`

**Interfaces:**
- Consumes: `EvidenceCondition`, `SufficientEvidenceSet`,
  `DiagnosisOutcome`, `EvaluationTrace`, `AttemptRecord`, and `RateMetric`
  without modifying their modules.
- Produces:
  `load_external_manifest(path: Path) -> ExternalDatasetManifest`,
  `canonical_json_bytes(value: BaseModel) -> bytes`, and
  `manifest_sha256(manifest: ExternalDatasetManifest) -> str`.

- [ ] **Step 1: Write model tests**

Cover frozen/extra-forbid behavior, UTC timestamps, SHA format, truth-free
analysis filenames, source/group identifiers, parent family consistency, and
confidence eligibility:

```python
def test_ev_t006_weak_case_cannot_expose_correctness_truth() -> None:
    with pytest.raises(ValueError, match="weak/unknown cases forbid scoring truth"):
        make_external_case(
            confidence="weak_observation",
            acceptable_outcomes=("supported_fault",),
            causal_faults=("clipping",),
        )


def test_ev_t007_strong_case_requires_transform_provenance() -> None:
    with pytest.raises(ValueError, match="strong ground truth requires transform"):
        make_external_case(confidence="strong_ground_truth", transform=None)
```

- [ ] **Step 2: Confirm the tests fail**

Run: `pytest tests/evaluation/external/test_models.py tests/evaluation/external/test_manifest.py -v`

Expected: FAIL on missing external models.

- [ ] **Step 3: Implement exact model vocabulary**

Define:

```python
ExternalSplit = Literal["development", "validation", "final_external_test"]
SourceGroup = Literal["A", "B", "C"]
LabelConfidence = Literal[
    "strong_ground_truth",
    "reference_supported",
    "weak_observation",
    "unknown",
]
ExternalClass = Literal[
    "clean",
    "clipping",
    "harmonic",
    "combined",
    "inconclusive",
    "ambiguous",
]
TransformKind = Literal["none", "clipping", "second_harmonic", "combined"]
```

`ExternalCase` contains opaque `case_id`, split/group/class, truth-free relative
WAV path, WAV digest/format, provenance reference, group keys, optional
`parent_master_id`, transform, confidence, review reference,
`observable_conditions`, `sufficient_evidence_sets`, knowledge policy/tags,
acceptable first Tools, eligible outcomes, and causal faults.

Validators enforce:

- strong/reference cases contain score truth;
- weak/unknown cases contain no score truth;
- only B degraded cases may be strong;
- all B cases have a parent; non-B cases do not claim transform truth;
- combined causal order is clipping then harmonic only in the canonical tuple
  `("clipping", "harmonic_distortion")`;
- every filename matches
  `extwav_(development|validation|final_external_test)_[0-9a-f]{16}.wav`.

The same module declares the serializable boundary types used later:

```python
ExternalTargetStatus = Literal[
    "not_evaluated",
    "meets_target",
    "below_target",
]

# Frozen Pydantic models with extra="forbid":
# SourceCatalog, AcquiredAsset, DerivationSpec, DerivedAsset,
# TransformConfig, ReferenceSummary, ExternalValidationReport,
# ReviewRecord, BlindPackage, ReviewAgreement, FinalSeal,
# ExternalRunScore, ExternalAggregate, and ExternalStudyReport.
```

Array-owning `PcmWindow` and `TransformResult` remain frozen dataclasses in
`pcm.py` and `transforms.py`; they are never serialized directly.

- [ ] **Step 4: Implement canonical serialization**

Use sorted-key, UTF-8, newline-terminated JSON with `allow_nan=False`. Reject
unknown schema versions and manifest identity other than:

```text
dataset_id=s1-distortion-external-wav
version=1.0.0
study_id=v0.2-external-wav-validity-1
rule_profile_id=profile_s1_distortion
rule_profile_version=1.0.0-demo
external_scoring_id=signal_diag.external_scoring
external_scoring_version=1.0.0
```

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/evaluation/external/test_models.py tests/evaluation/external/test_manifest.py -v`

Expected: PASS.

- [ ] **Step 6: Review checkpoint**

If authorized:

```powershell
git add src/signal_diag/evaluation/external tests/evaluation/external
git commit -m "feat: add external validation models"
```

---

### Task 3: Implement Explicit, Bounded Public-Source Acquisition

**Files:**
- Create: `src/signal_diag/evaluation/external/source.py`
- Create: `tests/evaluation/external/test_source.py`
- Create later after download authorization:
  `docs/evaluations/v0_2_external_wav/protocol/source_catalog.json`
  `docs/evaluations/v0_2_external_wav/protocol/source_decision_record.md`

**Interfaces:**
- Consumes: `SourceCatalog` and injected `UrlOpener`.
- Produces:
  `acquire_assets(catalog, destination, *, opener, allow_network, max_total_bytes) -> tuple[AcquiredAsset, ...]`.

- [ ] **Step 1: Write acquisition-gate tests**

```python
def test_ev_t011_network_is_opt_in(tmp_path: Path, catalog: SourceCatalog) -> None:
    with pytest.raises(PermissionError, match="--allow-network"):
        acquire_assets(
            catalog,
            tmp_path,
            opener=FailIfCalledOpener(),
            allow_network=False,
            max_total_bytes=5 * 1024**3,
        )


def test_ev_t012_partial_or_oversize_download_is_removed(
    tmp_path: Path,
) -> None:
    opener = BytesOpener(b"x" * 33, declared_size=33)
    with pytest.raises(SourceLimitError):
        acquire_assets(
            one_asset_catalog(expected_max_bytes=32),
            tmp_path,
            opener=opener,
            allow_network=True,
            max_total_bytes=32,
        )
    assert list(tmp_path.iterdir()) == []
```

- [ ] **Step 2: Confirm tests fail**

Run: `pytest tests/evaluation/external/test_source.py -v`

Expected: FAIL because source acquisition is absent.

- [ ] **Step 3: Implement catalog validation**

Define the injectable boundary in `source.py`:

```python
class UrlOpener(Protocol):
    def open(self, url: str) -> ContextManager[BinaryIO]: ...
```

Each catalog row includes official source, authoritative page URL, direct asset
URL, citation, terms URL, terms snapshot digest, upstream ID/group ID,
published checksum when available, maximum bytes, intended split eligibility,
license/terms classification, attribution, and redistribution decision.

Allow only HTTPS URLs and these approved authoritative hosts after terms review:

```text
www.es.aau.dk
github.com
raw.githubusercontent.com
magenta.withgoogle.com
storage.googleapis.com
```

Adding a host requires a design amendment and a catalog-version change.

- [ ] **Step 4: Implement bounded streaming**

Use `urllib.request` through an injected opener, stream fixed-size chunks,
enforce both per-file and 5 GiB campaign limits, write to `.partial`, fsync,
calculate SHA-256 while streaming, then atomically rename. Never overwrite an
existing digest/path. Tests use fake openers only.

- [ ] **Step 5: Populate source records only after authorization**

Inspect official indexes, snapshot terms, select the smallest necessary SMARD,
Pyramic, ESC-10, and NSynth records, and record exact upstream group keys.
Do not fetch the complete SMARD archive. If SMARD terms are not accepted,
stop and request the approved design revision.

- [ ] **Step 6: Run focused tests**

Run: `pytest tests/evaluation/external/test_source.py -v`

Expected: PASS with zero network access.

- [ ] **Step 7: Review checkpoint**

If authorized:

```powershell
git add src/signal_diag/evaluation/external/source.py tests/evaluation/external/test_source.py docs/evaluations/v0_2_external_wav/protocol
git commit -m "feat: gate external audio acquisition"
```

---

### Task 4: Derive Loader-Compatible Mono PCM Without Normalization

**Files:**
- Create: `src/signal_diag/evaluation/external/pcm.py`
- Create: `tests/evaluation/external/test_pcm.py`

**Interfaces:**
- Produces:
  `read_pcm_window(path: Path, spec: DerivationSpec) -> PcmWindow`,
  `encode_pcm24_mono(samples: np.ndarray, sample_rate_hz: int) -> bytes`,
  and
  `derive_analysis_wav(source: Path, spec: DerivationSpec, destination: Path) -> DerivedAsset`.

`PcmWindow` is defined here as a frozen dataclass with `samples: np.ndarray`,
`sample_rate_hz: int`, `sample_width_bytes: int`, and `source_channels: int`;
its constructor copies to contiguous `float32` and marks the array read-only.

- [ ] **Step 1: Write failing byte-level PCM tests**

Test 8/16/24/32-bit signed PCM conversion, a selected channel from 48 channels,
left-closed/right-open frame crops, no peak normalization, RIFF sizes, filename
sanitization, immutable destination, and compatibility with the frozen loader:

```python
def test_ev_t018_derived_pcm24_loads_without_peak_normalization(tmp_path: Path) -> None:
    source = write_pcm16_fixture(
        tmp_path / "source.wav",
        channels=np.array([[-16384, 8192], [16384, -8192]], dtype=np.int16),
    )
    derived = derive_analysis_wav(
        source,
        DerivationSpec(channel_index=0, start_frame=0, stop_frame=2),
        tmp_path / "extwav_development_0123456789abcdef.wav",
    )
    loaded = load_wav_bytes(derived.path.read_bytes(), filename=derived.path.name)
    np.testing.assert_allclose(
        loaded.record.samples[:, 0],
        np.array([-0.5, 0.5], dtype=np.float32),
        atol=2**-23,
    )
```

- [ ] **Step 2: Confirm tests fail**

Run: `pytest tests/evaluation/external/test_pcm.py -v`

Expected: FAIL on missing PCM derivation.

- [ ] **Step 3: Implement bounded window decoding**

Use standard-library `wave` for uncompressed integer PCM. Seek directly to the
crop, decode only requested frames, extract the predeclared channel, and reject
float/compressed data, invalid sample widths, unknown frame counts, empty
crops, and output beyond 30 seconds, 2,000,000 frames, or 20 MiB.

- [ ] **Step 4: Implement deterministic 24-bit encoding**

Clip only representational roundoff to `[-1, 1 - 2^-23]`, use round-to-nearest
with a frozen rule, pack little-endian 24-bit integers, and write exact RIFF
headers. Do not normalize, denoise, resample, EQ, or enhance.

- [ ] **Step 5: Run focused tests**

Run:

```powershell
pytest tests/evaluation/external/test_pcm.py tests/signal/test_wav.py -v
```

Expected: PASS; frozen WAV tests remain unchanged.

- [ ] **Step 6: Review checkpoint**

If authorized, commit as `feat: add reproducible external PCM derivation`.

---

### Task 5: Implement Paired Semi-Real Transforms and Reference Analysis

**Files:**
- Create: `src/signal_diag/evaluation/external/transforms.py`
- Create: `src/signal_diag/evaluation/external/reference.py`
- Create: `tests/evaluation/external/test_transforms.py`
- Create: `tests/evaluation/external/test_reference.py`

**Interfaces:**
- Produces:
  `hard_clip(samples, tail_proportion, *, quantile_method="lower") -> TransformResult`,
  `inject_second_harmonic(samples, alpha, post_gain) -> TransformResult`,
  `apply_combined(samples, config) -> TransformResult`, and
  `analyze_reference(samples, sample_rate_hz, *, fmin_hz, fmax_hz) -> ReferenceSummary`.

`TransformResult` is a frozen dataclass with a read-only `float32` sample array,
transform kind, canonical parameter mapping, input digest, and output digest.

- [ ] **Step 1: Write transform tests**

```python
def test_ev_t023_combined_order_is_harmonic_then_clipping() -> None:
    actual = apply_combined(BASE, FROZEN_CONFIG).samples
    harmonic = inject_second_harmonic(
        BASE,
        FROZEN_CONFIG.alpha,
        FROZEN_CONFIG.post_gain,
    ).samples
    expected = hard_clip(
        harmonic,
        FROZEN_CONFIG.tail_proportion,
        quantile_method="lower",
    ).samples
    np.testing.assert_array_equal(actual, expected)


def test_ev_t024_transform_does_not_normalize_each_master() -> None:
    low = inject_second_harmonic(BASE * 0.5, alpha=0.15, post_gain=0.8)
    high = inject_second_harmonic(BASE, alpha=0.15, post_gain=0.8)
    assert np.max(np.abs(low.samples)) < np.max(np.abs(high.samples))
```

- [ ] **Step 2: Write reference-analysis tests**

Use deterministic fixtures for clean, clipped, order-2, combined, and
unvoiced input. Assert exact analyzer identity, input digest, applicability,
clipping ratio, flat-top status, F0, THD, and order-2 ratio.

- [ ] **Step 3: Confirm tests fail**

Run:

```powershell
pytest tests/evaluation/external/test_transforms.py tests/evaluation/external/test_reference.py -v
```

Expected: FAIL on missing implementations.

- [ ] **Step 4: Implement the frozen formulas**

```python
def inject_second_harmonic(
    samples: np.ndarray,
    alpha: float,
    post_gain: float,
) -> TransformResult:
    squared = samples.astype(np.float64) ** 2
    transformed = (
        samples.astype(np.float64)
        + alpha * (squared - float(np.mean(squared)))
    ) * post_gain
    return checked_result(transformed, kind="second_harmonic")
```

Clipping candidates are exactly `0.03`, `0.05`, and `0.10`; alpha candidates
are exactly `0.10`, `0.15`, and `0.20`. Final values come only from the frozen
validation selection rule.

- [ ] **Step 5: Implement evaluator-only reference analysis**

Call `analyze_clipping`, `estimate_f0_autocorrelation`, and
`analyze_harmonic_distortion` directly. The module accepts waveform/provenance
only and has no import from Agent, planner, runner, scoring, or reporting.
Stamp `reference_analyzer_id=signal_diag.external_reference` and
`reference_analyzer_version=1.0.0`.

- [ ] **Step 6: Run focused and architecture tests**

Run:

```powershell
pytest tests/evaluation/external/test_transforms.py tests/evaluation/external/test_reference.py -v
pytest tests/test_architecture_boundaries.py -v
```

Expected: PASS.

- [ ] **Step 7: Review checkpoint**

If authorized, commit as `feat: add semi-real WAV transforms`.

---

### Task 6: Validate Counts, Provenance, Labels, and Group Isolation

**Files:**
- Create: `src/signal_diag/evaluation/external/validation.py`
- Create: `tests/evaluation/external/test_validation.py`

**Interfaces:**
- Produces:
  `validate_external_manifest(manifest, asset_root, *, stage) -> ExternalValidationReport`
  where `stage` is `"development"`, `"validation"`, or `"final_preflight"`.

- [ ] **Step 1: Write failing validation tests**

Cover:

- 14/10/28 split counts and 12/28/12 A/B/C counts;
- seven complete B families with four variants each;
- whole/final confidence distributions 21/23/4/4 and 12/12/2/2;
- whole/final class distributions from the spec;
- original/derived digest and group-key non-overlap;
- all B derivatives remain with the parent split;
- source-record, ESC `src_file`, NSynth instrument, and configuration isolation;
- exact WAV digest/format and frozen loader acceptance;
- truth-free filename/question/signal ID;
- strong/reference-only correctness mask;
- A overload mechanism never promoted to strong truth.

```python
def test_ev_t033_parent_family_cannot_cross_splits(
    valid_manifest: ExternalDatasetManifest,
) -> None:
    leaked = move_one_variant_to_validation(valid_manifest)
    report = validate_external_manifest(leaked, FIXTURE_ROOT, stage="validation")
    assert "parent_master_split_leakage" in issue_codes(report)
```

- [ ] **Step 2: Confirm tests fail**

Run: `pytest tests/evaluation/external/test_validation.py -v`

Expected: FAIL on missing validator.

- [ ] **Step 3: Implement staged validation**

Development permits incomplete planned counts but validates every present case.
Validation requires 14 development plus 10 validation cases and a frozen global
transform config. Final preflight requires all 52 cases, 28 final slots, exactly
24 scoreable final cases, all review references, and zero split leakage.

- [ ] **Step 4: Add coverage reporting**

Report documented loudspeaker, microphone/position, distance, level, acoustic
environment, and F0-band coverage. Missing public metadata is `unavailable`,
never inferred. A coverage miss blocks `meets_target` but does not rewrite the
data.

- [ ] **Step 5: Run focused tests**

Run: `pytest tests/evaluation/external/test_validation.py -v`

Expected: PASS.

- [ ] **Step 6: Review checkpoint**

If authorized, commit as `feat: validate external study isolation`.

---

### Task 7: Add Delayed Blinded Re-Review and Final Sealing

**Files:**
- Create: `src/signal_diag/evaluation/external/review.py`
- Extend: `src/signal_diag/evaluation/external/sealing.py`
- Create: `tests/evaluation/external/test_review.py`
- Create: `tests/evaluation/external/test_sealing.py`
- Create: `docs/evaluations/v0_2_external_wav/protocol/label_manual.md`

**Interfaces:**
- Produces:
  `build_blind_package(manifest, round1, *, alias_salt, created_at) -> BlindPackage`,
  `score_delayed_review(round1, round2) -> ReviewAgreement`, and
  `seal_final_external_test(inputs, destination) -> FinalSeal`.

- [ ] **Step 1: Write blindness and delay tests**

```python
def test_ev_t036_blind_package_excludes_truth_and_source_fields() -> None:
    payload = build_blind_package(
        manifest=MANIFEST,
        round1=ROUND1,
        alias_salt=b"fixed-test-salt",
        created_at=UTC_NOW,
    ).model_dump(mode="json")
    text = json.dumps(payload)
    for forbidden in ("SMARD", "clipping", "alpha", "parent_master", "final_external_test"):
        assert forbidden not in text


def test_ev_t037_round2_before_fourteen_days_is_rejected() -> None:
    with pytest.raises(ValueError, match="14 complete days"):
        score_delayed_review(ROUND1, round2_at(days=13, hours=23))
```

- [ ] **Step 2: Confirm tests fail**

Run:
`pytest tests/evaluation/external/test_review.py tests/evaluation/external/test_sealing.py -v`

Expected: FAIL on missing review/seal behavior.

- [ ] **Step 3: Implement the label manual and review forms**

Use the four confidence definitions verbatim from the spec. Round 1 and Round 2
record outcome, exact causal set, confidence, applicability, reason codes, and
review timestamp. Round 2 receives only alias, audio, neutral allowed metadata,
and reference summaries.

- [ ] **Step 4: Implement agreement statistics**

Return raw outcome agreement, causal-set agreement on eligible cases,
unweighted outcome Cohen kappa, and quadratic-weighted confidence kappa.
Return `None` plus a reason when kappa is undefined. Disagreement cannot upgrade
confidence; unresolved A/C cases downgrade to weak/unknown.

- [ ] **Step 5: Implement write-once final sealing**

Require final-preflight validity, elapsed review delay, 28 final cases, 24
scoreable labels, review targets, protected-asset validity, absent destination,
and no existing run output. Write canonical manifest, scoreability mask,
reference summaries, review agreement, protected audit, and `seal.sha256` using
create-new semantics.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
pytest tests/evaluation/external/test_review.py tests/evaluation/external/test_sealing.py tests/evaluation/external/test_preservation.py -v
```

Expected: PASS.

- [ ] **Step 7: Review checkpoint**

If authorized, commit as `feat: seal delayed blind external review`.

---

### Task 8: Implement Additive External Scoring and Stratification

**Files:**
- Create: `src/signal_diag/evaluation/external/scoring.py`
- Create: `tests/evaluation/external/test_scoring.py`

**Interfaces:**
- Produces:
  `score_external_trace(case: ExternalCase, trace: EvaluationTrace) -> ExternalRunScore`,
  `aggregate_external_scores(cases, scores, attempts) -> ExternalAggregate`, and
  `evaluate_external_targets(aggregate, review) -> ExternalTargetStatus`.

- [ ] **Step 1: Write scoreability tests**

```python
def test_ev_t040_unknown_case_has_no_correctness_boolean() -> None:
    score = score_external_trace(UNKNOWN_CASE, TRACE_WITH_CLIPPING_CLAIM)
    assert score.outcome_correct is None
    assert score.causal_exact_set_correct is None
    assert score.positive_causal_claim_on_unscored is True


def test_ev_t041_grounding_is_same_run_even_for_unscored_case() -> None:
    score = score_external_trace(
        UNKNOWN_CASE,
        trace_with_foreign_evidence_reference(),
    )
    assert score.evidence_grounding == RateMetric(
        numerator=0,
        denominator=1,
        value=0.0,
    )
    assert score.unsupported_same_run_claims == 1
```

- [ ] **Step 2: Confirm tests fail**

Run: `pytest tests/evaluation/external/test_scoring.py -v`

Expected: FAIL on missing external scorer.

- [ ] **Step 3: Implement correctness and behavior scoring**

For strong/reference cases, score outcome and exact causal set against the
sealed truth. For weak/unknown cases, store `None` for correctness and count
positive causal claims only as conservatism observations. Grounding validates
Evidence, rule, and knowledge references against the same trace regardless of
confidence.

Implement the existing behavioral definitions against external
`observable_conditions` and `sufficient_evidence_sets` without importing or
changing private functions in `evaluation/scoring.py`. Stamp
`signal_diag.external_scoring=1.0.0`.

- [ ] **Step 4: Implement aggregate metrics**

Return explicit numerator/denominator/exclusions for:

```text
outcome accuracy
causal exact-set accuracy
clipping/harmonic per-class precision and recall
causal macro-F1
evidence grounding
unsupported same-run claim rate
unnecessary Tool action rate
inconclusive appropriateness
positive causal claims on weak/unknown
scoreable coverage
```

Produce strata by path, A/B/C, source, confidence, class, capture family, and
parent master. Master-cluster summaries count four related B variants as one
cluster.

- [ ] **Step 5: Implement the three status states**

`harness_completed` depends only on deterministic integrity. `experiment_completed`
requires 28 Agent plus 28 fixed attempt records. `meets_target` uses the exact
thresholds in Section 17.3 of the spec. Any miss becomes
`external_validation_completed/below_target`.

- [ ] **Step 6: Prove historical scoring identity does not drift**

Run:

```powershell
pytest tests/evaluation/external/test_scoring.py tests/evaluation/test_phase4_3_1_scoring.py -v
pytest tests/evaluation/external/test_preservation.py -v
```

Expected: PASS and the historical scoring hash remains frozen.

- [ ] **Step 7: Review checkpoint**

If authorized, commit as `feat: add external validation scoring`.

---

### Task 9: Run Identical WAVs Through the Frozen Agent and Baseline

**Files:**
- Create: `src/signal_diag/evaluation/external/runner.py`
- Create: `tests/evaluation/external/test_runner.py`

**Interfaces:**
- Produces:
  `run_external_baseline(seal, asset_root, output) -> tuple[EvaluationTrace, ...]`
  and
  `run_external_agent(seal, asset_root, output, *, planner_factory, authorized) -> tuple[EvaluationTrace, ...]`.

- [ ] **Step 1: Write runner preflight tests**

Assert preflight occurs before credentials/client construction, final seal and
digests are mandatory, opaque filenames are passed to `load_wav_bytes`, and the
same derived SHA is used for Agent and baseline.

- [ ] **Step 2: Write no-retry/no-fallback tests**

```python
@pytest.mark.asyncio
async def test_ev_t045_provider_failure_consumes_slot_without_fallback(
    sealed_case: ExternalCase,
) -> None:
    factory = CountingFactory(FailingRealPlanner())
    report = await run_external_agent(
        ONE_CASE_SEAL,
        FIXTURE_ROOT,
        TMP_OUTPUT,
        planner_factory=factory,
        authorized=True,
    )
    assert factory.calls == 1
    assert len(report.attempts) == 1
    assert report.attempts[0].status == "infrastructure_error"
    assert report.traces == ()
    assert "ScriptedPlanner" not in factory.constructed_types
```

- [ ] **Step 3: Confirm tests fail**

Run: `pytest tests/evaluation/external/test_runner.py -v`

Expected: FAIL on missing runner.

- [ ] **Step 4: Implement shared WAV materialization**

For each case, verify bytes and loader metadata, create deterministic opaque
an ID matching `sig_ext_[0-9a-f]{16}`, insert one immutable record, and use it
for both paths.
Capture complete `EvaluationTrace` using `RecordingPlanner` and
`assemble_agent_events`. This exercises the frozen WAV loader and runtime but
does not claim that CLI/Web itself was rerun.

- [ ] **Step 5: Implement fixed-pipeline execution**

Instantiate the accepted `FixedPipelineBaseline` with the same repository,
`SignalToolService`, `RuleEngine`, `YamlRuleProfileLoader`, and frozen profile.
Run exactly one baseline slot per final case.

- [ ] **Step 6: Implement the separately authorized Agent execution**

Use `RealLLMPlanner` with provider `deepseek`, model
`deepseek-v4-flash`, prompt `v0.2-s1-planner-8.1`, temperature zero,
thinking disabled, the frozen prompt hash, max concurrency one,
`max_infrastructure_retries=0`, and the neutral request from the spec.
Reject a factory returning `ScriptedPlanner`.

Write an attempt record before each provider call and atomically finalize it
after success/failure. An existing case-slot attempt blocks rerun.

- [ ] **Step 7: Run deterministic runner tests**

Run:

```powershell
pytest tests/evaluation/external/test_runner.py -v
pytest tests/evaluation/test_baseline.py tests/evaluation/test_recording.py -v
```

Expected: PASS with fake planners only and zero network/model calls.

- [ ] **Step 8: Review checkpoint**

If authorized, commit as `feat: add sealed external WAV runner`.

---

### Task 10: Write Append-Only Bundles, Reports, and an Explicit CLI

**Files:**
- Create: `src/signal_diag/evaluation/external/reporting.py`
- Create: `src/signal_diag/evaluation/external/__main__.py`
- Create: `tests/evaluation/external/test_reporting.py`
- Create: `tests/evaluation/external/test_cli.py`

**Interfaces:**
- Produces:
  `write_external_bundle(report, destination) -> tuple[Path, ...]` and
  `verify_external_bundle(bundle: Path) -> None`.

- [ ] **Step 1: Write append-only bundle tests**

Require these files:

```text
study_manifest.json
provenance.jsonl
reference_summaries.jsonl
review_agreement.json
attempts.jsonl
runs.jsonl
metrics.json
strata.csv
report.md
protected_assets.json
checksums.sha256
```

Test deterministic ordering/checksums, secret and local-path redaction,
retention of failed/unscored attempts, destination-exists rejection, and
absence of original third-party audio.

- [ ] **Step 2: Write CLI gate tests**

The CLI exposes:

```text
validate-source-catalog
acquire --allow-network
derive
reference
validate-manifest
build-review-package
score-review
seal-final
run-baseline
run-agent --authorize-real-model
write-report
verify-bundle
verify-preservation
```

`acquire` fails without `--allow-network`. `run-agent` fails without
`--authorize-real-model` and valid credentials; it never constructs a
ScriptedPlanner.

- [ ] **Step 3: Confirm tests fail**

Run:
`pytest tests/evaluation/external/test_reporting.py tests/evaluation/external/test_cli.py -v`

Expected: FAIL on missing writer/CLI.

- [ ] **Step 4: Implement bundle writing and verification**

Use create-new directory semantics, canonical UTF-8/LF files, sorted SHA-256
lines, and no self-hash. Reports show numerator/denominator/exclusions,
Agent/fixed comparison, all strata, review agreement, licensing, public-data
limitations, and the three distinct status values.

- [ ] **Step 5: Implement the explicit CLI**

Use `argparse`. Every mutating subcommand accepts explicit input/output paths;
no default points into historical Phase 4/5 directories. Validate output paths
before reading credentials or final audio.

- [ ] **Step 6: Run focused tests**

Run:

```powershell
pytest tests/evaluation/external/test_reporting.py tests/evaluation/external/test_cli.py -v
python -m signal_diag.evaluation.external --help
```

Expected: PASS/help only; no downloads, product run, or model call.

- [ ] **Step 7: Review checkpoint**

If authorized, commit as `feat: add external validation bundles and CLI`.

---

### Task 11: Execute Phase B Pilot and Phase C Development/Validation

**Files:**
- Populate: `docs/evaluations/v0_2_external_wav/protocol/source_catalog.json`
- Create: `docs/evaluations/v0_2_external_wav/development/study_v0_2_external_wav_dev_1/`
- Create: `docs/evaluations/v0_2_external_wav/validation/study_v0_2_external_wav_validation_1/`
- Keep raw/cache: `private/external_wav/`

**Interfaces:**
- Consumes: separately approved network/download budget and accepted source
  terms.
- Produces: 14 development cases, 10 validation cases, frozen transform config,
  and Round 1 labels; it does not access final Agent cases.

- [ ] **Step 1: Stop for download authorization**

Present exact selected source URLs, declared/estimated bytes, terms/license
classification, redistribution decision, and destination. Do not run
`acquire` until approved.

- [ ] **Step 2: Acquire the minimal pilot**

Acquire one or two development-only master families and a minimal stress
sample. Retain observed digests and terms snapshots. Abort on unexpected size,
redirected host, content type, or digest mismatch.

- [ ] **Step 3: Derive and reproduce the pilot**

Create clean/base, clipping, harmonic, and combined files twice in separate
temporary directories and assert identical SHA-256. Verify every analysis WAV
with `load_wav_bytes`.

- [ ] **Step 4: Run independent reference analysis**

Confirm master eligibility and evaluate all predeclared `q`/`alpha` candidates.
If no candidate satisfies validation rules, retain the pilot failure and stop
for a written design amendment.

- [ ] **Step 5: Materialize development and validation**

Build exactly 14 development and 10 validation cases from isolated groups.
Freeze the lowest valid global clipping proportion, the smallest valid global
alpha, common attenuation/post-gain, quantile/rounding identities, neutral
question, target bands, and report schema.

- [ ] **Step 6: Run deterministic and fixed-pipeline gates**

Run the reference, manifest, preservation, scoring-fixture, and baseline
commands. Do not call a real model. Retain failed candidates and exclusions.

- [ ] **Step 7: Record Round 1 review**

Complete the common label form before any final Agent output exists. Generate
the blind Round 2 package and record its earliest permitted review timestamp.

- [ ] **Step 8: Stop at the validation gate**

Report selected configuration, actual source/device/environment/F0 coverage,
disk usage, license decisions, exclusions, and all deterministic results.
Request authorization before acquiring/materializing final source records.

---

### Task 12: Freeze Final Data, Run Once, and Publish Honest Results

**Files:**
- Create after final-data authorization:
  `docs/evaluations/v0_2_external_wav/final_external_test/study_v0_2_external_wav_final_1/`
- Modify only after immutable results exist:
  `README.md`
  `docs/README.md`
  `docs/PROJECT_CASE_STUDY.md`

**Interfaces:**
- Consumes: approved final source list, completed 14-day review, sealed
  28-case manifest, and separate real-model authorization.
- Produces: one immutable external campaign and evidence-linked resume wording.

- [ ] **Step 1: Stop for final-data authorization**

Present only group/source IDs, counts, bytes, terms, and split proof—not truth
labels or audio content to the Agent.

- [ ] **Step 2: Materialize and review final data**

Create 28 unseen final cases from unseen group keys. Finish Round 2 only after
14 complete days, calculate agreement, apply downgrade rules, and require
exactly 24 scoreable cases plus four weak/unknown cases before a target-eligible
seal.

- [ ] **Step 3: Seal and verify final**

Run final preflight, protected-asset verification, write-once destination
checks, source/derived checksums, identity checks, and scoreability-mask seal.
After sealing, do not replace or relabel a case.

- [ ] **Step 4: Run the fixed pipeline**

Run exactly 28 baseline slots against the sealed WAVs and write all records.
This does not authorize the Agent campaign.

- [ ] **Step 5: Stop for real-model authorization**

Report model/provider/prompt hash, 28-slot budget, zero-retry policy,
credential readiness, output destination, and sealed fingerprint. Wait for
explicit approval.

- [ ] **Step 6: Execute the Agent campaign once**

Run exactly 28 consumed Agent slots chronologically with concurrency one. Keep
timeouts, provider errors, output errors, behavior failures, and unscored slots.
Never rerun for quality and never invoke `ScriptedPlanner`.

- [ ] **Step 7: Score and write the immutable result**

Compute all required metrics/strata and classify independently as harness
completed, experiment completed, and meets target/below target. Verify the
bundle checksums and protected assets.

- [ ] **Step 8: Update presentation documents from frozen evidence**

Add exact numerators/denominators, source and license limitations, public
real-capture versus semi-real distinctions, Agent/fixed comparison, failures,
and the allowed resume sentence. Do not say official benchmark, industrial
validation, production ready, self-recorded device coverage, or industry
standard.

- [ ] **Step 9: Run the cumulative release-quality gate**

Run:

```powershell
pytest -v
ruff check .
mypy src tests
pytest tests/test_architecture_boundaries.py -v
git diff --check 605c8a8
$externalPy311 = py -3.11 -c "import sys; print(sys.executable)"
$externalPy312 = py -3.12 -c "import sys; print(sys.executable)"
python scripts/verify_phase5_local_matrix.py --python-3.11 $externalPy311 --python-3.12 $externalPy312
```

Expected: zero required skip/xfail, all deterministic gates green, both clean
environment versions green, and no protected checksum drift. Real-model
behavior remains a separately recorded non-CI result.

- [ ] **Step 10: Final review checkpoint**

If commits have been separately authorized, commit code/harness and data/report
artifacts in reviewable checkpoints without committing restricted audio. Do
not merge, push, or move the tag without separate authority.

---

## Execution Stop Gates

```text
After Task 10: implementation/harness review; no network has been used.
Before Task 11 Step 2: explicit download and source-terms authorization.
Before Task 12 Step 2: explicit final-data authorization.
Before Task 12 Step 6: explicit one-time real-model authorization.
Before every commit/push/merge: explicit Git authorization.
```

At every gate, a failure is a retained result. It does not authorize use of
final data for tuning, replacement of cases, a prompt/rule/scoring change,
ScriptedPlanner fallback, or modification of historical V0.2 evidence.
