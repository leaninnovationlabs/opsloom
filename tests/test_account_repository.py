import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.account.repository import AccountRepository
from backend.api.account.models import AccountCreate, AccountUpdate
from backend.api.account.account_schema import AccountORM


@pytest.mark.asyncio
async def test_create_and_get_account(session: AsyncSession):
    repo = AccountRepository(session)
    acct = AccountCreate(email="repo@example.com", short_code="repo", name="Repo")
    created = await repo.create_account(acct)
    fetched = await repo.get_account_by_id(created.account_id)
    assert fetched.email == "repo@example.com"
    await repo.delete_account(created.account_id)

@pytest.mark.asyncio
async def test_update_account(session: AsyncSession):
    repo = AccountRepository(session)
    acct = AccountCreate(email="update@example.com", short_code="upd", name="Upd")
    created = await repo.create_account(acct)
    update = AccountUpdate(account_id=created.account_id, name="Updated")
    updated = await repo.update_account(update)
    assert updated.name == "Updated"
    await repo.delete_account(created.account_id)
