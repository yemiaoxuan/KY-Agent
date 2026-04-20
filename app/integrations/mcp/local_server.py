from __future__ import annotations

from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

from mcp.server.fastmcp import FastMCP

mcp = FastMCP("ky-local-tools")


@mcp.tool(description="获取当前北京时间，返回 ISO 时间和格式化文本。")
def get_current_time() -> dict[str, str]:
    now = datetime.now(ZoneInfo("Asia/Shanghai"))
    return {
        "timezone": "Asia/Shanghai",
        "iso": now.isoformat(),
        "formatted": now.strftime("%Y-%m-%d %H:%M:%S"),
        "weekday": now.strftime("%A"),
    }


@mcp.tool(description="对输入文本做本地统计，返回字数、行数、段落数和预览。")
def summarize_text_stats(text: str) -> dict[str, object]:
    stripped = text.strip()
    lines = [line for line in text.splitlines() if line.strip()]
    paragraphs = [item for item in stripped.split("\n\n") if item.strip()] if stripped else []
    tokens = [token for token in text.replace("\n", " ").split(" ") if token]
    return {
        "char_count": len(text),
        "word_count": len(tokens),
        "line_count": len(lines),
        "paragraph_count": len(paragraphs),
        "preview": stripped[:280],
    }


@mcp.tool(description="用简单词频方法抽取关键词，适合中英文混合短文本。")
def extract_keywords_local(text: str, top_k: int = 8) -> dict[str, object]:
    normalized = text.replace("\n", " ").replace("\t", " ")
    stopwords = {
        "the",
        "and",
        "for",
        "with",
        "that",
        "this",
        "from",
        "into",
        "have",
        "will",
        "your",
        "研究",
        "我们",
        "以及",
        "一个",
        "进行",
        "相关",
        "可以",
        "当前",
    }
    counts: dict[str, int] = {}
    for token in normalized.split(" "):
        word = token.strip(" ,.:;!?()[]{}\"'").lower()
        if len(word) < 2 or word in stopwords:
            continue
        counts[word] = counts.get(word, 0) + 1
    ranked = sorted(counts.items(), key=lambda item: (-item[1], item[0]))[:top_k]
    return {"keywords": [{"term": term, "count": count} for term, count in ranked]}


@mcp.tool(description="读取本地 Markdown 文件片段，默认读取前 80 行。")
def read_local_markdown_excerpt(path: str, max_lines: int = 80) -> dict[str, object]:
    file_path = Path(path).expanduser().resolve()
    if not file_path.exists():
        return {"ok": False, "error": f"file not found: {file_path}"}
    if file_path.suffix.lower() not in {".md", ".txt"}:
        return {"ok": False, "error": f"unsupported file type: {file_path.suffix}"}
    content = file_path.read_text(encoding="utf-8")
    lines = content.splitlines()
    excerpt = "\n".join(lines[:max_lines])
    return {
        "ok": True,
        "path": str(file_path),
        "line_count": len(lines),
        "excerpt": excerpt,
    }


if __name__ == "__main__":
    mcp.run()
