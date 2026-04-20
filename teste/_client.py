from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from typing import Any

import requests

BASE_URL = os.getenv("KY_API_BASE", "http://127.0.0.1:8000").rstrip("/")
TIMEOUT = int(os.getenv("KY_API_TIMEOUT", "180"))


def print_section(title: str) -> None:
    print(f"\n=== {title} ===")


def fail(message: str, response: requests.Response | None = None) -> None:
    print(f"[FAIL] {message}")
    if response is not None:
        print(f"status={response.status_code}")
        try:
            print(json.dumps(response.json(), ensure_ascii=False, indent=2))
        except Exception:
            print(response.text)
    sys.exit(1)


def ok(message: str) -> None:
    print(f"[OK] {message}")


def get(path: str, **kwargs: Any) -> requests.Response:
    return requests.get(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def post(path: str, **kwargs: Any) -> requests.Response:
    return requests.post(f"{BASE_URL}{path}", timeout=TIMEOUT, **kwargs)


def ensure_status(response: requests.Response, expected: int | tuple[int, ...] = 200) -> None:
    expected_codes = (expected,) if isinstance(expected, int) else expected
    if response.status_code not in expected_codes:
        fail(f"Unexpected status for {response.request.method} {response.request.url}", response)


def write_sample_markdown() -> Path:
    sample_path = Path(__file__).with_name("sample_progress.md")
    if not sample_path.exists():
        sample_path.write_text(
            "# Sample Research Progress\n\n"
            "Topic: LLM Agents\n\n"
            "- Implemented a retrieval workflow.\n"
            "- Added evaluation metrics for scientific summaries.\n"
            "- Open question: how to reduce hallucination in paper digests?\n",
            encoding="utf-8",
        )
    return sample_path
