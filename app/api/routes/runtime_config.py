from __future__ import annotations

from fastapi import APIRouter, Request

from app.schemas.runtime_config import RuntimeConfig
from app.services.runtime.runtime_config_service import load_runtime_config, save_runtime_config

router = APIRouter(prefix="/runtime-config", tags=["runtime-config"])


@router.get("", response_model=RuntimeConfig)
def get_runtime_config() -> RuntimeConfig:
    return load_runtime_config()


@router.post("", response_model=RuntimeConfig)
def update_runtime_config(request: RuntimeConfig, raw_request: Request) -> RuntimeConfig:
    config = save_runtime_config(request)
    app = raw_request.app
    scheduler = getattr(app.state, "scheduler", None)
    if scheduler is not None:
        from app.core.scheduler import reload_scheduler

        reload_scheduler(scheduler)
    return config
