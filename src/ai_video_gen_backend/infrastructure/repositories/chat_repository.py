from __future__ import annotations

from datetime import UTC, datetime
from typing import cast
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.orm import Session

from ai_video_gen_backend.domain.chat import ChatImageInput, ChatMessage, ChatRole, ChatThread
from ai_video_gen_backend.infrastructure.db.models import ChatMessageModel, ChatThreadModel


class ChatSqlRepository:
    def __init__(self, session: Session) -> None:
        self._session = session

    def create_thread(self) -> ChatThread:
        model = ChatThreadModel()
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_thread_domain(model)

    def get_thread_by_id(self, thread_id: UUID) -> ChatThread | None:
        model = self._session.get(ChatThreadModel, thread_id)
        return self._to_thread_domain(model) if model is not None else None

    def list_messages(self, thread_id: UUID) -> list[ChatMessage]:
        stmt = (
            select(ChatMessageModel)
            .where(ChatMessageModel.thread_id == thread_id)
            .order_by(ChatMessageModel.created_at.asc(), ChatMessageModel.id.asc())
        )
        models = self._session.execute(stmt).scalars().all()
        return [self._to_message_domain(model) for model in models]

    def create_message(
        self,
        *,
        thread_id: UUID,
        role: ChatRole,
        text: str,
        image_urls: list[str],
    ) -> ChatMessage:
        model = ChatMessageModel(
            thread_id=thread_id,
            role=role,
            text=text,
            images_json=image_urls,
            created_at=datetime.now(UTC),
        )
        self._session.add(model)
        self._session.commit()
        self._session.refresh(model)
        return self._to_message_domain(model)

    def _to_thread_domain(self, model: ChatThreadModel) -> ChatThread:
        return ChatThread(id=model.id, created_at=model.created_at, updated_at=model.updated_at)

    def _to_message_domain(self, model: ChatMessageModel) -> ChatMessage:
        images = [ChatImageInput(url=url) for url in self._read_image_urls(model)]
        return ChatMessage(
            id=model.id,
            thread_id=model.thread_id,
            role=cast(ChatRole, model.role),
            text=model.text,
            images=images,
            created_at=model.created_at,
        )

    def _read_image_urls(self, model: ChatMessageModel) -> list[str]:
        image_urls: list[str] = []
        for value in model.images_json:
            if isinstance(value, str):
                image_urls.append(value)
        return image_urls
