import pytest
from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from backend.api.account.account_schema import Base as AccountBase
from backend.api.session.session_schema import Base as SessionBase
from backend.api.kbase.kbase_schema import Base as KbaseBase
from backend.api.assistant.assistant_schema import Base as AssistantBase
from backend.api.chat.chat_schema import Base as ChatBase
from backend.api.auth.user_schema import Base as UserBase

@pytest.fixture
async def async_session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", future=True)
    async with engine.begin() as conn:
        await conn.run_sync(AccountBase.metadata.create_all)
        await conn.run_sync(SessionBase.metadata.create_all)
        await conn.run_sync(KbaseBase.metadata.create_all)
        await conn.run_sync(AssistantBase.metadata.create_all)
        await conn.run_sync(ChatBase.metadata.create_all)
        await conn.run_sync(UserBase.metadata.create_all)
    SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
    async with SessionLocal() as session:
        yield session
    await engine.dispose()
