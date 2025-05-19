import pytest
from unittest.mock import AsyncMock
from uuid import uuid4
from fastapi import HTTPException
from backend.api.chat.services import ChatService
from backend.api.session.models import UserSession
from backend.util.auth_utils import TokenData

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "session_result,user_id,account_id,expect_error",
    [
        (UserSession(id=uuid4(), user_id=uuid4(), account_id=uuid4(), assistant_id=uuid4()), None, None, False),
        (None, uuid4(), uuid4(), True),
    ],
)
async def test_validate_session(session_result, user_id, account_id, expect_error):
    db = AsyncMock()
    service = ChatService(db)
    service.session_repository.get_user_session = AsyncMock(return_value=session_result)

    current_user = TokenData(user_id=str(user_id or session_result.user_id), account_id=str(account_id or session_result.account_id), email="e")

    if expect_error:
        with pytest.raises(HTTPException):
            await service.validate_session(str(uuid4()), current_user)
    else:
        result = await service.validate_session(str(session_result.id), current_user)
        assert result.id == session_result.id
