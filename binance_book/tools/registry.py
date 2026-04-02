"""Auto-discovers public methods on BinanceBook and generates JSON schema from type hints.

This is the core of the agentic AI layer. Every public method with a docstring
is registered as a callable tool with a JSON Schema describing its parameters.
"""

from __future__ import annotations

import inspect
import re
from typing import Any, Callable, Optional, get_type_hints


class ToolDefinition:
    """A single registered tool with its metadata and JSON schema."""

    def __init__(
        self,
        name: str,
        description: str,
        parameters: dict[str, Any],
        method: Callable,
    ) -> None:
        self.name = name
        self.description = description
        self.parameters = parameters
        self.method = method

    def to_dict(self) -> dict[str, Any]:
        """Export as a plain dict."""
        return {
            "name": self.name,
            "description": self.description,
            "parameters": self.parameters,
        }


class ToolRegistry:
    """Registry of all callable tools derived from BinanceBook methods.

    Introspects all public methods on a target object, parses their type
    hints and docstrings, and generates JSON Schema parameter definitions.
    Supports dispatch via ``execute(tool_name, arguments)``.

    Parameters
    ----------
    target : object
        The object whose public methods will be registered (typically
        a ``BinanceBook`` instance).
    """

    def __init__(self, target: Any) -> None:
        self._target = target
        self._tools: dict[str, ToolDefinition] = {}
        self._discover()

    def _discover(self) -> None:
        """Introspect target and register all eligible public methods."""
        for name in dir(self._target):
            if name.startswith("_"):
                continue
            attr = getattr(self._target, name, None)
            if not callable(attr) or not inspect.ismethod(attr):
                continue
            doc = inspect.getdoc(attr) or ""
            if not doc:
                continue

            sig = inspect.signature(attr)
            params_schema = _build_params_schema(attr, sig)
            description = _extract_summary(doc)

            self._tools[name] = ToolDefinition(
                name=name,
                description=description,
                parameters=params_schema,
                method=attr,
            )

    @property
    def tool_names(self) -> list[str]:
        """List of all registered tool names."""
        return list(self._tools.keys())

    def get(self, name: str) -> Optional[ToolDefinition]:
        """Get a tool definition by name."""
        return self._tools.get(name)

    def get_all(self) -> list[ToolDefinition]:
        """Get all registered tool definitions."""
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, Any]) -> Any:
        """Dispatch a tool call by name with the given arguments.

        Parameters
        ----------
        name : str
            Tool name (method name on BinanceBook).
        arguments : dict
            Keyword arguments to pass to the method.

        Returns
        -------
        Any
            The method's return value.

        Raises
        ------
        ValueError
            If the tool name is not registered.
        """
        tool = self._tools.get(name)
        if tool is None:
            raise ValueError(f"Unknown tool: {name!r}. Available: {self.tool_names}")
        return tool.method(**arguments)


# ---------------------------------------------------------------------------
# Schema generation helpers
# ---------------------------------------------------------------------------

_PYTHON_TO_JSON_TYPE: dict[str, str] = {
    "str": "string",
    "int": "integer",
    "float": "number",
    "bool": "boolean",
    "list": "array",
    "dict": "object",
    "None": "null",
    "NoneType": "null",
}


def _build_params_schema(method: Callable, sig: inspect.Signature) -> dict[str, Any]:
    """Build a JSON Schema object for a method's parameters."""
    properties: dict[str, Any] = {}
    required: list[str] = []

    try:
        hints = get_type_hints(method)
    except Exception:
        hints = {}

    param_docs = _parse_param_docs(inspect.getdoc(method) or "")

    for param_name, param in sig.parameters.items():
        if param_name in ("self", "cls"):
            continue

        prop: dict[str, Any] = {}

        hint = hints.get(param_name)
        json_type = _resolve_json_type(hint)
        if json_type:
            prop["type"] = json_type

        if param_name in param_docs:
            prop["description"] = param_docs[param_name]

        if param.default is not inspect.Parameter.empty:
            default = param.default
            if default is not None and not callable(default):
                prop["default"] = default
        else:
            required.append(param_name)

        properties[param_name] = prop

    schema: dict[str, Any] = {
        "type": "object",
        "properties": properties,
    }
    if required:
        schema["required"] = required
    return schema


def _resolve_json_type(hint: Any) -> Optional[str]:
    """Convert a Python type hint to a JSON Schema type string."""
    if hint is None:
        return None

    type_name = getattr(hint, "__name__", str(hint))

    for py_name, json_name in _PYTHON_TO_JSON_TYPE.items():
        if py_name in type_name:
            return json_name

    origin = getattr(hint, "__origin__", None)
    if origin is not None:
        origin_name = getattr(origin, "__name__", str(origin))
        if "list" in origin_name.lower():
            return "array"
        if "dict" in origin_name.lower():
            return "object"
        if "Union" in str(origin) or "Optional" in str(origin):
            args = getattr(hint, "__args__", ())
            for arg in args:
                if arg is type(None):
                    continue
                return _resolve_json_type(arg)

    if "Literal" in str(hint):
        return "string"

    return "string"


def _parse_param_docs(docstring: str) -> dict[str, str]:
    """Extract parameter descriptions from a NumPy-style docstring."""
    params: dict[str, str] = {}
    lines = docstring.split("\n")
    in_params = False
    current_param: Optional[str] = None
    current_desc: list[str] = []

    for line in lines:
        stripped = line.strip()
        if stripped in ("Parameters", "Parameters:"):
            in_params = True
            continue
        if stripped.startswith("---") and in_params:
            continue
        if in_params and stripped in ("Returns", "Returns:", "Raises", "Raises:", "Examples", "Examples:", "Yields", "Yields:", "Notes", "Notes:"):
            if current_param:
                params[current_param] = " ".join(current_desc).strip()
            break

        if in_params:
            match = re.match(r"^(\w+)\s*:", stripped)
            if match and not stripped.startswith("    "):
                if current_param:
                    params[current_param] = " ".join(current_desc).strip()
                current_param = match.group(1)
                current_desc = []
            elif current_param and stripped:
                current_desc.append(stripped)

    if current_param:
        params[current_param] = " ".join(current_desc).strip()

    return params


def _extract_summary(docstring: str) -> str:
    """Extract the first paragraph of a docstring as a summary."""
    lines = docstring.strip().split("\n")
    summary_lines: list[str] = []
    for line in lines:
        stripped = line.strip()
        if not stripped and summary_lines:
            break
        if stripped:
            summary_lines.append(stripped)
    return " ".join(summary_lines)
