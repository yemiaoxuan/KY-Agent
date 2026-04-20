from __future__ import annotations

import json
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, ToolMessage
from langchain_core.tools import BaseTool
from langgraph.graph import END, StateGraph, add_messages
from sqlalchemy.orm import Session

from app.agents.toolkit import build_agent_tools
from app.services.ai.llm_service import get_llm

SEARCH_TOOL_NAMES = {"semantic_search_public_progress"}
ANSWER_TOOL_NAMES = {"rag_answer_public_progress"}
REPORT_TOOL_NAMES = {"list_reports", "get_report_content"}
EMAIL_TOOL_NAMES = {"send_markdown_email", "send_report_email", "send_plain_email"}
DAILY_TOOL_NAMES = {"run_daily_report"}
TOOL_ROUTE_ORDER = ("retrieve", "answer", "report", "email", "daily", "tools")
TOOL_ROUTE_BY_NAME = {
    **{name: "retrieve" for name in SEARCH_TOOL_NAMES},
    **{name: "answer" for name in ANSWER_TOOL_NAMES},
    **{name: "report" for name in REPORT_TOOL_NAMES},
    **{name: "email" for name in EMAIL_TOOL_NAMES},
    **{name: "daily" for name in DAILY_TOOL_NAMES},
}


class AgentGraphState(TypedDict, total=False):
    messages: Annotated[list[BaseMessage], add_messages]
    search_limit: int
    tool_limit: int


def _coerce_tool_result(result: object) -> object:
    if hasattr(result, "model_dump"):
        return result.model_dump(mode="json")
    return result


def _serialize_tool_result(result: object) -> str:
    payload = _coerce_tool_result(result)
    if isinstance(payload, str):
        return payload
    return json.dumps(payload, ensure_ascii=False)


def _tool_registry(tools: list[BaseTool]) -> dict[str, BaseTool]:
    return {tool.name: tool for tool in tools}


def _last_ai_message(state: AgentGraphState) -> AIMessage | None:
    for message in reversed(state.get("messages", [])):
        if isinstance(message, AIMessage):
            return message
    return None


def _pending_tool_calls(state: AgentGraphState) -> list[dict[str, Any]]:
    message = _last_ai_message(state)
    if message is None:
        return []
    tool_calls = list(getattr(message, "tool_calls", []) or [])
    tool_limit = state.get("tool_limit")
    if tool_limit is not None:
        return tool_calls[:tool_limit]
    return tool_calls


def _tool_route(tool_name: str) -> str:
    return TOOL_ROUTE_BY_NAME.get(tool_name, "tools")


def route_agent_actions(state: AgentGraphState) -> str | list[str]:
    tool_calls = _pending_tool_calls(state)
    if not tool_calls:
        return END
    routes = {_tool_route(str(tool_call.get("name", ""))) for tool_call in tool_calls}
    return [route for route in TOOL_ROUTE_ORDER if route in routes]


def _tool_calls_for_route(state: AgentGraphState, route: str) -> list[dict[str, Any]]:
    return [
        tool_call
        for tool_call in _pending_tool_calls(state)
        if _tool_route(str(tool_call.get("name", ""))) == route
    ]


def _prepared_tool_args(
    tool_name: str,
    args: dict[str, Any],
    state: AgentGraphState,
) -> dict[str, Any]:
    prepared = dict(args)
    if tool_name in SEARCH_TOOL_NAMES | ANSWER_TOOL_NAMES:
        limit = int(prepared.get("limit", state.get("search_limit", 5)))
        prepared["limit"] = min(limit, state.get("search_limit", limit))
    return prepared


def _build_tool_executor_node(
    tool_registry: dict[str, BaseTool],
    route: str,
    db: Session | None = None,
):
    def run_tools(state: AgentGraphState) -> dict[str, list[ToolMessage]]:
        messages: list[ToolMessage] = []
        for tool_call in _tool_calls_for_route(state, route):
            tool_name = str(tool_call.get("name", ""))
            tool = tool_registry.get(tool_name)
            if tool is None:
                result: object = {"ok": False, "message": f"tool not found: {tool_name}"}
                status = "error"
            else:
                args = _prepared_tool_args(
                    tool_name,
                    dict(tool_call.get("args", {}) or {}),
                    state,
                )
                try:
                    result = tool.invoke(args)
                    status = "success"
                except Exception as exc:
                    if db is not None:
                        db.rollback()
                    result = {"ok": False, "message": repr(exc), "tool_name": tool_name}
                    status = "error"

            messages.append(
                ToolMessage(
                    content=_serialize_tool_result(result),
                    name=tool_name,
                    tool_call_id=str(tool_call.get("id", tool_name)),
                    status=status,
                )
            )
        return {"messages": messages}

    return run_tools


def build_agent_graph(db: Session):
    tools = build_agent_tools(db)
    tool_registry = _tool_registry(tools)
    llm = get_llm().bind_tools(tools)

    def assistant(state: AgentGraphState) -> dict[str, list[BaseMessage]]:
        return {"messages": [llm.invoke(state["messages"])]}

    graph = StateGraph(AgentGraphState)
    graph.add_node("assistant", assistant)
    for route in TOOL_ROUTE_ORDER:
        graph.add_node(route, _build_tool_executor_node(tool_registry, route, db=db))
    graph.set_entry_point("assistant")
    graph.add_conditional_edges("assistant", route_agent_actions)
    for route in TOOL_ROUTE_ORDER:
        graph.add_edge(route, "assistant")
    return graph.compile()
