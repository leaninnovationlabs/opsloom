import pytest
from uuid import uuid4
from backend.api.kbase.repository import KbaseRepository
from backend.api.kbase.models import KnowledgeBase

@pytest.mark.asyncio
@pytest.mark.parametrize(
    "kb_in,new_name",
    [
        (KnowledgeBase(id=uuid4(), name="k1", description="d1"), "k1u"),
        (KnowledgeBase(id=uuid4(), name="k2", description="d2"), "k2u"),
    ],
)
async def test_kbase_crud(async_session, kb_in, new_name):
    repo = KbaseRepository(async_session)

    created = await repo.create_kbase(kb_in)
    assert created.name == kb_in.name

    fetched = await repo.get_kbase_by_id(kb_in.id)
    assert fetched.id == kb_in.id

    updated = await repo.update_kbase(KnowledgeBase(id=kb_in.id, name=new_name, description="d"))
    assert updated.name == new_name

    listed = await repo.list_kbases()
    assert any(k.id == kb_in.id for k in listed.kbases)

    deleted = await repo.delete_kbase(kb_in.id)
    assert deleted is True
