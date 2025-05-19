import pytest
from uuid import uuid4
from backend.api.auth.repository import UserRepository
from backend.api.auth.models import User

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "user_in,new_email",
    [
        (User(id=uuid4(), account_id=uuid4(), account_short_code="acc", email="e1@example.com", password="p", phone_no="1"), "u1@example.com"),
        (User(id=uuid4(), account_id=uuid4(), account_short_code="acc", email="e2@example.com", password="p", phone_no="2"), "u2@example.com"),
    ],
)
async def test_user_crud(async_session, user_in, new_email):
    repo = UserRepository(async_session)

    created = await repo.create_user(user_in)
    assert created.email == user_in.email

    fetched = await repo.get_user_by_id(user_in.id)
    assert fetched.id == user_in.id

    fetched.email = new_email
    updated = await repo.update_user(fetched)
    assert updated.email == new_email

    assert await repo.validate_password(user_in.password)

    by_email = await repo.get_user_by_email(updated.email)
    assert by_email.id == user_in.id

    deleted = await repo.delete_user(user_in.id)
    assert deleted is True
