from __future__ import annotations

import json
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, Request
from fastapi.responses import StreamingResponse

from ai_video_gen_backend.application.chat import (
    ChatThreadNotFoundError,
    InvalidChatMessagesError,
    InvalidScreenplayChatContextError,
    ScreenplayAssistantRequiresStreamingError,
    SendChatMessageUseCase,
)
from ai_video_gen_backend.domain.chat import (
    ChatImageInput,
    ChatInputMessage,
    ChatModelPort,
    ChatStreamCancelledError,
    ChatThread,
    ScreenplayChatContext,
    ScreenplayChatContextError,
    SendChatResult,
)
from ai_video_gen_backend.domain.screenplay import Screenplay
from ai_video_gen_backend.infrastructure.db.session import get_session_factory
from ai_video_gen_backend.infrastructure.providers import (
    ChatWorkflowStreamOperation,
    LangGraphChatWorkflow,
)
from ai_video_gen_backend.infrastructure.repositories import (
    ChatSqlRepository,
    ScreenplaySqlRepository,
)
from ai_video_gen_backend.presentation.api.dependencies import (
    get_chat_model_provider,
    get_screenplay_langgraph_checkpointer,
    get_send_chat_message_use_case,
)
from ai_video_gen_backend.presentation.api.errors import ApiError
from ai_video_gen_backend.presentation.api.v1.schemas import (
    ChatRequest,
    ChatResponse,
    ChatStreamRequest,
    ErrorEnvelope,
)
from ai_video_gen_backend.presentation.api.v1.schemas.screenplay_schema import ScreenplayResponse

router = APIRouter(tags=['chat'])


@router.post('/chat', response_model=ChatResponse, responses={404: {'model': ErrorEnvelope}})
def post_chat(
    request: ChatRequest,
    use_case: SendChatMessageUseCase = Depends(get_send_chat_message_use_case),
) -> ChatResponse:
    result = _execute_chat_request(request=request, use_case=use_case)
    return ChatResponse.from_domain(result)


@router.post('/chat/stream')
def post_chat_stream(
    fastapi_request: Request,
    request: ChatStreamRequest,
    chat_model_provider: ChatModelPort = Depends(get_chat_model_provider),
    screenplay_checkpointer: object = Depends(get_screenplay_langgraph_checkpointer),
) -> StreamingResponse:
    if request.agent_type != 'screenplay_assistant':
        raise ApiError(
            status_code=400,
            code='invalid_agent_type',
            message='Only screenplay assistant is supported on /chat/stream',
        )

    async def _stream() -> AsyncIterator[str]:
        session = get_session_factory()()
        cancel_state = {'cancelled': False}
        try:
            chat_repository = ChatSqlRepository(session)
            workflow = LangGraphChatWorkflow(
                chat_repository=chat_repository,
                chat_model=chat_model_provider,
                screenplay_repository=ScreenplaySqlRepository(session),
                screenplay_checkpointer=screenplay_checkpointer,
            )
            thread = _resolve_stream_thread(chat_repository=chat_repository, request=request)
            message_index = _message_count_from_state(request.state)
            latest_user_message, user_message_operations = (
                _extract_latest_user_message_and_operations(
                    request=request,
                    start_index=message_index,
                )
            )
            message_index += len(user_message_operations)
            screenplay_context = _screenplay_context_from_request(request)

            initial_operations = [
                ChatWorkflowStreamOperation(type='set', path=['threadId'], value=str(thread.id)),
                *user_message_operations,
            ]
            if initial_operations:
                yield _format_assistant_transport_operations(initial_operations)

            async for operation in workflow.stream(
                thread_id=thread.id,
                start_message_index=message_index,
                latest_user_message=latest_user_message,
                agent_type=request.agent_type,
                screenplay_context=screenplay_context,
                is_cancelled=lambda: cancel_state['cancelled'],
            ):
                if await fastapi_request.is_disconnected():
                    cancel_state['cancelled'] = True
                    break
                yield _format_assistant_transport_operations([operation])
        except ChatStreamCancelledError:
            session.rollback()
        except Exception as exc:
            session.rollback()
            api_error = _to_api_error(exc)
            # Ensure transient tool status does not remain visible after stream failure.
            yield _format_assistant_transport_operations(
                [ChatWorkflowStreamOperation(type='set', path=['toolActivity'], value=None)]
            )
            yield _format_assistant_transport_error(api_error.message)
        finally:
            cancel_state['cancelled'] = True
            session.close()

    return StreamingResponse(
        _stream(),
        media_type='text/plain',
        headers={
            'Cache-Control': 'no-cache',
            'X-Accel-Buffering': 'no',
        },
    )


def _format_assistant_transport_operations(operations: list[ChatWorkflowStreamOperation]) -> str:
    payload = [
        {
            'type': operation.type,
            'path': operation.path,
            'value': _to_transport_value(operation),
        }
        for operation in operations
    ]
    return f'aui-state:{json.dumps(payload, default=str)}\n'


def _format_assistant_transport_error(message: str) -> str:
    return f'3:{json.dumps(message)}\n'


def _execute_chat_request(
    *,
    request: ChatRequest,
    use_case: SendChatMessageUseCase,
) -> SendChatResult:
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
            agent_type=request.agent_type,
            screenplay_context=(
                ScreenplayChatContext(
                    project_id=request.project_id,
                    screenplay_id=request.screenplay_id,
                    active_scene_id=request.active_scene_id,
                )
                if request.project_id is not None and request.screenplay_id is not None
                else None
            ),
        )
    except (
        ChatThreadNotFoundError,
        InvalidChatMessagesError,
        InvalidScreenplayChatContextError,
        ScreenplayAssistantRequiresStreamingError,
        ScreenplayChatContextError,
    ) as exc:
        raise _to_api_error(exc) from exc

    return result


def _to_api_error(exc: Exception) -> ApiError:
    if isinstance(exc, ChatThreadNotFoundError):
        return ApiError(
            status_code=404,
            code='thread_not_found',
            message='Chat thread not found',
        )
    if isinstance(exc, InvalidChatMessagesError):
        return ApiError(
            status_code=400,
            code='invalid_chat_messages',
            message='At least one user message is required',
        )
    if isinstance(exc, InvalidScreenplayChatContextError):
        return ApiError(
            status_code=400,
            code='invalid_screenplay_context',
            message='projectId and screenplayId are required for screenplay assistant',
        )
    if isinstance(exc, ScreenplayAssistantRequiresStreamingError):
        return ApiError(
            status_code=400,
            code='screenplay_requires_stream',
            message='Use /api/v1/chat/stream for screenplay assistant requests',
        )
    if isinstance(exc, ScreenplayChatContextError):
        return ApiError(
            status_code=400,
            code='invalid_screenplay_context',
            message='screenplay context references a missing screenplay',
        )
    return ApiError(
        status_code=500,
        code='internal_server_error',
        message='Internal server error',
    )


def _resolve_stream_thread(
    *, chat_repository: ChatSqlRepository, request: ChatRequest | ChatStreamRequest
) -> ChatThread:
    if request.thread_id is None:
        return chat_repository.create_thread()
    thread = chat_repository.get_thread_by_id(request.thread_id)
    if thread is None:
        raise ChatThreadNotFoundError
    return thread


def _screenplay_context_from_request(
    request: ChatRequest | ChatStreamRequest,
) -> ScreenplayChatContext | None:
    if request.agent_type == 'screenplay_assistant' and (
        request.project_id is None or request.screenplay_id is None
    ):
        raise InvalidScreenplayChatContextError
    if request.project_id is not None and request.screenplay_id is not None:
        return ScreenplayChatContext(
            project_id=request.project_id,
            screenplay_id=request.screenplay_id,
            active_scene_id=request.active_scene_id,
        )
    return None


def _extract_latest_user_message_and_operations(
    *, request: ChatStreamRequest, start_index: int
) -> tuple[ChatInputMessage, list[ChatWorkflowStreamOperation]]:
    operations: list[ChatWorkflowStreamOperation] = []
    latest_user_message: ChatInputMessage | None = None
    message_index = start_index

    # Assistant transport requests carry turn input in commands.
    # Persisting user turns in streamed state keeps frontend state authoritative.
    for command in request.commands:
        if command.type != 'add-message' or command.message is None:
            continue
        if command.message.role != 'user':
            continue

        text_chunks = [
            part.text
            for part in command.message.parts
            if part.type == 'text' and isinstance(part.text, str) and part.text
        ]
        if not text_chunks:
            continue

        text = '\n'.join(text_chunks)
        latest_user_message = ChatInputMessage(role='user', text=text, images=[])
        operations.append(
            ChatWorkflowStreamOperation(
                type='set',
                path=['messages', message_index],
                value={
                    'role': 'user',
                    'parts': [{'type': 'text', 'text': text}],
                },
            )
        )
        message_index += 1

    if latest_user_message is None:
        raise InvalidChatMessagesError
    return latest_user_message, operations


def _to_transport_value(operation: ChatWorkflowStreamOperation) -> object:
    if operation.path == ['updatedScreenplay'] and isinstance(operation.value, Screenplay):
        return ScreenplayResponse.from_domain(operation.value).model_dump(by_alias=True)
    return operation.value


def _message_count_from_state(state: dict[str, object] | None) -> int:
    if not isinstance(state, dict):
        return 0
    messages = state.get('messages')
    if isinstance(messages, list):
        return len(messages)
    return 0
