"""Tests for agentic AI tools — registry, OpenAI/Anthropic export, execute dispatch."""

from __future__ import annotations

import pytest

from binance_book.client import BinanceBook
from binance_book.tools.registry import ToolRegistry
from binance_book.tools.openai import to_openai_tools
from binance_book.tools.anthropic import to_anthropic_tools


@pytest.fixture
def book():
    return BinanceBook()


@pytest.fixture
def registry(book):
    return ToolRegistry(book)


class TestToolRegistry:
    def test_discovers_public_methods(self, registry):
        names = registry.tool_names
        assert len(names) > 0
        assert "ob_snapshot" in names
        assert "ob_snapshot_wide" in names
        assert "ob_snapshot_flat" in names
        assert "imbalance" in names
        assert "spread" in names
        assert "trades" in names
        assert "klines" in names
        assert "quote" in names
        assert "schema" in names

    def test_excludes_private_methods(self, registry):
        for name in registry.tool_names:
            assert not name.startswith("_")

    def test_tool_has_description(self, registry):
        tool = registry.get("ob_snapshot_wide")
        assert tool is not None
        assert len(tool.description) > 10

    def test_tool_has_parameters(self, registry):
        tool = registry.get("ob_snapshot_wide")
        assert tool is not None
        assert tool.parameters["type"] == "object"
        assert "properties" in tool.parameters
        assert "symbol" in tool.parameters["properties"]

    def test_required_params(self, registry):
        tool = registry.get("imbalance")
        assert tool is not None
        assert "required" in tool.parameters
        assert "symbol" in tool.parameters["required"]

    def test_optional_params_have_defaults(self, registry):
        tool = registry.get("ob_snapshot_wide")
        assert tool is not None
        props = tool.parameters["properties"]
        if "max_levels" in props:
            assert "default" in props["max_levels"]

    def test_get_nonexistent(self, registry):
        assert registry.get("nonexistent_method") is None

    def test_get_all(self, registry):
        all_tools = registry.get_all()
        assert isinstance(all_tools, list)
        assert len(all_tools) == len(registry.tool_names)

    def test_to_dict(self, registry):
        tool = registry.get("spread")
        assert tool is not None
        d = tool.to_dict()
        assert "name" in d
        assert "description" in d
        assert "parameters" in d
        assert d["name"] == "spread"


class TestOpenAIExport:
    def test_format(self, registry):
        tools = to_openai_tools(registry)
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tool_structure(self, registry):
        tools = to_openai_tools(registry)
        for tool in tools:
            assert tool["type"] == "function"
            assert "function" in tool
            fn = tool["function"]
            assert "name" in fn
            assert "description" in fn
            assert "parameters" in fn
            assert fn["parameters"]["type"] == "object"

    def test_specific_tool(self, registry):
        tools = to_openai_tools(registry)
        ob_tools = [t for t in tools if t["function"]["name"] == "ob_snapshot_wide"]
        assert len(ob_tools) == 1
        fn = ob_tools[0]["function"]
        assert "symbol" in fn["parameters"]["properties"]


class TestAnthropicExport:
    def test_format(self, registry):
        tools = to_anthropic_tools(registry)
        assert isinstance(tools, list)
        assert len(tools) > 0

    def test_tool_structure(self, registry):
        tools = to_anthropic_tools(registry)
        for tool in tools:
            assert "name" in tool
            assert "description" in tool
            assert "input_schema" in tool
            assert tool["input_schema"]["type"] == "object"

    def test_no_type_field(self, registry):
        """Anthropic format should NOT have 'type': 'function' wrapper."""
        tools = to_anthropic_tools(registry)
        for tool in tools:
            assert "type" not in tool or tool.get("type") != "function"


class TestBookToolsMethod:
    def test_openai_format(self, book):
        tools = book.tools(format="openai")
        assert isinstance(tools, list)
        assert tools[0]["type"] == "function"

    def test_anthropic_format(self, book):
        tools = book.tools(format="anthropic")
        assert isinstance(tools, list)
        assert "input_schema" in tools[0]

    def test_raw_format(self, book):
        tools = book.tools(format="raw")
        assert isinstance(tools, list)
        assert "name" in tools[0]
        assert "parameters" in tools[0]


class TestExecuteDispatch:
    def test_schema_dispatch(self, book):
        result = book.execute("schema", {"data_type": "trade"})
        assert isinstance(result, dict)
        assert "PRICE" in result

    def test_unknown_tool(self, book):
        with pytest.raises(ValueError, match="Unknown tool"):
            book.execute("nonexistent_tool", {})
