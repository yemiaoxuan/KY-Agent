from langchain_core.messages import AIMessage
from langchain_core.tools import StructuredTool

from app.agents.chat_graph import (
    _build_tool_executor_node,
    _prepared_tool_args,
    route_agent_actions,
)


def test_route_agent_actions_returns_end_when_no_tool_calls() -> None:
    state = {"messages": [AIMessage(content="plain answer")]}

    assert route_agent_actions(state) == "__end__"


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
