from __future__ import annotations

from _client import ensure_status, ok, post, print_section


def main() -> None:
    print_section("Email Config Status")
    status_response = post("/email/send", json={"subject": "配置检查", "plain_text": "test"})
    ensure_status(status_response, 200)
    payload = status_response.json()
    if "ok" not in payload or "message" not in payload:
        raise SystemExit(f"Unexpected email send payload: {payload}")
    ok("/email/send returned structured result")


if __name__ == "__main__":
    main()
