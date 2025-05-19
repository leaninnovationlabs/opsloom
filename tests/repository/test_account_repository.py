import pytest
from uuid import uuid4
from backend.api.account.repository import AccountRepository
from backend.api.account.models import AccountCreate, AccountUpdate

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "acct_create,update_name",
    [
        (AccountCreate(short_code="a1", name="Alpha", email="a@example.com"), "New Alpha"),
        (AccountCreate(short_code="a2", name="Beta", email="b@example.com"), "New Beta"),
    ],
)
async def test_account_crud(async_session, acct_create, update_name):
    repo = AccountRepository(async_session)

    # Arrange & Act - create
    account = await repo.create_account(acct_create)

    # Assert create
    assert account.short_code == acct_create.short_code

    # Act - get by short code
    fetched = await repo.get_account_by_short_code(acct_create.short_code)

    # Assert get
    assert fetched.account_id == account.account_id

    # Act - update
    updated = await repo.update_account(
        AccountUpdate(account_id=account.account_id, name=update_name)
    )

    # Assert update
    assert updated.name == update_name

    # Act - delete
    result = await repo.delete_account(account.account_id)

    # Assert delete
    assert result is True
