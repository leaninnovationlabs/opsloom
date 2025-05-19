import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from backend.api.session.services import SessionService
from backend.api.session.models import UserSession, SessionList
from backend.util.auth_utils import TokenData

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "method,repo_method,arg,expected",
    [
        (
            "create_session_object",
            None,
            (TokenData(user_id=str(uuid4()), account_id=str(uuid4()), email="e"), uuid4()),
            UserSession(id=uuid4(), user_id=uuid4(), account_id=uuid4(), assistant_id=uuid4()),
        ),
    ],
)
async def test_session_service_create_session_object(method, repo_method, arg, expected):
    db = AsyncMock()
    service = SessionService(db)
    # Mock assistant_repo.get_assistant_by_id to return something
    service.assistant_repo.get_assistant_by_id = AsyncMock(return_value=True)
    token, assistant_id = arg
    result = await service.create_session_object(token, assistant_id)
    assert isinstance(result, UserSession)
