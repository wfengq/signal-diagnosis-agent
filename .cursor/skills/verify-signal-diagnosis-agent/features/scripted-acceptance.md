# ScriptedPlanner acceptance

Deterministic Agent/runtime acceptance uses an injected `ScriptedPlanner`.
This is the CI/unit path (`tests\agent\test_s1_acceptance.py` and related).
It is **not** the product CLI/API planner and must not be reported as a
RealLLM Demo.

## Sub-features

- `s1-acceptance` — `pytest tests\agent\test_s1_acceptance.py`
- `architecture` — `pytest tests\test_architecture_boundaries.py`
- `external-preservation` — `pytest tests\evaluation\external\test_preservation.py` (V0.2 external study freeze)

## How to get to it (user POV)

- A developer runs pytest from the repo root with the dev extra.
- Users of the Web UI / CLI never select ScriptedPlanner.

## Driving it with pytest

Preconditions:

- `.venv` with `[dev]` extras (`pytest` on PATH via `.\.venv\Scripts\pytest.exe`).
- No live network / DeepSeek required.
- Do not pass `-k` that skips required assertions and then call the feature verified.

- **S1 acceptance.** `.\.venv\Scripts\pytest.exe tests\agent\test_s1_acceptance.py -q`. Exit 0. Save to `evidence/pytest-s1-acceptance.txt`.
- **Architecture gate.** `.\.venv\Scripts\pytest.exe tests\test_architecture_boundaries.py -q`. Exit 0. Save to `evidence/pytest-architecture.txt`.
- **Proof.** Pytest exit 0 artifacts. Explicitly record: “ScriptedPlanner only; RealLLM product path not verified.”

## Gotchas

- A green pytest run is not `presentation_harness_accepted` and not a live Demo.
- Do not set product composition to ScriptedPlanner to make HTTP diagnose return 200.
- Full-suite counts in README (T001–T285) are historical acceptance; this feature file only claims the tests you actually ran.
- V0.3 contextual pytest files are out of scope unless a later map entry names them.
