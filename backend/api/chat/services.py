import asyncio
import json
from typing import AsyncGenerator
from uuid import UUID

from fastapi import HTTPException, BackgroundTasks
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.chat.models import (
    Message,
    MessagePair,
    ChatRequest,
    AIResponse,
    MessageBlock,
)
from backend.api.chat.repository import ChatRepository, AgentMessagesRepository
from backend.api.chat.ai_response_service import AIResponseService
from backend.api.chat.models import OpsLoomMessageChunk  # for typing
from backend.api.session.models import UserSession
from backend.api.session.repository import SessionRepository
from backend.api.assistant.repository import AssistantRepository
from backend.api.kbase.repository import KbaseRepository
from backend.util.log_setup import SetupLogging
from backend.util.auth_utils import TokenData

logger = SetupLogging()

class ChatService:
    """
    Manages chat requests and streaming LLM responses,
    with logic to skip new title generation if a session already has one.
    """
    __slots__ = (
        "db",
        "chat_repository",
        "agent_message_repository",
        "session_repository",
        "assistant_repository",
        "current_user",
        "kbase_repository",
        "retriever",
    )

    def __init__(self, db: AsyncSession, current_user: TokenData = None):
        self.db = db
        self.chat_repository = ChatRepository(db)
        self.agent_message_repository = AgentMessagesRepository(db)
        self.session_repository = SessionRepository(db)
        self.assistant_repository = AssistantRepository(db)
        self.kbase_repository = KbaseRepository(db)
        self.current_user = current_user
        self.retriever = None  # optional retrieval pipeline

    async def process_chat_request(
        self,
        request: ChatRequest,
        current_user: TokenData,
        background_tasks: BackgroundTasks
    ) -> AsyncGenerator[str, None]:
        """
        Orchestrates streaming from the LLM, storing one final user+AI message pair.
        Skips title generation if session already has one.

        Yields JSON strings (SSE or chunked) to the caller. Each chunk is built
        from OpsLoomMessageChunk data plus some metadata (message_id, blocks, etc.).
        """
        # 1) Validate the session
        logger.info(f"\n\n\n\n\n\ncurrent user: {current_user}\n\n\n\n\n\n")
        session = await self.validate_session(request.session_id, current_user)

        # 2) Convert assistant_id to a standard UUID if needed
        if not isinstance(session.assistant_id, UUID):
            assistant_id_uuid = UUID(str(session.assistant_id))
        else:
            assistant_id_uuid = session.assistant_id

        # 3) Initialize the AIResponseService
        ai_service = AIResponseService(
            db=self.db,
            chat_repo=self.chat_repository,
            agent_message_repo=self.agent_message_repository,
            current_user = self.current_user,
            retriever=self.retriever
        )
        await ai_service.initialize(assistant_id_uuid)

        # 4) Prepare an AIResponse to hold the final accumulated text
        full_resp = AIResponse(content="", blocks=[])

        # 5) Check if the session already has a title
        title_exists = await self.session_repository.check_session_title(session.id)
        title_future = None
        title_sent = True  # default to True if we won't fetch a new title

        if not title_exists:
            # If there's no existing title, we fetch a new one asynchronously
            title_future = asyncio.ensure_future(ai_service.get_summary_title(request))
            title_sent = False

        # We'll store an interim 'block_content'
        block_content: MessageBlock | None = None

        async def response_stream():
            nonlocal full_resp, title_sent, block_content, title_future

            # 1) Stream chunked responses from the assistant as OpsLoomMessageChunk
            async for ops_chunk in ai_service.get_ai_response_stream(request):
                # ops_chunk is a dictionary with fields like "content", "type", etc.
                content_str = ops_chunk.get("content", "")
                chunk_type = ops_chunk.get("type", "text")
                response_md = ops_chunk.get("response_metadata", {})

                # Append chunk's text content into the final full response
                full_resp.content += content_str

                # Construct a 'block_content' for JSON. Customize to your UI needs:
                if chunk_type == "text":
                    block_content = MessageBlock(type="text", text=full_resp.content)
                elif chunk_type == "table":
                    block_content = MessageBlock(
                        type="table",
                        data=content_str,
                        config={
                            "title": response_md.get("title", ""),
                            "description": response_md.get("description", ""),
                        },
                    )
                elif chunk_type == "dialog":
                    block_content = MessageBlock(
                        type="dialog",
                        content=content_str,
                        config={
                            "title": response_md.get("title", ""),
                            "description": response_md.get("description", ""),
                            "actions": response_md.get("actions", []),
                        },
                    )
                elif chunk_type == "barchart":
                    block_content = MessageBlock(
                        type="barchart",
                        data=content_str,
                        config={
                            "title": response_md.get("title", ""),
                            "description": response_md.get("description", ""),
                            "xAxis": response_md.get("xAxis", ""),
                            "yAxis": response_md.get("yAxis", ""),
                            "explanation": response_md.get("explanation", ""),
                        },
                    )
                else:
                    block_content = MessageBlock(type=chunk_type, content=content_str)

                # Build partial chunk_data to yield
                chunk_data = {
                    "message_id": str(full_resp.message_id),
                    "assistant_id": str(assistant_id_uuid),
                    "blocks": [block_content.model_dump()],
                }

                # If we are generating a new title asynchronously, attach it once it's ready
                if title_future and not title_sent and title_future.done():
                    try:
                        possible_title = title_future.result()
                        chunk_data["title"] = possible_title
                        title_sent = True
                    except Exception as e:
                        logger.error(f"Error retrieving summary title: {str(e)}")

                # Yield the chunk_data as a JSON line (SSE or chunked HTTP response)
                yield json.dumps(chunk_data) + "\n"

            # 2) Once the stream finishes, finalize the blocks
            full_resp.blocks = [block_content] if block_content else []

            # 3) Store the user's question as a single text block
            request.message.blocks = [MessageBlock(type="text", text=request.message.content)]

            # 4) If we never attached the title during the loop, do it now
            if title_future and not title_sent:
                try:
                    final_title = await title_future
                    yield json.dumps({"title": final_title}) + "\n"
                except Exception as e:
                    logger.error(f"Error retrieving summary title (late): {str(e)}")

            # 5) Store user + AI message pair in DB
            await self.store_message_pair(session, request, full_resp)

            # 6) Possibly update the session title in the background
            try:
                if title_future:
                    final_title = title_future.result() if title_future.done() else None
                    if final_title:
                        background_tasks.add_task(
                            self.session_repository.update_session_title,
                            session.id,
                            final_title
                        )
            except Exception as e:
                logger.error(f"Error updating session title: {str(e)}")

        return response_stream()

    async def validate_session(self, session_id: str, current_user: TokenData) -> UserSession:
        """
        Load session, ensure it belongs to current_user.
        """
        session_uuid = UUID(session_id)
        user_session = await self.session_repository.get_user_session(session_uuid)
        if not user_session:
            raise HTTPException(status_code=404, detail="Session not found")

        # Check permission
        if (
            str(current_user.user_id) != str(user_session.user_id)
            or str(current_user.account_id) != str(user_session.account_id)
        ):
            raise HTTPException(status_code=403, detail="Forbidden")

        return user_session

    async def store_message_pair(self, session: UserSession, request: ChatRequest, response: AIResponse):
        """
        Store a single user+AI message pair in the DB, with final AIResponse blocks.
        """
        try:
            pair = MessagePair(
                user_message=request.message,
                ai_message=Message(
                    role="ai",
                    content=response.content,
                    blocks=response.blocks
                ),
                message_id=response.message_id,
                user_id=session.user_id,
                account_id=session.account_id,
                session_id=session.id
            )
            saved_ok = await self.chat_repository.save_message_pair(pair)
            if not saved_ok:
                logger.error(f"Failed to save message pair for session {request.session_id}")
        except Exception as e:
            logger.error(
                f"Error storing message pair for session {request.session_id}: {str(e)}",
                exc_info=True
            )
            raise

    async def get_messages(self, session_id: str, current_user: TokenData):
        """
        Validate session, then return all stored messages.
        """
        _ = await self.validate_session(session_id, current_user)
        return await self.chat_repository.get_messages(UUID(session_id))

    async def submit_feedback(self, feedback_req, current_user: TokenData):
        """
        Possibly verify user has rights to this message, etc.
        """
        return await self.chat_repository.update_message_feedback(
            message_id=feedback_req.message_id,
            feedback=feedback_req.feedback
        )
