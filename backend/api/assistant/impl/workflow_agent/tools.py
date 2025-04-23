from langchain_core.tools import tool
from uuid import UUID
from typing import List, Literal, Optional
import logging

# Import the repository and models
from .repositories import WorkflowRepository, WorkflowRepositoryError
from .models import EntityEnum

logger = logging.getLogger(__name__)

# TODO: Implement actual logic for these tools, potentially interacting with repositories

# Tool Implementation Functions (accept repo as first argument)
# These are NOT decorated with @tool directly here.

async def _search_entities_impl(repo: WorkflowRepository, entity_type: Literal["account", "person"], query: str) -> List[dict]:
    """Implementation: Search for accounts or people by name."""
    logger.info(f"Tool call: Searching {entity_type} for '{query}'")
    try:
        # Convert string literal to Enum
        search_type = EntityEnum[entity_type]
        results = await repo.search_entities(entity_type=search_type, query=query)
        if not results:
            return f"No {entity_type} found matching '{query}'."
        return results
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in search_entities: {e}")
        return f"Error searching for {entity_type}: {e}"
    except KeyError:
        return f"Invalid entity_type specified: {entity_type}. Must be 'account' or 'person'."
    except Exception as e:
        logger.exception(f"Unexpected error in search_entities tool for {entity_type} '{query}'")
        return f"An unexpected error occurred while searching."

async def _get_account_details_impl(repo: WorkflowRepository, account_id: UUID) -> dict:
    """Implementation: Get full account record."""
    logger.info(f"Tool call: Getting details for account {account_id}")
    try:
        details = await repo.get_account_details(account_id=account_id)
        if details is None:
            return f"Account with ID {account_id} not found."
        return details
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in get_account_details: {e}")
        return f"Error getting account details: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in get_account_details tool for {account_id}")
        return f"An unexpected error occurred while getting account details."

async def _get_person_details_impl(repo: WorkflowRepository, person_id: UUID) -> dict:
    """Implementation: Get person record including territories."""
    logger.info(f"Tool call: Getting details for person {person_id}")
    try:
        details = await repo.get_person_territories(person_id=person_id)
        if details is None:
            return f"Person with ID {person_id} not found."
        # Check for multiple territories (future-proofing based on description)
        if len(details.get("territories", [])) > 1:
            logger.warning(f"Person {person_id} found in multiple territories, may need disambiguation.")
            # The tool itself returns the data; the agent node decides on disambiguation.
        return details
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in get_person_details: {e}")
        return f"Error getting person details: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in get_person_details tool for {person_id}")
        return f"An unexpected error occurred while getting person details."

async def _get_territory_details_impl(repo: WorkflowRepository, territory_id: UUID) -> dict:
    """Implementation: Get territory details."""
    logger.info(f"Tool call: Getting details for territory {territory_id}")
    try:
        details = await repo.get_territory_details(territory_id=territory_id)
        if details is None:
            return f"Territory with ID {territory_id} not found."
        return details
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in get_territory_details: {e}")
        return f"Error getting territory details: {e}"
    except Exception as e:
        logger.exception(f"Unexpected error in get_territory_details tool for {territory_id}")
        return f"An unexpected error occurred while getting territory details."

async def _propose_move_impl(
    repo: WorkflowRepository,
    entity_type: Literal["account", "person"],
    entity_ids: List[UUID],
    to_territory_id: UUID,
    family: bool,
    actor_id: Optional[UUID] = None
) -> dict:
    """Implementation: Propose a move by creating a 'move_event' record."""
    logger.info(f"Tool call: Proposing move for {entity_type}(s) {entity_ids} to {to_territory_id} by actor {actor_id}")
    if not entity_ids:
        return {"error": "No entity IDs provided for the move."}

    try:
        move_type = EntityEnum[entity_type]
        # For simplicity in POC, assume the 'from_territory' is the same for all entities
        # and get it from the first entity. A real implementation might need more checks.
        first_entity_id = entity_ids[0]
        from_territory_id_str = None
        if move_type == EntityEnum.account:
            details = await repo.get_account_details(first_entity_id)
            if details: from_territory_id_str = details.get('territory_id')
        elif move_type == EntityEnum.person:
            details = await repo.get_person_territories(first_entity_id)
            if details and details.get('territories'): from_territory_id_str = details['territories'][0].get('id')

        if not from_territory_id_str:
             return {"error": f"Could not determine current territory for {entity_type} {first_entity_id}"}

        from_territory_id = UUID(from_territory_id_str)

        # Create one move event per entity for auditability
        # A real implementation might group them or handle families differently.
        # For this POC, we'll just record the first proposed move ID. #TODO Sumedh: we should record all move ids, ask Bala/Tyler for confirmation, we need to avoid multiple move events for the same entity
        first_move_id = None
        for entity_id in entity_ids:
            move_id = await repo.create_move_event(
                entity_type=move_type,
                entity_id=entity_id,
                from_territory_id=from_territory_id,
                to_territory_id=to_territory_id,
                family_flag=family,
                actor_person_id=actor_id,
                committed=False
            )
            if first_move_id is None: first_move_id = move_id

        if first_move_id is None:
             return {"error": "Failed to create any move events in the database."}

        logger.info(f"Move proposed, first event ID: {first_move_id}")
        # Return the ID of the first created event for potential commit tracking
        return { "move_id": first_move_id, "status": "proposed" }
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in propose_move: {e}")
        return {"error": f"Error proposing move: {e}"}
    except KeyError:
        return {"error": f"Invalid entity_type specified: {entity_type}. Must be 'account' or 'person'."}
    except Exception as e:
        logger.exception(f"Unexpected error in propose_move tool")
        return {"error": f"An unexpected error occurred while proposing the move."}

async def _commit_move_impl(repo: WorkflowRepository, move_id: int) -> dict:
    """Implementation: Commit a previously proposed move."""
    logger.info(f"Tool call: Committing move {move_id}")
    try:
        success = await repo.commit_move_event(move_id=move_id)
        if not success:
            return {"error": f"Failed to commit move event {move_id}. It might not exist or already be committed."}

        # TODO: Add logic here to call the actual external Fullcast API if needed.
        # logger.info(f"Triggering external commit for move {move_id}...")

        return { "move_id": move_id, "status": "committed" }
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in commit_move: {e}")
        return {"error": f"Error committing move: {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error in commit_move tool for {move_id}")
        return {"error": f"An unexpected error occurred while committing the move."}

async def _get_audit_history_impl(repo: WorkflowRepository, entity_id: UUID, limit: int = 10) -> List[dict]:
    """Implementation: Get the audit history for a specific entity."""
    logger.info(f"Tool call: Getting audit history for entity {entity_id} (limit: {limit})")
    try:
        history = await repo.get_move_event_history(entity_id=entity_id, limit=limit)
        if not history:
            return f"No move history found for entity {entity_id}."
        return history
    except WorkflowRepositoryError as e:
        logger.error(f"Repo error in get_audit_history: {e}")
        return {"error": f"Error getting audit history: {e}"}
    except Exception as e:
        logger.exception(f"Unexpected error in get_audit_history tool for {entity_id}")
        return {"error": f"An unexpected error occurred while getting audit history."}

# Note: The actual @tool decoration and list creation will happen in graph.py
# where the 'repo' instance is available. 