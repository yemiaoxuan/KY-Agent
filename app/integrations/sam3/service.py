from __future__ import annotations

import json
import os
import re
import subprocess
from datetime import datetime
from pathlib import Path
from uuid import uuid4

from langchain_core.output_parsers import StrOutputParser
from langchain_core.prompts import ChatPromptTemplate

from app.schemas.runtime_config import RuntimeSamConfig
from app.services.ai.llm_service import get_rewriter_llm
from app.services.observability.tool_logging_service import write_tool_call_log
from app.services.runtime.runtime_config_service import load_runtime_config


class SamIntegrationError(RuntimeError):
    pass


PROMPT_FALLBACK_KEYWORDS = [
    ("soccer ball", ["足球", "soccer ball", "football"]),
    ("basketball", ["篮球", "basketball"]),
    ("tennis ball", ["网球", "tennis ball"]),
    ("volleyball", ["排球", "volleyball"]),
    ("person", ["人", "人物", "行人", "person", "people", "human"]),
    ("car", ["汽车", "轿车", "车", "car", "vehicle"]),
    ("truck", ["卡车", "货车", "truck"]),
    ("bus", ["公交车", "巴士", "bus"]),
    ("bicycle", ["自行车", "单车", "bicycle", "bike"]),
    ("motorcycle", ["摩托车", "motorcycle"]),
    ("dog", ["狗", "dog"]),
    ("cat", ["猫", "cat"]),
]


def _slugify(value: str | None) -> str:
    text = (value or "").strip().lower()
    text = re.sub(r"[^a-z0-9\u4e00-\u9fff]+", "-", text)
    text = re.sub(r"-{2,}", "-", text).strip("-")
    return text or "sam-task"


def _resolve_runtime_config() -> RuntimeSamConfig:
    return load_runtime_config().sam


def _validate_runtime_config(config: RuntimeSamConfig) -> None:
    if not config.enabled:
        raise SamIntegrationError("SAM 功能未启用，请先在 runtime-config 中开启 sam.enabled。")
    if not config.python_executable:
        raise SamIntegrationError("SAM 未配置 python_executable。")

    python_path = Path(config.python_executable).expanduser()
    if not python_path.exists():
        raise SamIntegrationError(f"SAM Python 不存在: {python_path}")

    project_root = Path(config.project_root).expanduser()
    if not project_root.exists():
        raise SamIntegrationError(f"SAM 项目目录不存在: {project_root}")

    checkpoint_path = Path(config.checkpoint_path).expanduser()
    if not checkpoint_path.exists():
        raise SamIntegrationError(f"SAM checkpoint 不存在: {checkpoint_path}")

    if config.bpe_path:
        bpe_path = Path(config.bpe_path).expanduser()
        if not bpe_path.exists():
            raise SamIntegrationError(f"SAM BPE 文件不存在: {bpe_path}")


def _write_sam_run_log(run_dir: Path, payload: dict) -> None:
    run_dir.mkdir(parents=True, exist_ok=True)
    log_path = run_dir / "sam_call_log.json"
    log_path.write_text(
        json.dumps(payload, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def _build_prompt_candidates(instruction: str) -> list[str]:
    stripped = instruction.strip()
    english_prompt = optimize_sam_instruction_to_english(stripped)
    candidates: list[str] = [english_prompt]
    lowered = stripped.lower()
    for fallback_prompt, keywords in PROMPT_FALLBACK_KEYWORDS:
        if any(keyword in stripped or keyword in lowered for keyword in keywords):
            candidates.append(fallback_prompt)
    lowered_english = english_prompt.lower()
    if "transparent background" in lowered or "透明背景" in stripped:
        candidates.extend(["foreground object", "main object"])
    if "segment" in lowered_english and "soccer ball" in lowered_english:
        candidates.append("soccer ball")

    unique_candidates: list[str] = []
    seen: set[str] = set()
    for candidate in candidates:
        candidate = candidate.strip()
        if not candidate or candidate in seen:
            continue
        seen.add(candidate)
        unique_candidates.append(candidate)
    return unique_candidates


def optimize_sam_instruction_to_english(instruction: str) -> str:
    stripped = instruction.strip()
    if not stripped:
        return ""
    if stripped.isascii():
        return stripped

    lowered = stripped.lower()
    for fallback_prompt, keywords in PROMPT_FALLBACK_KEYWORDS:
        if any(keyword in stripped or keyword in lowered for keyword in keywords):
            return fallback_prompt

    runtime_config = load_runtime_config()
    if not runtime_config.enable_query_rewrite:
        return "main object"

    prompt = ChatPromptTemplate.from_messages(
        [
            (
                "system",
                "You convert image segmentation instructions into a short English prompt for "
                "SAM-like models. Output only the final English prompt. Keep it short, "
                "concrete, object-centric, and noun-focused. Avoid explanations, "
                "punctuation-heavy sentences, and non-English text.",
            ),
            (
                "human",
                "Original instruction:\n{instruction}\n\n"
                "Return only the optimized English segmentation prompt.",
            ),
        ]
    )
    chain = prompt | get_rewriter_llm() | StrOutputParser()
    try:
        raw = chain.invoke({"instruction": stripped}).strip()
        cleaned = raw.removeprefix("```").removesuffix("```").strip().strip('"').strip("'")
        if cleaned:
            return cleaned
    except Exception:
        pass
    return "main object"


def _run_sam_command(
    *,
    command: list[str],
    cwd: str,
    env: dict[str, str],
    timeout_seconds: int,
) -> tuple[subprocess.CompletedProcess[str], dict | None, str, str]:
    completed = subprocess.run(
        command,
        cwd=cwd,
        capture_output=True,
        text=True,
        timeout=timeout_seconds,
        check=False,
        env=env,
    )
    stdout_text = (completed.stdout or "").strip()
    stderr_text = (completed.stderr or "").strip()
    payload = None
    if stdout_text:
        for line in reversed(stdout_text.splitlines()):
            line = line.strip()
            if not line:
                continue
            try:
                payload = json.loads(line)
                break
            except json.JSONDecodeError:
                continue
    return completed, payload, stdout_text, stderr_text


def segment_image_with_sam(
    *,
    image_path: str,
    instruction: str,
    output_name: str | None = None,
    confidence_threshold: float | None = None,
    top_k: int | None = None,
) -> dict:
    config = _resolve_runtime_config()
    _validate_runtime_config(config)

    source_image = Path(image_path).expanduser()
    if not source_image.exists():
        raise SamIntegrationError(f"图片不存在: {source_image}")
    if not instruction.strip():
        raise SamIntegrationError("instruction 不能为空。")

    output_root = Path(config.output_dir).expanduser()
    if not output_root.is_absolute():
        output_root = (Path.cwd() / output_root).resolve()
    output_root.mkdir(parents=True, exist_ok=True)

    run_name = (
        f"{datetime.now().strftime('%Y%m%d-%H%M%S')}-"
        f"{_slugify(output_name or instruction)}-{uuid4().hex[:8]}"
    )
    run_dir = output_root / run_name
    run_dir.mkdir(parents=True, exist_ok=True)

    runner_path = Path(__file__).with_name("runner.py").resolve()
    effective_threshold = confidence_threshold or config.confidence_threshold
    effective_top_k = top_k or config.top_k

    base_command = [
        str(Path(config.python_executable).expanduser()),
        str(runner_path),
        "--sam-project-root",
        str(Path(config.project_root).expanduser()),
        "--checkpoint",
        str(Path(config.checkpoint_path).expanduser()),
        "--image",
        str(source_image.resolve()),
        "--output-dir",
        str(run_dir),
        "--device",
        config.device,
        "--confidence-threshold",
        str(effective_threshold),
        "--top-k",
        str(effective_top_k),
    ]
    if config.bpe_path:
        base_command.extend(["--bpe-path", str(Path(config.bpe_path).expanduser())])

    env = os.environ.copy()
    completed = None
    prompt_candidates = _build_prompt_candidates(instruction)
    log_payload = {
        "timestamp": datetime.now().isoformat(),
        "tool_name": "segment_image_with_sam",
        "request": {
            "image_path": str(source_image.resolve()),
            "instruction": instruction,
            "optimized_instruction": prompt_candidates[0] if prompt_candidates else instruction,
            "output_name": output_name,
            "confidence_threshold": effective_threshold,
            "top_k": effective_top_k,
        },
        "runtime_config": {
            "python_executable": str(Path(config.python_executable).expanduser()),
            "project_root": str(Path(config.project_root).expanduser()),
            "checkpoint_path": str(Path(config.checkpoint_path).expanduser()),
            "bpe_path": str(Path(config.bpe_path).expanduser()) if config.bpe_path else None,
            "device": config.device,
            "timeout_seconds": config.timeout_seconds,
        },
        "prompt_candidates": prompt_candidates,
        "attempts": [],
    }
    try:
        payload = None
        stdout_text = ""
        stderr_text = ""
        for attempt_index, prompt_candidate in enumerate(prompt_candidates, start=1):
            command = list(base_command)
            command.extend(["--prompt", prompt_candidate])
            completed, payload, stdout_text, stderr_text = _run_sam_command(
                command=command,
                cwd=str(Path(config.project_root).expanduser()),
                env=env,
                timeout_seconds=config.timeout_seconds,
            )
            attempt_log = {
                "attempt_index": attempt_index,
                "prompt": prompt_candidate,
                "command": command,
                "returncode": completed.returncode,
                "stdout": stdout_text,
                "stderr": stderr_text,
                "parsed_payload": payload,
            }
            log_payload["attempts"].append(attempt_log)
            if completed.returncode != 0:
                break
            if isinstance(payload, dict) and int(payload.get("detection_count") or 0) > 0:
                break
    except subprocess.TimeoutExpired as exc:
        log_payload["timeout"] = True
        log_payload["error"] = f"SAM 推理超时，超过 {config.timeout_seconds} 秒。"
        _write_sam_run_log(run_dir, log_payload)
        write_tool_call_log(
            tool_name="segment_image_with_sam",
            args={
                "image_path": str(source_image.resolve()),
                "instruction": instruction,
                "output_name": output_name,
                "confidence_threshold": effective_threshold,
                "top_k": effective_top_k,
            },
            error=log_payload["error"],
            extra={"run_dir": str(run_dir.resolve())},
        )
        raise SamIntegrationError(
            f"SAM 推理超时，超过 {config.timeout_seconds} 秒。"
        ) from exc

    log_payload["returncode"] = completed.returncode
    log_payload["stdout"] = stdout_text
    log_payload["stderr"] = stderr_text
    log_payload["parsed_payload"] = payload

    if completed.returncode != 0:
        if isinstance(payload, dict) and payload.get("error"):
            log_payload["error"] = str(payload["error"])
            _write_sam_run_log(run_dir, log_payload)
            write_tool_call_log(
                tool_name="segment_image_with_sam",
                args={
                    "image_path": str(source_image.resolve()),
                    "instruction": instruction,
                    "output_name": output_name,
                    "confidence_threshold": effective_threshold,
                    "top_k": effective_top_k,
                },
                error=log_payload["error"],
                result=payload,
                extra={"run_dir": str(run_dir.resolve())},
            )
            raise SamIntegrationError(str(payload["error"]))
        detail = stderr_text or stdout_text or f"return code {completed.returncode}"
        log_payload["error"] = f"SAM 调用失败: {detail}"
        _write_sam_run_log(run_dir, log_payload)
        write_tool_call_log(
            tool_name="segment_image_with_sam",
            args={
                "image_path": str(source_image.resolve()),
                "instruction": instruction,
                "output_name": output_name,
                "confidence_threshold": effective_threshold,
                "top_k": effective_top_k,
            },
            error=log_payload["error"],
            extra={"run_dir": str(run_dir.resolve())},
        )
        raise SamIntegrationError(f"SAM 调用失败: {detail}")

    if not isinstance(payload, dict):
        log_payload["error"] = "SAM 返回结果不是有效 JSON。"
        _write_sam_run_log(run_dir, log_payload)
        write_tool_call_log(
            tool_name="segment_image_with_sam",
            args={
                "image_path": str(source_image.resolve()),
                "instruction": instruction,
                "output_name": output_name,
                "confidence_threshold": effective_threshold,
                "top_k": effective_top_k,
            },
            error=log_payload["error"],
            extra={"run_dir": str(run_dir.resolve())},
        )
        raise SamIntegrationError("SAM 返回结果不是有效 JSON。")

    if int(payload.get("detection_count") or 0) == 0 and len(prompt_candidates) > 1:
        log_payload["warning"] = "原始 prompt 未命中，已尝试 fallback prompts，但仍未检测到目标。"

    log_payload["result"] = payload
    _write_sam_run_log(run_dir, log_payload)
    write_tool_call_log(
        tool_name="segment_image_with_sam",
        args={
            "image_path": str(source_image.resolve()),
            "instruction": instruction,
            "output_name": output_name,
            "confidence_threshold": effective_threshold,
            "top_k": effective_top_k,
        },
        result=payload,
        extra={"run_dir": str(run_dir.resolve())},
    )
    return payload
