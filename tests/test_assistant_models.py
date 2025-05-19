import uuid
from backend.api.assistant.assistant_schema import AssistantORM
from backend.api.assistant.models import Assistant
from backend.api.assistant.models import AssistantConfig, Metadata


def test_assistant_model_validation():
    # arrange
    orm = AssistantORM(
        id=uuid.uuid4(),
        account_short_code="m",
        kbase_id=None,
        name="model",
        config={"provider": "openai", "type": "rag", "model": "gpt-4o"},
        system_prompts={"system": "hi"},
        assistant_metadata={"title": "t", "description": "d", "icon": "i"},
        active=True,
    )

    # act
    model = Assistant.model_validate(
        {
            "id": orm.id,
            "account_short_code": orm.account_short_code,
            "kbase_id": orm.kbase_id,
            "name": orm.name,
            "config": orm.config,
            "system_prompts": orm.system_prompts,
            "assistant_metadata": orm.assistant_metadata,
        }
    )

    # assert
    assert model.id == orm.id
    assert model.config.provider == "openai"
    assert model.assistant_metadata.title == "t"
