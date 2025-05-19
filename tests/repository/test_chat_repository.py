import pytest
from uuid import uuid4
from backend.api.chat.repository import ChatRepository
from backend.api.chat.models import MessagePair, Message

@pytest.mark.asyncio
async def test_chat_repository_roundtrip(async_session):
    repo = ChatRepository(async_session)

    pair = MessagePair(
        user_id=uuid4(),
        account_id=uuid4(),
        session_id=uuid4(),
        user_message=Message(role="user", content="hi"),
        ai_message=Message(role="ai", content="yo"),
    )
    saved = await repo.save_message_pair(pair)
    assert saved is True

    messages = await repo.get_messages(pair.session_id)
    assert len(messages.messages) == 2

    ok = await repo.update_message_feedback(pair.message_id, 1)
    assert ok is True
