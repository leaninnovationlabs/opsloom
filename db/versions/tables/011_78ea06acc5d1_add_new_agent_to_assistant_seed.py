"""add new agent to assistant seed

Revision ID: 78ea06acc5d1
Revises: 95fce5bd97c2
Create Date: 2025-04-20 22:40:06.413734

"""
from typing import Sequence, Union
import uuid
import os

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql
from sqlalchemy.orm import Session

# -- Imports from your 'backend/api/assistant' folder.
from backend.api.assistant.assistant_schema import AssistantORM
from backend.api.assistant.models import (
    Assistant,
    AssistantConfig,
    Metadata,
)

# revision identifiers, used by Alembic.
revision: str = '78ea06acc5d1'
down_revision: Union[str, None] = '95fce5bd97c2'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None

# Define the default short code
is_multitenant = False
default_short_code = "default"

# New Assistant UUID
NEW_ASSISTANT_ID = uuid.UUID("203870e3-f088-4e61-847b-d994d6138f17")


def get_new_assistant_data() -> Assistant:
    """
    Return a Pydantic Assistant model for the new assistant.
    """
    return Assistant(
        id=NEW_ASSISTANT_ID,
        name="workflow_agent",
        account_short_code=default_short_code,
        kbase_id=None,
        config=AssistantConfig(
            provider="openai",
            type="workflow_agent",
            model="gpt-4",
        ),
        system_prompts={
            "system": "You are the Workflow Agent, specialized in helping users automate their workflows using APIs. Your primary role is to assist users in setting up, connecting, and optimizing their workflow automation. You can provide guidance on API integration, suggest best practices for workflow design, and help troubleshoot automation issues. You're knowledgeable about common workflow patterns, API authentication methods, and data transformation techniques. Always be concise and focus on practical, implementable solutions."
        },
        assistant_metadata=Metadata(
            title="Workflow Agent",
            description="Get help to automate workflow APIs",
            icon="autorenew",
            prompts=[
                "What can you help me with?",
                "Can you help me move Pixar to Bob Johnson's territory?",
                "What territories does Disney have?",
            ],
            num_history_messages=5,
        ),
    )


def upgrade() -> None:
    """Seed the 'assistant' table with the new assistant record."""
    print(f"Adding new assistant with ID: {NEW_ASSISTANT_ID}")
    assistant_data = get_new_assistant_data()

    bind = op.get_bind()
    session = Session(bind=bind)

    # 1) Check if the assistant row already exists
    existing = session.get(AssistantORM, assistant_data.id)
    if existing:
        print(f"Assistant {assistant_data.id} already exists; skipping insert.")
        session.close()
        return

    # 2) Convert Pydantic -> ORM
    new_assistant = AssistantORM(
        id=assistant_data.id,
        account_short_code=assistant_data.account_short_code,
        kbase_id=assistant_data.kbase_id,
        name=assistant_data.name,
        config=assistant_data.config.model_dump(),
        system_prompts=assistant_data.system_prompts,
        assistant_metadata=(
            assistant_data.assistant_metadata.model_dump()
            if assistant_data.assistant_metadata
            else None
        ),
    )

    session.add(new_assistant)
    try:
        session.commit()
        print(f"Successfully inserted assistant {assistant_data.id}")
    except Exception as e:
        session.rollback()
        print(f"Error inserting assistant {assistant_data.id}: {e}")
        raise e
    finally:
        session.close()


def downgrade() -> None:
    """Remove the newly added assistant record."""
    print(f"Removing assistant with ID: {NEW_ASSISTANT_ID}")
    assistant_id = NEW_ASSISTANT_ID

    bind = op.get_bind()
    session = Session(bind=bind)

    try:
        # Get the ORM object
        assistant_to_delete = session.get(AssistantORM, assistant_id)

        if assistant_to_delete:
             # Check if there are related sessions
            related_sessions_exist = session.query(sa.exists().where(sa.text("session.assistant_id = :assistant_id"))).params(assistant_id=assistant_id).scalar()

            if related_sessions_exist:
                print(f"Cannot delete assistant {assistant_id} as related sessions exist. Manually delete sessions and messages first if required.")
                # Delete related messages and sessions if needed
                session.execute(sa.text(
                    """
                    DELETE FROM message
                    WHERE session_id IN (
                      SELECT id FROM session WHERE assistant_id = :assistant_id
                    )
                    """
                ).bindparams(sa.bindparam("assistant_id", type_=sa.dialects.postgresql.UUID(as_uuid=True))).params(assistant_id=assistant_id))
                session.execute(sa.text("DELETE FROM session WHERE assistant_id = :assistant_id")
                    .bindparams(sa.bindparam("assistant_id", type_=sa.dialects.postgresql.UUID(as_uuid=True))).params(assistant_id=assistant_id))
                session.delete(assistant_to_delete)
            else:
                session.delete(assistant_to_delete)
                print(f"Deleted assistant {assistant_id}")
        else:
            print(f"Assistant {assistant_id} not found; skipping delete.")

        session.commit()
    except Exception as e:
        session.rollback()
        print(f"Error deleting assistant {assistant_id}: {e}")
        raise e
    finally:
        session.close()
