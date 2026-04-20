from __future__ import annotations

import asyncio
import json
from collections.abc import AsyncIterator
from typing import Any

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage, ToolMessage
from langgraph.errors import GraphRecursionError
from sqlalchemy.orm import Session

from app.agents.chat_graph import (
    ROUTER_ROUTE_ORDER,
    TOOL_ROUTE_ORDER,
    _coerce_tool_result,
    build_agent_graph,
)
from app.agents.chat_prompts import (
    DEFAULT_SYSTEM_PROMPT,
    build_attachment_registry_context_block,
    build_selected_topics_context_block,
    build_upload_context_block,
)
from app.schemas.agent import AgentChatMessage, AgentChatRequest, AgentSSEEvent
from app.services.ai.query_rewrite_service import rewrite_agent_request


def _serialize_event(event: AgentSSEEvent) -> str:
    data = json.dumps(event.data, ensure_ascii=False)
    return f"event: {event.event}\ndata: {data}\n\n"


def _history_to_messages(history: list[AgentChatMessage]) -> list[BaseMessage]:
    messages: list[BaseMessage] = [SystemMessage(content=DEFAULT_SYSTEM_PROMPT)]
    for item in history:
        if item.role == "system":
            messages.append(SystemMessage(content=item.content))
        elif item.role == "assistant":
            messages.append(AIMessage(content=item.content))
        else:
            messages.append(HumanMessage(content=item.content))
    return messages


async def stream_agent_chat(
    db: Session,
    request: AgentChatRequest,
    uploaded_documents: list[dict[str, Any]] | None = None,
) -> AsyncIterator[str]:
    yield _serialize_event(AgentSSEEvent(event="started", data={"max_steps": request.max_steps}))

    rewritten = await asyncio.to_thread(
        rewrite_agent_request,
        request.messages,
        request.selected_topics,
    )
    yield _serialize_event(AgentSSEEvent(event="rewrite", data=rewritten))
    effective_messages = list(request.messages)
    if effective_messages and rewritten.get("rewritten_query"):
        effective_messages[-1] = AgentChatMessage(
            role=effective_messages[-1].role,
            content=str(rewritten["rewritten_query"]),
        )
    messages = _history_to_messages(effective_messages)
    if request.selected_topics:
        messages.append(HumanMessage(content=build_selected_topics_context_block(request.selected_topics)))
        yield _serialize_event(
            AgentSSEEvent(event="context", data={"selected_topics": request.selected_topics})
        )
    if request.attachment_context:
        registry_block = build_attachment_registry_context_block(request.attachment_context)
        messages.append(HumanMessage(content=registry_block))
        attachment_context = [item.model_dump(mode="json") for item in request.attachment_context]
        yield _serialize_event(
            AgentSSEEvent(
                event="context",
                data={"attachment_context": attachment_context},
            )
        )
    if uploaded_documents:
        messages.append(HumanMessage(content=build_upload_context_block(uploaded_documents)))
        yield _serialize_event(
            AgentSSEEvent(event="context", data={"uploaded_documents": uploaded_documents})
        )
    final_answer = ""

    graph = build_agent_graph(db)
    step = 0
    try:
        async for update in graph.astream(
            {
                "messages": messages,
                "search_limit": request.search_limit,
                "tool_limit": request.tool_limit,
            },
            stream_mode="updates",
            config={"recursion_limit": request.max_steps * 2 + 2},
        ):
            if "assistant" in update:
                step += 1
                yield _serialize_event(AgentSSEEvent(event="step", data={"step": step}))
                new_messages = update["assistant"].get("messages", [])
                for message in new_messages:
                    if not isinstance(message, AIMessage):
                        continue
                    content = getattr(message, "content", "")
                    if content:
                        final_answer = str(content)
                        yield _serialize_event(
                            AgentSSEEvent(
                                event="message",
                                data={"step": step, "content": final_answer},
                            )
                        )
                    for tool_call in getattr(message, "tool_calls", []) or []:
                        yield _serialize_event(
                            AgentSSEEvent(
                                event="tool_call",
                                data={
                                    "step": step,
                                    "name": tool_call["name"],
                                    "args": tool_call.get("args", {}),
                                },
                            )
                        )
            for node_name in (*ROUTER_ROUTE_ORDER, *TOOL_ROUTE_ORDER):
                if node_name not in update:
                    continue
                new_messages = update[node_name].get("messages", [])
                for message in new_messages:
                    if not isinstance(message, ToolMessage):
                        continue
                    try:
                        result = json.loads(str(message.content))
                    except Exception:
                        result = _coerce_tool_result(message.content)
                    yield _serialize_event(
                        AgentSSEEvent(
                            event="tool_result",
                            data={
                                "step": step,
                                "name": getattr(message, "name", None) or "",
                                "result": result,
                            },
                        )
                    )
    except GraphRecursionError:
        yield _serialize_event(
            AgentSSEEvent(
                event="error",
                data={
                    "message": "max steps reached before agent produced a final answer",
                    "answer": final_answer,
                    "step": step,
                },
            )
        )
        return
    except Exception as exc:
        db.rollback()
        yield _serialize_event(
            AgentSSEEvent(
                event="error",
                data={
                    "message": "agent execution failed",
                    "error": repr(exc),
                    "answer": final_answer,
                    "step": step,
                },
            )
        )
        return

    yield _serialize_event(
        AgentSSEEvent(event="done", data={"step": step, "answer": final_answer})
    )
