from fastapi import APIRouter, HTTPException

from app.api.deps import DbSession
from app.schemas.topic import TopicCreate, TopicRead, TopicUpdate
from app.services.research.topic_service import (
    cleanup_invalid_topics,
    create_topic,
    delete_topic,
    get_topic_by_name,
    import_topics_from_config,
    list_topics,
    update_topic,
)

router = APIRouter(prefix="/topics", tags=["topics"])


@router.get("", response_model=list[TopicRead])
def list_topics_route(db: DbSession) -> list[TopicRead]:
    return [
        TopicRead.model_validate(topic, from_attributes=True)
        for topic in list_topics(db, enabled_only=False)
    ]


@router.post("/sync", response_model=list[TopicRead])
def sync_topics(db: DbSession) -> list[TopicRead]:
    return [
        TopicRead.model_validate(topic, from_attributes=True)
        for topic in import_topics_from_config(db)
    ]


@router.get("/{topic_name}", response_model=TopicRead | dict)
def get_topic_route(topic_name: str, db: DbSession) -> TopicRead | dict:
    topic = get_topic_by_name(db, topic_name)
    if topic is None:
        return {"error": "topic not found"}
    return TopicRead.model_validate(topic, from_attributes=True)


@router.post("", response_model=TopicRead)
def create_topic_route(request: TopicCreate, db: DbSession) -> TopicRead:
    try:
        topic = create_topic(db, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return TopicRead.model_validate(topic, from_attributes=True)


@router.put("/{topic_name}", response_model=TopicRead | dict)
def update_topic_route(topic_name: str, request: TopicUpdate, db: DbSession) -> TopicRead | dict:
    try:
        topic = update_topic(db, topic_name, request)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    if topic is None:
        return {"error": "topic not found"}
    return TopicRead.model_validate(topic, from_attributes=True)


@router.delete("/{topic_name}")
def delete_topic_route(topic_name: str, db: DbSession) -> dict:
    deleted = delete_topic(db, topic_name)
    if not deleted:
        return {"ok": False, "message": "topic not found"}
    return {"ok": True, "message": f"deleted topic {topic_name}"}


@router.post("/cleanup-invalid")
def cleanup_invalid_topics_route(db: DbSession) -> dict:
    deleted_count = cleanup_invalid_topics(db)
    return {"ok": True, "deleted_count": deleted_count}
