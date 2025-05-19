import pytest
from uuid import uuid4
from backend.api.session.repository import SessionRepository
from backend.api.session.models import UserSession

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "session_in,updated_title",
    [
        (UserSession(id=uuid4(), user_id=uuid4(), account_id=uuid4(), assistant_id=uuid4(), title=""), "t1"),
        (UserSession(id=uuid4(), user_id=uuid4(), account_id=uuid4(), assistant_id=uuid4(), title=""), "t2"),
    ],
)
async def test_session_crud(async_session, session_in, updated_title):
    repo = SessionRepository(async_session)

    created = await repo.set_user_session(session_in)
    assert created.id == session_in.id

    fetched = await repo.get_user_session(session_in.id)
    assert fetched.id == session_in.id

    title_set = await repo.update_session_title(session_in.id, updated_title)
    assert title_set is True
    assert await repo.check_session_title(session_in.id)

    sessions = await repo.list_user_sessions(session_in.user_id)
    assert any(s.id == session_in.id for s in sessions.list)

    deleted = await repo.delete_user_session(session_in.id)
    assert deleted is True
