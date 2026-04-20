from _client import ensure_status, ok, post, print_section


def main() -> None:
    print_section("Semantic Search")
    search_response = post(
        "/search",
        json={"query": "LLM agent retrieval workflow", "limit": 5},
    )
    ensure_status(search_response, 200)
    search_payload = search_response.json()
    if not isinstance(search_payload, list):
        raise SystemExit(f"Unexpected search payload: {search_payload}")
    ok(f"/search returned {len(search_payload)} chunks")

    print_section("Chat RAG")
    chat_response = post(
        "/chat",
        json={"question": "总结一下当前公共库里和 LLM agent 检索相关的进展", "limit": 5},
    )
    ensure_status(chat_response, 200)
    chat_payload = chat_response.json()
    if "answer" not in chat_payload or "sources" not in chat_payload:
        raise SystemExit(f"Unexpected chat payload: {chat_payload}")
    ok(f"/chat returned {len(chat_payload['sources'])} sources")
    print(chat_payload["answer"])


if __name__ == "__main__":
    main()
