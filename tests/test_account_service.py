import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.account.services import AccountService
from backend.api.account.repository import AccountRepository
from backend.api.account.models import AccountCreate
from backend.lib.exceptions import AccountNotFoundError


@pytest.mark.asyncio
async def test_service_create_and_get(session: AsyncSession):
    # arrange
    repo = AccountRepository(session)
    service = AccountService(repo)
    acct = AccountCreate(email="svc@example.com", short_code="svc", name="Svc")

    # act
    created = await service.create_account(acct)
    fetched = await service.get_account(created.account_id)
    await service.repository.delete_account(created.account_id)

    # assert
    assert fetched.email == acct.email

@pytest.mark.asyncio
async def test_service_get_missing(session: AsyncSession):
    # arrange
    repo = AccountRepository(session)
    service = AccountService(repo)

    # act/assert
    with pytest.raises(AccountNotFoundError):
        await service.get_account(uuid.uuid4())
