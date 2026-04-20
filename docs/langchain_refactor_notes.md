# LangChain Refactor Notes

This project keeps the existing FastAPI interfaces stable while moving agent and RAG internals onto LangChain/LangGraph primitives.

## Public Interfaces

- `/agent/chat/stream` and `/agent/chat/stream-with-files` keep the same SSE event contract.
- `/search` returns semantic search results from the public uploaded-document corpus.
- `/chat` runs RAG over the same public corpus.
- `/uploads` still persists uploaded files to PostgreSQL/pgvector through the upload service.

## Agent Boundaries

- `app/agents/core/` owns reusable agent definitions that are not tied to one business graph.
- `app/agents/core/context_prompts.py` owns user-session context blocks for selected topics, current uploads, and historical attachments.
- `app/agents/core/agent_prompts.py` owns router/specialist orchestration prompts.
- `app/agents/core/profiles.py` owns specialist agent profiles and tool-set ownership.
- `app/agents/core/tool_routes.py` owns shared tool route constants.
- `app/agents/graphs/chat_graph.py` owns the chat LangGraph state machine, router/specialist orchestration, delegate tool execution, and LLM binding.
- `app/agents/graphs/daily_research_graph.py` owns the daily arXiv research report workflow.
- `app/services/agent/chat_service.py` only translates API requests into LangChain messages and streams LangGraph updates as SSE events.
- `app/agents/toolkit.py` owns tool definitions and adapts application services to LangChain `StructuredTool`.

Tool failures are converted into `ToolMessage(status="error")`. If a DB-backed tool raises, the graph executor rolls back the SQLAlchemy session before continuing.

## RAG And PGVector

- `app/services/langchain_vector_store.py` is a LangChain `VectorStore` adapter over the existing `uploaded_documents` and `document_chunks` tables.
- The database schema remains SQLAlchemy + pgvector, so existing Alembic migrations and PostgreSQL operations keep working.
- `upsert_document()` now reuses an existing row with the same `file_path` and `file_type`, replacing chunks instead of creating duplicate documents.
- Embedding count mismatches are rejected before writing chunks, preventing partial or silent data loss.
- Write failures call `Session.rollback()` so the request session does not remain in a failed transaction.

## Async Boundaries

- FastAPI email routes keep using async email functions directly.
- LangChain tools are synchronous, so they use `send_email_sync()` / `send_markdown_email_sync()`.
- The sync bridge is safe inside an already-running event loop, which prevents `asyncio.run() cannot be called from a running event loop` errors in SSE agent calls.
