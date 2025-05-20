from backend.util.log_setup import SetupLogging
import os
from typing import AsyncIterator, List, Optional

from backend.api.assistant.models import Assistant
from backend.api.chat.models import ChatRequest, Message, OpsLoomMessageChunk
from backend.api.chat.repository import ChatRepository
from backend.api.assistant.base_assistant_gateway import BaseAssistantGateway
from backend.api.chat.chat_factory import ChatFactory

logger = SetupLogging()

class NoRagAssistant(BaseAssistantGateway):
    __slots__ = ("assistant", "message_gateway", "llm")

    def __init__(
        self,
        assistant: Assistant,
        message_gateway: ChatRepository,
    ):
        self.assistant = assistant
        self.message_gateway = message_gateway
        self.llm = self.initialize_llm()

    def initialize_llm(self, openai_key: Optional[str] = None):
        """
        Initialize the LLM using our ChatFactory.
        """
        provider = self.assistant.config.provider
        model_name = self.assistant.config.model

        return ChatFactory.create_chat_model(
            provider=provider,
            model=model_name,
            temperature=0.0,  # adjust temperature as needed
            api_key=openai_key or os.getenv("OPENAI_API_KEY")
        )

    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncIterator[OpsLoomMessageChunk]:
        """
        Yield the AI response as a stream of OpsLoomMessageChunk objects.
        """
        query = chat_request.message.content
        session_id = str(chat_request.session_id)

        # 1) Get chat history.
        history = await self.get_chat_history(session_id)

        # 2) Construct prompt.
        prompt = self.construct_prompt(query, history)

        # 3) Stream from LLM, yielding OpsLoomMessageChunk objects.
        async for chunk in self.stream_llm_response(prompt):
            yield chunk

    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        """
        Generate a concise conversation title.
        """
        query = chat_request.message.content
        prompt = (
            "Provide a concise and informative title (less than 100 characters) "
            f"for the following conversation:\n\nUser Query: {query}\n\nTitle:"
        )

        title = ""
        async for chunk in self.stream_llm_response(prompt):
            title += chunk["content"]
        return title.strip()

    async def get_chat_history(self, session_id: str) -> List[Message]:
        """
        Retrieve the most recent N messages from the chat history.
        """
        message_list = await self.message_gateway.get_messages(session_id)
        if message_list and message_list.messages:
            num_messages = self.assistant.assistant_metadata.num_history_messages
            history = message_list.messages[-num_messages:]
            logger.debug(f"Retrieved chat history with {len(history)} messages")
            return history
        else:
            logger.debug("No chat history found")
            return []

    async def stream_llm_response(self, prompt: str) -> AsyncIterator[OpsLoomMessageChunk]:
        """
        Stream responses from the LLM and yield each as an OpsLoomMessageChunk.

        The LLM’s astream() method is expected to return an async iterator of chunks.
        """
        # Wrap the prompt in a list to match the interface expected by our ChatFactory's chat model.
        async for chunk in self.llm.astream([prompt]):
            yield chunk

    def construct_prompt(self, query: str, history: List[Message]) -> str:
        """
        Create a prompt by combining the system message, chat history, and the user query.
        """
        system_message = self.assistant.system_prompts.get("system", "")

        # Format the chat history (using msg.blocks as in your original implementation).
        formatted_history = "\n".join(
            [f"{msg.role.capitalize()}: {msg.blocks}" for msg in history]
        )
        prompt = f"""{system_message}

---
Below is the complete history of your previous interaction with the user:
{formatted_history}

---
Here is the user message: 
{query}

---
Provide a helpful and accurate response to the user's query
"""
        logger.debug(f"Constructed prompt: {prompt}")
        return prompt
