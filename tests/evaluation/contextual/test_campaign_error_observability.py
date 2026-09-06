"""T-CX245–T-CX247: restricted campaign failure observability."""

from __future__ import annotations

import json
from dataclasses import replace
from pathlib import Path

import pytest


def test_t_cx245_provider_failure_fingerprint_excludes_message_and_secret() -> None:
    from signal_diag.evaluation.recording import restricted_error_fingerprint

    class APIStatusError(RuntimeError):
        status_code = 503

    APIStatusError.__module__ = "openai"
    error = APIStatusError("authorization=Bearer sk-must-not-survive")

    fingerprint = restricted_error_fingerprint(error)

    assert fingerprint == {
        "category": "provider_5xx",
        "error_type": "APIStatusError",
        "status_code": 503,
    }
    serialized = json.dumps(fingerprint)
    assert "must-not-survive" not in serialized
    assert "authorization" not in serialized.lower()


def test_t_cx246_internal_failure_is_not_misclassified_as_provider() -> None:
    from signal_diag.evaluation.recording import restricted_error_fingerprint

    fingerprint = restricted_error_fingerprint(
        RuntimeError("api_key=must-not-survive")
    )

    assert fingerprint == {
        "category": "evaluator_internal",
        "error_type": "RuntimeError",
        "status_code": None,
    }
    assert "must-not-survive" not in json.dumps(fingerprint)


def test_t_cx247_observability_ids_are_registered_once() -> None:
    root = Path(__file__).resolve().parents[3]
    plan = (root / "docs" / "TEST_PLAN_V0_3_CONTEXTUAL.md").read_text(
        encoding="utf-8"
    )
    rows = [line for line in plan.splitlines() if line.startswith("| T-CX")]
    for test_id in ("T-CX245", "T-CX246", "T-CX247"):
        assert sum(line.startswith(f"| {test_id} |") for line in rows) == 1


@pytest.mark.asyncio
async def test_t_cx247_real_executor_preserves_safe_provider_fingerprint(
) -> None:
    from signal_diag.agent.planner import RealLLMPlanner
    from signal_diag.app.composition import build_product_service
    from signal_diag.app.contextual_campaign import RealAgentSlotExecutor
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionSlot,
        ContextualRuntimeIdentity,
    )

    class APIConnectionError(RuntimeError):
        pass

    APIConnectionError.__module__ = "openai"

    class FailingCompletions:
        async def create(self, **kwargs: object) -> object:
            del kwargs
            raise APIConnectionError("Bearer sk-must-not-survive")

    client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {"completions": FailingCompletions()},
            )()
        },
    )()

    service = build_product_service(
        environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"}
    )
    original = service._dependencies
    service._dependencies = replace(
        original,
        planner_factory=lambda: RealLLMPlanner(
            provider="deepseek",
            api_key="present-but-not-persisted",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            client=client,  # type: ignore[arg-type]
        ),
    )
    repo = Path(__file__).resolve().parents[3]
    study = (
        repo
        / "docs"
        / "evaluations"
        / "v0_3"
        / "contextual"
        / "development"
        / "study_v0_3_contextual_dev_1"
    )
    executor = RealAgentSlotExecutor(
        service,
        study_dir=study,
        expected_identity=ContextualRuntimeIdentity(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            planner_class="RealLLMPlanner",
            prompt_version="v0.3-s1-planner-9.11",
            prompt_sha256="a" * 64,
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
            product_tree_sha256="b" * 64,
        ),
    )
    try:
        artifacts = await executor(
            ContextualExecutionSlot(
                case_id="case_provider_failure",
                arm="contextual_agent",
                mode="single_signal",
                test_wav_path="wav/cxdev_825a759a0ea47bb7_test.wav",
            )
        )
    finally:
        await service.aclose()

    assert artifacts.arm_result.infrastructure_failure is True
    assert artifacts.result["failure_diagnostic"] == {
        "category": "provider_transport",
        "error_type": "APIConnectionError",
        "status_code": None,
    }
    serialized = artifacts.model_dump_json()
    assert "must-not-survive" not in serialized
    assert "present-but-not-persisted" not in serialized


@pytest.mark.asyncio
async def test_t_cx247b_post_decide_execute_failure_gets_fingerprint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Fingerprint must attach when execute fails after decide (e.g. assemble)."""

    import json

    from signal_diag.agent.planner import RealLLMPlanner
    from signal_diag.app import service as service_mod
    from signal_diag.app.composition import build_product_service
    from signal_diag.app.contextual_campaign import RealAgentSlotExecutor
    from signal_diag.evaluation.contextual.models import (
        ContextualExecutionSlot,
        ContextualRuntimeIdentity,
    )

    finish_payload = {
        "decision_type": "finish",
        "task_assessment": {
            "task_type": "distortion_analysis",
            "objective": "diagnose",
        },
        "outcome": "inconclusive",
        "claims": [],
        "confidence_label": "low",
        "limitations": ["stop"],
    }

    class _FakeMessage:
        def __init__(self, content: str) -> None:
            self.content = content

    class _FakeChoice:
        def __init__(self, message: _FakeMessage) -> None:
            self.message = message

    class _FakeResponse:
        def __init__(self) -> None:
            self.choices = [_FakeChoice(_FakeMessage(json.dumps(finish_payload)))]

    class _FakeCompletions:
        async def create(self, **kwargs: object) -> object:
            del kwargs
            return _FakeResponse()

    client = type(
        "Client",
        (),
        {
            "chat": type(
                "Chat",
                (),
                {"completions": _FakeCompletions()},
            )()
        },
    )()

    def boom(*args: object, **kwargs: object) -> object:
        del args, kwargs
        raise ValueError("automatic rule batch does not match Tool")

    monkeypatch.setattr(service_mod, "assemble_agent_events", boom)

    service = build_product_service(
        environ={"DEEPSEEK_API_KEY": "present-but-not-persisted"}
    )
    original = service._dependencies
    service._dependencies = replace(
        original,
        planner_factory=lambda: RealLLMPlanner(
            provider="deepseek",
            api_key="present-but-not-persisted",
            base_url="https://api.deepseek.com",
            model="deepseek-v4-flash",
            client=client,  # type: ignore[arg-type]
        ),
    )
    repo = Path(__file__).resolve().parents[3]
    study = (
        repo
        / "docs"
        / "evaluations"
        / "v0_3"
        / "contextual"
        / "development"
        / "study_v0_3_contextual_dev_1"
    )
    executor = RealAgentSlotExecutor(
        service,
        study_dir=study,
        expected_identity=ContextualRuntimeIdentity(
            provider="deepseek",
            model="deepseek-v4-flash",
            base_url="https://api.deepseek.com",
            planner_class="RealLLMPlanner",
            prompt_version="v0.3-s1-planner-9.11",
            prompt_sha256="a" * 64,
            causal_policy_version="v9_11_mode_aware_no_fault_recovery",
            product_tree_sha256="b" * 64,
        ),
    )
    try:
        artifacts = await executor(
            ContextualExecutionSlot(
                case_id="case_post_decide_failure",
                arm="contextual_agent",
                mode="single_signal",
                test_wav_path="wav/cxdev_825a759a0ea47bb7_test.wav",
            )
        )
    finally:
        await service.aclose()

    assert artifacts.arm_result.infrastructure_failure is True
    assert artifacts.result["failure_diagnostic"] == {
        "category": "evaluator_internal",
        "error_type": "ValueError",
        "status_code": None,
    }
    assert "automatic rule batch" not in artifacts.model_dump_json()
