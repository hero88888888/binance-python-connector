"""Export tool definitions in OpenAI function-calling format."""

from __future__ import annotations

from typing import Any

from binance_book.tools.registry import ToolRegistry


def to_openai_tools(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Convert all registered tools to OpenAI function-calling format.

    Returns a list of tool definitions compatible with the OpenAI Chat
    Completions API ``tools`` parameter.

    Parameters
    ----------
    registry : ToolRegistry
        The tool registry to export.

    Returns
    -------
    list[dict]
        OpenAI-compatible tool definitions.

    Example output::

        [
            {
                "type": "function",
                "function": {
                    "name": "ob_snapshot",
                    "description": "Get orderbook snapshot ...",
                    "parameters": {
                        "type": "object",
                        "properties": { ... },
                        "required": ["symbol"]
                    }
                }
            },
            ...
        ]
    """
    tools: list[dict[str, Any]] = []
    for defn in registry.get_all():
        tools.append({
            "type": "function",
            "function": {
                "name": defn.name,
                "description": defn.description,
                "parameters": defn.parameters,
            },
        })
    return tools
