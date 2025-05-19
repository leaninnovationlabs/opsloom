import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.session.repository import SessionRepository
from backend.api.session.models import UserSession

@pytest.mark.asyncio
async def test_session_repository_crud(session: AsyncSession):
    # arrange
    repo = SessionRepository(session)
    user_session = UserSession(
        user_id=uuid.uuid4(),
        account_id=uuid.uuid4(),
        assistant_id=uuid.uuid4(),
        title="first",
    )

    # act
    created = await repo.set_user_session(user_session)
    fetched = await repo.get_user_session(created.id)
    await repo.update_session_title(created.id, "updated")
    updated = await repo.get_user_session(created.id)
    deleted = await repo.delete_user_session(created.id)

    # assert
    assert fetched.title == "first"
    assert updated.title == "updated"
    assert deleted
