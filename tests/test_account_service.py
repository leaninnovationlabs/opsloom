import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession
import pytest_asyncio

from backend.api.account.services import AccountService
from backend.api.account.repository import AccountRepository
from backend.api.account.models import AccountCreate
from backend.lib.exceptions import AccountNotFoundError

@pytest_asyncio.fixture
async def service(session: AsyncSession) -> AccountService:
    repo = AccountRepository(session)
    service = AccountService(repo)
    yield service

@pytest.mark.asyncio
async def test_service_create_and_get(service: AccountService):
    acct = AccountCreate(email="svc@example.com", short_code="svc", name="Svc")
    created = await service.create_account(acct)
    fetched = await service.get_account(created.account_id)
    assert fetched.email == acct.email
    await service.repository.delete_account(created.account_id)

@pytest.mark.asyncio
async def test_service_get_missing(service: AccountService):
    with pytest.raises(AccountNotFoundError):
        await service.get_account(uuid.uuid4())
