import os
from uuid import UUID
from typing import AsyncGenerator
import re
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.assistant.repository import AssistantRepository
from backend.api.kbase.repository import KbaseRepository
from backend.api.chat.repository import ChatRepository, AgentMessagesRepository
from backend.api.session.repository import SessionRepository
from backend.api.chat.models import ChatRequest
from backend.util.logging import SetupLogging
from backend.util.auth_utils import TokenData

logger = SetupLogging()

class AIResponseService:
    """
    Manages the LLM gateway and vector store for retrieval-augmented generation (RAG)
    """

    def __init__(
        self, 
        db: AsyncSession,
        chat_repo: ChatRepository,
        agent_message_repo: AgentMessagesRepository,
        current_user: TokenData = None,
        retriever=None
    ):
        self.db = db
        self.chat_repo = chat_repo
        self.agent_message_repo = agent_message_repo
        self.retriever = retriever
        self.current_user = current_user

        # Repositories for fetching assistant + knowledge base
        self.assistant_repo = AssistantRepository(db)
        self.kbase_repo = KbaseRepository(db)
        self.session_repo = SessionRepository(db)

        # These get set in initialize(...)
        self.assistant = None
        self.knowledge_base = None
        self.llm_gateway = None
        self.vector_store = None

    async def initialize(self, assistant_id: UUID):
        # 1) Load the assistant
        assistant = await self.assistant_repo.get_assistant_by_id(str(assistant_id))
        if not assistant:
            logger.error(f"Assistant not found with id {assistant_id}")
            # Raise an exception or handle appropriately
            raise ValueError(f"Assistant not found: {assistant_id}")
        self.assistant = assistant

        # 2) Load the knowledge base if the assistant type requires it
        kb = None
        if assistant.config.type in ["rag", "sql"]: # Only load KB if needed
            if not assistant.kbase_id:
                logger.error(f"Assistant {assistant_id} type '{assistant.config.type}' requires a kbase_id, but none found.")
                raise ValueError(f"Knowledge base ID missing for assistant {assistant_id}")
            kb = await self.kbase_repo.get_kbase_by_id(assistant.kbase_id)
            if not kb:
                logger.error(f"KnowledgeBase not found with id {assistant.kbase_id}")
                raise ValueError(f"Knowledge base not found: {assistant.kbase_id}")
        self.knowledge_base = kb # Might be None if not needed

        # 3) Possibly build a vector store
        if assistant.config.type == "rag": # Only RAG needs vector store here
            from backend.api.kbase.pgvectorstore import PostgresVectorStore
            self.vector_store = PostgresVectorStore(
                session=self.db,
                kbase_id=kb.id,
            )

        # 4) Build the LLM gateway
        from backend.api.assistant.gateway_factory import LLMGatewayFactory
        self.llm_gateway = LLMGatewayFactory.create_llm_gateway(
            db=self.db,
            assistant_id=assistant_id,
            assistant_type=assistant.config.type,
            knowledge_base=self.knowledge_base,
            assistant=assistant,
            message_gateway=self.chat_repo,
            agent_message_gateway=self.agent_message_repo,
            current_user=self.current_user,
            session_gateway=self.session_repo,
            vector_store=self.vector_store
        )


    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncGenerator:
        """
        Streams chunked responses from the LLM gateway. 
        Make sure you called 'initialize(...)' first.
        """
        if not self.llm_gateway:
            logger.error("LLM Gateway is not initialized. Call initialize() first.")
            # Raise or handle error appropriately
            raise RuntimeError("LLM Gateway not initialized.")

        async for chunk in self.llm_gateway.get_ai_response_stream(chat_request):
            yield chunk

    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        """
        Asks the LLM gateway for a short summary 'title' for the conversation.
        Removes leading/trailing quotes so it doesn't appear with extra quotes in the UI.
        """
        if not self.llm_gateway:
            logger.error("LLM Gateway is not initialized. Call initialize() first.")
            # Raise or handle error appropriately
            raise RuntimeError("LLM Gateway not initialized.")

        raw_title = await self.llm_gateway.get_summary_title(chat_request)

        raw_title = raw_title.strip()

        # Remove leading/trailing single or double quotes
        cleaned_title = re.sub(r'^[\'"]+|[\'"]+$', '', raw_title)

        return cleaned_title
