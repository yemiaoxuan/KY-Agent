# KY Research Agent

个人科研进展 Agent：每天从 arXiv 收集指定领域的新论文，生成 Markdown 简报并通过 Email 推送；同时支持上传个人研究进展到 public pgvector 向量库，用于语义检索和 RAG 问答。

## 当前 MVP 能力

- FastAPI 后端。
- LangGraph 每日 arXiv 简报工作流。
- arXiv 检索、关键词相关性评分、LLM 摘要降级 fallback。
- Markdown 报告保存到 `storage/reports`。
- Email 推送，未配置 SMTP 时自动跳过。
- Markdown、TXT、PDF、DOCX 上传。
- 上传内容抽取、切分、embedding、写入 pgvector。
- public 向量检索和简单 RAG 问答。
- APScheduler 每日定时任务。
- Docker Compose PostgreSQL + pgvector。

## 快速开始

```bash
cd /mnt/hdd/cjt/ky
cp .env.example .env
UV_DEFAULT_INDEX=https://pypi.tuna.tsinghua.edu.cn/simple UV_HTTP_TIMEOUT=180 uv sync --extra dev
./scripts/pg_start.sh
./.venv/bin/alembic upgrade head
./.venv/bin/uvicorn app.api.main:app --host 0.0.0.0 --port 8000 --reload
```

如果清华源不稳定，可以换成阿里云源：

```bash
UV_DEFAULT_INDEX=https://mirrors.aliyun.com/pypi/simple UV_HTTP_TIMEOUT=180 uv sync --extra dev
```

## 用户态 PostgreSQL

这个项目现在已经在用户目录安装好了本地 PostgreSQL 和 `psql`，不依赖系统 root 和 Docker。

环境位置：

```text
/mnt/hdd/cjt/local/mamba/envs/pg-local
```

数据目录：

```text
/mnt/hdd/cjt/local/pgsql/data
```

日志文件：

```text
/mnt/hdd/cjt/local/pgsql/logs/postgres.log
```

常用命令：

```bash
cd /mnt/hdd/cjt/ky
./scripts/pg_start.sh
./scripts/pg_status.sh
./scripts/pg_psql.sh
./scripts/pg_stop.sh
```

打开 API 文档：

```text
http://localhost:8000/docs
```

## 手动运行每日简报

不发送邮件，仅生成报告：

```bash
uv run python scripts/run_daily_report.py --topic llm_agents --no-email
```

报告会写入：

```text
storage/reports/llm_agents/YYYY-MM-DD.md
```

## 配置研究主题

编辑：

```text
configs/topics.yaml
```

修改 `query`、`arxiv_categories`、`include_keywords`、`exclude_keywords` 后，调用：

```bash
curl -X POST http://localhost:8000/topics/sync
```

## 配置镜像站模型

在 `.env` 中设置：

```env
LLM_BASE_URL=https://your-mirror.example.com/v1
LLM_API_KEY=replace-me
LLM_MODEL=gpt-4o-mini

EMBEDDING_BASE_URL=https://your-mirror.example.com/v1
EMBEDDING_API_KEY=replace-me
EMBEDDING_MODEL=text-embedding-3-small
EMBEDDING_DIMENSIONS=1536
```

你实际需要填写的就是：

- `LLM_BASE_URL`: 你的模型镜像站 API 地址
- `LLM_API_KEY`: 你的模型 key
- `LLM_MODEL`: 你的聊天模型名
- `EMBEDDING_BASE_URL`: embedding 服务地址
- `EMBEDDING_API_KEY`: embedding key
- `EMBEDDING_MODEL`: embedding 模型名
- `EMBEDDING_DIMENSIONS`: 向量维度

接口按 OpenAI-compatible 方式封装在：

```text
app/services/llm_service.py
app/services/embedding_service.py
```

如果 API key 仍为 `replace-me`，系统会使用 fallback：

- 论文摘要使用 arXiv 摘要截断。
- embedding 使用零向量，仅适合项目搭建验证，不适合真实检索。

## 配置 Email

在 `.env` 中设置：

```env
SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASSWORD=replace-me
SMTP_USE_TLS=true
EMAIL_FROM=your-email@example.com
EMAIL_TO=your-email@example.com
```

如果 `SMTP_PASSWORD=replace-me`，系统会跳过邮件发送，但仍保存 Markdown 报告。

## 常用 API

```text
GET  /health
GET  /topics
POST /topics/sync
POST /reports/run-daily
GET  /reports
POST /uploads
POST /search
POST /chat
```

## 开发检查

```bash
uv run pytest
uv run ruff check .
```

## 可选 Streamlit 页面

前端原型依赖较大，按需安装：

```bash
uv sync --extra dev --extra frontend
uv run streamlit run frontend/streamlit_app.py
```

## VS Code Remote 端口转发

如果你通过 VS Code Remote SSH 连接到 `cjt`，想在本地浏览器里访问服务，需要转发端口：

- FastAPI: `8000`
- Streamlit: `8501`
- PostgreSQL 如果你想在本地数据库工具里连：`5432`

常见访问地址：

```text
FastAPI docs: http://127.0.0.1:8000/docs
FastAPI health: http://127.0.0.1:8000/health
Streamlit: http://127.0.0.1:8501
```

## 注意事项

- 本项目默认上传内容为 `public`，个人使用阶段也不要上传敏感材料。
- pgvector 的 embedding 维度必须与 `.env` 中的 `EMBEDDING_DIMENSIONS` 一致。
- 切换 embedding 模型后，已有向量需要重建。
- arXiv API 有频率限制，不要高频反复运行。
