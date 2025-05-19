from typing import Optional
from uuid import UUID
from backend.api.assistant.models import (
    Assistant, AssistantList
)
from .repository import AssistantRepository
import logging

logger = logging.getLogger(__name__)

class AssistantService:
    """
    Business logic for managing Assistants.
    """
    __slots__ = ("repository",)
    def __init__(self, repository: AssistantRepository):
        self.repository = repository

    async def create_assistant(self, assistant_in: Assistant) -> Optional[Assistant]:
        return await self.repository.create_assistant(assistant_in)

    async def update_assistant(self, assistant_in: Assistant) -> Optional[Assistant]:
        return await self.repository.update_assistant(assistant_in)

    async def list_assistants(self, account_short_code: str) -> AssistantList:
        return await self.repository.list_assistants(account_short_code)

    async def get_assistant(self, assistant_id: UUID) -> Optional[Assistant]:
        return await self.repository.get_assistant_by_id(str(assistant_id))

    async def deactivate_assistant(self, assistant_id: UUID) -> bool:
        return await self.repository.deactivate_assistant(str(assistant_id))

    async def reactivate_assistant(self, assistant_id: UUID) -> bool:
        return await self.repository.reactivate_assistant(str(assistant_id))

    async def delete_assistant(self, assistant_id: UUID) -> bool:
        return await self.repository.delete_assistant(str(assistant_id))
