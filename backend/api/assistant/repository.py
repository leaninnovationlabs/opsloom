from typing import Optional
import uuid
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, update, delete
from sqlalchemy.exc import IntegrityError, NoResultFound
from backend.api.assistant.assistant_schema import AssistantORM
from backend.api.assistant.models import (
    Assistant,
    Metadata,
    AssistantConfig,
    AssistantList
)
from backend.lib.exceptions import (
    DatabaseError
)
from backend.util.config import get_config
import logging

logger = logging.getLogger(__name__)

class AssistantRepository:
    __slots__ = ("session",)
    def __init__(self, session: AsyncSession):
        self.session = session

    async def validate_config(self, config_dict: dict) -> bool:
        """
        Validate the assistant's config. 
        Pretend we're calling get_config() and checking allowed providers, types, models, etc.
        """
        config = get_config()
        allowed_providers = config.get('providers', 'allowed_providers', fallback='')
        allowed_types = config.get('types', 'allowed_assistant_types', fallback='')
        allowed_models = config.get('models', 'allowed_models', fallback='')

        if config_dict.get("provider") not in allowed_providers:
            logger.error(f"Invalid provider in config: {config_dict.get('provider')}")
            return False
        if config_dict.get("type") not in allowed_types:
            logger.error(f"Invalid type in config: {config_dict.get('type')}")
            return False
        if config_dict.get("model") not in allowed_models:
            logger.error(f"Invalid model in config: {config_dict.get('model')}")
            return False

        return True

    async def create_assistant(self, assistant_in: Assistant) -> Optional[Assistant]:
        try:
            # Example config validation (optional)
            valid = await self.validate_config(assistant_in.config.model_dump())
            if not valid:
                return None
            
            new_id = uuid.uuid4()

            # Convert config and metadata to dict before storing
            config_dict = assistant_in.config.model_dump()
            # rename to 'assistant_metadata'
            metadata_dict = None
            if assistant_in.assistant_metadata: 
                metadata_dict = assistant_in.assistant_metadata.model_dump()


            logger.info(f"metadata dict: {metadata_dict}")

            assistant_orm = AssistantORM(
                id=new_id,
                account_short_code=assistant_in.account_short_code,
                kbase_id=assistant_in.kbase_id,
                name=assistant_in.name,
                config=config_dict,
                system_prompts=assistant_in.system_prompts,
                assistant_metadata=metadata_dict,
                active=True
            )


            self.session.add(assistant_orm)
            await self.session.commit()
            await self.session.refresh(assistant_orm)

            return Assistant(
                id=assistant_orm.id,
                name=assistant_orm.name,
                account_short_code=assistant_orm.account_short_code,
                kbase_id=assistant_orm.kbase_id,
                config=AssistantConfig.model_validate(config_dict),
                system_prompts=assistant_orm.system_prompts,
                assistant_metadata=(
                    Metadata.model_validate(metadata_dict) if metadata_dict is not None else None
                ),
            )

        except IntegrityError as e:
            await self.session.rollback()
            logger.error(f"IntegrityError creating Assistant: {e}")
            return None
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error creating Assistant: {e}", exc_info=True)
            raise DatabaseError("A database error occurred while creating an assistant.")

    async def update_assistant(self, assistant_in: Assistant) -> Optional[Assistant]:
        """
        Update an existing assistant row from Pydantic model.
        """
        try:
            valid = await self.validate_config(assistant_in.config.model_dump())
            if not valid:
                logger.error(f"Invalid config for assistant: {assistant_in.config.model_dump()}")
                return None

            stmt = (
                update(AssistantORM)
                .where(AssistantORM.id == assistant_in.id)
                .values(
                    name=assistant_in.name,
                    system_prompts=assistant_in.system_prompts,
                    config=assistant_in.config.model_dump(),
                    assistant_metadata=assistant_in.assistant_metadata.model_dump() if assistant_in.assistant_metadata else None,
                )
                .returning(AssistantORM)
            )

            result = await self.session.execute(stmt)
            await self.session.commit()
            updated_orm = result.scalar_one_or_none()
            if not updated_orm:
                logger.error(f"No assistant exists with ID: {assistant_in.id}")
                return None

            return self._to_pydantic(updated_orm)

        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error updating Assistant: {str(e)}", exc_info=True)
            return None

    async def get_assistant_by_id(self, assistant_id: str) -> Optional[Assistant]:
        """
        Retrieve an assistant by string ID (UUID).
        """
        try:
            stmt = select(AssistantORM).where(AssistantORM.id == assistant_id)
            result = await self.session.execute(stmt)
            orm_obj = result.scalar_one_or_none()
            if not orm_obj:
                logger.error(f"Assistant with ID {assistant_id} not found.")
                return None

            return self._to_pydantic(orm_obj)
        except NoResultFound:
            logger.error(f"Assistant with ID {assistant_id} not found (NoResultFound).")
            return None
        except Exception as e:
            logger.error(f"Unexpected error retrieving Assistant: {str(e)}", exc_info=True)
            return None

    async def list_assistants(self, account_short_code: str) -> AssistantList:
        """
        Return all active assistants for a given short_code.
        """
        try:
            stmt = select(AssistantORM).where(
                AssistantORM.account_short_code == account_short_code,
                AssistantORM.active
            )
            result = await self.session.execute(stmt)
            rows = result.scalars().all()

            assistants = [
                self._to_pydantic(row)
                for row in rows
            ]
            return AssistantList(assistants=assistants)
        except Exception as e:
            logger.error(f"Unexpected error listing Assistants: {str(e)}", exc_info=True)
            return AssistantList(assistants=[])

    async def deactivate_assistant(self, assistant_id: str) -> bool:
        """
        Mark 'active' as False for the given assistant.
        """
        try:
            stmt = (
                update(AssistantORM)
                .where(AssistantORM.id == assistant_id)
                .values(active=False)
                .returning(AssistantORM)
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            if not result.scalar_one_or_none():
                logger.error(f"No assistant exists with ID: {assistant_id}")
                return False
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error inactivating Assistant: {str(e)}", exc_info=True)
            return False

    async def reactivate_assistant(self, assistant_id: str) -> bool:
        """
        Mark 'active' as True for the given assistant.
        """
        try:
            stmt = (
                update(AssistantORM)
                .where(AssistantORM.id == assistant_id)
                .values(active=True)
                .returning(AssistantORM)
            )
            result = await self.session.execute(stmt)
            await self.session.commit()
            if not result.scalar_one_or_none():
                logger.error(f"No assistant exists with ID: {assistant_id}")
                return False
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error reactivating Assistant: {str(e)}", exc_info=True)
            return False

    async def delete_assistant(self, assistant_id: str) -> bool:
        """
        Permanently delete the assistant row from DB.
        """
        try:
            stmt = delete(AssistantORM).where(AssistantORM.id == assistant_id)
            result = await self.session.execute(stmt)
            await self.session.commit()
            if result.rowcount == 0:
                logger.error(f"No assistant exists with ID: {assistant_id}")
                return False
            return True
        except Exception as e:
            await self.session.rollback()
            logger.error(f"Unexpected error deleting Assistant: {str(e)}", exc_info=True)
            return False

    def _to_pydantic(self, orm_obj: AssistantORM) -> Assistant:
        # We know config is a dict, assistant_metadata is a dict or None
        config_dict = orm_obj.config or {}
        meta_dict = orm_obj.assistant_metadata or None

        return Assistant(
            id=orm_obj.id,
            name=orm_obj.name,
            account_short_code=orm_obj.account_short_code,
            kbase_id=orm_obj.kbase_id,
            config=AssistantConfig.model_validate(config_dict),
            system_prompts=orm_obj.system_prompts,
            assistant_metadata=(
                Metadata.model_validate(meta_dict) if meta_dict is not None else None
            ),
        )

