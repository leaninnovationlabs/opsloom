import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.session.services import SessionService
from backend.api.session.repository import SessionRepository
from backend.api.assistant.repository import AssistantRepository
from backend.api.assistant.models import Assistant, AssistantConfig
from backend.util.auth_utils import TokenData

@pytest.mark.asyncio
async def test_session_service_crud(session: AsyncSession):
    # arrange
    service = SessionService(session)
    # create assistant for session
    assistant_repo = AssistantRepository(session)
    assistant = await assistant_repo.create_assistant(
        Assistant(
            name="s",
            account_short_code="svc",
            config=AssistantConfig(provider="openai", type="rag", model="gpt-4o"),
            system_prompts={"system": "hi"},
        )
    )
    token = TokenData(email=None, account_id=str(uuid.uuid4()), account_short_code="svc", user_id=str(uuid.uuid4()))

    # act
    sess_obj = await service.create_session_object(token, assistant.id)
    stored = await service.store_chat_session(sess_obj)
    fetched = await service.get_session(stored.id)
    await service.update_session_title(stored.id, "title")
    updated = await service.get_session(stored.id)
    deleted = await service.delete_session(stored.id)
    await assistant_repo.delete_assistant(str(assistant.id))

    # assert
    assert fetched.id == stored.id
    assert updated.title == "title"
    assert deleted
