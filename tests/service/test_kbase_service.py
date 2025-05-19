import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from backend.api.kbase.services import KbaseService
from backend.api.kbase.models import KnowledgeBase, KnowledgeBaseList

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,repo_method,arg,expected",
    [
        (
            "create_kbase",
            "create_kbase",
            KnowledgeBase(id=uuid4(), name="k", description="d"),
            KnowledgeBase(id=uuid4(), name="k", description="d"),
        ),
        (
            "list_kbases",
            "list_kbases",
            None,
            KnowledgeBaseList(kbases=[]),
        ),
    ],
)
async def test_kbase_service(method, repo_method, arg, expected):
    repo = AsyncMock()
    getattr(repo, repo_method).return_value = expected
    service = KbaseService(repo)

    if arg is None:
        result = await getattr(service, method)()
    else:
        result = await getattr(service, method)(arg)

    assert result == expected
    getattr(repo, repo_method).assert_awaited()
