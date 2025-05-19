import uuid
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from backend.api.kbase.repository import KbaseRepository
from backend.api.kbase.models import KnowledgeBase

@pytest.mark.asyncio
async def test_kbase_repository_crud(session: AsyncSession):
    # arrange
    repo = KbaseRepository(session)
    kbase_in = KnowledgeBase(name="kb1", description="desc", account_short_code="acct")

    # act
    created = await repo.create_kbase(kbase_in)
    fetched = await repo.get_kbase_by_id(created.id)
    kbase_update = KnowledgeBase(id=created.id, name="kb1-up", description="desc", account_short_code="acct")
    updated = await repo.update_kbase(kbase_update)
    delete_ok = await repo.delete_kbase(created.id)

    # assert
    assert fetched.name == "kb1"
    assert updated.name == "kb1-up"
    assert delete_ok
