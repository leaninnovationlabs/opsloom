import os
import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

from backend.api.account.services import AccountService
from backend.api.account.repository import AccountRepository
from backend.api.account.models import AccountCreate
from backend.lib.exceptions import AccountNotFoundError

DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+asyncpg://myuser:mypassword@localhost:5432/ragdb")
engine = create_async_engine(DATABASE_URL, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

@pytest.fixture
async def service():
    async with AsyncSessionLocal() as session:
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
