from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any
from uuid import uuid4

from app.core.config import get_settings


def _ensure_jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, dict):
        return {str(key): _ensure_jsonable(item) for key, item in value.items()}
    if isinstance(value, list | tuple | set):
        return [_ensure_jsonable(item) for item in value]
    if isinstance(value, str | int | float | bool) or value is None:
        return value
    return repr(value)


def get_tool_log_dir() -> Path:
    settings = get_settings()
    path = settings.storage_dir / "tool_logs"
    path.mkdir(parents=True, exist_ok=True)
    return path


def write_tool_call_log(
    *,
    tool_name: str,
    args: dict[str, Any] | None = None,
    result: Any = None,
    error: str | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
    log_path = get_tool_log_dir() / f"{timestamp}-{tool_name}-{uuid4().hex[:8]}.json"
    payload = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": tool_name,
        "args": _ensure_jsonable(args or {}),
        "result": _ensure_jsonable(result),
        "error": error,
        "extra": _ensure_jsonable(extra or {}),
    }
    log_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return log_path
