from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

import requests
import streamlit as st

st.set_page_config(page_title="科研进展协作台", page_icon="🔬", layout="wide")

DEFAULT_API_BASE = "http://127.0.0.1:8000"
CHAT_STORAGE_PATH = Path("/mnt/hdd/cjt/ky/storage/chat_sessions.json")
DOCUMENT_UPLOAD_TYPES = ["md", "txt", "pdf", "docx"]
IMAGE_UPLOAD_TYPES = ["png", "jpg", "jpeg", "webp", "bmp"]
AGENT_UPLOAD_TYPES = [*DOCUMENT_UPLOAD_TYPES, *IMAGE_UPLOAD_TYPES]
IMAGE_SUFFIXES = {".png", ".jpg", ".jpeg", ".webp", ".bmp"}


def inject_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Noto+Serif+SC:wght@400;600;700&family=IBM+Plex+Sans:wght@400;500;600&display=swap');
        :root {
            --bg: #f6f0e8;
            --panel: rgba(255, 251, 245, 0.92);
            --ink: #1f2521;
            --muted: #667069;
            --line: rgba(57, 72, 63, 0.12);
            --accent: #1e6b57;
            --accent-2: #c96c3d;
            --shadow: 0 20px 60px rgba(71, 54, 31, 0.10);
        }
        .stApp {
            background:
                radial-gradient(circle at top left, rgba(201,108,61,0.16), transparent 28%),
                radial-gradient(circle at top right, rgba(30,107,87,0.15), transparent 24%),
                linear-gradient(180deg, #fbf7f1 0%, var(--bg) 100%);
            color: var(--ink);
            font-family: 'IBM Plex Sans', sans-serif;
        }
        h1, h2, h3 {
            font-family: 'Noto Serif SC', serif !important;
            color: var(--ink);
            letter-spacing: 0.01em;
        }
        .block-container {
            padding-top: 1.5rem;
            padding-bottom: 2rem;
        }
        .hero {
            background: linear-gradient(135deg, rgba(255,251,245,0.95), rgba(247,240,230,0.92));
            border: 1px solid rgba(57, 72, 63, 0.10);
            border-radius: 28px;
            padding: 28px 30px;
            box-shadow: var(--shadow);
            margin-bottom: 1rem;
        }
        .hero-kicker {
            color: var(--accent);
            font-size: 0.85rem;
            letter-spacing: 0.16em;
            text-transform: uppercase;
            font-weight: 700;
        }
        .hero-title {
            font-size: 2.4rem;
            line-height: 1.15;
            margin: 0.4rem 0 0.8rem 0;
        }
        .hero-subtitle {
            color: var(--muted);
            font-size: 1.02rem;
            max-width: 900px;
        }
        .metric-card, .panel-card, .chat-tip {
            background: var(--panel);
            border: 1px solid var(--line);
            border-radius: 22px;
            box-shadow: var(--shadow);
        }
        .metric-card {
            padding: 18px 20px;
            min-height: 132px;
        }
        .metric-label {
            color: var(--muted);
            font-size: 0.88rem;
            margin-bottom: 0.6rem;
        }
        .metric-value {
            font-size: 2.2rem;
            font-weight: 700;
            color: var(--ink);
        }
        .metric-hint {
            margin-top: 0.8rem;
            color: var(--muted);
            font-size: 0.9rem;
        }
        .panel-card {
            padding: 18px 20px;
            margin-bottom: 1rem;
        }
        .section-note {
            color: var(--muted);
            margin-bottom: 0.75rem;
        }
        .status-pill {
            display: inline-block;
            padding: 0.24rem 0.7rem;
            border-radius: 999px;
            font-size: 0.82rem;
            font-weight: 600;
            margin-right: 0.45rem;
        }
        .status-ok { background: rgba(30,107,87,0.12); color: var(--accent); }
        .status-warn { background: rgba(201,108,61,0.14); color: var(--accent-2); }
        .status-bad { background: rgba(155,53,53,0.12); color: #8d3131; }
        .chat-tip {
            padding: 14px 16px;
            margin-bottom: 0.8rem;
        }
        div[data-testid="stChatMessage"] {
            background: rgba(255, 251, 245, 0.72);
            border: 1px solid var(--line);
            border-radius: 18px;
            padding: 0.35rem 0.65rem;
        }
        div[data-testid="stSidebar"] {
            background: rgba(252,247,241,0.88);
            border-right: 1px solid var(--line);
        }
        </style>
        """,
        unsafe_allow_html=True,
    )


inject_styles()


def api_get(path: str) -> requests.Response:
    return requests.get(f"{API_BASE}{path}", timeout=TIMEOUT)


def api_post(path: str, **kwargs: Any) -> requests.Response:
    return requests.post(f"{API_BASE}{path}", timeout=TIMEOUT, **kwargs)


def api_put(path: str, **kwargs: Any) -> requests.Response:
    return requests.put(f"{API_BASE}{path}", timeout=TIMEOUT, **kwargs)


def api_delete(path: str, **kwargs: Any) -> requests.Response:
    return requests.delete(f"{API_BASE}{path}", timeout=TIMEOUT, **kwargs)


def render_json_or_error(response: requests.Response) -> None:
    try:
        payload = response.json()
    except Exception:
        st.error(response.text)
        return
    if response.ok:
        st.json(payload)
    else:
        st.error(f"HTTP {response.status_code}")
        st.json(payload)


def check_health() -> tuple[bool, dict[str, Any] | str]:
    try:
        response = api_get("/health")
        response.raise_for_status()
        return True, response.json()
    except Exception as exc:
        return False, str(exc)


def load_topics() -> list[dict[str, Any]]:
    try:
        response = api_get("/topics")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def load_reports() -> list[dict[str, Any]]:
    try:
        response = api_get("/reports")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def load_uploads() -> list[dict[str, Any]]:
    try:
        response = api_get("/uploads")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, list) else []
    except Exception:
        return []


def load_email_status() -> dict[str, Any]:
    try:
        response = api_get("/email/config-status")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"configured": False, "message": str(exc)}


def load_runtime_config() -> dict[str, Any]:
    try:
        response = api_get("/runtime-config")
        response.raise_for_status()
        payload = response.json()
        return payload if isinstance(payload, dict) else {}
    except Exception as exc:
        return {"error": str(exc)}


def stream_agent_events_json(payload: dict[str, Any]) -> tuple[str, list[dict[str, Any]]]:
    return _consume_sse_response(
        api_post(
            "/agent/chat/stream",
            json=payload,
            headers={"Accept": "text/event-stream"},
            stream=True,
        )
    )


def stream_agent_events_with_files(
    payload: dict[str, Any],
    files: list[Any],
) -> tuple[str, list[dict[str, Any]]]:
    multipart_files = []
    for item in files:
        multipart_files.append(
            ("files", (item.name, item.getvalue(), item.type or "application/octet-stream"))
        )
    return _consume_sse_response(
        api_post(
            "/agent/chat/stream-with-files",
            data={"payload": json.dumps(payload, ensure_ascii=False)},
            files=multipart_files,
            headers={"Accept": "text/event-stream"},
            stream=True,
        )
    )


def _consume_sse_response(response: requests.Response) -> tuple[str, list[dict[str, Any]]]:
    answer_parts: list[str] = []
    final_answer: str | None = None
    events: list[dict[str, Any]] = []
    with response as stream_response:
        stream_response.raise_for_status()
        current_event = "message"
        current_data_lines: list[str] = []
        for raw_line in stream_response.iter_lines(decode_unicode=True):
            if raw_line is None:
                continue
            line = raw_line.strip()
            if not line:
                if current_data_lines:
                    raw_data = "\n".join(current_data_lines)
                    try:
                        data = json.loads(raw_data)
                    except Exception:
                        data = {"raw": raw_data}
                    event = {"event": current_event, "data": data}
                    events.append(event)
                    if current_event == "message" and isinstance(data, dict):
                        content = data.get("content")
                        if content:
                            answer_parts.append(str(content))
                    elif current_event == "done" and isinstance(data, dict):
                        content = data.get("answer")
                        if content:
                            final_answer = str(content)
                    current_event = "message"
                    current_data_lines = []
                continue
            if line.startswith("event:"):
                current_event = line.removeprefix("event:").strip()
            elif line.startswith("data:"):
                current_data_lines.append(line.removeprefix("data:").strip())
    answer = final_answer or ("\n\n".join(answer_parts).strip())
    return answer, events


def render_status_pill(ok: bool, text: str) -> None:
    css = "status-ok" if ok else "status-warn"
    st.markdown(f'<span class="status-pill {css}">{text}</span>', unsafe_allow_html=True)


def render_topic_summary_cards(topic_items: list[dict[str, Any]]) -> None:
    if not topic_items:
        st.info("暂无有效主题。")
        return
    for topic in topic_items:
        keywords = ", ".join(topic.get("include_keywords", [])[:6]) or "无"
        categories = ", ".join(topic.get("arxiv_categories", [])[:6]) or "无"
        hint = topic.get("report_prompt_hint") or "无"
        status_text = "启用" if topic.get("enabled") else "停用"
        st.markdown(
            f"""
            <div class="panel-card">
                <h4 style="margin:0 0 0.45rem 0;">{topic['display_name']} <span style="color:#667069;font-size:0.92rem;">({topic['name']})</span></h4>
                <div class="section-note">状态：{status_text} | 拉取上限：{topic['max_results']} | 日报入选：{topic['report_top_k']}</div>
                <div><strong>查询：</strong> {topic['query']}</div>
                <div><strong>分类：</strong> {categories}</div>
                <div><strong>包含关键词：</strong> {keywords}</div>
                <div><strong>主题日报提示：</strong> {hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )


def _default_session_title() -> str:
    return f"会话 {datetime.now().strftime('%m-%d %H:%M')}"


def _empty_chat_store() -> dict[str, Any]:
    session_id = datetime.now().strftime("%Y%m%d%H%M%S")
    return {
        "current_session_id": session_id,
        "sessions": [
            {
                "id": session_id,
                "title": _default_session_title(),
                "created_at": datetime.now().isoformat(),
                "updated_at": datetime.now().isoformat(),
                "messages": [],
                "events": [],
                "attachments": [],
            }
        ],
    }


def load_chat_store() -> dict[str, Any]:
    CHAT_STORAGE_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not CHAT_STORAGE_PATH.exists():
        store = _empty_chat_store()
        save_chat_store(store)
        return store
    try:
        payload = json.loads(CHAT_STORAGE_PATH.read_text(encoding="utf-8"))
        if "sessions" not in payload or not payload["sessions"]:
            store = _empty_chat_store()
            save_chat_store(store)
            return store
        for session in payload.get("sessions", []):
            session.setdefault("attachments", [])
        return payload
    except Exception:
        store = _empty_chat_store()
        save_chat_store(store)
        return store


def save_chat_store(store: dict[str, Any]) -> None:
    CHAT_STORAGE_PATH.write_text(
        json.dumps(store, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


def get_current_chat_session(store: dict[str, Any]) -> dict[str, Any]:
    current_id = store.get("current_session_id")
    sessions = store.get("sessions", [])
    for session in sessions:
        if session["id"] == current_id:
            return session
    store["current_session_id"] = sessions[0]["id"]
    return sessions[0]


def create_chat_session(store: dict[str, Any], title: str | None = None) -> dict[str, Any]:
    session_id = datetime.now().strftime("%Y%m%d%H%M%S%f")
    session = {
        "id": session_id,
        "title": title or _default_session_title(),
        "created_at": datetime.now().isoformat(),
        "updated_at": datetime.now().isoformat(),
        "messages": [],
        "events": [],
        "attachments": [],
    }
    store["sessions"].insert(0, session)
    store["current_session_id"] = session_id
    save_chat_store(store)
    return session


def delete_chat_session(store: dict[str, Any], session_id: str) -> None:
    store["sessions"] = [session for session in store["sessions"] if session["id"] != session_id]
    if not store["sessions"]:
        new_session = create_chat_session(store)
        store["current_session_id"] = new_session["id"]
    elif store.get("current_session_id") == session_id:
        store["current_session_id"] = store["sessions"][0]["id"]
        save_chat_store(store)
    else:
        save_chat_store(store)


def touch_chat_session(session: dict[str, Any]) -> None:
    session["updated_at"] = datetime.now().isoformat()


def is_image_file(item: Any) -> bool:
    suffix = Path(getattr(item, "name", "")).suffix.lower()
    mime_type = str(getattr(item, "type", "") or "").lower()
    return suffix in IMAGE_SUFFIXES or mime_type.startswith("image/")


def summarize_selected_files(files: list[Any]) -> str:
    if not files:
        return ""
    names = [item.name for item in files]
    if len(names) <= 3:
        return "，".join(names)
    return "，".join(names[:3]) + f" 等 {len(names)} 个文件"


def normalize_attachment_entry(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": str(item.get("id") or ""),
        "title": str(item.get("title") or ""),
        "description": item.get("description"),
        "file_path": str(item.get("file_path") or ""),
        "file_type": str(item.get("file_type") or ""),
        "visibility": str(item.get("visibility") or "public"),
        "source": str(item.get("source") or "history"),
    }


def get_session_attachment_registry(session: dict[str, Any]) -> list[dict[str, Any]]:
    attachments = session.get("attachments") or []
    return [normalize_attachment_entry(item) for item in attachments if item.get("file_path")]


def merge_session_attachments(
    session: dict[str, Any],
    new_attachments: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    existing = get_session_attachment_registry(session)
    merged_by_path = {item["file_path"]: item for item in existing}
    for item in new_attachments:
        normalized = normalize_attachment_entry(item)
        if not normalized["file_path"]:
            continue
        merged_by_path[normalized["file_path"]] = normalized
    merged = list(merged_by_path.values())
    session["attachments"] = merged
    return merged


def render_attachment_registry(session: dict[str, Any]) -> None:
    attachments = get_session_attachment_registry(session)
    if not attachments:
        st.caption("当前会话暂无已登记附件。")
        return
    image_attachments = [
        item for item in attachments if item["file_type"].lower() in {"png", "jpg", "jpeg", "webp", "bmp"}
    ]
    st.caption(f"当前会话已登记附件 {len(attachments)} 个，其中图片 {len(image_attachments)} 个。")
    with st.expander("历史附件索引", expanded=False):
        st.json(attachments)


def extract_sam_outputs(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    results: list[dict[str, Any]] = []
    seen: set[tuple[str, str]] = set()
    for event in events:
        if event.get("event") != "tool_result":
            continue
        data = event.get("data", {})
        if data.get("name") != "segment_image_with_sam":
            continue
        result = data.get("result", {})
        if not isinstance(result, dict) or not result.get("ok"):
            continue
        overlay_path = str(result.get("overlay_path") or "")
        mask_path = str(result.get("mask_path") or "")
        key = (overlay_path, mask_path)
        if key in seen:
            continue
        seen.add(key)
        results.append(
            {
                "prompt": result.get("prompt") or "",
                "message": result.get("message") or "ok",
                "image_path": result.get("image_path") or "",
                "overlay_path": overlay_path,
                "mask_path": mask_path,
                "detection_count": result.get("detection_count") or 0,
                "detections": result.get("detections") or [],
            }
        )
    return results


def render_chat_message_payload(message: dict[str, Any]) -> None:
    content = message.get("content", "")
    st.markdown(content)
    sam_outputs = message.get("sam_outputs") or []
    if not sam_outputs:
        return
    for index, item in enumerate(sam_outputs, start=1):
        prompt = item.get("prompt") or "未提供提示词"
        detection_count = item.get("detection_count") or 0
        st.caption(f"SAM 结果 {index} · prompt: {prompt} · 检测数: {detection_count}")
        overlay_path = item.get("overlay_path")
        mask_path = item.get("mask_path")
        image_columns = st.columns(2)
        with image_columns[0]:
            if overlay_path and Path(overlay_path).exists():
                st.image(overlay_path, caption="Overlay", use_container_width=True)
            elif overlay_path:
                st.caption(f"Overlay 不存在：{overlay_path}")
        with image_columns[1]:
            if mask_path and Path(mask_path).exists():
                st.image(mask_path, caption="Mask", use_container_width=True)
            elif mask_path:
                st.caption(f"Mask 不存在：{mask_path}")
        detections = item.get("detections") or []
        if detections:
            st.json(detections)


if "chat_store" not in st.session_state:
    st.session_state.chat_store = load_chat_store()
if "agent_file_uploader_nonce" not in st.session_state:
    st.session_state.agent_file_uploader_nonce = 0

chat_store = st.session_state.chat_store
current_chat_session = get_current_chat_session(chat_store)

with st.sidebar:
    st.markdown("### 连接设置")
    API_BASE = st.text_input("后端地址", DEFAULT_API_BASE).rstrip("/")
    TIMEOUT = st.number_input("请求超时（秒）", min_value=10, max_value=600, value=180, step=10)
    st.caption("如通过 VS Code Remote 访问，请转发 API 端口 `8000` 与前端端口 `8501`。")
    st.markdown("---")
    st.markdown("### Agent 会话")
    session_options = [session["id"] for session in chat_store["sessions"]]
    selected_session_id = st.selectbox(
        "当前会话",
        options=session_options,
        index=next(
            (
                idx
                for idx, session in enumerate(chat_store["sessions"])
                if session["id"] == chat_store["current_session_id"]
            ),
            0,
        ),
        format_func=lambda session_id: next(
            (
                f"{session['title']} · {session['updated_at'][5:16].replace('T', ' ')}"
                for session in chat_store["sessions"]
                if session["id"] == session_id
            ),
            session_id,
        ),
    )
    if selected_session_id != chat_store["current_session_id"]:
        chat_store["current_session_id"] = selected_session_id
        save_chat_store(chat_store)
        st.session_state.chat_store = chat_store
        st.rerun()
    new_session_title = st.text_input("新会话标题", value="")
    if st.button("新建会话", use_container_width=True):
        create_chat_session(chat_store, new_session_title or None)
        st.session_state.chat_store = chat_store
        st.rerun()
    if st.button("删除当前会话", use_container_width=True):
        delete_chat_session(chat_store, chat_store["current_session_id"])
        st.session_state.chat_store = chat_store
        st.rerun()


healthy, health_payload = check_health()
topics = [topic for topic in load_topics() if topic.get("name", "").strip()]
reports = load_reports()
uploads = load_uploads()
email_status = load_email_status()
runtime_config = load_runtime_config()

st.markdown(
    """
    <div class="hero">
        <div class="hero-kicker">KY · Research Copilot</div>
        <div class="hero-title">科研进展协作台</div>
        <div class="hero-subtitle">
            用一个中文界面管理科研日报、共享上传、语义检索、RAG 问答和可调用工具的 Agent。
            当前版本面向个人使用，默认公开知识库，同时保留后续扩展多用户协作与定时发布的接口。
        </div>
    </div>
    """,
    unsafe_allow_html=True,
)

overview_cols = st.columns(4)
cards = [
    ("研究主题", len(topics), "来自 `configs/topics.yaml` 的当前启用主题"),
    ("日报归档", len(reports), "可查看历史生成内容，也可手动再次触发"),
    ("共享文档", len(uploads), "上传后进入 pgvector 公共语义库"),
    ("邮件状态", "已配置" if email_status.get("configured") else "待配置", email_status.get("message", "")),
]
for col, (label, value, hint) in zip(overview_cols, cards, strict=False):
    with col:
        st.markdown(
            f"""
            <div class="metric-card">
                <div class="metric-label">{label}</div>
                <div class="metric-value">{value}</div>
                <div class="metric-hint">{hint}</div>
            </div>
            """,
            unsafe_allow_html=True,
        )

top_left, top_right = st.columns([3, 1.15])
with top_left:
    render_status_pill(healthy, "后端已连接" if healthy else "后端不可用")
    render_status_pill(bool(email_status.get("configured")), "邮件已准备" if email_status.get("configured") else "邮件待配置")
    render_status_pill(True, "本地 MCP 已接入")
with top_right:
    if not healthy:
        st.caption(str(health_payload))

tab_home, tab_topics, tab_reports, tab_upload, tab_search, tab_agent, tab_email, tab_runtime = st.tabs(
    ["总览", "主题配置", "日报中心", "资料上传", "检索与问答", "科研 Agent", "邮件发送", "系统配置"]
)

with tab_home:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("快速操作")
    quick_left, quick_mid, quick_right = st.columns([1.1, 1.2, 1.2])
    with quick_left:
        topic_names = st.multiselect(
            "选择要生成日报的主题",
            options=[topic["name"] for topic in topics],
            default=[topic["name"] for topic in topics[:1]],
            key="quick_report_topics",
            help="可多选；留空表示全部启用主题。",
        )
        if st.button("立即生成日报", use_container_width=True):
            response = api_post(
                "/reports/run-daily",
                json={
                    "topic_names": topic_names or None,
                    "send_email": False,
                },
            )
            render_json_or_error(response)
    with quick_mid:
        st.markdown("#### 系统说明")
        st.markdown(
            "- `arXiv` 为当前优先数据源\n"
            "- 向量库使用 `pgvector`\n"
            "- Agent 已接入日报、检索、上传、邮件和本地 MCP 工具\n"
            "- 日报生成后会自动写入公共向量库"
        )
    with quick_right:
        st.markdown("#### 当前服务状态")
        st.json(
            {
                "health": health_payload,
                "email": email_status,
                "api_base": API_BASE,
            }
        )
    st.markdown("</div>", unsafe_allow_html=True)

    recent_left, recent_right = st.columns([1.1, 1])
    with recent_left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("最近日报")
        if reports:
            st.dataframe(reports[:8], use_container_width=True, hide_index=True)
        else:
            st.info("还没有日报记录。")
        st.markdown("</div>", unsafe_allow_html=True)
    with recent_right:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("最近上传")
        if uploads:
            st.dataframe(uploads[:8], use_container_width=True, hide_index=True)
        else:
            st.info("还没有共享文档。")
        st.markdown("</div>", unsafe_allow_html=True)

with tab_topics:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("主题配置")
    st.caption("主题现在以数据库为准。你可以从 YAML 导入初始模板，也可以直接在前端新增、编辑、启停或删除。")
    top_action_left, top_action_right = st.columns([1, 1])
    with top_action_left:
        if st.button("从 YAML 导入主题模板", use_container_width=True):
            response = api_post("/topics/sync")
            render_json_or_error(response)
            st.rerun()
    with top_action_right:
        if st.button("清理无效主题", use_container_width=True):
            response = api_post("/topics/cleanup-invalid")
            render_json_or_error(response)
            st.rerun()

    st.markdown("#### 当前已有主题")
    render_topic_summary_cards(topics)

    create_left, create_right = st.columns([1.05, 1.4])
    with create_left:
        st.markdown("#### 新建主题")
        new_name = st.text_input("主题标识", key="topic_new_name")
        new_display_name = st.text_input("显示名称", key="topic_new_display_name")
        new_query = st.text_area(
            "arXiv 检索查询",
            key="topic_new_query",
            height=140,
            help="这里应填写适合 arXiv 的检索词，例如 `3dgs`、`\"3D Gaussian Splatting\"` 或逻辑查询，而不是中文备注。",
        )
        new_categories = st.text_input("arXiv 分类（逗号分隔）", key="topic_new_categories")
        new_include = st.text_input("包含关键词（逗号分隔）", key="topic_new_include")
        new_exclude = st.text_input("排除关键词（逗号分隔）", key="topic_new_exclude")
        new_top_k = st.number_input("日报入选上限", min_value=1, max_value=50, value=10)
        new_max_results = st.number_input("arXiv 拉取上限", min_value=1, max_value=100, value=30)
        new_enabled = st.checkbox("立即启用", value=True, key="topic_new_enabled")
        new_prompt_hint = st.text_area(
            "主题专属日报提示词",
            key="topic_new_prompt_hint",
            height=110,
            help="例如：更关注实验设置、对比基线、潜在落地价值。",
        )
        if st.button("创建主题", use_container_width=True):
            if not new_name.strip():
                st.error("主题标识不能为空。")
            elif not new_display_name.strip():
                st.error("显示名称不能为空。")
            elif not new_query.strip():
                st.error("检索查询不能为空。")
            else:
                response = api_post(
                    "/topics",
                    json={
                        "name": new_name.strip(),
                        "display_name": new_display_name.strip(),
                        "query": new_query.strip(),
                        "arxiv_categories": [
                            item.strip() for item in new_categories.split(",") if item.strip()
                        ],
                        "include_keywords": [
                            item.strip() for item in new_include.split(",") if item.strip()
                        ],
                        "exclude_keywords": [
                            item.strip() for item in new_exclude.split(",") if item.strip()
                        ],
                        "max_results": int(new_max_results),
                        "report_top_k": int(new_top_k),
                        "enabled": new_enabled,
                        "report_prompt_hint": new_prompt_hint.strip() or None,
                    },
                )
                render_json_or_error(response)
                if response.ok:
                    st.rerun()

    with create_right:
        st.markdown("#### 编辑已有主题")
        if topics:
            selected_topic_name = st.selectbox(
                "选择主题",
                options=[topic["name"] for topic in topics],
                key="topic_edit_selector",
            )
            selected_topic = next(
                topic for topic in topics if topic["name"] == selected_topic_name
            )
            edit_display_name = st.text_input(
                "显示名称",
                value=selected_topic["display_name"],
                key="topic_edit_display_name",
            )
            edit_query = st.text_area(
                "arXiv 检索查询",
                value=selected_topic["query"],
                key="topic_edit_query",
                height=140,
                help="建议使用 arXiv 可命中的英文关键词或逻辑查询。",
            )
            edit_categories = st.text_input(
                "arXiv 分类（逗号分隔）",
                value=", ".join(selected_topic["arxiv_categories"]),
                key="topic_edit_categories",
            )
            edit_include = st.text_input(
                "包含关键词（逗号分隔）",
                value=", ".join(selected_topic["include_keywords"]),
                key="topic_edit_include",
            )
            edit_exclude = st.text_input(
                "排除关键词（逗号分隔）",
                value=", ".join(selected_topic["exclude_keywords"]),
                key="topic_edit_exclude",
            )
            edit_top_k = st.number_input(
                "日报入选上限",
                min_value=1,
                max_value=50,
                value=int(selected_topic["report_top_k"]),
                key="topic_edit_top_k",
            )
            edit_max_results = st.number_input(
                "arXiv 拉取上限",
                min_value=1,
                max_value=100,
                value=int(selected_topic["max_results"]),
                key="topic_edit_max_results",
            )
            edit_enabled = st.checkbox(
                "启用该主题",
                value=selected_topic["enabled"],
                key="topic_edit_enabled",
            )
            edit_prompt_hint = st.text_area(
                "主题专属日报提示词",
                value=selected_topic.get("report_prompt_hint") or "",
                key="topic_edit_prompt_hint",
                height=110,
            )
            action_left, action_right = st.columns(2)
            with action_left:
                if st.button("保存主题修改", use_container_width=True):
                    if not edit_display_name.strip():
                        st.error("显示名称不能为空。")
                    elif not edit_query.strip():
                        st.error("检索查询不能为空。")
                    else:
                        response = api_put(
                            f"/topics/{selected_topic_name}",
                            json={
                                "display_name": edit_display_name.strip(),
                                "query": edit_query.strip(),
                                "arxiv_categories": [
                                    item.strip() for item in edit_categories.split(",") if item.strip()
                                ],
                                "include_keywords": [
                                    item.strip() for item in edit_include.split(",") if item.strip()
                                ],
                                "exclude_keywords": [
                                    item.strip() for item in edit_exclude.split(",") if item.strip()
                                ],
                                "max_results": int(edit_max_results),
                                "report_top_k": int(edit_top_k),
                                "enabled": edit_enabled,
                                "report_prompt_hint": edit_prompt_hint.strip() or None,
                            },
                        )
                        render_json_or_error(response)
                        if response.ok:
                            st.rerun()
            with action_right:
                if st.button("删除该主题", use_container_width=True):
                    response = api_delete(f"/topics/{selected_topic_name}")
                    render_json_or_error(response)
                    if response.ok:
                        st.rerun()
        else:
            st.info("暂无主题配置。")
    if topics:
        st.dataframe(topics, use_container_width=True, hide_index=True)
    else:
        st.info("暂无主题配置。")
    st.markdown("</div>", unsafe_allow_html=True)

with tab_reports:
    left, right = st.columns([0.9, 1.5])
    with left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("生成日报")
        selected_topics = st.multiselect(
            "主题",
            options=[topic["name"] for topic in topics],
            default=[topic["name"] for topic in topics[:1]],
            key="report_topic_names",
            help="可多选；留空表示全部启用主题。",
        )
        send_email_now = st.checkbox("生成后立即尝试发送邮件", value=False)
        report_recipients_raw = st.text_input(
            "日报收件人（逗号分隔，可留空走默认收件人）",
            key="report_email_recipients",
        )
        report_recipients = [
            item.strip() for item in report_recipients_raw.split(",") if item.strip()
        ] or None
        report_prompt_suffix = st.text_area(
            "本次附加提示词",
            value="",
            height=120,
            help="例如：更关注方法创新、实验充分性、是否适合落地到我的项目。",
        )
        if st.button("运行日报流程", use_container_width=True):
            response = api_post(
                "/reports/run-daily",
                json={
                    "topic_names": selected_topics or None,
                    "send_email": send_email_now,
                    "recipients": report_recipients,
                    "prompt_suffix": report_prompt_suffix or None,
                },
            )
            render_json_or_error(response)
        st.markdown("</div>", unsafe_allow_html=True)

    with right:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("日报列表与内容")
        if reports:
            st.dataframe(reports, use_container_width=True, hide_index=True)
            selected_report_id = st.selectbox(
                "选择一份日报阅读",
                options=[item["id"] for item in reports],
                format_func=lambda report_id: next(
                    (
                        f"{item['report_date']} | {item['title']}"
                        for item in reports
                        if item["id"] == report_id
                    ),
                    report_id,
                ),
            )
            content_response = api_get(f"/reports/{selected_report_id}/content")
            if content_response.ok:
                payload = content_response.json()
                st.markdown(f"#### {payload['title']}")
                st.caption(
                    f"日期：{payload['report_date']} | 邮件状态：{payload['email_status']}"
                )
                st.markdown(payload["markdown"])
            else:
                render_json_or_error(content_response)
        else:
            st.info("还没有可阅读的日报。")
        st.markdown("</div>", unsafe_allow_html=True)

with tab_upload:
    upload_left, upload_right = st.columns([1, 1.1])
    with upload_left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("上传研究进展")
        uploaded_file = st.file_uploader(
            "选择文件",
            type=AGENT_UPLOAD_TYPES,
            help="支持 Markdown、文本、PDF、Word 文档，也支持图片文件。",
        )
        title = st.text_input("标题")
        description = st.text_area("说明")
        if st.button("上传到共享库", use_container_width=True) and uploaded_file:
            response = api_post(
                "/uploads",
                files={
                    "file": (
                        uploaded_file.name,
                        uploaded_file.getvalue(),
                        uploaded_file.type or "application/octet-stream",
                    )
                },
                data={
                    "title": title or uploaded_file.name,
                    "description": description,
                    "visibility": "public",
                },
            )
            render_json_or_error(response)
        st.markdown("</div>", unsafe_allow_html=True)
    with upload_right:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("共享文档列表")
        if uploads:
            st.dataframe(uploads, use_container_width=True, hide_index=True)
        else:
            st.info("暂无上传记录。")
        st.markdown("</div>", unsafe_allow_html=True)

with tab_search:
    search_left, search_right = st.columns(2)
    with search_left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("语义检索")
        semantic_query = st.text_area(
            "检索问题",
            value="LLM agent retrieval workflow",
            key="semantic_query",
        )
        semantic_limit = st.slider("返回条数", min_value=1, max_value=10, value=5)
        if st.button("执行语义检索", use_container_width=True):
            response = api_post("/search", json={"query": semantic_query, "limit": semantic_limit})
            render_json_or_error(response)
        st.markdown("</div>", unsafe_allow_html=True)
    with search_right:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("RAG 问答")
        rag_question = st.text_area(
            "研究问题",
            value="总结一下当前公共库里和 LLM agent 检索相关的进展",
            key="rag_question",
        )
        rag_limit = st.slider("引用条数", min_value=1, max_value=10, value=5)
        if st.button("执行 RAG 问答", use_container_width=True):
            response = api_post("/chat", json={"question": rag_question, "limit": rag_limit})
            render_json_or_error(response)
        st.markdown("</div>", unsafe_allow_html=True)

with tab_agent:
    st.markdown(
        """
        <div class="chat-tip">
            Agent 支持调用日报、上传、共享检索、RAG、邮件发送、本地 MCP 与 SAM 图像分割工具。
            你可以在提问时附带文档或图片，系统会先入库，再把文件上下文注入到本轮对话。
        </div>
        """,
        unsafe_allow_html=True,
    )
    agent_uploader_key = f"agent_files_{st.session_state.agent_file_uploader_nonce}"
    agent_files = st.file_uploader(
        "给 Agent 附带文档或图片",
        type=AGENT_UPLOAD_TYPES,
        accept_multiple_files=True,
        key=agent_uploader_key,
    )
    if agent_files:
        st.caption("这些附件会在你点击发送后上传。若包含图片，Agent 可直接调用 SAM 做目标分割。")
        image_files = [item for item in agent_files if is_image_file(item)]
        if image_files:
            preview_columns = st.columns(min(3, len(image_files)))
            for index, image_file in enumerate(image_files):
                with preview_columns[index % len(preview_columns)]:
                    st.image(image_file, caption=image_file.name, use_container_width=True)
        non_image_files = [item for item in agent_files if not is_image_file(item)]
        if non_image_files:
            st.markdown(
                "已选择资料：" + "，".join(item.name for item in non_image_files)
    )
    agent_selected_topics = st.multiselect(
        "本次会话关注主题",
        options=[topic["name"] for topic in topics],
        default=[topic["name"] for topic in topics[:1]],
        key="agent_selected_topics",
        help="Agent 会优先围绕这些主题做检索、总结和日报生成。",
    )
    render_attachment_registry(current_chat_session)

    for message in current_chat_session["messages"]:
        with st.chat_message(message["role"]):
            render_chat_message_payload(message)

    with st.expander("最近事件流", expanded=False):
        if current_chat_session["events"]:
            st.json(current_chat_session["events"][-40:])
        else:
            st.caption("暂无 Agent 事件。")

    user_input = st.chat_input("输入你的科研问题、协作需求或日报处理指令")
    if user_input:
        if not current_chat_session["messages"]:
            current_chat_session["title"] = user_input[:24] + ("..." if len(user_input) > 24 else "")
        display_user_input = user_input
        if agent_files:
            display_user_input = (
                f"{user_input}\n\n"
                f"_本轮附带文件：{summarize_selected_files(agent_files)}_"
            )
        current_chat_session["messages"].append({"role": "user", "content": display_user_input})
        touch_chat_session(current_chat_session)
        save_chat_store(chat_store)
        with st.chat_message("user"):
            st.markdown(display_user_input)

        with st.chat_message("assistant"):
            placeholder = st.empty()
            event_log: list[dict[str, Any]] = []
            sam_outputs: list[dict[str, Any]] = []
            try:
                attachment_context = get_session_attachment_registry(current_chat_session)
                payload = {
                    "messages": current_chat_session["messages"],
                    "selected_topics": agent_selected_topics,
                    "attachment_context": attachment_context,
                    "max_steps": 6,
                    "search_limit": 5,
                    "tool_limit": 10,
                }
                if agent_files:
                    answer, events = stream_agent_events_with_files(payload, agent_files)
                else:
                    answer, events = stream_agent_events_json(payload)
                event_log.extend(events)
                sam_outputs = extract_sam_outputs(events)
                uploaded_contexts = [
                    event["data"]["uploaded_documents"]
                    for event in events
                    if event.get("event") == "context"
                    and isinstance(event.get("data"), dict)
                    and event["data"].get("uploaded_documents")
                ]
                if uploaded_contexts:
                    latest_uploaded_documents = [
                        {
                            **item,
                            "source": "uploaded_this_session",
                        }
                        for item in uploaded_contexts[-1]
                    ]
                    merge_session_attachments(current_chat_session, latest_uploaded_documents)
                if answer:
                    placeholder.markdown(answer)
                else:
                    placeholder.info("Agent 已结束，但没有返回最终回答文本。")
                if sam_outputs:
                    for item in sam_outputs:
                        st.caption(
                            f"SAM 已返回结果 · prompt: {item.get('prompt') or '未提供'} · "
                            f"检测数: {item.get('detection_count') or 0}"
                        )
                        image_columns = st.columns(2)
                        with image_columns[0]:
                            overlay_path = item.get("overlay_path")
                            if overlay_path and Path(overlay_path).exists():
                                st.image(overlay_path, caption="Overlay", use_container_width=True)
                        with image_columns[1]:
                            mask_path = item.get("mask_path")
                            if mask_path and Path(mask_path).exists():
                                st.image(mask_path, caption="Mask", use_container_width=True)
                st.caption(f"本轮共收到 {len(events)} 条事件。")
            except Exception as exc:
                answer = f"Agent 请求失败：{exc}"
                placeholder.error(answer)
                event_log.append({"event": "error", "data": {"message": str(exc)}})

        current_chat_session["messages"].append(
            {
                "role": "assistant",
                "content": answer,
                "sam_outputs": sam_outputs,
            }
        )
        current_chat_session["events"].extend(event_log)
        touch_chat_session(current_chat_session)
        save_chat_store(chat_store)
        st.session_state.agent_file_uploader_nonce += 1
        st.rerun()

with tab_email:
    email_left, email_right = st.columns([0.95, 1.25])
    with email_left:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("邮件配置状态")
        if email_status:
            st.json(email_status)
        subject = st.text_input("邮件主题", value="科研进展测试邮件")
        markdown_text = st.text_area(
            "Markdown 正文",
            value="# 测试邮件\n\n这是一封从科研进展协作台发出的测试邮件。",
            height=220,
        )
        recipients_raw = st.text_input("收件人列表（逗号分隔，可留空走默认收件人）")
        recipients = [item.strip() for item in recipients_raw.split(",") if item.strip()] or None
        if st.button("发送 Markdown 邮件", use_container_width=True):
            response = api_post(
                "/email/send",
                json={
                    "subject": subject,
                    "plain_text": markdown_text,
                    "markdown_text": markdown_text,
                    "recipients": recipients,
                },
            )
            render_json_or_error(response)
        st.markdown("</div>", unsafe_allow_html=True)

    with email_right:
        st.markdown('<div class="panel-card">', unsafe_allow_html=True)
        st.subheader("发送已有日报")
        if reports:
            report_id = st.selectbox(
                "选择日报",
                options=[item["id"] for item in reports],
                format_func=lambda report_id: next(
                    (item["title"] for item in reports if item["id"] == report_id),
                    report_id,
                ),
                key="email_report_id",
            )
            override_subject = st.text_input("覆盖主题（可选）")
            report_send_recipients_raw = st.text_input(
                "日报收件人（逗号分隔，可留空走默认收件人）",
                key="email_report_recipients",
            )
            report_send_recipients = [
                item.strip() for item in report_send_recipients_raw.split(",") if item.strip()
            ] or None
            if st.button("发送所选日报", use_container_width=True):
                response = api_post(
                    "/email/send-report",
                    json={
                        "report_id": report_id,
                        "subject": override_subject or None,
                        "recipients": report_send_recipients,
                    },
                )
                render_json_or_error(response)

with tab_runtime:
    st.markdown('<div class="panel-card">', unsafe_allow_html=True)
    st.subheader("运行时配置")
    st.caption("这里的配置会写入 `storage/runtime_config.json`，保存后立即影响模型选择、MCP 和定时任务。")

    chat_options = runtime_config.get("chat_model_options", [])
    embedding_options = runtime_config.get("embedding_model_options", [])
    mcp_servers = runtime_config.get("mcp_servers", [])
    scheduler_config = runtime_config.get("scheduler", {})

    col_left, col_right = st.columns(2)
    with col_left:
        st.markdown("#### 模型配置")
        global_daily_prompt_suffix = st.text_area(
            "全局日报附加提示词",
            value=runtime_config.get("daily_report_system_prompt_suffix", ""),
            height=140,
            help="会自动拼接进每日报告的生成与摘要流程。",
        )
        enable_query_rewrite = st.checkbox(
            "启用请求重写",
            value=runtime_config.get("enable_query_rewrite", True),
            help="请求会先经过轻量模型重写，再进入主 Agent。",
        )
        chat_model_text = st.text_area(
            "可用聊天模型列表（每行一个）",
            value="\n".join(item["id"] for item in chat_options) if chat_options else "",
            height=160,
        )
        selected_rewrite_model = st.text_input(
            "当前重写模型",
            value=runtime_config.get("selected_rewrite_model") or runtime_config.get("selected_chat_model") or "",
        )
        selected_chat_model = st.text_input(
            "当前聊天模型",
            value=runtime_config.get("selected_chat_model") or "",
        )
        embedding_model_text = st.text_area(
            "可用向量模型列表（每行一个）",
            value="\n".join(item["id"] for item in embedding_options) if embedding_options else "",
            height=140,
        )
        selected_embedding_model = st.text_input(
            "当前向量模型",
            value=runtime_config.get("selected_embedding_model") or "",
        )

    with col_right:
        st.markdown("#### MCP 与定时任务")
        first_server = mcp_servers[0] if mcp_servers else {}
        mcp_enabled = st.checkbox("启用本地 MCP", value=first_server.get("enabled", True))
        mcp_command = st.text_input("MCP 启动命令", value=first_server.get("command", ".venv/bin/python"))
        mcp_args = st.text_area(
            "MCP 启动参数（每行一个）",
            value="\n".join(first_server.get("args", ["app/integrations/mcp/local_server.py"])),
            height=120,
        )
        schedule_enabled = st.checkbox(
            "启用定时日报",
            value=scheduler_config.get("enabled", True),
        )
        schedule_topics = st.multiselect(
            "定时日报主题",
            options=[topic["name"] for topic in topics],
            default=scheduler_config.get("topic_names", []),
            help="可多选；留空表示每天对全部启用主题生成日报。",
        )
        schedule_time = st.text_input(
            "定时发送时间（HH:MM）",
            value=scheduler_config.get("daily_report_time", "08:00"),
        )
        schedule_send_email = st.checkbox(
            "定时任务执行后自动发邮件",
            value=scheduler_config.get("send_email", True),
        )
        schedule_recipients_raw = st.text_area(
            "定时日报收件人（每行或逗号分隔，可留空走默认收件人）",
            value="\n".join(scheduler_config.get("email_recipients", [])),
            height=100,
        )

    if st.button("保存运行时配置", use_container_width=True):
        chat_ids = [item.strip() for item in chat_model_text.splitlines() if item.strip()]
        embedding_ids = [
            item.strip() for item in embedding_model_text.splitlines() if item.strip()
        ]
        payload = {
            "daily_report_system_prompt_suffix": global_daily_prompt_suffix,
            "enable_query_rewrite": enable_query_rewrite,
            "selected_rewrite_model": selected_rewrite_model
            or selected_chat_model
            or (chat_ids[0] if chat_ids else None),
            "selected_chat_model": selected_chat_model or (chat_ids[0] if chat_ids else None),
            "selected_embedding_model": selected_embedding_model
            or (embedding_ids[0] if embedding_ids else None),
            "chat_model_options": [
                {"id": item, "label": item, "kind": "chat", "enabled": True} for item in chat_ids
            ],
            "embedding_model_options": [
                {"id": item, "label": item, "kind": "embedding", "enabled": True}
                for item in embedding_ids
            ],
            "mcp_servers": [
                {
                    "enabled": mcp_enabled,
                    "name": "ky-local-tools",
                    "transport": "stdio",
                    "command": mcp_command,
                    "args": [item.strip() for item in mcp_args.splitlines() if item.strip()],
                    "cwd": ".",
                }
            ],
            "scheduler": {
                "enabled": schedule_enabled,
                "topic_names": schedule_topics,
                "daily_report_time": schedule_time,
                "send_email": schedule_send_email,
                "email_recipients": [
                    item.strip()
                    for chunk in schedule_recipients_raw.splitlines()
                    for item in chunk.split(",")
                    if item.strip()
                ],
            },
        }
        response = api_post("/runtime-config", json=payload)
        render_json_or_error(response)
    st.markdown("</div>", unsafe_allow_html=True)
