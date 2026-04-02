"""Model Context Protocol (MCP) server for binance-book.

Exposes all BinanceBook tools as an MCP-compatible JSON-RPC server that
any AI agent can discover and call over HTTP.
"""

from __future__ import annotations

import asyncio
import json
import logging
from typing import Any, Optional

from binance_book.tools.registry import ToolRegistry

logger = logging.getLogger(__name__)


class MCPServer:
    """A lightweight MCP server that exposes BinanceBook tools.

    Implements the MCP protocol subset needed for tool discovery and
    invocation: ``tools/list`` and ``tools/call``.

    Parameters
    ----------
    registry : ToolRegistry
        The tool registry to serve.
    name : str
        Server name advertised in MCP responses.
    """

    def __init__(self, registry: ToolRegistry, name: str = "binance-book") -> None:
        self._registry = registry
        self._name = name

    def handle_request(self, request: dict[str, Any]) -> dict[str, Any]:
        """Handle a single MCP JSON-RPC request.

        Parameters
        ----------
        request : dict
            JSON-RPC request with ``method`` and optional ``params``.

        Returns
        -------
        dict
            JSON-RPC response.
        """
        method = request.get("method", "")
        req_id = request.get("id")
        params = request.get("params", {})

        if method == "initialize":
            return self._response(req_id, {
                "protocolVersion": "2024-11-05",
                "capabilities": {"tools": {}},
                "serverInfo": {"name": self._name, "version": "0.1.0"},
            })

        elif method == "tools/list":
            tools = []
            for defn in self._registry.get_all():
                tools.append({
                    "name": defn.name,
                    "description": defn.description,
                    "inputSchema": defn.parameters,
                })
            return self._response(req_id, {"tools": tools})

        elif method == "tools/call":
            tool_name = params.get("name", "")
            arguments = params.get("arguments", {})
            try:
                result = self._registry.execute(tool_name, arguments)
                content = json.dumps(result, default=str)
                return self._response(req_id, {
                    "content": [{"type": "text", "text": content}],
                })
            except Exception as exc:
                return self._error(req_id, -32603, str(exc))

        else:
            return self._error(req_id, -32601, f"Method not found: {method}")

    def _response(self, req_id: Any, result: Any) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "result": result}

    def _error(self, req_id: Any, code: int, message: str) -> dict[str, Any]:
        return {"jsonrpc": "2.0", "id": req_id, "error": {"code": code, "message": message}}

    async def serve(self, host: str = "0.0.0.0", port: int = 8080) -> None:
        """Start the MCP server using aiohttp.

        Parameters
        ----------
        host : str
            Bind address. Default ``"0.0.0.0"``.
        port : int
            Port number. Default 8080.
        """
        try:
            from aiohttp import web
        except ImportError:
            raise ImportError("aiohttp is required for MCP server mode")

        app = web.Application()
        app.router.add_post("/mcp", self._handle_http)
        app.router.add_get("/health", self._handle_health)

        runner = web.AppRunner(app)
        await runner.setup()
        site = web.TCPSite(runner, host, port)
        logger.info("MCP server starting on %s:%d", host, port)
        await site.start()

        try:
            await asyncio.Event().wait()
        finally:
            await runner.cleanup()

    async def _handle_http(self, request: Any) -> Any:
        from aiohttp import web

        try:
            body = await request.json()
        except Exception:
            return web.json_response(
                self._error(None, -32700, "Parse error"), status=400
            )

        response = self.handle_request(body)
        return web.json_response(response)

    async def _handle_health(self, request: Any) -> Any:
        from aiohttp import web

        return web.json_response({
            "status": "ok",
            "server": self._name,
            "tools": len(self._registry.tool_names),
        })
