import pytest
from uuid import uuid4
from backend.api.assistant.repository import AssistantRepository
from backend.api.assistant.models import Assistant, AssistantConfig

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "assistant_in,new_name",
    [
        (
            Assistant(
                name="a1",
                account_short_code="acc",
                config=AssistantConfig(provider="p", type="t", model="m"),
                system_prompts={},
            ),
            "x1",
        ),
        (
            Assistant(
                name="a2",
                account_short_code="acc",
                config=AssistantConfig(provider="p", type="t", model="m"),
                system_prompts={},
            ),
            "x2",
        ),
    ],
)
async def test_assistant_crud(async_session, assistant_in, new_name):
    repo = AssistantRepository(async_session)

    created = await repo.create_assistant(assistant_in)
    assert created.name == assistant_in.name

    fetched = await repo.get_assistant_by_id(str(created.id))
    assert fetched.id == created.id

    created.name = new_name
    updated = await repo.update_assistant(created)
    assert updated.name == new_name

    listed = await repo.list_assistants(assistant_in.account_short_code)
    assert any(a.id == created.id for a in listed.assistants)

    deact = await repo.deactivate_assistant(str(created.id))
    assert deact is True
    react = await repo.reactivate_assistant(str(created.id))
    assert react is True

    deleted = await repo.delete_assistant(str(created.id))
    assert deleted is True
