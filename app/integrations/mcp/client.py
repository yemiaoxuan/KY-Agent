from __future__ import annotations

import asyncio
import os
from pathlib import Path
from typing import Any

from mcp import ClientSession
from mcp.client.stdio import StdioServerParameters, stdio_client

from app.core.config import get_settings
from app.services.runtime.runtime_config_service import load_runtime_config


def _coerce_content_item(item: Any) -> Any:
    if hasattr(item, "text"):
        return item.text
    if hasattr(item, "model_dump"):
        return item.model_dump(mode="json")
    return str(item)


async def call_local_mcp_tool(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    settings = get_settings()
    runtime_config = load_runtime_config()
    server_config = next((server for server in runtime_config.mcp_servers if server.enabled), None)
    if server_config is None or not settings.mcp_local_server_enabled:
        return {"ok": False, "error": "local MCP server is disabled"}

    project_root = Path(__file__).resolve().parents[3]
    command_path = Path(server_config.command)
    if not command_path.is_absolute():
        command_path = project_root / server_config.command
    args = []
    for arg in server_config.args:
        arg_path = Path(arg)
        if arg_path.suffix == ".py" and not arg_path.is_absolute():
            args.append(str(project_root / arg))
        else:
            args.append(arg)
    cwd = Path(server_config.cwd)
    if not cwd.is_absolute():
        cwd = project_root / server_config.cwd
    server = StdioServerParameters(
        command=str(command_path),
        args=args,
        cwd=cwd,
        env=os.environ.copy(),
    )

    async with stdio_client(server) as (read_stream, write_stream):
        async with ClientSession(read_stream, write_stream) as session:
            await session.initialize()
            result = await session.call_tool(tool_name, arguments=arguments)
            structured = getattr(result, "structuredContent", None)
            content = [_coerce_content_item(item) for item in getattr(result, "content", [])]
            payload: dict[str, Any] = {
                "ok": not getattr(result, "isError", False),
                "tool_name": tool_name,
                "content": content,
            }
            if structured is not None:
                payload["structured_content"] = structured
            return payload


def call_local_mcp_tool_sync(tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
    return asyncio.run(call_local_mcp_tool(tool_name, arguments))
