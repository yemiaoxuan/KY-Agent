from _client import ensure_status, get, ok, post, print_section, write_sample_markdown


def main() -> None:
    sample_path = write_sample_markdown()

    print_section("Upload Document")
    with sample_path.open("rb") as f:
        response = post(
            "/uploads",
            files={"file": (sample_path.name, f, "text/markdown")},
            data={
                "title": "Sample Progress",
                "description": "HTTP upload test",
                "visibility": "public",
            },
        )
    ensure_status(response, 200)
    payload = response.json()
    if "id" not in payload:
        raise SystemExit(f"Unexpected upload payload: {payload}")
    ok(f"/uploads created document {payload['id']}")

    print_section("List Uploads")
    list_response = get("/uploads")
    ensure_status(list_response, 200)
    uploads = list_response.json()
    if not isinstance(uploads, list):
        raise SystemExit(f"Unexpected uploads payload: {uploads}")
    ok(f"/uploads returned {len(uploads)} records")


if __name__ == "__main__":
    main()
