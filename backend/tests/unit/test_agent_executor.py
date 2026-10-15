from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from backend.app.agents.requirement_agent import build_requirement_agent
from backend.app.agents.reply_agent import build_reply_agent
from backend.app.agents.technical_agent import build_technical_agent
from backend.app.agents.model_compat import json_object_model_settings
from backend.app.executors.agent_executor import AgentStageExecutor
from backend.app.schemas.reply import ReplyAgentOutput
from backend.app.schemas.requirement import RequirementAgentInput, RequirementAgentOutput
from backend.app.schemas.technical import TechnicalAgentOutput


class FakeRunner:
    def __init__(self, final_output):
        self.final_output = final_output
        self.calls = []

    async def __call__(self, agent, prompt, **kwargs):
        self.calls.append((agent, prompt, kwargs))
        return SimpleNamespace(final_output=self.final_output)


@pytest.mark.asyncio
async def test_agent_adapter_validates_structured_final_output() -> None:
    expected = RequirementAgentOutput(
        project_type="website", features=["content_management"]
    )
    runner = FakeRunner(expected.model_dump())
    adapter = AgentStageExecutor(
        agent=build_requirement_agent(model="test-model"),
        output_type=RequirementAgentOutput,
        runner=runner,
    )

    result = await adapter.execute(
        RequirementAgentInput(requirement_text="开发企业官网")
    )

    assert result == expected
    assert "开发企业官网" in runner.calls[0][1]
    assert "JSON Schema" in runner.calls[0][1]


@pytest.mark.asyncio
async def test_agent_adapter_rejects_invalid_output() -> None:
    adapter = AgentStageExecutor(
        agent=build_requirement_agent(model="test-model"),
        output_type=RequirementAgentOutput,
        runner=FakeRunner({"features": []}),
    )

    with pytest.raises(ValidationError):
        await adapter.execute(RequirementAgentInput(requirement_text="开发官网"))


def test_requirement_agent_uses_its_independent_output_model() -> None:
    agent = build_requirement_agent(model="test-model")
    assert agent.name == "RequirementAgent"
    assert agent.output_type is None
    assert agent.model_settings.extra_body["response_format"] == {"type": "json_object"}


def test_deepseek_disables_reasoning_for_json_stages(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.deepseek.com")
    settings = json_object_model_settings()
    assert settings.extra_body == {
        "response_format": {"type": "json_object"},
        "thinking": {"type": "disabled"},
    }


def test_non_deepseek_json_stage_does_not_send_provider_specific_fields(monkeypatch) -> None:
    monkeypatch.setenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
    settings = json_object_model_settings()
    assert settings.extra_body == {"response_format": {"type": "json_object"}}


@pytest.mark.parametrize(
    ("factory", "name", "output_type"),
    [
        (build_requirement_agent, "RequirementAgent", RequirementAgentOutput),
        (build_technical_agent, "TechnicalAgent", TechnicalAgentOutput),
        (build_reply_agent, "ReplyAgent", ReplyAgentOutput),
    ],
)
def test_phase_one_agents_have_independent_outputs_and_no_handoffs(
    factory, name, output_type
) -> None:
    agent = factory(model="test-model")
    assert agent.name == name
    assert agent.output_type is None
    assert agent.model_settings.extra_body["response_format"] == {"type": "json_object"}
    assert agent.handoffs == []
