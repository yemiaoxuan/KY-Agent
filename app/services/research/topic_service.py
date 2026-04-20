from __future__ import annotations

from pathlib import Path

import yaml
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.models.topic import Topic
from app.schemas.topic import TopicConfig, TopicConfigFile, TopicCreate, TopicUpdate


def load_topic_config(path: Path | None = None) -> list[TopicConfig]:
    settings = get_settings()
    config_path = path or settings.topics_config_path
    if not config_path.exists():
        return []
    payload = yaml.safe_load(config_path.read_text(encoding="utf-8")) or {}
    return TopicConfigFile.model_validate(payload).topics


def import_topics_from_config(db: Session) -> list[Topic]:
    topics: list[Topic] = []
    for topic_config in load_topic_config():
        topic = db.scalar(select(Topic).where(Topic.name == topic_config.name))
        values = topic_config.model_dump()
        if topic is None:
            topic = Topic(**values)
            db.add(topic)
        else:
            for key, value in values.items():
                setattr(topic, key, value)
        topics.append(topic)
    db.commit()
    for topic in topics:
        db.refresh(topic)
    return topics


def list_topics(db: Session, enabled_only: bool = False) -> list[Topic]:
    stmt = select(Topic).where(Topic.name != "").order_by(Topic.name)
    if enabled_only:
        stmt = stmt.where(Topic.enabled.is_(True))
    return list(db.scalars(stmt))


def list_enabled_topics(db: Session) -> list[Topic]:
    return list_topics(db, enabled_only=True)


def get_topic_by_name(db: Session, topic_name: str) -> Topic | None:
    return db.scalar(select(Topic).where(Topic.name == topic_name))


def create_topic(db: Session, payload: TopicCreate) -> Topic:
    existing = get_topic_by_name(db, payload.name)
    if existing is not None:
        raise ValueError(f"主题标识已存在: {payload.name}")
    topic = Topic(**payload.model_dump())
    db.add(topic)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"主题创建失败，可能是名称重复: {payload.name}") from exc
    db.refresh(topic)
    return topic


def update_topic(db: Session, topic_name: str, payload: TopicUpdate) -> Topic | None:
    topic = get_topic_by_name(db, topic_name)
    if topic is None:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(topic, key, value)
    try:
        db.commit()
    except IntegrityError as exc:
        db.rollback()
        raise ValueError(f"主题更新失败: {topic_name}") from exc
    db.refresh(topic)
    return topic


def delete_topic(db: Session, topic_name: str) -> bool:
    topic = get_topic_by_name(db, topic_name)
    if topic is None:
        return False
    db.delete(topic)
    db.commit()
    return True


def cleanup_invalid_topics(db: Session) -> int:
    invalid_topics = db.scalars(select(Topic).where(Topic.name == "")).all()
    count = len(invalid_topics)
    for topic in invalid_topics:
        db.delete(topic)
    if count:
        db.commit()
    return count
