from __future__ import annotations

from typing import Any

from app.schemas.agent import AgentAttachment

DEFAULT_SYSTEM_PROMPT = """你是科研助手。

你的职责：
1. 优先帮助用户完成科研检索、公共研究进展问答、日报生成、研究笔记上传、报告阅读和图像分割。
2. 当用户的问题需要数据库、报告、上传文件、邮件或图像分割能力时，主动使用工具。
3. 回答尽量简洁、结构清晰，并在使用工具后基于工具结果回答。
4. 不要编造不存在的数据库内容或报告内容。
5. 如果用户上传了图片，且需求涉及目标分割、抠图、区域提取、掩码或框选，
   优先使用 segment_image_with_sam 工具。
6. 如果工具报错或结果为空，要明确说明。"""


def build_upload_context_block(uploaded_documents: list[dict[str, Any]]) -> str:
    if not uploaded_documents:
        return ""
    image_documents = [
        document
        for document in uploaded_documents
        if str(document.get("file_type", "")).lower() in {"png", "jpg", "jpeg", "webp", "bmp"}
    ]
    lines = [
        "以下是本次对话刚刚上传并已入库的文件，请在需要时结合这些文档进行检索、总结或引用："
    ]
    for index, document in enumerate(uploaded_documents, start=1):
        lines.append(
            f"{index}. 文档ID={document['id']} | 标题={document['title']} "
            f"| 类型={document['file_type']} | 路径={document['file_path']} "
            f"| 可见性={document['visibility']}"
        )
        if str(document.get("file_type", "")).lower() in {"png", "jpg", "jpeg", "webp", "bmp"}:
            lines.append(
                "   该文件是图片，如需做目标分割，可直接把路径 "
                f"{document['file_path']} 传给 segment_image_with_sam 工具。"
            )
    if image_documents:
        lines.append("图像工具规则：")
        lines.append(
            "1. 当用户要求分割、抠图、mask、框选、主体提取、区域提取时，"
            "先调用 segment_image_with_sam。"
        )
        lines.append("2. 不要在未调用工具前声称看到了图片中的具体内容。")
        if len(image_documents) == 1:
            lines.append(
                "3. 本轮只上传了一张图片；如果用户说“这张图”或未明确点名图片，"
                f"默认使用 {image_documents[0]['file_path']}。"
            )
        else:
            lines.append(
                "3. 本轮上传了多张图片；若用户未明确指定图片，"
                "可优先询问或选择最近提到的那张。"
            )
        lines.append(
            "4. 工具调用格式示例：segment_image_with_sam("
            "image_path='绝对路径', instruction='segment the main object')."
        )
    lines.append("如果用户询问这些文件内容，优先结合公共检索、RAG、日报或图像工具回答。")
    return "\n".join(lines)


def build_selected_topics_context_block(selected_topics: list[str]) -> str:
    if not selected_topics:
        return ""
    joined = "、".join(selected_topics)
    return (
        f"本次会话当前关注的研究主题为：{joined}。\n"
        "当你生成日报、做科研检索、总结进展时，优先围绕这些主题展开。"
    )


def build_attachment_registry_context_block(attachments: list[AgentAttachment]) -> str:
    if not attachments:
        return ""
    image_attachments = [
        item
        for item in attachments
        if item.file_type.lower() in {"png", "jpg", "jpeg", "webp", "bmp"}
    ]
    lines = [
        "以下是当前会话已登记的历史附件索引。它们不一定是本轮新上传，但仍可直接引用其路径："
    ]
    for index, item in enumerate(attachments, start=1):
        lines.append(
            f"{index}. 标题={item.title} | 类型={item.file_type} "
            f"| 路径={item.file_path} | 来源={item.source}"
        )
    if image_attachments:
        lines.append("历史图片使用规则：")
        lines.append(
            "1. 当用户说“上一张图”“前面那张图”“之前上传的图片”时，"
            "优先使用最近登记的相关图片。"
        )
        lines.append(
            "2. 即使当前轮没有重新上传图片，也可以直接使用这些历史图片路径调用 "
            "segment_image_with_sam。"
        )
        lines.append(
            "3. 如果用户没有明确点名图片，默认优先使用最近一次成功引用或最近一次上传的图片。"
        )
    return "\n".join(lines)
