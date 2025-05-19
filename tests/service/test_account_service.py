import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from backend.api.account.services import AccountService
from backend.api.account.models import Account, AccountCreate, AccountUpdate

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,repo_method,arg,expected",
    [
        (
            "create_account",
            "create_account",
            AccountCreate(short_code="a", name="x"),
            Account(account_id=uuid4(), short_code="a", name="x"),
        ),
        (
            "get_account",
            "get_account_by_id",
            uuid4(),
            Account(account_id=uuid4(), short_code="b", name="y"),
        ),
    ],
)
async def test_account_service_calls_repo(method, repo_method, arg, expected):
    repo = AsyncMock()
    getattr(repo, repo_method).return_value = expected
    service = AccountService(repo)

    if isinstance(arg, AccountCreate):
        result = await getattr(service, method)(arg)
    else:
        result = await getattr(service, method)(arg)

    assert result == expected
    getattr(repo, repo_method).assert_awaited()
