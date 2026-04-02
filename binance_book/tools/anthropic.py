"""Export tool definitions in Anthropic tool_use format."""

from __future__ import annotations

from typing import Any

from binance_book.tools.registry import ToolRegistry


def to_anthropic_tools(registry: ToolRegistry) -> list[dict[str, Any]]:
    """Convert all registered tools to Anthropic tool_use format.

    Returns a list of tool definitions compatible with the Anthropic Messages
    API ``tools`` parameter.

    Parameters
    ----------
    registry : ToolRegistry
        The tool registry to export.

    Returns
    -------
    list[dict]
        Anthropic-compatible tool definitions.

    Example output::

        [
            {
                "name": "ob_snapshot",
                "description": "Get orderbook snapshot ...",
                "input_schema": {
                    "type": "object",
                    "properties": { ... },
                    "required": ["symbol"]
                }
            },
            ...
        ]
    """
    tools: list[dict[str, Any]] = []
    for defn in registry.get_all():
        tools.append({
            "name": defn.name,
            "description": defn.description,
            "input_schema": defn.parameters,
        })
    return tools
