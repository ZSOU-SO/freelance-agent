from types import SimpleNamespace

import pytest

from backend.app.agents.technical_agent import build_technical_agent
from backend.app.executors.agent_executor import (
    AgentStageExecutor,
    CaseReferenceValidationError,
)
from backend.app.schemas.case import AgentCaseImpact, CaseInsight
from backend.app.schemas.common import (
    AcceptanceVerdict,
    DurationEstimate,
    Recommendation,
)
from backend.app.schemas.requirement import RequirementAgentOutput
from backend.app.schemas.technical import (
    TechnicalAgentInput,
    TechnicalAgentOutput,
    TechnicalSolution,
)


def technical_output(*, project_number: str | None = None) -> TechnicalAgentOutput:
    impacts = []
    if project_number:
        impacts.append(
            AgentCaseImpact(
                agent="TechnicalAgent",
                project_number=project_number,
                summary="参考案例",
            )
        )
    return TechnicalAgentOutput(
        solution=TechnicalSolution(
            frontend=["Vue 3"],
            backend=["FastAPI"],
            database=["SQLite"],
            deployment=["Docker"],
            architecture="前后端分离",
            deliverables=["源代码"],
        ),
        estimated_duration=DurationEstimate(
            min_days=10, max_days=15, explanation="估算"
        ),
        risks=[],
        recommendation=Recommendation(
            should_accept=True,
            verdict=AcceptanceVerdict.ACCEPT,
            reasons=["可实现"],
        ),
        case_impacts=impacts,
    )


class Runner:
    def __init__(self, output):
        self.output = output
        self.prompt = ""

    async def __call__(self, agent, prompt, **kwargs):
        self.prompt = prompt
        return SimpleNamespace(final_output=self.output)


@pytest.mark.asyncio
async def test_technical_agent_receives_structured_case_insight() -> None:
    runner = Runner(technical_output())
    stage_input = TechnicalAgentInput(
        requirement=RequirementAgentOutput(project_type="web_app"),
        case_insight=CaseInsight(
            technical_notes=["历史案例提示工期风险"],
            source_project_numbers=["CASE-001"],
        ),
    )
    executor = AgentStageExecutor(
        agent=build_technical_agent(model="test-model"),
        output_type=TechnicalAgentOutput,
        runner=runner,
    )

    await executor.execute(stage_input)

    assert "CASE-001" in runner.prompt
    assert "历史案例" in str(executor.agent.instructions)
    assert "不可信" in str(executor.agent.instructions)


@pytest.mark.asyncio
async def test_technical_agent_rejects_unknown_case_reference() -> None:
    executor = AgentStageExecutor(
        agent=build_technical_agent(model="test-model"),
        output_type=TechnicalAgentOutput,
        runner=Runner(technical_output(project_number="MADE-UP")),
    )

    with pytest.raises(CaseReferenceValidationError):
        await executor.execute(
            TechnicalAgentInput(
                requirement=RequirementAgentOutput(project_type="web_app")
            )
        )

