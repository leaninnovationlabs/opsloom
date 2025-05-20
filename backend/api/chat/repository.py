from uuid import UUID
from sqlalchemy.ext.asyncio import AsyncSession
import json
from sqlalchemy import select, update, desc
from sqlalchemy.exc import SQLAlchemyError
from backend.api.chat.chat_schema import MessageORM, AgentMessageORM
from backend.api.chat.models import (
    MessagePair,
    MessageList,
    Message,
    AgentMessages,
    MessageBlock,
)
from backend.util.log_setup import SetupLogging
from sqlalchemy.sql import func
from pydantic_ai.messages import ModelMessagesTypeAdapter

logger = SetupLogging()

class ChatRepository:
    """
    Repository class to handle DB operations for chat messages.
    """
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def save_message_pair(self, message_pair: MessagePair) -> bool:
        """
        Insert a user/assistant message pair in the DB.
        """
        try:
            message_orm = MessageORM(
                id=message_pair.message_id,
                session_id=message_pair.session_id,
                user_id=message_pair.user_id,
                account_id=message_pair.account_id,
                user_message=[b.model_dump() for b in message_pair.user_message.blocks],
                ai_message=[b.model_dump() for b in message_pair.ai_message.blocks],
                feedback=message_pair.feedback,
            )
            self.session.add(message_orm)
            await self.session.commit()
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"save_message_pair: SQLAlchemy Error: {str(e)}")
            return False

    async def get_messages(self, session_id: UUID) -> MessageList:
        """
        Return a list of messages (user + AI) for the given session
        """
        try:
            stmt = select(MessageORM).where(
                MessageORM.session_id == session_id
            ).order_by(MessageORM.created_at)
            result = await self.session.execute(stmt)
            rows = result.scalars().all()

            messages = []
            for row in rows:
                user_blocks = [MessageBlock(**b) for b in (row.user_message or [])]
                user_msg = Message(
                    role="user",
                    content="",
                    blocks=user_blocks,
                    message_id=row.id,
                )
                messages.append(user_msg)

                ai_blocks = [MessageBlock(**b) for b in (row.ai_message or [])]
                ai_msg = Message(
                    role="ai",
                    content="",
                    blocks=ai_blocks,
                    message_id=row.id,
                )
                messages.append(ai_msg)

            return MessageList(messages=messages)
        except Exception as e:
            logger.error(f"Error in get_messages: {str(e)}")
            return MessageList(messages=[])
        

    async def update_message_feedback(self, message_id: UUID, feedback: int) -> bool:
        """
        Update the feedback column for a single message row by ID.
        """
        try:
            stmt = (
                update(MessageORM)
                .where(MessageORM.id == message_id)
                .values(feedback=feedback, updated_at=func.now())
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount == 0:
                logger.error(f"No message found with uuid {message_id} to update feedback.")
                return False
            logger.info(f"Feedback updated for message uuid {message_id}")
            return True
        except SQLAlchemyError as e:
            await self.session.rollback()
            logger.error(f"update_message_feedback: SQLAlchemy Error: {str(e)}")
            return False

class AgentMessagesRepository:
    __slots__ = ("db",)
    def __init__(self, db: AsyncSession):
        self.db = db

    async def save_agent_run_messages(self, agent_messages: AgentMessages) -> AgentMessageORM:
        messages_json_bytes = ModelMessagesTypeAdapter.dump_json(agent_messages.messages_json)

        messages_as_dicts = json.loads(messages_json_bytes.decode('utf-8'))

        logger.info(f"messages_as_dicts: {messages_as_dicts}")

        orm_record = AgentMessageORM(
            session_id=agent_messages.session_id,
            user_id=agent_messages.user_id,
            account_id=agent_messages.account_id,
            messages_json=messages_as_dicts, 
        )

        self.db.add(orm_record)
        await self.db.flush()
        await self.db.commit()
        return orm_record


    async def get_agent_run_messages(
        self,
        session_id: UUID,
        limit: int = 1
    ) -> list[AgentMessageORM]:
        """
        Get the most recent agent messages runs for a given user/session, ordering by created_at desc.
        """
        query = (
            select(AgentMessageORM)
            .where(AgentMessageORM.session_id == session_id)
            .order_by(desc(AgentMessageORM.created_at))
            .limit(limit)
        )
        results = (await self.db.execute(query)).scalars().all()

        return results