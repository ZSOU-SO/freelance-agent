from __future__ import annotations

from typing import Any, Awaitable, Callable, Generic, TypeVar

from pydantic import BaseModel

from backend.app.agents.quote_agent import QuoteRunContext, build_quote_agent
from backend.app.schemas.quote import QuoteAgentInput, QuoteAgentOutput
from backend.app.services.pricing import PricingService


InputModelT = TypeVar("InputModelT", bound=BaseModel)
OutputModelT = TypeVar("OutputModelT", bound=BaseModel)
RunnerCallable = Callable[..., Awaitable[Any]]


async def _sdk_runner(agent: Any, prompt: str, **kwargs: Any) -> Any:
    from agents import Runner

    return await Runner.run(agent, prompt, **kwargs)


def _validate_final_output(value: Any, output_type: type[OutputModelT]) -> OutputModelT:
    if isinstance(value, str):
        return output_type.model_validate_json(value)
    if isinstance(value, BaseModel):
        return output_type.model_validate(value.model_dump())
    return output_type.model_validate(value)


class AgentStageExecutor(Generic[InputModelT, OutputModelT]):
    def __init__(
        self,
        *,
        agent: Any,
        output_type: type[OutputModelT],
        runner: RunnerCallable | None = None,
    ):
        self.agent = agent
        self.output_type = output_type
        self.runner = runner or _sdk_runner

    async def execute(self, stage_input: InputModelT) -> OutputModelT:
        prompt = (
            "请分析以下经过 Pydantic 校验的 JSON，只返回指定结构：\n"
            + stage_input.model_dump_json()
        )
        result = await self.runner(self.agent, prompt)
        return _validate_final_output(result.final_output, self.output_type)


class QuoteToolNotCalledError(RuntimeError):
    pass


class QuoteAgentExecutor:
    def __init__(
        self,
        pricing_service: PricingService,
        *,
        model: str | None = None,
        runner: RunnerCallable | None = None,
    ):
        self.pricing_service = pricing_service
        self.agent = build_quote_agent(pricing_service, model=model)
        self.runner = runner or _sdk_runner

    async def execute(self, stage_input: QuoteAgentInput) -> QuoteAgentOutput:
        context = QuoteRunContext(stage_input=stage_input)
        prompt = (
            "请先调用 calculate_quote，再对以下已验证数据给出报价说明：\n"
            + stage_input.model_dump_json()
        )
        result = await self.runner(self.agent, prompt, context=context)
        model_output = _validate_final_output(result.final_output, QuoteAgentOutput)
        if context.pricing is None:
            raise QuoteToolNotCalledError("QuoteAgent did not call calculate_quote")
        return model_output.model_copy(update={"pricing": context.pricing})
