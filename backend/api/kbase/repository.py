from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError
from backend.api.kbase.kbase_schema import KnowledgeBaseORM
from backend.api.kbase.models import KnowledgeBase, KnowledgeBaseList
from backend.util.log_setup import SetupLogging

logger = SetupLogging()

class KbaseRepository:
    """
    Repository to handle direct DB operations for the KnowledgeBase.
    """
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def create_kbase(self, kbase_in: KnowledgeBase) -> Optional[KnowledgeBase]:
        """
        Insert a row into the 'kbase' table from a Pydantic KnowledgeBase model.
        """
        try:
            new_orm = KnowledgeBaseORM(
                id=kbase_in.id,
                name=kbase_in.name,
                description=kbase_in.description,
                account_short_code=kbase_in.account_short_code
            )
            self.session.add(new_orm)
            await self.session.commit()
            await self.session.refresh(new_orm)
            logger.info(f"Successfully created new KnowledgeBase with UUID: {new_orm.id}")
            return self._to_pydantic(new_orm)
        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"Error creating KnowledgeBase: Duplicate UUID {kbase_in.id}\n{str(e)}")
            return None
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error creating KnowledgeBase: {str(e)}", exc_info=True)
            return None

    async def update_kbase(self, kbase_in: KnowledgeBase) -> Optional[KnowledgeBase]:
        """
        Update an existing knowledge base.
        """
        try:
            stmt = (
                update(KnowledgeBaseORM)
                .where(KnowledgeBaseORM.id == kbase_in.id)
                .values(
                    name=kbase_in.name,
                    description=kbase_in.description
                )
                .returning(KnowledgeBaseORM)
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            updated_orm = result.scalar_one_or_none()
            if not updated_orm:
                logger.error(f"KnowledgeBase with UUID: {kbase_in.id} not found.")
                return None

            logger.info(f"Successfully updated KnowledgeBase with UUID: {kbase_in.id}")
            return self._to_pydantic(updated_orm)
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error updating KnowledgeBase: {str(e)}", exc_info=True)
            return None

    async def get_kbase_by_name(self, name: str) -> Optional[KnowledgeBase]:
        """
        Retrieve a KnowledgeBase by its 'name' field.
        """
        try:
            stmt = select(KnowledgeBaseORM).where(KnowledgeBaseORM.name == name)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"KnowledgeBase with name: {name} not found")
                return None
            return self._to_pydantic(orm_obj)
        except Exception as e:
            logger.error(f"Unexpected error retrieving KnowledgeBase by name: {str(e)}", exc_info=True)
            return None

    async def get_kbase_by_id(self, id: UUID) -> Optional[KnowledgeBase]:
        """
        Retrieve a KnowledgeBase by its ID (UUID).
        """
        try:
            stmt = select(KnowledgeBaseORM).where(KnowledgeBaseORM.id == id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"KnowledgeBase with ID: {id} not found")
                return None
            return self._to_pydantic(orm_obj)
        except Exception as e:
            logger.error(f"Unexpected error retrieving KnowledgeBase: {str(e)}", exc_info=True)
            return None

    async def list_kbases(self) -> KnowledgeBaseList:
        """
        Return all KnowledgeBase entries.
        """
        try:
            stmt = select(KnowledgeBaseORM)
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
            kbase_list = [
                self._to_pydantic(row) for row in rows
            ]
            return KnowledgeBaseList(kbases=kbase_list)
        except Exception as e:
            logger.error(f"Unexpected error listing KnowledgeBases: {str(e)}", exc_info=True)
            return KnowledgeBaseList(kbases=[])

    async def delete_kbase(self, id: UUID) -> bool:
        """
        Delete the KnowledgeBase by UUID.
        """
        try:
            stmt = delete(KnowledgeBaseORM).where(KnowledgeBaseORM.id == id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount == 0:
                logger.error(f"KnowledgeBase with UUID: {id} not found for deletion.")
                return False
            logger.info(f"Successfully deleted KnowledgeBase with UUID: {id}")
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error deleting KnowledgeBase: {str(e)}", exc_info=True)
            return False

    def _to_pydantic(self, orm_obj: KnowledgeBaseORM) -> KnowledgeBase:
        """
        Convert an ORM object into a Pydantic KnowledgeBase model.
        """
        return KnowledgeBase(
            id=orm_obj.id,
            name=orm_obj.name,
            description=orm_obj.description,
            account_short_code=orm_obj.account_short_code,
            created_at=orm_obj.created_at,
            updated_at=orm_obj.updated_at
        )
