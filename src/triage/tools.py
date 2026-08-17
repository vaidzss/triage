# tools.py - Tool/TOOL_REGISTRY schema wrapper.
#
# Adapted from vaidz-llm/backend/agent_core.py:39-77, which is generic and
# Jarvis-independent. Kept close to the original; dropped `dangerous` /
# `outbound` (Jarvis's trust-boundary flags for destructive/egress actions -
# not meaningful for this project's tools, which only touch an ephemeral
# sandbox and the model's own diff output).

import inspect
from typing import Callable, Dict


class Tool:
    """A single callable tool plus the JSON schema the model needs to call it."""

    def __init__(self, func: Callable, name: str, description: str, parameters: dict):
        self.func = func
        self.name = name
        self.description = description
        self.parameters = parameters

    def schema(self) -> dict:
        """Return the OpenAI/Ollama-compatible function-calling schema."""
        return {
            "type": "function",
            "function": {
                "name": self.name,
                "description": self.description,
                "parameters": self.parameters,
            },
        }


TOOL_REGISTRY: Dict[str, Tool] = {}


def register_tool(
    func: Callable,
    name: str = None,
    description: str = None,
    parameters: dict = None,
) -> Tool:
    """Register a tool. Can be used directly or as a decorator factory."""
    name = name or func.__name__
    description = description or (inspect.getdoc(func) or "").split("\n")[0]
    parameters = parameters or {"type": "object", "properties": {}}
    tool = Tool(func, name, description, parameters)
    TOOL_REGISTRY[name] = tool
    return tool
