from backend.util.log_setup import SetupLogging
import json
import logfire
from typing import Optional, List, AsyncIterator
from pydantic_ai import Agent
from backend.api.chat.models import OpsLoomMessageChunk
from backend.api.chat.models import ChatRequest, Message, MessagePair
from backend.api.assistant.base_assistant_gateway import BaseAssistantGateway
from backend.api.chat.repository import ChatRepository, AgentMessagesRepository
from backend.api.chat.models import AgentMessages
from backend.api.session.repository import SessionRepository
from backend.util.auth_utils import TokenData
from pydantic_ai.messages import (
    ModelMessagesTypeAdapter,
    ModelRequest,
    UserPromptPart,
    ModelResponse,
    TextPart
)

from .schemas import (
    GuestSchema,
    ServiceSchema,
    ReservationSchema,
    ActionURLSchema
)
from .client import HotelApiClient
from .tools import register_agent_tools

logger = SetupLogging()


class AgentGateway(BaseAssistantGateway):
    """
    Example of a refactored class that uses an external HTTP client
    and implements BaseAssistantGateway.

    Now includes "two-phase" confirmation approach for create/modify.
    """
    __slots__ = ("chat_repo", "session_repo", "agent_messages_gateway", "current_user", "agent", "guest", "available_services", "reservations",
                 "_pending_reservation_info", "_pending_modification_info", "_pending_deletion_info", "api_client")
    def __init__(
        self,
        message_gateway: ChatRepository,
        agent_messages_gateway: AgentMessagesRepository,
        session_gateway: SessionRepository, 
        current_user: TokenData = None
    ):
        self.chat_repo = message_gateway
        self.session_repo = session_gateway
        self.agent_messages_gateway = agent_messages_gateway
        self.current_user = current_user

        # The AI Agent: pydantic-ai approach
        self.agent = Agent(
            name="hotel_agent",
            model="openai:gpt-4o",
            end_strategy="exhaustive",
            retries=2,
            model_settings={"parallel_tool_calls": False},
        )

        self.guest: Optional[GuestSchema] = None
        self.available_services: List[ServiceSchema] = []
        self.reservations: List[ReservationSchema] = []

        self._pending_reservation_info = None
        self._pending_modification_info = None
        self._pending_deletion_info = None

        self.api_client = HotelApiClient()

        # register logfire
        self._configure_logfire()

        # Register the tools
        self._register_tools()
        

    def _register_tools(self):
        register_agent_tools(self.agent, self)

    def _configure_logfire(self):
        logfire.configure(send_to_logfire='if-token-present', service_name="hotel-agent")

    # ---------------
    # BaseAssistantGateway Implementation
    # ---------------

    async def get_ai_response_stream(self, chat_request: ChatRequest) -> AsyncIterator[str]:
        session_uuid = str(chat_request.session_id)

        prior_message_list = await self.chat_repo.get_messages(session_id=session_uuid)
        message_history = []

        for m in prior_message_list.messages:
            if m.role == "user":
                user_text = self._blocks_to_text(m.blocks)
                message_history.append(
                    ModelRequest(parts=[UserPromptPart(content=user_text)])
                )
            elif m.role in ("ai", "assistant"):
                ai_text = self._blocks_to_text(m.blocks)
                message_history.append(
                    ModelResponse(parts=[TextPart(content=ai_text)])
                )

        new_user_text = self._blocks_to_text(chat_request.message.blocks)
        if chat_request.message.content:
            new_user_text += f"\n{chat_request.message.content}"
        message_history.append(
            ModelRequest(parts=[UserPromptPart(content=new_user_text)])
        )

        if not self.guest:
            self.guest = GuestSchema(
                guest_id=self.current_user.user_id,
                full_name="Peter Griffin",
                email=self.current_user.email,
            )
        if not self.available_services:
            self.available_services = await self.api_client.list_all_services()
        if not self.reservations and self.guest:
            self.reservations = await self.api_client.get_reservations_for_guest(
                self.guest.guest_id
            )
        url_schema = ActionURLSchema()
        
        improved_prompt = f"""
            <context>
            Current reservations: {self.reservations}
            </context>

            <system prompt>
            If the following prompt involves creating, modifying, or deleting something, please set the type of the 
            result OpsLoomMessageChunk to 'dialog' and include the fields 'title', 'actions', and 'description' in response_metadata.
            Use the following example as a guide.
            The 'title' and 'description' must have some meaningful information about the action being taken for 'dialog' result types.
            Always put the type first in the result type.
            
            # For CREATING a new reservation:
            This is an example of a dialog result type: 
            {{
                "type": "dialog",
                "content": "I have prepared a reservation plan for a single room from May 20th, 2025 to May 21st, 2025. Would you like to proceed with the booking?",
                "name": "Reservation Confirmation",
                "id": "1",
                "response_metadata": {{
                    "title": "Reservation Confirmation",
                    "description": "Single Room Booking Confirmation",
                    "actions": [
                        {{
                            "action": "Submit",
                            "url": "{ActionURLSchema.get_reservation_create_url()}",
                            "body": {{
                                "guest_id": "{self.guest.guest_id if self.guest else '<uuid from current user>'}",
                                "full_name": "Peter Griffin",
                                "email": "{self.guest.email if self.guest else '<email from current user>'}",
                                "room_type": "<fill in with user choice>",
                                "check_in": "<fill in with user choice>",
                                "check_out": "<fill in with user choice>"
                            }},
                            "method": "POST",
                            "variant": "default"
                        }},
                        {{
                            "action": "Cancel",
                            "url": null,
                            "variant": "outline"
                        }}
                    ]
                }}
            }}
            
            # For MODIFYING an existing reservation:
            NEVER ADD /modify to the URL. The URL for modify IS the same as the URL for create but we use patch instead of post.
            This is an example of a dialog result type for modification: 
            {{
                "type": "dialog",
                "content": "I have prepared a modification plan for your reservation. Would you like to proceed with these changes?",
                "name": "Reservation Modification",
                "id": "2",
                "response_metadata": {{
                    "title": "Reservation Modification",
                    "description": "Update Check-Out Date",
                    "actions": [
                        {{
                            "action": "Submit",
                            "url": "{ActionURLSchema.get_reservation_modify_url(11) if self.reservations and self.reservations[0].reservation_id else 'http://localhost:8081/reservations/<reservation_id>'}",
                            "body": {{
                                "check_in": "2025-06-09T15:00:00",
                                "check_out": "2025-06-13T11:00:00",
                                "room_type": "single"
                            }},
                            "method": "PATCH",
                            "variant": "default"
                        }},
                        {{
                            "action": "Cancel",
                            "url": null,
                            "variant": "outline"
                        }}
                    ]
                }}
            }}
            
            # IMPORTANT: When modifying reservations, the URL format MUST be: 
            http://localhost:8081/reservations/<reservation_id> (e.g., http://localhost:8081/reservations/11)
            
            # IMPORTANT: When modifying reservations, the body parameters MUST be:
            "check_in" (not "new_check_in")
            "check_out" (not "new_check_out")
            "room_type" (not "new_room_type")
            
            This is an example of a text result type: 
            {{
                "type": "text",
                "content": "Your reservation has been successfully created! Here are the details:\\n\\n- **Room Type:** Single\\n- **Check-In:** May 5, 2024\\n- **Check-Out:** May 9, 2024\\n- **Reservation ID:** 18\\n\\nIf you need any further assistance, feel free to ask!"
            }}

            Do not use the 'create', 'modify', or 'delete' tools unless the user has confirmed that they want these changes
            in the previous message.
            </system prompt>

            <user prompt>
            {new_user_text}
            </user prompt>
        """

        prev_run_history = await self.agent_messages_gateway.get_agent_run_messages(session_uuid)

        all_messages: list[dict] = []
        for row in prev_run_history:
            all_messages.extend(row.messages_json)

        typed_history = ModelMessagesTypeAdapter.validate_python(all_messages)

        # 6) Start streaming from the agent
        async with self.agent.run_stream(
            user_prompt=improved_prompt,
            message_history=typed_history,
            deps=[self.guest, self.reservations],
            result_type=OpsLoomMessageChunk
        ) as run_result:
            final_text = ""

            async for chunk in run_result.stream():
                # Suppose chunk["content"] is the entire text so far
                full_content_so_far = chunk.get("content", "")

                # The difference between what we had before and now
                new_text = full_content_so_far[len(final_text) :]

                # We replace chunk["content"] with just the new text
                chunk["content"] = new_text

                # Then accumulate it
                final_text += new_text

                yield chunk

            logger.info(f"\n\nFinal AI response: {final_text}\n\n")

            # 1) Store the entire “agentic” run in agent_message table
            logger.info(f"all_messages type: {type(run_result.all_messages_json())}")
            all_msg_list = json.loads(run_result.all_messages_json().decode("utf-8"))
            logger.info(f"all_messages: {all_msg_list}")

            # Build your pydantic model for storing
            cur_user = await self.session_repo.get_user_session(chat_request.session_id)
            agent_msg = AgentMessages(
                user_id=cur_user.user_id,
                account_id=cur_user.account_id,
                session_id=chat_request.session_id,
                messages_json=all_msg_list,
            )
            await self.agent_messages_gateway.save_agent_run_messages(agent_msg)
            # await self.agent_messages_gateway.save_agent_run_messages(agent_msg)

            # 2) Optionally store a single user+AI pair in the existing message table
            new_msgs = run_result.new_messages()
            if len(new_msgs) == 2:
                user_m, ai_m = new_msgs
                user_blocks = [{"type": "text", "content": user_m.parts[0].content}]
                ai_blocks = [{"type": "text", "content": ai_m.parts[0].content}]

                user_message = Message(role="user", content="", blocks=user_blocks)
                ai_message = Message(role="ai", content="", blocks=ai_blocks)

                pair = MessagePair(
                    user_id=cur_user.user_id,
                    account_id=cur_user.account_id,
                    user_message=user_message,
                    ai_message=ai_message,
                    session_id=str(chat_request.session_id)
                )
                await self.chat_repo.save_message_pair(pair)


    async def get_summary_title(self, chat_request: ChatRequest) -> str:
        """Minimal placeholder for summarizing the conversation."""
        return "Short conversation summary"

    # ---------------
    # Helpers
    # ---------------
    def _blocks_to_text(self, blocks: List[dict]) -> str:
        """
        Convert a list of block objects (with {type, content}) to a single text string.
        """
        text_parts = []
        for block in blocks:
            if block.get("type") == "text":
                text_parts.append(block.get("content", ""))
        return "\n".join(text_parts)
