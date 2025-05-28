from pydantic import BaseModel, Field, ConfigDict
from typing import List, Optional, Any, Dict, Literal
from uuid import UUID, uuid4
from typing_extensions import NotRequired, TypedDict
from pydantic_ai.messages import ModelMessage


class MessageBlock(BaseModel):
    model_config = ConfigDict(extra="allow")

    type: str
    text: Optional[str] = None
    content: Optional[str] = None
    data: Optional[Any] = None
    config: Optional[Dict[str, Any]] = None

class Message(BaseModel):
    role: str = "user"
    content: str
    blocks: List[MessageBlock] = Field(default_factory=list)
    message_id: UUID = Field(default_factory=uuid4)

class AgentMessages(BaseModel):
    model_config = ConfigDict(from_attributes=True, allow_population_by_field_name = True)  # This allows using .model_validate(orm_obj)
    user_id: UUID
    account_id: UUID
    session_id: UUID
    messages_json: List[ModelMessage]
    created_at: Optional[str] = None
    updated_at: Optional[str] = None

class MessagePair(BaseModel):
    message_id: UUID = Field(default_factory=uuid4)
    user_id: UUID
    account_id: UUID
    user_message: Message
    ai_message: Message
    feedback: Optional[int] = None
    session_id: UUID

class FeedbackRequest(BaseModel):
    message_id: UUID
    feedback: int

class ChatRequest(BaseModel):
    session_id: str
    message: Message

class Source(BaseModel):
    source: str
    link: str

class AIResponse(BaseModel):
    content: str
    sources: List[Source] = Field(default_factory=list)
    relevance_score: float = 0.0
    message_id: UUID = Field(default_factory=uuid4)
    blocks: List[MessageBlock] = Field(default_factory=list)

class MessageList(BaseModel):
    messages: List[Message]

class OpsLoomMessageChunk(TypedDict, total=False):
    content: str
    type: Literal["text", "dialog"]
    name: NotRequired[str]
    id: NotRequired[str]
    additional_kwargs: NotRequired[dict]
    response_metadata: NotRequired[dict]