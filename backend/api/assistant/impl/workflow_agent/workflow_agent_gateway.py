import logging
import json
import asyncio
from typing import Optional, List, AsyncIterator
from uuid import UUID, uuid4

from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.chat.models import OpsLoomMessageChunk, ChatRequest, Message, MessagePair
from backend.api.assistant.base_assistant_gateway import BaseAssistantGateway
from backend.api.chat.repository import ChatRepository, AgentMessagesRepository
from backend.api.session.repository import SessionRepository
from backend.util.auth_utils import TokenData
from langchain_core.messages import HumanMessage, AIMessage, BaseMessage

# Import the LangGraph components and the new repository
from .graph import create_graph
from .state import AgentState
from .repositories import WorkflowRepository

logger = logging.getLogger(__name__)


class WorkflowAgentGateway(BaseAssistantGateway):
    """
    Implements the BaseAssistantGateway using a LangGraph workflow.
    Handles the interaction between the FastAPI application and the compiled LangGraph agent.
    """
    __slots__ = ("chat_repo", "session_repo", "agent_messages_gateway", "current_user", "repo", "app", "assistant_id")

    def __init__(
        self,
        db: AsyncSession,
        assistant_id: UUID,
        message_gateway: ChatRepository,
        agent_messages_gateway: AgentMessagesRepository,
        session_gateway: SessionRepository,
        current_user: TokenData = None
    ):
        self.chat_repo = message_gateway
        self.session_repo = session_gateway
        self.agent_messages_gateway = agent_messages_gateway
        self.current_user = current_user
        self.repo = WorkflowRepository(session=db)
        self.assistant_id = assistant_id
        self.app = create_graph(repo=self.repo)

    # ---------------
    # BaseAssistantGateway Implementation
    # ---------------

    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncIterator[str]:
        """
        Streams responses from the compiled LangGraph application.
        Adapts the input/output formats and saves the final message pair.
        """
        session_id = str(chat_request.session_id)
        assistant_id_str = str(self.assistant_id)
        thread_id = f"session_{session_id}"

        final_ai_message_id = uuid4()
        current_ai_response_content = ""
        tool_just_finished = False # Flag to track if a tool just ran

        # 1. Prepare initial state for LangGraph
        prior_message_list = await self.chat_repo.get_messages(session_id=session_id)
        langchain_messages: List[BaseMessage] = []
        for msg in prior_message_list.messages:
            msg_content = self._blocks_to_text(msg.blocks) or msg.content
            if msg.role == "user":
                langchain_messages.append(HumanMessage(content=msg_content))
            elif msg.role in ("ai", "assistant"):
                langchain_messages.append(AIMessage(content=msg_content))
            # TODO: Handle tool messages if converting from stored history

        # Add the current user message
        current_user_message_text = self._blocks_to_text(chat_request.message.blocks) or chat_request.message.content
        if not current_user_message_text:
            logger.warning(f"Received chat request for session {session_id} with no message content.")
            yield OpsLoomMessageChunk(type="error", content="Cannot process empty message.")
            return
        
        langchain_messages.append(HumanMessage(content=current_user_message_text))

        # Prepare the initial state dictionary
        initial_state: AgentState = {
            "messages": langchain_messages,
            # Set actor_id to None for now to bypass FK constraint issue in POC
            # A real implementation might map current_user.user_id to a person_id #TODO Sumedh: we should use the current user's id here, this will be used for RBAC and security
            # or handle cases where the actor isn't in the person table differently.
            "actor_id": None, # Was: UUID(self.current_user.user_id) if self.current_user else None
            "account_ids": None, "account_names": None,
            "person_id": None, "person_name": None, "target_person_name": None,
            "target_territory_id": None, "target_territory_name": None,
            "move_family": None, "is_committed": None,
            "needs_disambiguation": None, "disambiguation_options": None,
            "needs_confirmation": None, "pending_move_id": None,
        }

        # 2. Stream events from the LangGraph application
        config = {"configurable": {"thread_id": thread_id}}
        stream_error = None
        try:
            async for event in self.app.astream_events(initial_state, config=config, version="v2"):
                kind = event["event"]

                if kind == "on_chat_model_stream":
                    chunk_content = event["data"]["chunk"].content
                    if chunk_content:
                        # Check if a tool finished right before this chunk
                        if tool_just_finished:
                            # Yield a newline chunk first
                            newline_chunk = OpsLoomMessageChunk(
                                type="text",
                                content="\n", # Just a newline
                                message_id=str(final_ai_message_id),
                                assistant_id=assistant_id_str
                            )
                            yield newline_chunk
                            current_ai_response_content += "\n\n" # Add to accumulator too
                            tool_just_finished = False # Reset the flag

                        # Yield the actual content chunk
                        current_ai_response_content += chunk_content
                        ops_chunk_obj = OpsLoomMessageChunk(
                            type="text",
                            content=chunk_content,
                            message_id=str(final_ai_message_id),
                            assistant_id=assistant_id_str
                        )
                        yield ops_chunk_obj

                elif kind == "on_tool_end":
                    tool_name = event["name"]
                    logger.info(f"Tool {tool_name} finished.")
                    tool_just_finished = True # Set the flag
                    # Optionally yield tool status
                    # yield {"type": "tool_status", "name": tool_name, "status": "completed"} # This us good for tracking tool status, but we are not using it for now
                elif kind == "on_tool_start":
                    tool_name = event["name"]
                    logger.info(f"Tool {tool_name} starting...")
                    # Optionally yield tool status
                    # yield {"type": "tool_status", "name": tool_name, "status": "running"} # This us good for tracking tool status, but we are not using it for now
        except Exception as e:
            logger.exception(f"Error during LangGraph stream for session {session_id}")
            stream_error = e
            # Assume OpsLoomMessageChunk already returns a dict-like structure
            error_chunk_obj = OpsLoomMessageChunk(type="error", content=f"An error occurred: {e}")
            # Yield the object/dict directly
            yield error_chunk_obj

        # 3. Post-stream processing: Save message pair
        logger.info(f"Finished streaming for session {session_id}. Final AI content length: {len(current_ai_response_content)}")
        
        # Only save if there was content generated and no stream error occurred
        if current_ai_response_content and not stream_error:
            try:
                # Construct the final AI Message object
                ai_message_obj = Message(
                    role="ai",
                    content=current_ai_response_content,
                    blocks=[{"type": "text", "content": current_ai_response_content}] # Simple text block
                )
                
                # Construct the User Message object (ensure it has blocks)
                user_message_obj = chat_request.message
                if not user_message_obj.blocks:
                    user_message_obj.blocks = [{"type": "text", "content": current_user_message_text}]

                # Create the MessagePair
                pair = MessagePair(
                    user_message=user_message_obj,
                    ai_message=ai_message_obj,
                    message_id=final_ai_message_id, # Use the ID generated earlier
                    user_id=UUID(self.current_user.user_id) if self.current_user else None,
                    account_id=UUID(self.current_user.account_id) if self.current_user else None,
                    session_id=UUID(session_id)
                )
                
                # Save using the chat repository
                saved_ok = await self.chat_repo.save_message_pair(pair)
                if not saved_ok:
                    logger.error(f"Failed to save final message pair for session {session_id}")
                else:
                    logger.info(f"Successfully saved final message pair for session {session_id} with message_id {final_ai_message_id}")
            except Exception as e:
                logger.exception(f"Error saving final message pair for session {session_id}")
        elif stream_error:
             logger.error(f"Skipping message save for session {session_id} due to stream error.")
        else:
             logger.warning(f"Skipping message save for session {session_id} as no AI content was generated.")

        # TODO: Consider checkpointer logic for state persistence if needed, or Redis for this


    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        """Generates a summary title for the conversation.
           TODO: Determine how best to integrate this with LangGraph.
        """
        logger.warning("get_summary_title is not fully implemented for LangGraph gateway.")
        return "Workflow Agent Interaction" # Placeholder #TODO Sumedh: we should actually implement this

    # ---------------
    # Helpers
    # ---------------
    def _blocks_to_text(self, blocks: Optional[List[dict]]) -> str:
        """
        Convert a list of block objects (with {type, content/text}) to a single text string.
        Handles None input.
        """
        if not blocks: return ""
        text_parts = []
        for block in blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("content") or block.get("text", ""))
        return "\n".join(filter(None, text_parts))

    # Placeholder for saving final messages if needed separate from checkpointer
    # async def _save_final_messages(self, session_id: str, messages: List[BaseMessage]):
    #     if len(messages) >= 2:
    #         last_user_msg = messages[-2]
    #         last_ai_msg = messages[-1]
    #         if isinstance(last_user_msg, HumanMessage) and isinstance(last_ai_msg, AIMessage):
    #             # Convert back to OpsLoom Message format and save using chat_repo
    #             logger.info(f"Saving final message pair for session {session_id}")
    #             # ... implementation needed ...
    #     pass 