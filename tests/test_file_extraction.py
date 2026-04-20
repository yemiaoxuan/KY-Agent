from app.services.content.file_extraction_service import chunk_text


def test_chunk_text() -> None:
    chunks = chunk_text("a" * 1300, chunk_size=1000, overlap=100)
    assert len(chunks) == 2
    assert len(chunks[0]) == 1000
