import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.assistant.repository import AssistantRepository
from backend.api.assistant.models import Assistant, AssistantConfig

@pytest.mark.asyncio
async def test_assistant_repository_crud(session: AsyncSession):
    # arrange
    repo = AssistantRepository(session)
    assistant_in = Assistant(
        name="assist",
        account_short_code="acct",
        config=AssistantConfig(provider="openai", type="rag", model="gpt-4o"),
        system_prompts={"system": "hi"},
    )

    # act
    created = await repo.create_assistant(assistant_in)
    fetched = await repo.get_assistant_by_id(str(created.id))
    assistant_update = Assistant(
        id=created.id,
        name="assist2",
        account_short_code="acct",
        config=AssistantConfig(provider="openai", type="rag", model="gpt-4o"),
        system_prompts={"system": "hi"},
    )
    updated = await repo.update_assistant(assistant_update)
    listed = await repo.list_assistants("acct")
    deact = await repo.deactivate_assistant(str(created.id))
    react = await repo.reactivate_assistant(str(created.id))
    deleted = await repo.delete_assistant(str(created.id))

    # assert
    assert fetched.name == "assist"
    assert updated.name == "assist2"
    assert len(listed.assistants) >= 1
    assert deact and react and deleted
