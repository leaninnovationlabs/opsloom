from typing import Optional
from uuid import UUID
from backend.api.kbase.models import KnowledgeBase, KnowledgeBaseList
from .repository import KbaseRepository
import logging

logger = logging.getLogger(__name__)

class KbaseService:
    __slots__ = ("repository",)
    def __init__(self, repository: KbaseRepository):
        self.repository = repository

    async def create_kbase(self, kbase_in: KnowledgeBase) -> Optional[KnowledgeBase]:
        return await self.repository.create_kbase(kbase_in)

    async def list_kbases(self) -> KnowledgeBaseList:
        return await self.repository.list_kbases()

    async def get_kbase(self, id: UUID) -> Optional[KnowledgeBase]:
        return await self.repository.get_kbase_by_id(id)
    
    async def get_kbase_by_name(self, name: str) -> Optional[KnowledgeBase]:
        return await self.repository.get_kbase_by_name(name)

    async def update_kbase(self, kbase_in: KnowledgeBase) -> Optional[KnowledgeBase]:
        return await self.repository.update_kbase(kbase_in)

    async def delete_kbase(self, id: UUID) -> bool:
        return await self.repository.delete_kbase(id)
