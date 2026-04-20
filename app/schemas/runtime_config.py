from __future__ import annotations

from pydantic import BaseModel, Field


class RuntimeModelOption(BaseModel):
    id: str
    label: str
    kind: str = "chat"
    enabled: bool = True


class RuntimeMCPServerConfig(BaseModel):
    enabled: bool = True
    name: str = "ky-local-tools"
    transport: str = "stdio"
    command: str = ".venv/bin/python"
    args: list[str] = Field(default_factory=lambda: ["app/integrations/mcp/local_server.py"])
    cwd: str = "."


class RuntimeSchedulerConfig(BaseModel):
    enabled: bool = True
    daily_report_time: str = "08:00"
    send_email: bool = True
    email_recipients: list[str] = Field(default_factory=list)
    topic_names: list[str] = Field(default_factory=list)


class RuntimeSamConfig(BaseModel):
    enabled: bool = False
    python_executable: str = ""
    project_root: str = "/mnt/hdd/cjt/3dgs/SAM3Test"
    checkpoint_path: str = "/mnt/hdd/cjt/3dgs/SAM3Test/checkpoints/sam3.pt"
    bpe_path: str | None = None
    output_dir: str = "./storage/sam_outputs"
    device: str = "cuda"
    confidence_threshold: float = Field(default=0.5, ge=0.0, le=1.0)
    top_k: int = Field(default=5, ge=1, le=20)
    timeout_seconds: int = Field(default=600, ge=30, le=3600)


class RuntimeConfig(BaseModel):
    daily_report_system_prompt_suffix: str = ""
    enable_query_rewrite: bool = True
    selected_rewrite_model: str | None = None
    selected_chat_model: str | None = None
    selected_embedding_model: str | None = None
    chat_model_options: list[RuntimeModelOption] = Field(default_factory=list)
    embedding_model_options: list[RuntimeModelOption] = Field(default_factory=list)
    mcp_servers: list[RuntimeMCPServerConfig] = Field(
        default_factory=lambda: [RuntimeMCPServerConfig()]
    )
    scheduler: RuntimeSchedulerConfig = Field(default_factory=RuntimeSchedulerConfig)
    sam: RuntimeSamConfig = Field(default_factory=RuntimeSamConfig)
