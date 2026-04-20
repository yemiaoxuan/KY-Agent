from __future__ import annotations

import subprocess
import sys
from pathlib import Path

SCRIPTS = [
    "test_health.py",
    "test_topics.py",
    "test_reports.py",
    "test_uploads.py",
    "test_search_chat.py",
    "test_agent_sse.py",
    "test_email.py",
    "test_runtime_config.py",
]


def main() -> None:
    base = Path(__file__).parent
    python = sys.executable
    for script in SCRIPTS:
        path = base / script
        print(f"\n##### Running {script} #####")
        completed = subprocess.run([python, str(path)], cwd=base)
        if completed.returncode != 0:
            raise SystemExit(completed.returncode)


if __name__ == "__main__":
    main()
