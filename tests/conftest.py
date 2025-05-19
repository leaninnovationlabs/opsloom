import os
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING", "postgresql+asyncpg://myuser:mypassword@localhost:5432/ragdb")
engine = create_async_engine(DATABASE_URL, future=True)
AsyncSessionLocal = sessionmaker(bind=engine, expire_on_commit=False, class_=AsyncSession)

@pytest_asyncio.fixture
async def session() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        yield session
