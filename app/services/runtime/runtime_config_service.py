from __future__ import annotations

import json
from pathlib import Path

from app.core.config import get_settings
from app.schemas.runtime_config import RuntimeConfig, RuntimeModelOption


def _default_runtime_config() -> RuntimeConfig:
    settings = get_settings()
    return RuntimeConfig(
        daily_report_system_prompt_suffix="",
        enable_query_rewrite=True,
        selected_rewrite_model=settings.llm_model,
        selected_chat_model=settings.llm_model,
        selected_embedding_model=settings.embedding_model,
        chat_model_options=[
            RuntimeModelOption(id=settings.llm_model, label=settings.llm_model, kind="chat")
        ],
        embedding_model_options=[
            RuntimeModelOption(
                id=settings.embedding_model,
                label=settings.embedding_model,
                kind="embedding",
            )
        ],
        scheduler={
            "enabled": True,
            "daily_report_time": settings.daily_report_time,
            "send_email": True,
            "email_recipients": [],
            "topic_names": [],
        },
        mcp_servers=[
            {
                "enabled": settings.mcp_local_server_enabled,
                "name": "ky-local-tools",
                "transport": "stdio",
                "command": ".venv/bin/python",
                "args": ["app/integrations/mcp/local_server.py"],
                "cwd": ".",
            }
        ],
        sam={
            "enabled": False,
            "python_executable": "",
            "project_root": "/mnt/hdd/cjt/3dgs/SAM3Test",
            "checkpoint_path": "/mnt/hdd/cjt/3dgs/SAM3Test/checkpoints/sam3.pt",
            "bpe_path": None,
            "output_dir": "./storage/sam_outputs",
            "device": "cuda",
            "confidence_threshold": 0.5,
            "top_k": 5,
            "timeout_seconds": 600,
        },
    )


def get_runtime_config_path() -> Path:
    settings = get_settings()
    settings.runtime_config_path.parent.mkdir(parents=True, exist_ok=True)
    return settings.runtime_config_path


def load_runtime_config() -> RuntimeConfig:
    path = get_runtime_config_path()
    if not path.exists():
        config = _default_runtime_config()
        save_runtime_config(config)
        return config
    payload = json.loads(path.read_text(encoding="utf-8"))
    return RuntimeConfig.model_validate(payload)


def save_runtime_config(config: RuntimeConfig) -> RuntimeConfig:
    path = get_runtime_config_path()
    path.write_text(
        json.dumps(config.model_dump(mode="json"), ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    return config


def update_runtime_config(request: RuntimeConfig) -> RuntimeConfig:
    existing = load_runtime_config()
    selected_chat_model = request.selected_chat_model or existing.selected_chat_model
    selected_embedding_model = (
        request.selected_embedding_model or existing.selected_embedding_model
    )
    merged = request.model_copy(
        update={
            "selected_chat_model": selected_chat_model,
            "selected_embedding_model": selected_embedding_model,
        }
    )
    return save_runtime_config(merged)
