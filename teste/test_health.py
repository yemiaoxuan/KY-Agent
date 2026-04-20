from _client import ensure_status, get, ok, print_section


def main() -> None:
    print_section("Health")
    response = get("/health")
    ensure_status(response, 200)
    payload = response.json()
    if payload.get("status") != "ok":
        raise SystemExit(f"Unexpected payload: {payload}")
    ok("/health is healthy")


if __name__ == "__main__":
    main()
