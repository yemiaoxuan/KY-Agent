from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Annotated, Any, TypedDict

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langchain_core.tools import BaseTool, StructuredTool
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
ROUTER_ROUTE_ORDER = ("delegate",)
TOOL_ROUTE_BY_NAME = {
    **{name: "retrieve" for name in SEARCH_TOOL_NAMES},
    **{name: "answer" for name in ANSWER_TOOL_NAMES},
    **{name: "report" for name in REPORT_TOOL_NAMES},
    **{name: "email" for name in EMAIL_TOOL_NAMES},
    **{name: "daily" for name in DAILY_TOOL_NAMES},
}
ALL_SPECIALIST_TOOL_NAMES = (
    SEARCH_TOOL_NAMES
    | ANSWER_TOOL_NAMES
    | REPORT_TOOL_NAMES
    | EMAIL_TOOL_NAMES
    | DAILY_TOOL_NAMES
    | {
        "list_topics",
        "upload_research_note",
        "list_uploads",
        "mcp_get_current_time",
        "mcp_summarize_text_stats",
        "mcp_extract_keywords_local",
        "mcp_read_local_markdown_excerpt",
        "segment_image_with_sam",
    }
)

ROUTER_SYSTEM_PROMPT = """你是一级路由/规划 agent。

你的职责：
1. 判断用户请求应由哪个二级 agent 处理，并把必要目标、约束和上下文转交给它。
2. 你只能使用 delegate_to_*_agent 工具；不要直接调用科研检索、报告、邮件、上传、MCP 或图像工具。
3. 如果一个请求需要多个能力，按合理顺序委派给多个二级 agent，并基于返回结果综合回答。
4. 不要编造工具结果；二级 agent 结果为空或报错时要说明。
5. 简单闲聊或不需要工具的问题可以直接回答。"""

SPECIALIST_SYSTEM_PROMPT_TEMPLATE = """你是{display_name}二级 agent。

职责边界：
{responsibilities}

工具使用规则：
1. 你只能使用当前绑定给你的工具，不要声称可以调用其他工具。
2. 需要工具时主动调用工具，并基于工具结果给出简洁结论。
3. 工具报错或结果为空时明确说明。
4. 不要编造数据库、报告、上传文件或图像处理结果。"""


@dataclass(frozen=True)
class AgentToolProfile:
    name: str
    display_name: str
    tool_names: frozenset[str]
    responsibilities: str
    delegation_description: str


AGENT_TOOL_PROFILES: tuple[AgentToolProfile, ...] = (
    AgentToolProfile(
        name="research",
        display_name="科研检索与问答",
        tool_names=frozenset(
            {
                "list_topics",
                "semantic_search_public_progress",
                "rag_answer_public_progress",
                "upload_research_note",
                "list_uploads",
                "mcp_summarize_text_stats",
                "mcp_extract_keywords_local",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 列出研究主题、检索公共研究进展、基于 RAG 回答科研问题。\n"
            "- 上传/登记文本研究笔记，读取上传文档或本地 markdown 摘要。\n"
            "- 对文本做本地统计或关键词提取。"
        ),
        delegation_description=(
            "Delegate research search, RAG Q&A, topic listing, upload listing, "
            "research-note ingestion, local markdown reading, and text analysis tasks."
        ),
    ),
    AgentToolProfile(
        name="reporting",
        display_name="日报与报告",
        tool_names=frozenset(
            {
                "list_topics",
                "run_daily_report",
                "list_reports",
                "get_report_content",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 生成每日 arXiv 研究报告。\n"
            "- 列出、读取和总结已生成的日报内容。\n"
            "- 必要时读取报告 markdown 摘要。"
        ),
        delegation_description=(
            "Delegate daily arXiv report generation, report listing, report reading, "
            "and report summarization tasks."
        ),
    ),
    AgentToolProfile(
        name="communication",
        display_name="邮件通知",
        tool_names=frozenset(
            {
                "send_markdown_email",
                "send_report_email",
                "send_plain_email",
                "list_reports",
                "get_report_content",
            }
        ),
        responsibilities=(
            "- 发送 markdown、纯文本邮件或已有日报邮件。\n"
            "- 需要发送报告前可查询报告列表和报告内容。"
        ),
        delegation_description=(
            "Delegate email sending and report-email delivery tasks, including "
            "looking up report metadata/content when needed."
        ),
    ),
    AgentToolProfile(
        name="vision",
        display_name="图像分割",
        tool_names=frozenset({"segment_image_with_sam"}),
        responsibilities=(
            "- 对本地图片执行 SAM 目标分割、抠图、mask、框选、主体或区域提取。\n"
            "- 输入必须包含可用的本地图片路径和自然语言分割指令。"
        ),
        delegation_description=(
            "Delegate image segmentation, mask extraction, cutout, object/region "
            "selection, and bounding-box style vision tasks."
        ),
    ),
    AgentToolProfile(
        name="utility",
        display_name="通用本地工具",
        tool_names=frozenset(
            {
                "mcp_get_current_time",
                "mcp_summarize_text_stats",
                "mcp_extract_keywords_local",
                "mcp_read_local_markdown_excerpt",
            }
        ),
        responsibilities=(
            "- 获取当前时间。\n"
            "- 做轻量文本统计、关键词提取或读取本地 markdown 摘要。"
        ),
        delegation_description=(
            "Delegate lightweight local utility tasks such as current time, text "
            "statistics, keyword extraction, and markdown excerpt reading."
        ),
    ),
)


class AgentGraphState(TypedDict, total=False):
    # LangGraph 会把 messages 作为主状态通道累计追加，便于多轮工具调用后继续推理。
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


def _tools_for_profile(
    tool_registry: dict[str, BaseTool],
    profile: AgentToolProfile,
) -> list[BaseTool]:
    return [tool for name in sorted(profile.tool_names) if (tool := tool_registry.get(name))]


def _tool_names(tools: list[BaseTool]) -> set[str]:
    return {tool.name for tool in tools}


def _router_messages(messages: list[BaseMessage]) -> list[BaseMessage]:
    return [SystemMessage(content=ROUTER_SYSTEM_PROMPT), *messages]


def _specialist_messages(
    messages: list[BaseMessage],
    profile: AgentToolProfile,
    task: str,
    context: str | None = None,
) -> list[BaseMessage]:
    system_prompt = SPECIALIST_SYSTEM_PROMPT_TEMPLATE.format(
        display_name=profile.display_name,
        responsibilities=profile.responsibilities,
    )
    task_lines = [f"一级 agent 委派任务：{task}"]
    if context:
        task_lines.append(f"额外上下文：\n{context}")
    task_lines.append("请完成该任务，并返回可供一级 agent 直接综合给用户的结果。")
    return [
        SystemMessage(content=system_prompt),
        *messages,
        HumanMessage(content="\n\n".join(task_lines)),
    ]


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


def _router_tool_route(tool_name: str) -> str:
    if tool_name.startswith("delegate_to_") and tool_name.endswith("_agent"):
        return "delegate"
    return "delegate"


def route_agent_actions(state: AgentGraphState) -> str | list[str]:
    tool_calls = _pending_tool_calls(state)
    if not tool_calls:
        return END
    routes = {_tool_route(str(tool_call.get("name", ""))) for tool_call in tool_calls}
    return [route for route in TOOL_ROUTE_ORDER if route in routes]


def route_router_actions(state: AgentGraphState) -> str | list[str]:
    tool_calls = _pending_tool_calls(state)
    if not tool_calls:
        return END
    routes = {_router_tool_route(str(tool_call.get("name", ""))) for tool_call in tool_calls}
    return [route for route in ROUTER_ROUTE_ORDER if route in routes]


def _tool_calls_for_route(state: AgentGraphState, route: str) -> list[dict[str, Any]]:
    return [
        tool_call
        for tool_call in _pending_tool_calls(state)
        if _tool_route(str(tool_call.get("name", ""))) == route
    ]


def _router_tool_calls_for_route(state: AgentGraphState, route: str) -> list[dict[str, Any]]:
    return [
        tool_call
        for tool_call in _pending_tool_calls(state)
        if _router_tool_route(str(tool_call.get("name", ""))) == route
    ]


def _prepared_tool_args(
    tool_name: str,
    args: dict[str, Any],
    state: AgentGraphState,
) -> dict[str, Any]:
    prepared = dict(args)
    # 把检索类工具的 top-k 统一收口，避免模型自行放大查询规模。
    if tool_name in SEARCH_TOOL_NAMES | ANSWER_TOOL_NAMES:
        limit = int(prepared.get("limit", state.get("search_limit", 5)))
        prepared["limit"] = min(limit, state.get("search_limit", limit))
    return prepared


def _final_message_text(messages: list[BaseMessage]) -> str:
    for message in reversed(messages):
        if isinstance(message, AIMessage):
            content = getattr(message, "content", "")
            if content:
                return str(content)
    return ""


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
                    # 某个工具如果已经触发 DB 异常，需要先 rollback 才能继续当前会话里的后续工具。
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


def _build_router_delegate_executor_node(
    tool_registry: dict[str, BaseTool],
    db: Session | None = None,
):
    def run_tools(state: AgentGraphState) -> dict[str, list[ToolMessage]]:
        messages: list[ToolMessage] = []
        for tool_call in _router_tool_calls_for_route(state, "delegate"):
            tool_name = str(tool_call.get("name", ""))
            tool = tool_registry.get(tool_name)
            if tool is None:
                result: object = {"ok": False, "message": f"delegate tool not found: {tool_name}"}
                status = "error"
            else:
                try:
                    result = tool.invoke(dict(tool_call.get("args", {}) or {}))
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


def _build_specialist_graph(
    profile: AgentToolProfile,
    tools: list[BaseTool],
    db: Session | None = None,
):
    tool_registry = _tool_registry(tools)
    llm = get_llm().bind_tools(tools)

    def specialist(state: AgentGraphState) -> dict[str, list[BaseMessage]]:
        return {"messages": [llm.invoke(state["messages"])]}

    graph = StateGraph(AgentGraphState)
    graph.add_node(profile.name, specialist)
    for route in TOOL_ROUTE_ORDER:
        graph.add_node(route, _build_tool_executor_node(tool_registry, route, db=db))
    graph.set_entry_point(profile.name)
    graph.add_conditional_edges(profile.name, route_agent_actions)
    for route in TOOL_ROUTE_ORDER:
        graph.add_edge(route, profile.name)
    return graph.compile()


def _run_specialist_agent(
    profile: AgentToolProfile,
    tools: list[BaseTool],
    db: Session,
    parent_state: AgentGraphState,
    task: str,
    context: str | None = None,
) -> dict[str, Any]:
    if not tools:
        return {
            "ok": False,
            "agent": profile.name,
            "message": "specialist has no available tools",
        }

    graph = _build_specialist_graph(profile, tools, db=db)
    specialist_messages = _specialist_messages(
        list(parent_state.get("messages", [])),
        profile,
        task,
        context=context,
    )
    tool_limit = int(parent_state.get("tool_limit", 10))
    output = graph.invoke(
        {
            "messages": specialist_messages,
            "search_limit": parent_state.get("search_limit", 5),
            "tool_limit": tool_limit,
        },
        config={"recursion_limit": max(tool_limit * 2 + 4, 8)},
    )
    final_answer = _final_message_text(output.get("messages", []))
    return {
        "ok": bool(final_answer),
        "agent": profile.name,
        "answer": final_answer,
        "tool_names": sorted(_tool_names(tools)),
    }


def _build_delegate_tool(
    profile: AgentToolProfile,
    tools: list[BaseTool],
    db: Session,
    state_getter,
) -> StructuredTool:
    def delegate(task: str, context: str | None = None) -> dict[str, Any]:
        """Delegate a scoped task to a specialist agent."""
        return _run_specialist_agent(
            profile,
            tools,
            db,
            state_getter(),
            task,
            context=context,
        )

    return StructuredTool.from_function(
        delegate,
        name=f"delegate_to_{profile.name}_agent",
        description=profile.delegation_description,
    )


def build_delegate_tools(
    db: Session,
    tool_registry: dict[str, BaseTool],
    state_getter,
) -> list[BaseTool]:
    return [
        _build_delegate_tool(
            profile,
            _tools_for_profile(tool_registry, profile),
            db,
            state_getter,
        )
        for profile in AGENT_TOOL_PROFILES
    ]


def build_agent_graph(db: Session):
    business_tools = build_agent_tools(db)
    business_tool_registry = _tool_registry(business_tools)
    current_router_state: AgentGraphState = {}
    delegate_tools = build_delegate_tools(
        db,
        business_tool_registry,
        lambda: current_router_state,
    )
    delegate_tool_registry = _tool_registry(delegate_tools)
    # 一级 agent 只绑定委派工具；业务工具 schema 只暴露给对应二级 agent。
    llm = get_llm().bind_tools(delegate_tools)

    def assistant(state: AgentGraphState) -> dict[str, list[BaseMessage]]:
        nonlocal current_router_state
        current_router_state = state
        return {"messages": [llm.invoke(_router_messages(state["messages"]))]}

    graph = StateGraph(AgentGraphState)
    graph.add_node("assistant", assistant)
    graph.add_node(
        "delegate",
        _build_router_delegate_executor_node(delegate_tool_registry, db=db),
    )
    graph.set_entry_point("assistant")
    graph.add_conditional_edges("assistant", route_router_actions)
    graph.add_edge("delegate", "assistant")
    return graph.compile()
