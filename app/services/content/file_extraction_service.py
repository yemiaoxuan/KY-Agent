from pathlib import Path

from docx import Document as DocxDocument
from pypdf import PdfReader

IMAGE_EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}
SUPPORTED_EXTENSIONS = {".pdf", ".md", ".txt", ".docx", *IMAGE_EXTENSIONS}


def detect_file_type(path: Path) -> str:
    suffix = path.suffix.lower()
    if suffix not in SUPPORTED_EXTENSIONS:
        raise ValueError(f"Unsupported file type: {suffix}")
    return suffix.removeprefix(".")


def extract_text(path: Path) -> str:
    file_type = detect_file_type(path)
    if file_type in {"md", "txt"}:
        return path.read_text(encoding="utf-8", errors="ignore")
    if file_type == "pdf":
        reader = PdfReader(str(path))
        return "\n".join(page.extract_text() or "" for page in reader.pages)
    if file_type == "docx":
        doc = DocxDocument(str(path))
        return "\n".join(paragraph.text for paragraph in doc.paragraphs)
    if path.suffix.lower() in IMAGE_EXTENSIONS:
        return ""
    raise ValueError(f"Unsupported file type: {file_type}")


def chunk_text(text: str, chunk_size: int = 1200, overlap: int = 150) -> list[str]:
    clean = "\n".join(line.strip() for line in text.splitlines() if line.strip())
    if not clean:
        return []
    chunks: list[str] = []
    start = 0
    while start < len(clean):
        end = start + chunk_size
        chunks.append(clean[start:end])
        if end >= len(clean):
            break
        start = max(0, end - overlap)
    return chunks
