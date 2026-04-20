from _client import ensure_status, get, ok, post, print_section


def main() -> None:
    print_section("Run Daily Report")
    response = post(
        "/reports/run-daily",
        json={
            "topic_name": "llm_agents",
            "send_email": False,
            "recipients": ["nobody@example.com"],
            "prompt_suffix": "请更关注实验设置与可复现性。",
        },
    )
    ensure_status(response, 200)
    payload = response.json()
    if not isinstance(payload, list):
        raise SystemExit(f"Unexpected report payload: {payload}")
    ok(f"/reports/run-daily returned {len(payload)} report results")
    print(payload)

    print_section("List Reports")
    list_response = get("/reports")
    ensure_status(list_response, 200)
    reports = list_response.json()
    if not isinstance(reports, list):
        raise SystemExit(f"Unexpected reports payload: {reports}")
    ok(f"/reports returned {len(reports)} records")
    if reports:
        print(f"latest={reports[0]['title']}")


if __name__ == "__main__":
    main()
