import uvicorn
from fastapi import FastAPI

from app.api.routes import (
    agent,
    email,
    health,
    reports,
    runtime_config,
    search,
    topics,
    uploads,
    vision,
)
from app.core.config import get_settings
from app.core.logging import configure_logging
from app.core.scheduler import create_scheduler


def create_app() -> FastAPI:
    configure_logging()
    app = FastAPI(title="KY Research Agent", version="0.1.0")
    app.include_router(health.router)
    app.include_router(agent.router)
    app.include_router(email.router)
    app.include_router(runtime_config.router)
    app.include_router(topics.router)
    app.include_router(reports.router)
    app.include_router(uploads.router)
    app.include_router(search.router)
    app.include_router(vision.router)

    @app.on_event("startup")
    def startup() -> None:
        settings = get_settings()
        if settings.app_env != "test" and settings.scheduler_enabled:
            scheduler = create_scheduler()
            scheduler.start()
            app.state.scheduler = scheduler

    @app.on_event("shutdown")
    def shutdown() -> None:
        scheduler = getattr(app.state, "scheduler", None)
        if scheduler:
            scheduler.shutdown(wait=False)

    return app


app = create_app()


def run() -> None:
    settings = get_settings()
    uvicorn.run(
        "app.api.main:app",
        host=settings.app_host,
        port=settings.app_port,
        reload=settings.app_debug,
    )
