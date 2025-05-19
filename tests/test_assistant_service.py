import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.assistant.repository import AssistantRepository
from backend.api.assistant.services import AssistantService
from backend.api.assistant.models import Assistant, AssistantConfig

@pytest.mark.asyncio
async def test_assistant_service_crud(session: AsyncSession):
    # arrange
    repo = AssistantRepository(session)
    service = AssistantService(repo)
    assistant_in = Assistant(
        name="svcassist",
        account_short_code="svc",
        config=AssistantConfig(provider="openai", type="rag", model="gpt-4o"),
        system_prompts={"system": "hi"},
    )

    # act
    created = await service.create_assistant(assistant_in)
    fetched = await service.get_assistant(created.id)
    update = Assistant(
        id=created.id,
        name="svcassist2",
        account_short_code="svc",
        config=AssistantConfig(provider="openai", type="rag", model="gpt-4o"),
        system_prompts={"system": "hi"},
    )
    updated = await service.update_assistant(update)
    await service.deactivate_assistant(created.id)
    await service.reactivate_assistant(created.id)
    deleted = await service.delete_assistant(created.id)

    # assert
    assert fetched.name == "svcassist"
    assert updated.name == "svcassist2"
    assert deleted
