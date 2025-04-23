from typing import List, TypedDict, Annotated, Optional
from uuid import UUID
import operator

from langchain_core.messages import BaseMessage

# Define the state for the LangGraph agent
class AgentState(TypedDict):
    messages: Annotated[List[BaseMessage], operator.add]
    # Information resolved from user query
    account_ids: Optional[List[UUID]]
    account_names: Optional[List[str]]
    person_id: Optional[UUID] # ID of person being moved (if applicable)
    person_name: Optional[str]
    target_person_name: Optional[str] # Name of target person used to find territory
    target_territory_id: Optional[UUID]
    target_territory_name: Optional[str]
    # Flags for workflow decisions
    move_family: Optional[bool]
    is_committed: Optional[bool] # User wants to commit (True) or propose (False)
    # Intermediate state for disambiguation or confirmation
    needs_disambiguation: Optional[bool]
    disambiguation_options: Optional[List[dict]] # e.g., list of territories for a person
    needs_confirmation: Optional[bool] # True if we need propose/commit/family answers
    pending_move_id: Optional[int] # Store ID from proposed move event
    actor_id: Optional[UUID] # Renamed from actor_person_id - ID of user initiating the move 