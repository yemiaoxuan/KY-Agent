import re
from uuid import UUID

from pydantic import BaseModel, Field, field_validator

TOPIC_NAME_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_-]{0,99}$")


class TopicConfig(BaseModel):
    name: str
    display_name: str
    query: str
    arxiv_categories: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    max_results: int = 30
    report_top_k: int = 10
    enabled: bool = True
    report_prompt_hint: str | None = None


class TopicConfigFile(BaseModel):
    topics: list[TopicConfig] = Field(default_factory=list)


class TopicRead(BaseModel):
    id: UUID | None = None
    name: str
    display_name: str
    query: str
    arxiv_categories: list[str]
    include_keywords: list[str]
    exclude_keywords: list[str]
    max_results: int
    report_top_k: int
    enabled: bool
    report_prompt_hint: str | None = None

    model_config = {"from_attributes": True}


class TopicCreate(BaseModel):
    name: str
    display_name: str
    query: str
    arxiv_categories: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    max_results: int = 30
    report_top_k: int = 10
    enabled: bool = True
    report_prompt_hint: str | None = None

    @field_validator("name")
    @classmethod
    def validate_name(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("主题标识不能为空")
        if not TOPIC_NAME_PATTERN.fullmatch(normalized):
            raise ValueError("主题标识只能包含字母、数字、下划线和中划线，且必须以字母或数字开头")
        return normalized

    @field_validator("display_name", "query")
    @classmethod
    def validate_required_text(cls, value: str) -> str:
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized

    @field_validator("report_prompt_hint")
    @classmethod
    def normalize_optional_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None


class TopicUpdate(BaseModel):
    display_name: str | None = None
    query: str | None = None
    arxiv_categories: list[str] | None = None
    include_keywords: list[str] | None = None
    exclude_keywords: list[str] | None = None
    max_results: int | None = None
    report_top_k: int | None = None
    enabled: bool | None = None
    report_prompt_hint: str | None = None

    @field_validator("display_name", "query")
    @classmethod
    def validate_optional_required_text(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        if not normalized:
            raise ValueError("该字段不能为空")
        return normalized

    @field_validator("report_prompt_hint")
    @classmethod
    def normalize_optional_prompt(cls, value: str | None) -> str | None:
        if value is None:
            return None
        normalized = value.strip()
        return normalized or None
