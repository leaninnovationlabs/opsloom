import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from backend.api.assistant.services import AssistantService
from backend.api.assistant.models import Assistant, AssistantConfig, AssistantList

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,repo_method,arg,expected",
    [
        (
            "create_assistant",
            "create_assistant",
            Assistant(name="a", account_short_code="acc", config=AssistantConfig(provider="p", type="t", model="m"), system_prompts={}),
            Assistant(id=uuid4(), name="a", account_short_code="acc", config=AssistantConfig(provider="p", type="t", model="m"), system_prompts={}),
        ),
        (
            "list_assistants",
            "list_assistants",
            "acc",
            AssistantList(assistants=[]),
        ),
    ],
)
async def test_assistant_service(method, repo_method, arg, expected):
    repo = AsyncMock()
    getattr(repo, repo_method).return_value = expected
    service = AssistantService(repo)

    if isinstance(arg, str) or arg is None:
        result = await getattr(service, method)(arg)
    else:
        result = await getattr(service, method)(arg)

    assert result == expected
    getattr(repo, repo_method).assert_awaited()
