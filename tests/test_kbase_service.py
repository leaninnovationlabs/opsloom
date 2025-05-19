import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from backend.api.kbase.repository import KbaseRepository
from backend.api.kbase.services import KbaseService
from backend.api.kbase.models import KnowledgeBase

@pytest.mark.asyncio
async def test_kbase_service_crud(session: AsyncSession):
    # arrange
    repo = KbaseRepository(session)
    service = KbaseService(repo)
    kbase_in = KnowledgeBase(name="svc_kb", description="desc", account_short_code="svc")

    # act
    created = await service.create_kbase(kbase_in)
    fetched = await service.get_kbase(created.id)
    update = KnowledgeBase(id=created.id, name="svc_kb2", description="desc", account_short_code="svc")
    updated = await service.update_kbase(update)
    delete_ok = await service.delete_kbase(created.id)

    # assert
    assert fetched.name == "svc_kb"
    assert updated.name == "svc_kb2"
    assert delete_ok
