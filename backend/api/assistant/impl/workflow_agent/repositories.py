import logging
from uuid import UUID
from typing import List, Optional, Sequence, Tuple, Any

from sqlalchemy import select, update, func
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from .models import Territory, AccountFullcast, Person, MoveEvent, EntityEnum

logger = logging.getLogger(__name__)

class WorkflowRepositoryError(Exception):
    """Custom exception for repository errors."""
    pass

class WorkflowRepository:
    """Handles database operations for the workflow agent tables."""

    def __init__(self, session: AsyncSession):
        self.db = session

    async def search_entities(
        self, entity_type: EntityEnum, query: str, limit: int = 5
    ) -> List[dict]:
        """Search for accounts or people by name."""
        logger.info(f"Searching for {entity_type.value} matching '{query}' (limit: {limit})")
        try:
            if entity_type == EntityEnum.account:
                stmt = (
                    select(AccountFullcast.account_id, AccountFullcast.account_name)
                    .where(AccountFullcast.account_name.ilike(f"%{query}%"))
                    .limit(limit)
                )
                results = await self.db.execute(stmt)
                return [{"id": str(row.account_id), "name": row.account_name} for row in results.all()]
            elif entity_type == EntityEnum.person:
                stmt = (
                    select(Person.person_id, Person.person_name)
                    .where(Person.person_name.ilike(f"%{query}%"))
                    .limit(limit)
                )
                results = await self.db.execute(stmt)
                return [{"id": str(row.person_id), "name": row.person_name} for row in results.all()]
            else:
                raise ValueError(f"Unsupported entity type: {entity_type}")
        except Exception as e:
            logger.error(f"Error searching entities ({entity_type.value} '{query}'): {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error during search: {e}")

    async def get_account_details(self, account_id: UUID) -> Optional[dict]:
        """Get full account details including territory and children (subsidiaries)."""
        logger.info(f"Getting details for account {account_id}")
        try:
            stmt = (
                select(AccountFullcast)
                .options(selectinload(AccountFullcast.children))
                .where(AccountFullcast.account_id == account_id)
            )
            result = await self.db.execute(stmt)
            account = result.scalar_one_or_none()
            if not account:
                return None

            # Prepare children data (assuming direct children are subsidiaries for this context)
            subsidiaries = [
                {"id": str(child.account_id), "name": child.account_name}
                for child in account.children
            ]

            return {
                "id": str(account.account_id),
                "name": account.account_name,
                "territory_id": str(account.territory_id),
                "family_id": str(account.family_id) if account.family_id else None,
                "subsidiaries": subsidiaries
            }
        except Exception as e:
            logger.error(f"Error getting account details for {account_id}: {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error getting account details: {e}")

    async def get_person_territories(self, person_id: UUID) -> Optional[dict]:
        """Get person details including their assigned territory/territories."""
        # Note: Current schema (person.territory_id) only supports one territory per person.
        # The tool description anticipates multiple, so we return a list for future flexibility.
        logger.info(f"Getting territory info for person {person_id}")
        try:
            stmt = (
                select(Person.person_id, Person.person_name, Person.territory_id, Territory.territory_name)
                .join(Territory, Person.territory_id == Territory.territory_id)
                .where(Person.person_id == person_id)
            )
            result = await self.db.execute(stmt)
            person = result.first() # Use first() as person_id is unique

            if not person:
                return None

            territories = [
                {"id": str(person.territory_id), "name": person.territory_name}
            ]

            return {
                "id": str(person.person_id),
                "name": person.person_name,
                "territories": territories
            }
        except Exception as e:
            logger.error(f"Error getting person territories for {person_id}: {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error getting person territories: {e}")

    async def get_territory_details(self, territory_id: UUID) -> Optional[dict]:
        """Get territory details including name and generate a pseudo-path."""
        # Generating the full path might require a recursive query or separate logic.
        # For now, just return the name.
        logger.info(f"Getting details for territory {territory_id}")
        try:
            stmt = select(Territory).where(Territory.territory_id == territory_id)
            result = await self.db.execute(stmt)
            territory = result.scalar_one_or_none()
            if not territory:
                return None

            # Placeholder for path generation logic
            path = f"/Placeholder/{territory.territory_name}"

            return {
                "id": str(territory.territory_id),
                "name": territory.territory_name,
                "path": path # TODO: Implement proper path generation if needed
            }
        except Exception as e:
            logger.error(f"Error getting territory details for {territory_id}: {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error getting territory details: {e}")

    async def create_move_event(
        self,
        entity_type: EntityEnum,
        entity_id: UUID,
        from_territory_id: UUID,
        to_territory_id: UUID,
        family_flag: bool,
        actor_person_id: Optional[UUID],
        committed: bool = False
    ) -> int:
        """Creates a new move event record."""
        logger.info(f"Creating move event: {entity_type.value} {entity_id} to {to_territory_id} by actor {actor_person_id}")
        try:
            move = MoveEvent(
                entity_type=entity_type,
                entity_id=entity_id,
                from_territory_id=from_territory_id,
                to_territory_id=to_territory_id,
                committed=committed,
                family_flag=family_flag,
                actor_person_id=actor_person_id
            )
            self.db.add(move)
            await self.db.flush()
            await self.db.commit()
            logger.info(f"Move event created with ID: {move.move_id}")
            return move.move_id
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error creating move event: {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error creating move event: {e}")

    async def commit_move_event(self, move_id: int) -> bool:
        """Updates a move event to set committed = TRUE AND updates the actual entity's territory."""
        logger.info(f"Attempting to commit move event {move_id}")
        try:
            # 1. Get the move event details first
            get_stmt = select(MoveEvent).where(MoveEvent.move_id == move_id)
            result = await self.db.execute(get_stmt)
            move_event = result.scalar_one_or_none()

            if not move_event:
                logger.warning(f"Move event {move_id} not found for commit.")
                return False
            
            if move_event.committed:
                logger.warning(f"Move event {move_id} is already committed.")
                # Decide if this should be True (already done) or False (no action taken now)
                return True # Let's consider it success if already done

            # 2. Update the entity table based on entity_type
            update_entity_stmt = None
            if move_event.entity_type == EntityEnum.account:
                update_entity_stmt = (
                    update(AccountFullcast)
                    .where(AccountFullcast.account_id == move_event.entity_id)
                    .values(territory_id=move_event.to_territory_id)
                )
                logger.info(f"Prepared update for account {move_event.entity_id} to territory {move_event.to_territory_id}")
            elif move_event.entity_type == EntityEnum.person:
                update_entity_stmt = (
                    update(Person)
                    .where(Person.person_id == move_event.entity_id)
                    .values(territory_id=move_event.to_territory_id)
                )
                logger.info(f"Prepared update for person {move_event.entity_id} to territory {move_event.to_territory_id}")
            else:
                # Should not happen if validation is correct, but handle defensively
                logger.error(f"Cannot commit move: Unsupported entity_type '{move_event.entity_type}' in move event {move_id}")
                raise WorkflowRepositoryError(f"Unsupported entity type for commit: {move_event.entity_type}")

            # Execute entity update
            await self.db.execute(update_entity_stmt)
            logger.info(f"Executed entity update for move event {move_id}")

            # 3. Update the move event table to mark as committed
            update_move_stmt = (
                update(MoveEvent)
                .where(MoveEvent.move_id == move_id)
                .values(committed=True)
                .returning(MoveEvent.move_id) # Optional: confirm update happened
            )
            result = await self.db.execute(update_move_stmt)
            updated_id = result.scalar_one_or_none()

            # 4. Commit the transaction (covers both updates)
            await self.db.commit()

            if updated_id is None:
                 # This case should technically be caught earlier by the initial select,
                 # but adding a belt-and-suspenders check.
                logger.error(f"Failed to update commit status for move event {move_id} after entity update.")
                # Consider raising an error here as state is inconsistent
                return False 

            logger.info(f"Move event {move_id} and associated entity territory committed successfully.")
            return True
        except Exception as e:
            await self.db.rollback()
            logger.error(f"Error committing move event {move_id}: {e}", exc_info=True)
            # Re-raise or return False based on desired error handling
            raise WorkflowRepositoryError(f"Database error committing move event: {e}")

    async def get_move_event_history(self, entity_id: UUID, limit: int = 10) -> List[dict]:
        """Get the history of move events for a specific entity."""
        logger.info(f"Getting move history for entity {entity_id} (limit: {limit})")
        try:
            stmt = (
                select(MoveEvent)
                .where(MoveEvent.entity_id == entity_id)
                .order_by(MoveEvent.created_at.desc())
                .limit(limit)
            )
            results = await self.db.execute(stmt)
            history = results.scalars().all()
            return [
                {
                    "move_id": event.move_id,
                    "entity_type": event.entity_type.value,
                    "entity_id": str(event.entity_id),
                    "from_territory_id": str(event.from_territory_id),
                    "to_territory_id": str(event.to_territory_id),
                    "committed": event.committed,
                    "family_flag": event.family_flag,
                    "actor_person_id": str(event.actor_person_id) if event.actor_person_id else None,
                    "created_at": event.created_at.isoformat(),
                }
                for event in history
            ]
        except Exception as e:
            logger.error(f"Error getting move history for entity {entity_id}: {e}", exc_info=True)
            raise WorkflowRepositoryError(f"Database error getting move history: {e}") 