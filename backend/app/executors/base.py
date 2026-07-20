from __future__ import annotations

from typing import Protocol, TypeVar


InputT = TypeVar("InputT", contravariant=True)
OutputT = TypeVar("OutputT", covariant=True)


class StageExecutor(Protocol[InputT, OutputT]):
    async def execute(self, stage_input: InputT) -> OutputT: ...

