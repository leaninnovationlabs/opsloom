from typing import Optional
from uuid import UUID
from backend.api.session.models import (
    UserSession,
    SessionList
)
from backend.api.session.repository import SessionRepository
from backend.api.kbase.repository import KbaseRepository
from backend.api.assistant.repository import AssistantRepository
from backend.util.log_setup import SetupLogging
from backend.util.auth_utils import TokenData
from sqlalchemy.ext.asyncio import AsyncSession

logger = SetupLogging()

class SessionService:
    __slots__ = ("db", "session_repo", "kbase_repo", "assistant_repo")
    def __init__(self, db: AsyncSession):
        self.db = db
        self.session_repo = SessionRepository(db)

        self.kbase_repo = KbaseRepository(db)

        self.assistant_repo = AssistantRepository(db)

    async def create_session_object(self, curr_user: TokenData, assistant_id: UUID) -> UserSession:
        # Validate assistant exists
        assistant = await self.assistant_repo.get_assistant_by_id(assistant_id)
        if not assistant:
            logger.error(f"Assistant with ID {assistant_id} not found.")
            # Possibly raise an exception

        session = UserSession(
            user_id=curr_user.user_id,
            account_id=curr_user.account_id,
            assistant_id=assistant_id,
            # title can be set later, or left blank
        )
        return session

    async def store_chat_session(self, session: UserSession) -> Optional[UserSession]:
        """
        Insert a new session row in the DB.
        """
        return await self.session_repo.set_user_session(session)

    async def get_session(self, session_id: UUID) -> Optional[UserSession]:
        logger.info(f"Getting session with ID: {session_id}")
        return await self.session_repo.get_user_session(session_id)

    async def update_session_title(self, session_id: UUID, title: str) -> bool:
        return await self.session_repo.update_session_title(session_id, title)

    async def delete_session(self, session_id: UUID) -> bool:
        return await self.session_repo.delete_user_session(session_id)

    async def list_sessions(self, user_id: UUID) -> SessionList:
        return await self.session_repo.list_user_sessions(user_id)