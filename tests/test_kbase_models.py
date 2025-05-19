import uuid
from backend.api.kbase.kbase_schema import KnowledgeBaseORM
from backend.api.kbase.models import KnowledgeBase


def test_kbase_model_validation():
    # arrange
    orm = KnowledgeBaseORM(
        id=uuid.uuid4(),
        name="kb",
        description="d",
        account_short_code="a",
    )

    # act
    model = KnowledgeBase.model_validate(
        {
            "id": orm.id,
            "name": orm.name,
            "description": orm.description,
            "account_short_code": orm.account_short_code,
        }
    )

    # assert
    assert model.id == orm.id
    assert model.name == "kb"
