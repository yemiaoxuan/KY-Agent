# 科研进展 Agent 项目搭建参考

## 1. 项目定位

本项目是一个个人使用优先的科研进展收集与共享检索系统。系统每天早晨自动收集用户指定领域的 arXiv 科研进展，使用 LangChain / LangGraph 进行筛选、摘要和报告生成，最终将 Markdown 科研简报通过 Email 推送给用户。

除自动推送外，系统还允许用户上传自己的研究进展，默认作为 public 内容进入公共向量数据库。后续可基于公共向量库进行语义检索、RAG 问答、研究方向匹配和科研协作对接。

## 2. 当前已确认决策

| 项目 | 决策 |
| --- | --- |
| 使用场景 | 先做个人使用，保留多用户扩展能力 |
| 推送渠道 | Email |
| 科研来源 | 第一版优先 arXiv |
| 向量库 | PostgreSQL + pgvector |
| 当前环境 | pgvector 暂未安装，搭建时需要处理 |
| LLM | 使用镜像站模型接口，优先兼容 OpenAI SDK 格式 |
| Embedding | 使用镜像站 embedding 模型，优先兼容 OpenAI SDK 格式 |
| 上传内容权限 | 默认 public |
| 报告格式 | Markdown |
| Agent 框架 | LangChain + LangGraph |
| 后端 | Python + FastAPI |
| 定时任务 | MVP 先用 APScheduler，后续可换 Celery Beat |
| 前端 | MVP 可先用 Streamlit 或简单 FastAPI 页面，后续再换 Next.js |

## 3. MVP 目标

第一阶段目标是跑通一个完整闭环：

1. 用户在配置文件或页面中定义研究领域、关键词、排除词和推送时间。
2. 系统定时从 arXiv 获取相关论文。
3. Agent 对论文进行去重、相关性判断、分类和摘要。
4. 系统生成 Markdown 格式的每日科研简报。
5. 系统通过 Email 将报告发送给用户。
6. 用户可以上传 Markdown、TXT 或 PDF 格式的研究进展。
7. 上传内容被抽取文本、切分、生成 embedding，并写入 pgvector。
8. 用户可以基于公共向量库做语义检索和 RAG 问答。

暂不优先实现：

1. 完整多用户权限系统。
2. 复杂团队空间。
3. 多渠道推送。
4. 复杂论文全文抓取。
5. 自动登录第三方平台。
6. 大规模分布式任务队列。

## 4. 推荐技术栈

| 层级 | 技术 |
| --- | --- |
| 语言 | Python 3.11+ |
| Web API | FastAPI |
| Agent / Chain | LangChain |
| 工作流编排 | LangGraph |
| 数据库 | PostgreSQL |
| 向量扩展 | pgvector |
| ORM | SQLAlchemy 2.x |
| Migration | Alembic |
| 定时任务 | APScheduler |
| 文件解析 | pypdf, python-docx, markdown/plain text parser |
| 邮件 | aiosmtplib 或 smtplib |
| 配置 | pydantic-settings |
| 日志 | structlog 或标准 logging |
| 测试 | pytest |
| 包管理 | uv 或 poetry，优先 uv |

## 5. 推荐目录结构

```text
ky/
  app/
    api/
      routes/
        health.py
        reports.py
        uploads.py
        search.py
      deps.py
      main.py
    agents/
      core/
        agent_prompts.py
        context_prompts.py
        profiles.py
        tool_routes.py
      graphs/
        chat_graph.py
        daily_research_graph.py
        ingestion_graph.py
        report_chain.py
        rag_agent.py
      toolkit.py
    core/
      config.py
      logging.py
      scheduler.py
    db/
      base.py
      session.py
      repositories/
    models/
      user.py
      topic.py
      paper.py
      report.py
      document.py
      chunk.py
      agent_run.py
    schemas/
      topic.py
      report.py
      upload.py
      search.py
    services/
      arxiv_service.py
      email_service.py
      report_service.py
      upload_service.py
      embedding_service.py
      vector_service.py
      search_service.py
    tools/
      arxiv_tool.py
      email_tool.py
      file_extractors.py
    workers/
      daily_jobs.py
      ingestion_jobs.py
  frontend/
    streamlit_app.py
  storage/
    uploads/
    reports/
  migrations/
  tests/
  scripts/
    init_db.py
    run_daily_report.py
  docker-compose.yml
  pyproject.toml
  README.md
  .env.example
  codex.md
```

## 6. 配置设计

MVP 阶段可以先使用 `.env` 和一个 YAML/JSON 配置文件共同管理。

`.env` 示例：

```env
APP_ENV=local
DATABASE_URL=postgresql+psycopg://postgres:postgres@localhost:5432/ky

LLM_BASE_URL=https://your-mirror.example.com/v1
LLM_API_KEY=replace-me
LLM_MODEL=gpt-4o-mini

EMBEDDING_BASE_URL=https://your-mirror.example.com/v1
EMBEDDING_API_KEY=replace-me
EMBEDDING_MODEL=text-embedding-3-small

SMTP_HOST=smtp.example.com
SMTP_PORT=465
SMTP_USER=your-email@example.com
SMTP_PASSWORD=replace-me
EMAIL_FROM=your-email@example.com
EMAIL_TO=your-email@example.com

DAILY_REPORT_TIME=08:00
TIMEZONE=Asia/Shanghai
STORAGE_DIR=./storage
```

研究主题配置示例：

```yaml
topics:
  - name: llm_agents
    display_name: LLM Agents
    query: '("large language model" OR LLM) AND (agent OR agents OR multi-agent)'
    arxiv_categories:
      - cs.AI
      - cs.CL
      - cs.LG
    include_keywords:
      - agent
      - multi-agent
      - tool use
      - planning
      - reasoning
    exclude_keywords:
      - survey
    max_results: 30
    report_top_k: 10
```

## 7. 核心工作流

## 6.1 工具日志约定

从当前版本开始，所有 Agent tool 都应记录调用日志，便于排查“模型调用了工具但结果异常”这类问题。

约定如下：

1. 所有工具统一写入 `storage/tool_logs/`
2. 每次调用单独一个 JSON 文件，至少记录：
   - `timestamp`
   - `tool_name`
   - `args`
   - `result`
   - `error`
   - `extra`
3. 对有独立输出目录的工具，除了统一日志，还要在输出目录下写一份局部详细日志
4. `SAM` 工具的局部日志文件固定为：
   - `sam_call_log.json`
5. `SAM` 日志至少要包含：
   - 输入图片路径
   - instruction / prompt
   - threshold / top_k
   - 运行时 python / checkpoint / device
   - 实际子进程 command
   - stdout / stderr
   - returncode
   - 解析后的 JSON 结果
6. 以后新增工具时，默认先补日志，再补功能细节；避免前端只看到“没生效”但后端没有排查依据

### 7.1 每日科研简报工作流

推荐使用 LangGraph 实现，便于后续加入重试、人工审核和状态追踪。

```text
start
  -> load_topic_config
  -> search_arxiv
  -> normalize_papers
  -> deduplicate_papers
  -> score_relevance
  -> summarize_papers
  -> generate_markdown_report
  -> save_report
  -> send_email
  -> record_agent_run
end
```

各节点职责：

| 节点 | 职责 |
| --- | --- |
| `load_topic_config` | 读取用户订阅领域和关键词 |
| `search_arxiv` | 调用 arXiv API 搜索论文 |
| `normalize_papers` | 标准化标题、作者、摘要、链接、发布时间 |
| `deduplicate_papers` | 根据 arXiv ID、标题相似度去重 |
| `score_relevance` | 根据关键词和 LLM 判断相关性 |
| `summarize_papers` | 对单篇论文生成简短中文摘要 |
| `generate_markdown_report` | 汇总为完整 Markdown 报告 |
| `save_report` | 保存到 `storage/reports` 并写入数据库 |
| `send_email` | 发送 Email |
| `record_agent_run` | 记录成功、失败、耗时和错误信息 |

### 7.2 用户上传入库工作流

```text
start
  -> receive_upload
  -> save_original_file
  -> extract_text
  -> extract_metadata
  -> chunk_text
  -> create_embeddings
  -> write_vector_store
  -> write_document_metadata
  -> update_user_profile
end
```

默认权限：

```text
visibility = public
```

后续可以扩展为：

```text
public | private | group
```

### 7.3 RAG 检索问答工作流

```text
user_question
  -> classify_query_intent
  -> retrieve_relevant_chunks
  -> rerank_optional
  -> generate_answer_with_citations
  -> return_answer
```

第一版可以只检索用户上传的 public 内容。后续再把 arXiv 每日论文也写入向量库，支持外部论文和内部研究进展的混合检索。

## 8. 数据库模型草案

### 8.1 `topics`

保存研究方向配置。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `name` | string | 内部名称 |
| `display_name` | string | 展示名称 |
| `query` | text | arXiv 查询表达式 |
| `include_keywords` | jsonb | 包含关键词 |
| `exclude_keywords` | jsonb | 排除关键词 |
| `arxiv_categories` | jsonb | arXiv 分类 |
| `enabled` | boolean | 是否启用 |
| `created_at` | datetime | 创建时间 |

### 8.2 `external_papers`

保存 arXiv 论文元数据。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `source` | string | arxiv |
| `source_id` | string | arXiv ID |
| `title` | text | 标题 |
| `abstract` | text | 摘要 |
| `authors` | jsonb | 作者 |
| `categories` | jsonb | 分类 |
| `published_at` | datetime | 发布时间 |
| `updated_at` | datetime | 更新时间 |
| `url` | text | abs 页面 |
| `pdf_url` | text | PDF 链接 |
| `topic_id` | UUID | 关联 topic |
| `relevance_score` | float | 相关性评分 |
| `summary_zh` | text | 中文摘要 |

### 8.3 `daily_reports`

保存每日报告。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `topic_id` | UUID | 关联 topic |
| `title` | text | 报告标题 |
| `report_date` | date | 报告日期 |
| `markdown_path` | text | Markdown 文件路径 |
| `email_status` | string | pending / sent / failed |
| `created_at` | datetime | 创建时间 |

### 8.4 `uploaded_documents`

保存用户上传文档元数据。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `owner_id` | UUID | 第一版可使用默认本地用户 |
| `title` | text | 文档标题 |
| `description` | text | 用户描述 |
| `file_path` | text | 原始文件路径 |
| `file_type` | string | pdf / md / txt / docx |
| `visibility` | string | 默认 public |
| `metadata` | jsonb | LLM 抽取的结构化信息 |
| `created_at` | datetime | 上传时间 |

### 8.5 `document_chunks`

保存 chunk 元数据和向量引用。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `document_id` | UUID | 关联上传文档 |
| `chunk_index` | integer | chunk 序号 |
| `content` | text | chunk 文本 |
| `embedding` | vector | pgvector 字段 |
| `metadata` | jsonb | 检索元数据 |
| `created_at` | datetime | 创建时间 |

### 8.6 `agent_runs`

记录 Agent 执行历史。

| 字段 | 类型 | 说明 |
| --- | --- | --- |
| `id` | UUID | 主键 |
| `agent_name` | string | agent 名称 |
| `status` | string | running / success / failed |
| `input` | jsonb | 输入 |
| `output` | jsonb | 输出摘要 |
| `error` | text | 错误信息 |
| `started_at` | datetime | 开始时间 |
| `finished_at` | datetime | 结束时间 |

## 9. 向量库设计

第一版使用 pgvector，直接把 embedding 存在 `document_chunks.embedding` 字段中。

建议：

1. 使用 cosine distance。
2. 初期数据量小，可以先不建复杂索引。
3. 数据量上来后添加 HNSW 或 IVFFlat 索引。
4. embedding 维度必须与模型一致，例如 1536 或 3072。
5. 数据库迁移时不要硬编码未知维度，先根据选定 embedding 模型确定。

示例 SQL：

```sql
CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE document_chunks (
  id UUID PRIMARY KEY,
  document_id UUID NOT NULL,
  chunk_index INTEGER NOT NULL,
  content TEXT NOT NULL,
  embedding VECTOR(1536),
  metadata JSONB DEFAULT '{}',
  created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);

CREATE INDEX document_chunks_embedding_hnsw_idx
ON document_chunks
USING hnsw (embedding vector_cosine_ops);
```

如果本机暂时没有 pgvector，可以先使用两种 fallback：

1. Docker Compose 启动带 pgvector 的 PostgreSQL 镜像。
2. 临时使用 Chroma 或 FAISS 跑通流程，正式切回 pgvector。

优先方案是 Docker Compose：

```yaml
services:
  postgres:
    image: pgvector/pgvector:pg16
    environment:
      POSTGRES_DB: ky
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    ports:
      - "5432:5432"
    volumes:
      - postgres_data:/var/lib/postgresql/data

volumes:
  postgres_data:
```

## 10. arXiv 收集策略

第一版只使用 arXiv API，不抓取 PDF 全文。

检索参数建议：

| 参数 | 建议 |
| --- | --- |
| `search_query` | 由 topic query 和 category 组合 |
| `sortBy` | submittedDate |
| `sortOrder` | descending |
| `max_results` | 30 到 100 |
| 时间窗口 | 最近 1 到 3 天 |

去重规则：

1. 优先根据 arXiv ID 去重。
2. 如果 source_id 不同但标题高度相似，也认为重复。
3. 数据库中已出现过的论文不再重复推送，除非 updated_at 变化且用户配置允许更新提醒。

相关性评分：

```text
score = keyword_score * 0.4 + category_score * 0.2 + llm_score * 0.4
```

MVP 可以先简化为：

```text
score = keyword_score + llm_relevance_yes_no
```

## 11. Markdown 报告格式

生成报告时建议稳定使用以下结构，便于后续解析和前端展示。

```markdown
# 每日科研进展简报：{{topic_display_name}}

- 日期：{{date}}
- 数据源：arXiv
- 候选论文数：{{candidate_count}}
- 入选论文数：{{selected_count}}

## 今日概览

{{overview}}

## 重点论文

### 1. {{paper_title}}

- 作者：{{authors}}
- 发布时间：{{published_at}}
- arXiv：{{url}}
- PDF：{{pdf_url}}
- 相关性：{{relevance_reason}}

**一句话总结：** {{one_sentence_summary}}

**核心贡献：**
{{contributions}}

**可能局限：**
{{limitations}}

**为什么值得关注：**
{{why_it_matters}}

## 趋势观察

{{trend_observations}}

## 建议行动

{{action_items}}
```

## 12. Email 推送设计

MVP 可以直接发送 Markdown 文本，也可以转换为 HTML。

建议第一版：

1. 邮件标题：`[科研简报] {{topic_display_name}} - {{date}}`
2. 邮件正文：Markdown 转 HTML。
3. 同时附上原始 `.md` 文件。
4. 发送结果写入 `daily_reports.email_status`。

失败处理：

1. SMTP 失败时重试 2 次。
2. 最终失败时保留本地报告。
3. 错误写入 `agent_runs.error`。

## 13. 镜像站模型适配

为了兼容镜像站，模型调用层不要在业务代码中散落 SDK 调用，统一封装：

```text
app/services/llm_service.py
app/services/embedding_service.py
```

要求：

1. 支持 OpenAI-compatible `base_url`。
2. 支持从 `.env` 读取 API key、base URL、model。
3. 支持超时和重试。
4. 业务代码只调用统一 service，不直接创建 OpenAI client。

LangChain 示例方向：

```python
from langchain_openai import ChatOpenAI, OpenAIEmbeddings

llm = ChatOpenAI(
    model=settings.llm_model,
    api_key=settings.llm_api_key,
    base_url=settings.llm_base_url,
)

embeddings = OpenAIEmbeddings(
    model=settings.embedding_model,
    api_key=settings.embedding_api_key,
    base_url=settings.embedding_base_url,
)
```

## 14. 初始 API 设计

### Health

```text
GET /health
```

### Topic

```text
GET /topics
POST /topics
PATCH /topics/{topic_id}
```

### Report

```text
POST /reports/run-daily
GET /reports
GET /reports/{report_id}
```

### Upload

```text
POST /uploads
GET /uploads
GET /uploads/{document_id}
```

### Search

```text
POST /search
POST /chat
```

## 15. 搭建顺序建议

建议按以下顺序实现，避免一开始复杂化：

1. 初始化 Python 项目、FastAPI、配置系统和日志。
2. 添加 Docker Compose PostgreSQL + pgvector。
3. 建立 SQLAlchemy models 和 Alembic migration。
4. 实现 arXiv 搜索 service。
5. 实现 LLM service 和论文摘要 chain。
6. 实现 Markdown report service。
7. 实现 Email service。
8. 实现 LangGraph daily research workflow。
9. 添加 APScheduler 定时任务。
10. 实现文件上传和文本抽取。
11. 实现 embedding 和 pgvector 写入。
12. 实现语义检索 API。
13. 实现简单 RAG 问答。
14. 添加 Streamlit 简单页面。
15. 补测试和 README。

## 16. 风险与注意事项

1. arXiv API 有访问频率限制，需要加缓存和重试。
2. 镜像站模型可能不稳定，需要统一设置 timeout、retry 和错误记录。
3. pgvector 维度必须与 embedding 模型一致，切换 embedding 模型前要处理旧数据。
4. 默认 public 会带来隐私风险，即使个人使用，也应在界面和文档中明确提示。
5. LLM 摘要可能 hallucinate，报告中必须保留 arXiv 原文链接。
6. Email 推送失败不能影响报告保存。
7. 每日任务要记录 agent run，方便排查失败原因。
8. 初期不要过度设计多用户权限，但数据库字段要预留 `owner_id` 和 `visibility`。

## 17. 后续扩展方向

1. 支持 PubMed、OpenAlex、Semantic Scholar。
2. 将每日 arXiv 论文也写入向量库，支持历史趋势检索。
3. 增加用户研究画像和相似研究方向推荐。
4. 增加团队空间和权限管理。
5. 增加人工审核节点，发送前可编辑报告。
6. 接入 LangSmith 或自建 trace dashboard。
7. 增加 Web UI，支持报告浏览、收藏、反馈和检索。
8. 支持飞书、企业微信、Telegram 等推送渠道。
9. 增加论文 PDF 全文解析和图表提取。
10. 增加每周/月度趋势报告。
