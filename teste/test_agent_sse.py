from __future__ import annotations

import json

from _client import ok, post, print_section, write_sample_markdown


def _consume_sse(response) -> list[dict]:
    events: list[dict] = []
    current_event = "message"
    current_data_lines: list[str] = []
    for raw_line in response.iter_lines(decode_unicode=True):
        if raw_line is None:
            continue
        line = raw_line.strip()
        if not line:
            if current_data_lines:
                raw_data = "\n".join(current_data_lines)
                try:
                    data = json.loads(raw_data)
                except Exception:
                    data = {"raw": raw_data}
                events.append({"event": current_event, "data": data})
                current_event = "message"
                current_data_lines = []
            continue
        if line.startswith("event:"):
            current_event = line.removeprefix("event:").strip()
        elif line.startswith("data:"):
            current_data_lines.append(line.removeprefix("data:").strip())
    return events


def main() -> None:
    print_section("Agent SSE JSON")
    response = post(
        "/agent/chat/stream",
        json={
            "messages": [
                {
                    "role": "user",
                    "content": "请列出你目前可用的科研工具能力，并简短说明。",
                }
            ],
            "max_steps": 3,
            "search_limit": 3,
            "tool_limit": 6,
        },
        headers={"Accept": "text/event-stream"},
        stream=True,
    )
    if response.status_code != 200:
        raise SystemExit(f"Unexpected status: {response.status_code}, body={response.text}")
    events = _consume_sse(response)
    if not events:
        raise SystemExit("No SSE events returned from /agent/chat/stream")
    if not any(item["event"] == "rewrite" for item in events):
        raise SystemExit(f"Expected rewrite event, got: {events[:5]}")
    ok(f"/agent/chat/stream returned {len(events)} SSE events")

    print_section("Agent SSE With Files")
    sample_path = write_sample_markdown()
    with sample_path.open("rb") as handle:
        response = post(
            "/agent/chat/stream-with-files",
            data={
                "payload": json.dumps(
                    {
                        "messages": [
                            {
                                "role": "user",
                                "content": "结合我上传的文件，概括一下其中提到的研究进展。",
                            }
                        ],
                        "max_steps": 3,
                        "search_limit": 3,
                        "tool_limit": 6,
                    },
                    ensure_ascii=False,
                )
            },
            files={"files": (sample_path.name, handle, "text/markdown")},
            headers={"Accept": "text/event-stream"},
            stream=True,
        )
        if response.status_code != 200:
            raise SystemExit(
                f"Unexpected status: {response.status_code}, body={response.text[:400]}"
            )
        file_events = _consume_sse(response)
        if not any(item["event"] == "context" for item in file_events):
            raise SystemExit(f"Expected context event, got: {file_events[:5]}")
        ok(f"/agent/chat/stream-with-files returned {len(file_events)} SSE events")


if __name__ == "__main__":
    main()
