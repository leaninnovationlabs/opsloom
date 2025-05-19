from typing import Optional
from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.sql import func

from backend.api.session.session_schema import SessionORM
from backend.api.session.models import UserSession, SessionList
import logging

logger = logging.getLogger(__name__)

class SessionRepository:
    """
    Repository to handle direct DB interactions for 'session' data.
    """
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def get_user_session(self, session_id: UUID) -> Optional[UserSession]:
        try:
            stmt = select(SessionORM).where(SessionORM.id == session_id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.debug(f"No session found with uuid {session_id}")
                return None

            return self._to_pydantic(orm_obj)
        except SQLAlchemyError as e:
            logger.error(f"Error in get_user_session: {str(e)}")
            return None

    async def list_user_sessions(self, user_id: UUID) -> SessionList:
        try:
            stmt = select(SessionORM).where(SessionORM.user_id == user_id)
            result = await self.session.execute(stmt)
            rows = result.scalars().all()
            sessions = [self._to_pydantic(row) for row in rows]
            return SessionList(list=sessions)
        except SQLAlchemyError as e:
            logger.error(f"Error in list_user_sessions: {str(e)}")
            return SessionList(list=[])

    async def set_user_session(self, user_session: UserSession) -> Optional[UserSession]:
        """
        Insert a new session row.
        """
        try:
            new_orm = SessionORM(
                id=user_session.id,
                user_id=user_session.user_id,
                account_id=user_session.account_id,
                assistant_id=user_session.assistant_id,
                title=user_session.title[:50] if user_session.title else "",
                data=user_session.data,
            )
            self.session.add(new_orm)
            await self.session.commit()
            await self.session.refresh(new_orm)
            return self._to_pydantic(new_orm)
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"set_user_session: SQLAlchemy Error: {str(e)}")
            return None

    async def delete_user_session(self, session_id: UUID) -> bool:
        try:
            stmt = delete(SessionORM).where(SessionORM.id == session_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount == 0:
                logger.debug(f"No session found with uuid {session_id} to delete.")
                return False
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"delete_user_session: SQLAlchemy Error: {str(e)}")
            return False

    async def check_session_title(self, session_id: UUID) -> bool:
        """
        check and see if a title exists for the session. used in the chat service to determine whether to get a new title or not
        """
        try: 
            stmt = select(SessionORM).where(SessionORM.id == session_id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.debug(f"No session found with uuid {session_id}")
                return False
            if orm_obj.title:
                return True
            return False
        except SQLAlchemyError as e:
            logger.error(f"Error in check_session_title: {str(e)}")
            return False


    async def update_session_title(self, session_id: UUID, title: str) -> bool:
        """
        Update the session title (up to 50 chars).
        """
        try:
            title_str = title[:50] if title else ""
            stmt = (
                update(SessionORM)
                .where(SessionORM.id == session_id)
                .values(title=title_str, updated_at=func.now())
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount == 0:
                logger.debug(f"No session found with uuid {session_id} to update title.")
                return False
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"update_session_title: SQLAlchemy Error: {str(e)}")
            return False

    def _to_pydantic(self, orm_obj: SessionORM) -> UserSession:
        return UserSession(
            id=orm_obj.id,
            title=orm_obj.title or "",
            user_id=orm_obj.user_id,
            account_id=orm_obj.account_id,
            assistant_id=orm_obj.assistant_id,
            data=orm_obj.data,
            created_at=orm_obj.created_at,
        )
