from __future__ import annotations

from fastapi import APIRouter, Depends

from ai_video_gen_backend.application.chat import (
    ChatThreadNotFoundError,
    InvalidChatMessagesError,
    SendChatMessageUseCase,
)
from ai_video_gen_backend.domain.chat import ChatImageInput, ChatInputMessage
from ai_video_gen_backend.presentation.api.dependencies import get_send_chat_message_use_case
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    ChatRequest,
    ChatResponse,
    ErrorEnvelope,
)

router = APIRouter(tags=['chat'])


@router.post('/chat', response_model=ChatResponse, responses={404: {'model': ErrorEnvelope}})
def post_chat(
    request: ChatRequest,
    use_case: SendChatMessageUseCase = Depends(get_send_chat_message_use_case),
) -> ChatResponse:
    try:
        result = use_case.execute(
            thread_id=request.thread_id,
            messages=[
                ChatInputMessage(
                    role=message.role,
                    text=message.text,
                    images=[ChatImageInput(url=str(image.url)) for image in message.images],
                )
                for message in request.messages
            ],
        )
    except ChatThreadNotFoundError as exc:
        raise ApiError(
            status_code=404,
            code='thread_not_found',
            message='Chat thread not found',
        ) from exc
    except InvalidChatMessagesError as exc:
        raise ApiError(
            status_code=400,
            code='invalid_chat_messages',
            message='At least one user message is required',
        ) from exc

    return ChatResponse.from_domain(result)
