from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.chat_graph import (
    AGENT_TOOL_PROFILES,
    ALL_SPECIALIST_TOOL_NAMES,
    _build_router_delegate_executor_node,
    _build_tool_executor_node,
    _prepared_tool_args,
    _tool_registry,
    _tools_for_profile,
    build_delegate_tools,
    route_agent_actions,
    route_router_actions,
)


def test_route_agent_actions_returns_end_when_no_tool_calls() -> None:
    state = {"messages": [AIMessage(content="plain answer")]}

    assert route_agent_actions(state) == "__end__"


def test_route_router_actions_only_routes_delegate_tools() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "1",
                        "name": "delegate_to_research_agent",
                        "args": {"task": "search"},
                    }
                ],
            )
        ]
    }

    assert route_router_actions(state) == ["delegate"]


def test_route_agent_actions_splits_tools_into_specialized_nodes() -> None:
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {"id": "1", "name": "semantic_search_public_progress", "args": {"query": "a"}},
                    {
                        "id": "2",
                        "name": "send_plain_email",
                        "args": {"subject": "s", "plain_text": "x"},
                    },
                    {
                        "id": "3",
                        "name": "segment_image_with_sam",
                        "args": {"image_path": "/tmp/x", "instruction": "seg"},
                    },
                ],
            )
        ]
    }

    assert route_agent_actions(state) == ["retrieve", "email", "tools"]


def test_prepared_tool_args_caps_retrieval_limit() -> None:
    state = {"search_limit": 3}

    prepared = _prepared_tool_args(
        "semantic_search_public_progress",
        {"query": "test", "limit": 10},
        state,
    )

    assert prepared["limit"] == 3


def test_tool_executor_runs_only_matching_route() -> None:
    captured: list[dict] = []

    def search_tool(query: str, limit: int = 5) -> dict:
        captured.append({"query": query, "limit": limit})
        return {"ok": True, "query": query, "limit": limit}

    registry = {
        "semantic_search_public_progress": StructuredTool.from_function(
            search_tool,
            name="semantic_search_public_progress",
            description="search",
        )
    }
    node = _build_tool_executor_node(registry, "retrieve")
    state = {
        "search_limit": 2,
        "tool_limit": 5,
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tool-1",
                        "name": "semantic_search_public_progress",
                        "args": {"query": "abc", "limit": 9},
                    }
                ],
            )
        ],
    }

    output = node(state)

    assert captured == [{"query": "abc", "limit": 2}]
    assert len(output["messages"]) == 1
    assert output["messages"][0].name == "semantic_search_public_progress"


def test_tool_executor_rolls_back_db_session_on_tool_error() -> None:
    class FakeDb:
        def __init__(self) -> None:
            self.rollback_called = False

        def rollback(self) -> None:
            self.rollback_called = True

    def failing_tool(query: str) -> dict:
        raise RuntimeError(f"failed: {query}")

    db = FakeDb()
    registry = {
        "semantic_search_public_progress": StructuredTool.from_function(
            failing_tool,
            name="semantic_search_public_progress",
            description="search",
        )
    }
    node = _build_tool_executor_node(registry, "retrieve", db=db)
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "tool-1",
                        "name": "semantic_search_public_progress",
                        "args": {"query": "abc"},
                    }
                ],
            )
        ],
    }

    output = node(state)

    assert db.rollback_called
    assert output["messages"][0].status == "error"


def test_specialist_profiles_cover_all_business_tools() -> None:
    covered: set[str] = set()
    for profile in AGENT_TOOL_PROFILES:
        covered.update(profile.tool_names)

    assert ALL_SPECIALIST_TOOL_NAMES <= covered


def test_tools_for_profile_filters_to_profile_tool_names() -> None:
    def search_tool(query: str) -> dict:
        return {"query": query}

    def email_tool(subject: str, plain_text: str) -> dict:
        return {"subject": subject, "plain_text": plain_text}

    registry = _tool_registry(
        [
            StructuredTool.from_function(
                search_tool,
                name="semantic_search_public_progress",
                description="search",
            ),
            StructuredTool.from_function(
                email_tool,
                name="send_plain_email",
                description="email",
            ),
        ]
    )
    research_profile = next(
        profile for profile in AGENT_TOOL_PROFILES if profile.name == "research"
    )

    tools = _tools_for_profile(registry, research_profile)

    assert [tool.name for tool in tools] == ["semantic_search_public_progress"]


def test_delegate_tools_expose_only_router_level_tools() -> None:
    registry = {}
    delegate_tools = build_delegate_tools(
        db=None,
        tool_registry=registry,
        state_getter=lambda: {},
    )

    names = {tool.name for tool in delegate_tools}

    assert names == {f"delegate_to_{profile.name}_agent" for profile in AGENT_TOOL_PROFILES}
    assert names.isdisjoint(ALL_SPECIALIST_TOOL_NAMES)


def test_router_delegate_executor_runs_delegate_tool() -> None:
    captured: list[dict] = []

    def delegate(task: str, context: str | None = None) -> dict:
        captured.append({"task": task, "context": context})
        return {"ok": True, "answer": task}

    registry = {
        "delegate_to_research_agent": StructuredTool.from_function(
            delegate,
            name="delegate_to_research_agent",
            description="delegate",
        )
    }
    node = _build_router_delegate_executor_node(registry)
    state = {
        "messages": [
            AIMessage(
                content="",
                tool_calls=[
                    {
                        "id": "delegate-1",
                        "name": "delegate_to_research_agent",
                        "args": {"task": "find papers", "context": "topic=agents"},
                    }
                ],
            )
        ]
    }

    output = node(state)

    assert captured == [{"task": "find papers", "context": "topic=agents"}]
    assert output["messages"][0].name == "delegate_to_research_agent"
    assert output["messages"][0].status == "success"
