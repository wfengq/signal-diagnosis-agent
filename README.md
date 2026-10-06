# Signal Diagnosis Agent

[中文对照](README.zh-CN.md)

An LLM agent that answers one narrow question about audio test signals, and
proves its answers: **"Why does this periodic signal sound distorted?"**

Give it a WAV file and, optionally, a plain-language description. It decides
which measurements to run, runs them with deterministic DSP, judges them against
versioned rules, and returns a diagnosis (clipping, harmonic distortion, both,
no supported fault, or inconclusive) in which every claim cites the measurements
behind it.

- **The LLM plans; it never measures.** Every number comes from deterministic
  DSP, and every threshold comes from a versioned rule profile. Raw waveforms
  and full FFT arrays are never sent to the model.
- **Claims are gated by evidence.** A conclusion is accepted only if it cites
  same-run Evidence and rule evaluations, and the runtime rejects one that does
  not. When the evidence cannot settle the question, the answer is
  `inconclusive`.
- **Results are measured against honest baselines.** Every behavioral claim
  below comes from a pre-registered evaluation with a held-out set run once, and
  the misses are kept in the repository next to the hits.

> This is a demonstrable vertical slice, not a production audio-QA,
> chip-validation or standards-compliance product. Rule thresholds (1 %
> clipping, 5 % THD) are demonstration settings, not industry standards.

## Results at a glance

| Evaluation | What it measured | Result |
|---|---|---|
| **V0.2 official held-out** (accepted product: commit `b48790c`, prompt `v0.2-s1-planner-8.1`) | 80 held-out agent runs on synthetic S1 cases | **79/80** correct outcomes; causal macro F1 1.0; evidence grounding 1.0; unsupported-claim rate 0.0 |
| **Agent-increment study** (2026-10-06; study prompts `v0.3-s1-planner-9.15` / `v0.3-s1-intake-1.1`, not the product default) | How many more cases the agent gets right than the strongest fixed pipeline, on 24 held-out cases per task family | **T1, free-text intake:** **+5** (22 vs 17), a measurable increment. **T2, localized faults:** **0** (18 vs 18), but with **96 vs 824** tool calls. The agent made **0** unsupported positive conclusions in 48 cases. |
| **V0.3 contextual validation** | Diagnosis with a declared reference or nominal tone on external WAVs | See the [acceptance report](docs/evaluations/v0_3/contextual/V9_11_CONTEXTUAL_VALIDATION_ACCEPTANCE_REPORT.md) |

Each figure belongs to the identity named in its row, and none of them stands in
for another. The 79/80 attaches only to the V0.2 product identity. The
agent-increment numbers come from study prompts that the product does not run
by default. Full reports:

- [Agent-increment results report](docs/evaluations/v0_3/agent_increment/STUDY_S1_AGENT_INCREMENT_1_REPORT.md):
  verdicts, per-arm tables, the limits that bound the numbers, and the five
  development rounds it took to get there.
- [Engineering case study](docs/PROJECT_CASE_STUDY.md): the difficult failures,
  corrections and decisions across the project.

## Why the numbers can be trusted

- **Held-out discipline.** Development sets are for iteration. Prompts are
  frozen, with their hashes recorded, before a held-out set runs, and a
  held-out set runs once.
- **Honest baselines.** The agent is compared with the strongest fixed pipeline
  we could build: a regex intake for T1, and an exhaustive segment scan for T2.
  "The fixed pipeline is enough" counts as a valid outcome.
- **Failures stay visible.** The first official run (`below_target`), the
  development misses, and the defective agent-increment rounds are all
  committed alongside the accepted results, and every correction is recorded in
  [DECISIONS.md](docs/DECISIONS.md).
- **No silent fallbacks.** The product path is the real-LLM planner. A scripted
  planner exists only for tests and is never substituted when credentials are
  missing.

## Quick start

Requires Python 3.11 or 3.12 and a DeepSeek API key, set in your environment.
Never commit the key.

```text
python -m pip install ".[app,llm]"
set DEEPSEEK_API_KEY=<your-key>        # export on macOS/Linux
signal-diag serve --host 127.0.0.1 --port 8765
```

Open `http://127.0.0.1:8765`. The health endpoint, presets and static UI load
without credentials. Submitting a diagnosis without them returns a
configuration error rather than a scripted answer.

The page opens on **describe the problem**: write what you hear, choose one or
two WAV files, review the drafted context field by field, then diagnose. The
interface is in Chinese, with the key English terms kept alongside. The manual
form and the demo presets sit under an "advanced" section.

**This is a local, single-user, no-auth service. Do not expose it to an
untrusted network.**

From the command line:

```text
signal-diag presets
signal-diag diagnose synthetic clipping
signal-diag diagnose wav path/to/file.wav --channel mixdown --output json --html-output report.html
signal-diag intake diagnose --text "the 1 kHz test tone sounds harsh" --test-file new.wav --file old.wav
```

`intake diagnose` prompts you to keep, edit or skip each drafted field. Use
`--yes` or explicit field flags (`--mode`, `--reference`,
`--nominal-fundamental-hz`, `--stimulus-kind`) in scripts.

Exit 0 means the agent completed a valid result, including `inconclusive` or
`no_supported_fault`. Exit 1 is an agent, runtime or application failure. Exit 2
is a usage, input or configuration error.

### What the default path will and will not claim

The default path takes a single file and stays conservative. It can confirm
clipping. It does not call rich harmonics "added distortion" without context.
Supplying a clean reference WAV or a declared single-tone frequency is an
optional upgrade that lets it attribute harmonic distortion. It does not assume
that every user has an undistorted original.

Free-text intake only drafts that context. The model sees your text and the
file names, never the audio. A drafted field is used only after you confirm
it. If a mode's required fields are not all confirmed, the run falls back to
the single-file path and says why. A nominal frequency comes only from your
text or your input, never from measurement. Reports note when the context came
from a confirmed draft.

## Architecture

```text
signal -> dsp -> tools -> rules/knowledge -> agent -> evaluation -> app
```

```text
CLI / Web UI / API
        |
DiagnosisApplicationService
        |
DistortionDiagnosisRuntime <-> RealLLMPlanner
        |
SignalToolService -> deterministic DSP -> Evidence
        |
RuleEngine / KnowledgeIndex
        |
StructuredDiagnosis -> JSON / HTML / UI
```

Architecture tests enforce the dependency direction. `signal`, `dsp`, `tools`,
`rules` and `knowledge` do not depend on the agent or on any LLM framework.

To read the code, follow one request vertically:

1. `src/signal_diag/app/cli.py` and `app/composition.py`: entry point and
   dependency assembly.
2. `app/service.py`: from a WAV or preset request to one agent run.
3. `agent/models.py`, `agent/planner.py` and `agent/runtime.py`: decisions, the
   model boundary, the state machine, limits and termination.
4. `tools/service.py` into `dsp/clipping.py` or `dsp/harmonics.py`:
   deterministic computation becoming Evidence.
5. `rules/engine.py` and `knowledge/index.py`: configured judgments and
   deterministic retrieval.
6. `evaluation/`: campaigns, scoring and the agent-increment study harness.
7. `tests/agent/test_s1_acceptance.py` and
   `tests/test_architecture_boundaries.py`: end-to-end contract and dependency
   proof.

## Limitations

- **Scope:** S1 distortion only. This is not a general audio or hardware-test
  platform.
- **Inputs:** synthetic cases and bounded integer-PCM WAV. Arbitrary production
  captures are not a validated corpus.
- **F0 estimation:** an autocorrelation baseline, not a universal pitch tracker.
  At 8 kHz it can lock onto a subharmonic; the agent-increment report shows
  this cost.
- **Deployment:** local only. No authentication, database, Docker, vector
  search or multi-agent runtime.
- **Disclosed misses:**
  - The accepted official run has two behavior-coded runs and one wrong outcome
    out of 80.
  - The agent-increment study rests on 24 held-out cases per family, a single
    run and a single model.

## Versions and identities

- **Accepted V0.2 product:** commit `b48790c`, prompt `v0.2-s1-planner-8.1`.
  The 79/80 above and the retained
  [Phase 5 Demo](docs/demo/phase5/v0_2_acceptance/README.md) belong to this
  anchor. To replay that Demo, check out `b48790c` (or tag `v0.2.0` when
  present).
- **Current default branch:** the product runs the additive V0.3 planner
  `v0.3-s1-planner-9.11` in contextual mode. Its reports are not certified by
  the V0.2 evaluation. Package metadata still says `0.2.0`, which preserves
  tag and wheel history.
- **Free-text intake:** the product uses intake prompt `v0.3-s1-intake-1.1`,
  the one evaluated in the agent-increment study, but diagnoses with the
  product planner `v0.3-s1-planner-9.11`.
- **Agent-increment study planner** (`v0.3-s1-planner-9.15`): evaluated in the
  study, but not the product default.

## Input and install details

WAV boundary:

- Little-endian RIFF/WAVE, either integer PCM or extensible PCM with a PCM
  subtype.
- 8/16/24/32 bit, mono or stereo, 8 kHz to 192 kHz.
- At most 20 MiB, 2,000,000 frames and 30 seconds.
- Exact full-scale `float32` conversion, with no per-signal peak normalization.
- RIFX, RF64, IEEE float, compressed formats and more than two channels are
  rejected.

Development install: `python -m pip install ".[app,llm,dev]"`. The core
DSP/rules/knowledge/agent install, `pip install .`, does not pull in FastAPI.
Required tests never call a live model. CI runs the full suite on Python 3.11
and 3.12.

## Documentation

Start with the [documentation index](docs/README.md). It has a short reviewer
path, the sources of truth, and an index of every evaluation.

- [Architecture](docs/ARCHITECTURE_V0_2.md)
- [V0.2 frozen contracts](docs/CONTRACTS_V0_2.md)
- [V0.3 contextual contracts](docs/CONTRACTS_V0_3_CONTEXTUAL.md)
- [Design decisions](docs/DECISIONS.md)
- [Engineering case study](docs/PROJECT_CASE_STUDY.md)
