from __future__ import annotations

from _client import ensure_status, get, ok, post, print_section


def main() -> None:
    print_section("Runtime Config")
    response = get("/runtime-config")
    ensure_status(response, 200)
    payload = response.json()
    if "scheduler" not in payload or "mcp_servers" not in payload:
        raise SystemExit(f"Unexpected runtime-config payload: {payload}")
    if "topic_names" not in payload["scheduler"]:
        raise SystemExit(f"Missing scheduler.topic_names in payload: {payload}")
    ok("/runtime-config returned runtime settings")

    payload["scheduler"]["enabled"] = payload["scheduler"].get("enabled", True)
    save_response = post("/runtime-config", json=payload)
    ensure_status(save_response, 200)
    saved_payload = save_response.json()
    if (
        saved_payload.get("scheduler", {}).get("daily_report_time")
        != payload["scheduler"]["daily_report_time"]
    ):
        raise SystemExit(f"Unexpected saved runtime-config payload: {saved_payload}")
    ok("/runtime-config saved successfully")


if __name__ == "__main__":
    main()
