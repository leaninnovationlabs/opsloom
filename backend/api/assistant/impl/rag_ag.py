from backend.util.log_setup import SetupLogging
import logging
import os
from typing import AsyncIterator, List, Optional
import cohere

from backend.api.assistant.models import Assistant
from backend.api.chat.models import ChatRequest, Message
from backend.api.kbase.models import KnowledgeBase
from backend.api.chat.repository import ChatRepository
from backend.api.chat.chat_factory import ChatFactory  
from backend.util.config import get_config_value
from backend.api.kbase.pgvectorstore import PostgresVectorStore
from backend.api.assistant.base_assistant_gateway import BaseAssistantGateway

from backend.api.chat.models import OpsLoomMessageChunk 

logger = SetupLogging()
logging.basicConfig(level=logging.DEBUG)

ENV_RERANK = get_config_value("RERANK") == "true"

class RagAssistant(BaseAssistantGateway):
    __slots__ = (
        "vector_store",
        "message_gateway",
        # "cohere_client",
        "knowledge_base",
        "assistant",
        "llm"
    )

    def __init__(
        self,
        knowledge_base: KnowledgeBase,
        assistant: Assistant,
        message_gateway: ChatRepository,
        vector_store: PostgresVectorStore,
        openai_key: Optional[str] = None,
        cohere_key: Optional[str] = None,
    ):
        self.vector_store = vector_store
        self.message_gateway = message_gateway
        # self.cohere_client = cohere.Client(cohere_key or os.getenv("COHERE_API_KEY"))
        self.knowledge_base = knowledge_base
        self.assistant = assistant
        self.llm = self.initialize_llm(openai_key)

    def initialize_llm(self, openai_key: Optional[str] = None):
        """
        Create a chat model via our ChatFactory, rather than using ChatOpenAI/ChatBedrock directly.
        """
        provider = self.assistant.config.provider
        model_name = self.assistant.config.model

        return ChatFactory.create_chat_model(
            provider=provider,
            model=model_name,
            temperature=0.0,  # or adjust if you want some creativity
            api_key=openai_key or os.getenv("OPENAI_API_KEY")
        )

    def embed_query(self, query: str) -> List[float]:
        """
        Embed the query text using Cohere's embed API.
        Note: This is a synchronous call. If needed, consider an async executor.
        """
        embedded_query = self.llm.embed_query(query)
        return embedded_query

    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncIterator[OpsLoomMessageChunk]:
        """
        High-level generator:
          1) Retrieve relevant docs
          2) Gather chat history
          3) Construct prompt
          4) Stream LLM response as OpsLoomMessageChunk objects
        """
        query = chat_request.message.content
        session_id = str(chat_request.session_id)

        # Step 1: Retrieve relevant documents
        context = await self.retrieve_relevant_documents(query)

        # Step 2: Get chat history
        history = await self.get_chat_history(session_id)

        # Step 3: Construct prompt
        prompt = self.construct_prompt(query, context, history)

        # Step 4: Stream LLM response
        # Return OpsLoomMessageChunk pieces directly so that the caller can process them.
        async for chunk in self.stream_llm_response(prompt):
            yield chunk

    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        """
        Generate a short conversation title (<=100 chars) by streaming from the LLM.
        """
        query = chat_request.message.content
        prompt = (
            "Provide a concise and informative title (less than 100 characters) "
            "for the following conversation:\n\n"
            f"User Query: {query}\n\nTitle:"
        )

        # Accumulate content from streaming
        title = ""
        async for chunk in self.stream_llm_response(prompt):
            if chunk.get("content"):
                title += chunk["content"]
        return title.strip()

    async def retrieve_relevant_documents(self, query: str, k: int = 5) -> str:
        """
        1) Embed query
        2) Vector search
        3) Possibly rerank
        4) Return a concatenated context
        """
        query_embedding = self.embed_query(query)
        logger.info(f"Knowledge base: {self.knowledge_base.name}")

        # 1) Retrieve documents from the vector store
        retrieved_chunks = await self.vector_store.mmr_by_vector(
            query_embedding=query_embedding,
            k=k,
        )
        logger.info(f"Retrieved {len(retrieved_chunks.chunks)} documents from the vector store")

        # 2) Prepare doc texts for optional re-rank
        docs_for_rerank = [chunk.content for chunk in retrieved_chunks.chunks]

        if ENV_RERANK:
            # Rerank using Cohere
            rerank_results = self.cohere_client.rerank(
                query=query,
                documents=docs_for_rerank,
                top_n=2,
                model='rerank-english-v3.0',
                return_documents=True
            )
            ranked_documents = [str(result.document) for result in rerank_results.results]
            context = "\n\n".join(ranked_documents)
        else:
            context = "\n\n".join(docs_for_rerank)

        return context

    async def get_chat_history(self, session_id: str) -> List[Message]:
        """
        Retrieve the most recent N messages from the chat history.
        """
        message_list = await self.message_gateway.get_messages(session_id)
        if message_list and message_list.messages:
            num_messages = self.assistant.assistant_metadata.num_history_messages
            history = message_list.messages[-num_messages:]
            logger.info(f"Retrieved chat history with {len(history)} messages")
            return history
        else:
            logger.info("No chat history found")
            return []

    def construct_prompt(self, query: str, context: str, history: List[Message]) -> str:
        """
        Format the system prompt, chat history, relevant context, plus user query
        into a single textual prompt for the LLM.
        """
        system_message = self.assistant.system_prompts.get("system", "")

        formatted_history = "\n".join([
            f"{msg.role.capitalize()}: {msg.content}" for msg in history
        ])

        prompt = f"""System: {system_message}

Chat History:
{formatted_history}

Relevant Context:
{context}

User Query: {query}

Instructions:
1. Analyze the user query in relation to the chat history and relevant context.
2. Provide a helpful and accurate response that directly addresses the user's query while following the system prompt.
3. Incorporate information from the relevant context when applicable.
4. Ensure your response maintains continuity with the ongoing conversation.
5. If the query cannot be fully answered with the given information, acknowledge this and provide the best possible answer based on available data.
6. Be concise yet informative in your response.
"""
        logger.debug(f"Constructed prompt: {prompt}")
        return prompt

    async def stream_llm_response(self, prompt: str) -> AsyncIterator[OpsLoomMessageChunk]:
        """
        Actually call the LLM's astream() method, returning OpsLoomMessageChunk items.
        """
        # We pass the entire user prompt as a single user message (list of length 1).
        async for chunk in self.llm.astream([prompt]):
            # chunk is already an OpsLoomMessageChunk:
            #   {
            #       "content": "...",
            #       "type": "text",
            #       "id": "...",
            #       "additional_kwargs": {...},
            #       "response_metadata": {...},
            #       ...
            #   }
            yield chunk
