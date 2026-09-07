"""A Strands Model that answers from a script, so the invoke path runs without Bedrock."""

from __future__ import annotations

import json
from typing import Any, AsyncGenerator

from strands.models.model import Model


class FakeModel(Model):
    def __init__(self, text: str = "fake answer", structured: dict | None = None, call_tool: str | None = None):
        self.text, self.structured, self.call_tool = text, structured, call_tool
        self.calls = 0
        self.seen_system: list[str | None] = []

    def update_config(self, **model_config: Any) -> None:  # noqa: D401
        pass

    def get_config(self) -> Any:
        return {"model_id": "fake"}

    async def structured_output(self, output_model, prompt, system_prompt=None, **kwargs) -> AsyncGenerator[dict, None]:
        self.calls += 1
        self.seen_system.append(system_prompt)
        yield {"output": output_model.model_validate(self.structured or {})}

    async def stream(self, messages, tool_specs=None, system_prompt=None, **kwargs):
        self.calls += 1
        self.seen_system.append(system_prompt)
        yield {"messageStart": {"role": "assistant"}}
        # Structured output: Strands forces a tool named after the output model.
        if self.structured and tool_specs:
            spec = next((s for s in tool_specs if s["name"] in ("ObligationList",)), tool_specs[0])
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "so1", "name": spec["name"]}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps(self.structured)}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        # First turn: optionally call a tool once; second turn: answer with text.
        elif self.call_tool and self.calls == 1 and tool_specs:
            yield {"contentBlockStart": {"start": {"toolUse": {"toolUseId": "t1", "name": self.call_tool}}}}
            yield {"contentBlockDelta": {"delta": {"toolUse": {"input": json.dumps({})}}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "tool_use"}}
        else:
            yield {"contentBlockStart": {"start": {}}}
            for chunk in self.text.split(" "):
                yield {"contentBlockDelta": {"delta": {"text": chunk + " "}}}
            yield {"contentBlockStop": {}}
            yield {"messageStop": {"stopReason": "end_turn"}}
        yield {"metadata": {"usage": {"inputTokens": 10, "outputTokens": 5, "totalTokens": 15}, "metrics": {"latencyMs": 1}}}
