from __future__ import annotations

SEARCH_TOOL_NAMES = {"semantic_search_public_progress"}
ANSWER_TOOL_NAMES = {"rag_answer_public_progress"}
REPORT_TOOL_NAMES = {"list_reports", "get_report_content"}
EMAIL_TOOL_NAMES = {"send_markdown_email", "send_report_email", "send_plain_email"}
DAILY_TOOL_NAMES = {"run_daily_report"}

TOOL_ROUTE_ORDER = ("retrieve", "answer", "report", "email", "daily", "tools")
ROUTER_ROUTE_ORDER = ("delegate",)

TOOL_ROUTE_BY_NAME = {
    **{name: "retrieve" for name in SEARCH_TOOL_NAMES},
    **{name: "answer" for name in ANSWER_TOOL_NAMES},
    **{name: "report" for name in REPORT_TOOL_NAMES},
    **{name: "email" for name in EMAIL_TOOL_NAMES},
    **{name: "daily" for name in DAILY_TOOL_NAMES},
}
