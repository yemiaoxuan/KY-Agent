import requests
from _client import BASE_URL, TIMEOUT, ensure_status, get, ok, post, print_section


def main() -> None:
    print_section("Topics Sync")
    sync_response = post("/topics/sync")
    ensure_status(sync_response, 200)
    sync_payload = sync_response.json()
    if not isinstance(sync_payload, list):
        raise SystemExit(f"Unexpected sync payload: {sync_payload}")
    ok(f"/topics/sync returned {len(sync_payload)} topics")

    print_section("Topics List")
    list_response = get("/topics")
    ensure_status(list_response, 200)
    topics = list_response.json()
    if not isinstance(topics, list):
        raise SystemExit(f"Unexpected list payload: {topics}")
    ok(f"/topics returned {len(topics)} topics")
    for topic in topics:
        print(f"- {topic['name']}: {topic['display_name']}")

    print_section("Topic Create / Update / Delete")
    create_response = post(
        "/topics",
        json={
            "name": "test_dynamic_topic",
            "display_name": "Test Dynamic Topic",
            "query": "test query",
            "arxiv_categories": ["cs.AI"],
            "include_keywords": ["test"],
            "exclude_keywords": ["survey"],
            "max_results": 5,
            "report_top_k": 3,
            "enabled": True,
            "report_prompt_hint": "请更关注实验设计。",
        },
    )
    ensure_status(create_response, 200)
    ok("/topics create succeeded")

    update_response = requests.put(
        f"{BASE_URL}/topics/test_dynamic_topic",
        json={"display_name": "Updated Topic", "enabled": False},
        timeout=TIMEOUT,
    )
    ensure_status(update_response, 200)
    ok("/topics update succeeded")

    delete_response = requests.delete(
        f"{BASE_URL}/topics/test_dynamic_topic",
        timeout=TIMEOUT,
    )
    ensure_status(delete_response, 200)
    ok("/topics delete succeeded")


if __name__ == "__main__":
    main()
