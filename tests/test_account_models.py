import uuid
import datetime as dt
import pytest
from backend.api.account.account_schema import AccountORM
from backend.api.account.models import Account


def test_account_model_validation():
    orm = AccountORM(
        account_id=uuid.uuid4(),
        short_code="test",
        name="Test Account",
        email="test@example.com",
        protection="none",
        account_metadata={"foo": "bar"},
        root=False,
        created_at=dt.datetime.now(),
    )
    model = Account.model_validate(orm)
    assert model.account_id == orm.account_id
    assert model.short_code == orm.short_code
    assert model.email == orm.email
    assert model.metadata == orm.account_metadata
