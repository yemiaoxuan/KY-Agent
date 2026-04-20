from app.agents.graphs.daily_research_graph import run_daily_research
from app.db.session import SessionLocal


def run_once(topic_name: str | None = None, send_email: bool = True) -> list[dict]:
    db = SessionLocal()
    try:
        return [
            result.model_dump(mode="json")
            for result in run_daily_research(db, topic_name=topic_name, send_email=send_email)
        ]
    finally:
        db.close()
