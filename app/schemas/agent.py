from typing import Literal

from pydantic import BaseModel, Field


class AgentAttachment(BaseModel):
    id: str
    title: str
    description: str | None = None
    file_path: str
    file_type: str
    visibility: str = "public"
    source: str = "history"


class AgentChatMessage(BaseModel):
    role: Literal["system", "user", "assistant"]
    content: str


class AgentChatRequest(BaseModel):
    messages: list[AgentChatMessage] = Field(default_factory=list)
    selected_topics: list[str] = Field(default_factory=list)
    attachment_context: list[AgentAttachment] = Field(default_factory=list)
    max_steps: int = Field(default=6, ge=1, le=12)
    search_limit: int = Field(default=5, ge=1, le=20)
    tool_limit: int = Field(default=10, ge=1, le=20)


class AgentSSEEvent(BaseModel):
    event: str
    data: dict
