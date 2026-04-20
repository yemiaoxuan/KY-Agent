# Frontend API Guide

本文档说明当前前端需要对接的后端接口，包括普通 HTTP 接口、邮件接口、视觉分割接口以及基于 SSE 的 Agent 对话接口。

默认基础地址：

```text
http://127.0.0.1:8000
```

## 1. Health

### `GET /health`

用途：

- 检查后端是否存活。

返回示例：

```json
{
  "status": "ok"
}
```

## 2. Topics

### `GET /topics`

用途：

- 获取当前数据库中的研究主题列表。

### `POST /topics/sync`

用途：

- 从 `configs/topics.yaml` 导入一批初始主题模板到数据库。
- 注意：数据库主题现在是主数据源，前端新增和修改的主题不会被自动覆盖。

请求体：

- 无

### `POST /topics`

用途：

- 新建主题。

### `PUT /topics/{topic_name}`

用途：

- 更新主题。

### `DELETE /topics/{topic_name}`

用途：

- 删除主题。

## 3. Reports

### `POST /reports/run-daily`

用途：

- 手动触发单个主题或全部主题的日报生成。

请求体：

```json
{
  "topic_name": "llm_agents",
  "send_email": false,
  "recipients": ["name@example.com"],
  "prompt_suffix": "请更关注实验设置、可复现性和工程可落地性。"
}
```

字段说明：

- `topic_name`: 可选，空值表示全部启用主题。
- `send_email`: 是否在生成后尝试发送邮件。
- `recipients`: 可选，生成日报后发送邮件的收件人列表；留空则使用默认 `EMAIL_TO`。
- `prompt_suffix`: 可选，本次日报生成的附加提示词。

返回示例：

```json
[
  {
    "topic_name": "llm_agents",
    "report_date": "2026-04-16",
    "title": "每日科研进展简报：LLM Agents - 2026-04-16",
    "markdown_path": "storage/reports/llm_agents/2026-04-16.md",
    "selected_count": 10,
    "email_status": "skipped"
  }
]
```

### `GET /reports`

用途：

- 获取历史日报列表。

### `GET /reports/{report_id}`

用途：

- 获取单个日报元数据。

### `GET /reports/{report_id}/content`

用途：

- 获取单个日报的完整 Markdown 正文。

返回示例：

```json
{
  "id": "uuid",
  "title": "每日科研进展简报：LLM Agents - 2026-04-16",
  "report_date": "2026-04-16",
  "markdown_path": "storage/reports/llm_agents/2026-04-16.md",
  "email_status": "skipped",
  "markdown": "# 每日科研进展简报：LLM Agents\n..."
}
```

## 4. Uploads

### `POST /uploads`

用途：

- 上传研究进展文档并写入公共向量库。

请求类型：

- `multipart/form-data`

表单字段：

- `file`: 必填，支持 `md`、`txt`、`pdf`、`docx`、`png`、`jpg`、`jpeg`、`webp`、`bmp`
- `title`: 可选
- `description`: 可选
- `visibility`: 可选，当前推荐固定为 `public`

返回示例：

```json
{
  "id": "uuid",
  "title": "My Note",
  "description": "Weekly research update",
  "file_path": "storage/uploads/xxxx.md",
  "file_type": "md",
  "visibility": "public"
}
```

### `GET /uploads`

用途：

- 获取上传文档列表。

## 5. Search

### `POST /search`

用途：

- 对公共研究进展做语义检索。

请求体：

```json
{
  "query": "LLM agent retrieval workflow",
  "limit": 5
}
```

### `POST /chat`

用途：

- 基于公共向量库做 RAG 问答。

请求体：

```json
{
  "question": "总结一下当前公共库里和 LLM agent 检索相关的进展",
  "limit": 5
}
```

返回示例：

```json
{
  "answer": "当前公共库里与 LLM agent 检索相关的内容主要集中在 ... [1][2]",
  "sources": [
    {
      "document_id": "uuid",
      "chunk_id": "uuid",
      "title": "Sample Progress",
      "content": "Implemented a retrieval workflow...",
      "score": 0.89,
      "metadata": {
        "visibility": "public",
        "title": "Sample Progress"
      }
    }
  ]
}
```

## 6. Agent SSE

Agent 当前支持：

- 日报生成
- 公共库语义检索
- 公共库 RAG 问答
- 上传文本笔记
- 上传图片并在后续工具调用中使用图片路径
- 读取报告内容
- 发送邮件
- 调用 SAM 图像分割工具
- 调用本地 MCP 工具

### `POST /agent/chat/stream`

用途：

- 使用 JSON 请求体发起 SSE 对话。

请求头：

```text
Accept: text/event-stream
Content-Type: application/json
```

请求体：

```json
{
  "messages": [
    {
      "role": "user",
      "content": "帮我总结最近的 LLM agent 检索进展"
    }
  ],
  "max_steps": 6,
  "search_limit": 5,
  "tool_limit": 10
}
```

字段说明：

- `messages`: 聊天历史，角色仅支持 `system`、`user`、`assistant`
- `max_steps`: Agent 最多推理轮数
- `search_limit`: 预留字段，前端可继续透传
- `tool_limit`: 预留字段，前端可继续透传

### `POST /agent/chat/stream-with-files`

用途：

- 使用多部分表单上传文件并发起 SSE 对话。
- 文件会先进入上传链路并写入向量库，然后再把文件元信息注入 Agent 上下文。

请求类型：

- `multipart/form-data`

表单字段：

- `payload`: JSON 字符串，对应 `AgentChatRequest`
- `files`: 一个或多个文件

前端示例：

```js
const form = new FormData();
form.append(
  "payload",
  JSON.stringify({
    messages: [{ role: "user", content: "结合我上传的文件给出总结" }],
    max_steps: 6,
    search_limit: 5,
    tool_limit: 10
  })
);
for (const file of files) {
  form.append("files", file);
}

fetch("/agent/chat/stream-with-files", {
  method: "POST",
  headers: { Accept: "text/event-stream" },
  body: form
});
```

### SSE 事件格式

服务端会持续输出如下格式：

```text
event: step
data: {"step":1}
```

当前可能出现的事件：

- `started`: 对话开始
- `rewrite`: 请求重写阶段的结果
- `context`: 当前轮上传文件的上下文信息
- `step`: Agent 进入新一轮推理
- `message`: 模型输出中间或最终文本
- `tool_call`: 模型准备调用某个工具
- `tool_result`: 工具执行结果
- `done`: 对话结束
- `error`: 出错或达到最大步数

`context` 事件示例：

```json
{
  "uploaded_documents": [
    {
      "id": "uuid",
      "title": "paper-note.md",
      "description": "agent chat attachment",
      "file_path": "storage/uploads/xxx.md",
      "file_type": "md",
      "visibility": "public"
    }
  ]
}
```

如果使用带文件版本：

### `POST /agent/chat/stream-with-files`

用途：

- 以 `multipart/form-data` 发起 SSE 对话，同时上传文档或图片。
- 图片上传后，Agent 会拿到本地绝对路径，可进一步调用 `segment_image_with_sam` 工具。

表单字段：

- `payload`: 必填，JSON 字符串，结构与 `/agent/chat/stream` 相同
- `files`: 可重复上传，支持文档与图片

## 7. Vision

### `POST /vision/sam-segment`

用途：

- 调用本地 SAM3 模型，对单张图片执行文本驱动分割。
- 可用于前端直连测试，也可作为 Agent 工具能力的独立接口。

请求类型：

- `multipart/form-data`

表单字段：

- `instruction`: 必填，分割要求，例如 `segment the person with red clothes`
- `image_path`: 可选，本机图片绝对路径；与 `file` 二选一
- `file`: 可选，直接上传图片；与 `image_path` 二选一
- `output_name`: 可选，结果目录名提示
- `confidence_threshold`: 可选，默认走 runtime-config 中的 `sam.confidence_threshold`
- `top_k`: 可选，默认走 runtime-config 中的 `sam.top_k`

返回示例：

```json
{
  "ok": true,
  "message": "ok",
  "prompt": "segment the red car",
  "image_path": "/mnt/hdd/cjt/ky/storage/uploads/demo.png",
  "mask_path": "/mnt/hdd/cjt/ky/storage/sam_outputs/20260417-130000-red-car-xxxx/mask.png",
  "overlay_path": "/mnt/hdd/cjt/ky/storage/sam_outputs/20260417-130000-red-car-xxxx/overlay.png",
  "output_dir": "/mnt/hdd/cjt/ky/storage/sam_outputs/20260417-130000-red-car-xxxx",
  "device": "cuda",
  "confidence_threshold": 0.5,
  "top_k": 3,
  "detection_count": 1,
  "detections": [
    {
      "index": 1,
      "score": 0.9132,
      "box": [33.5, 51.2, 420.7, 301.4],
      "area_pixels": 58231
    }
  ]
}
```

## 8. Runtime Config 补充

`GET /runtime-config` 与 `POST /runtime-config` 里新增了 `sam` 配置段，前端可据此做可视化配置：

```json
{
  "sam": {
    "enabled": false,
    "python_executable": "",
    "project_root": "/mnt/hdd/cjt/3dgs/SAM3Test",
    "checkpoint_path": "/mnt/hdd/cjt/3dgs/SAM3Test/checkpoints/sam3.pt",
    "bpe_path": null,
    "output_dir": "./storage/sam_outputs",
    "device": "cuda",
    "confidence_threshold": 0.5,
    "top_k": 5,
    "timeout_seconds": 600
  }
}
```

说明：

- `python_executable` 应填写装好 `torch`、`torchvision`、`sam3` 依赖的独立 Python 路径
- `enabled=true` 后，接口与 Agent 工具才可正常调用

`rewrite` 事件示例：

```json
{
  "enabled": true,
  "rewritten_query": "请围绕 3dgs 主题，检索最近科研进展并总结值得关注的方法与实验趋势。",
  "reasoning_focus": ["优先近期论文", "关注方法创新", "提炼实验表现"]
}
```

## 7. Email

邮件模块当前已经实现，但需要用户在 `.env` 中填写 SMTP 配置后才会真正发送。

建议配置项：

```env
EMAIL_ENABLED=true
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASSWORD=your-password
SMTP_USE_TLS=true
SMTP_STARTTLS=false
EMAIL_FROM=your-email@example.com
EMAIL_TO=default-recipient@example.com
```

### `GET /email/config-status`

用途：

- 获取当前邮件配置状态。

返回示例：

```json
{
  "configured": false,
  "message": "SMTP 未完成配置，缺少或仍为默认值: EMAIL_ENABLED, SMTP_HOST, SMTP_USER, SMTP_PASSWORD, EMAIL_FROM",
  "email_enabled": false,
  "smtp_host": "smtp.example.com",
  "smtp_port": 465,
  "email_from": "your-email@example.com",
  "default_recipient": "your-email@example.com"
}
```

### `POST /email/send`

用途：

- 发送普通文本或 Markdown 邮件。

请求体：

```json
{
  "subject": "科研进展测试邮件",
  "plain_text": "纯文本正文",
  "markdown_text": "# 测试邮件\n\n这里是 Markdown 正文",
  "recipients": ["name@example.com"]
}
```

### `POST /email/send-report`

用途：

- 按 `report_id` 发送已有日报。

请求体：

```json
{
  "report_id": "uuid",
  "subject": "可选覆盖主题",
  "recipients": ["name@example.com"]
}
```

## 8. Runtime Config

### `GET /runtime-config`

用途：

- 获取前端可编辑的运行时配置。
- 包含聊天模型列表、向量模型列表、本地 MCP 启动方式、定时任务配置。

返回示例：

```json
{
  "selected_chat_model": "gpt-4o-mini",
  "selected_embedding_model": "text-embedding-3-small",
  "chat_model_options": [
    {"id": "gpt-4o-mini", "label": "gpt-4o-mini", "kind": "chat", "enabled": true}
  ],
  "embedding_model_options": [
    {
      "id": "text-embedding-3-small",
      "label": "text-embedding-3-small",
      "kind": "embedding",
      "enabled": true
    }
  ],
  "mcp_servers": [
    {
      "enabled": true,
      "name": "ky-local-tools",
      "transport": "stdio",
      "command": ".venv/bin/python",
      "args": ["app/integrations/mcp/local_server.py"],
      "cwd": "."
    }
  ],
  "scheduler": {
    "enabled": true,
    "topic_names": ["3dgs", "llm_agents"],
    "daily_report_time": "08:00",
    "send_email": true,
    "email_recipients": ["name@example.com"]
  }
}
```

### `POST /runtime-config`

用途：

- 覆盖保存运行时配置。
- 保存后会自动刷新后端 scheduler。
- 聊天模型、向量模型和 MCP 启动配置将立即生效。

注意：

- 当前为单机版实现，配置落地到 `storage/runtime_config.json`
- 定时日报生成后会自动写入公共向量库，并可按 scheduler 配置自动发邮件
- `daily_report_system_prompt_suffix` 可用于设置全局日报附加提示词
- `enable_query_rewrite` 和 `selected_rewrite_model` 用于配置 Agent 前置重写阶段

## 9. 当前 Agent 可调用工具说明

当前后端已注册的核心工具包括：

- `list_topics`
- `semantic_search_public_progress`
- `rag_answer_public_progress`
- `run_daily_report`
- `list_reports`
- `get_report_content`
- `upload_research_note`
- `list_uploads`
- `send_markdown_email`
- `send_report_email`
- `send_plain_email`
- `mcp_get_current_time`
- `mcp_summarize_text_stats`
- `mcp_extract_keywords_local`
- `mcp_read_local_markdown_excerpt`

其中 MCP 工具来自本地 stdio MCP server，不需要额外申请外部 API。

## 10. 前端接入建议

- 对于 SSE，建议使用 `EventSource` 替代方案或 `fetch + ReadableStream` 逐行解析。
- 如果聊天需要附带文件，优先调用 `/agent/chat/stream-with-files`。
- 邮件相关按钮建议先显示 `/email/config-status` 的结果，未配置时给用户明确提示。
- 模型选择、MCP 配置、定时任务推荐统一走 `/runtime-config`
- 若使用 VS Code Remote，至少转发：
  - API: `8000`
  - Streamlit: `8501`
