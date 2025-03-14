import os
from typing import AsyncGenerator

from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from sqlalchemy.orm import sessionmaker

DATABASE_URL = os.getenv("POSTGRES_CONNECTION_STRING")

engine = create_async_engine(
    DATABASE_URL,
    echo=False,  
    future=True      
    # pool_size=5,       
    # max_overflow=10
)

async def get_async_session() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides an AsyncSession.
    Yields the session, ensuring that it is closed after use.
    """
    # print(f"Creating new session for request")

    async_session = sessionmaker(
        bind=engine,
        class_=AsyncSession,
        expire_on_commit=False,
        autoflush=False,
    )
    async with async_session() as session:
        try:
            yield session
        finally:
            # The session context manager handles rollback/close if needed
            await session.close()
