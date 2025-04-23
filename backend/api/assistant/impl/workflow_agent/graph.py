import functools
import logging
from uuid import UUID
from typing import List, Optional
from langgraph.graph import StateGraph, END
# from langgraph.checkpoint.aiosqlite import AsyncSqliteSaver # Commented out but we should use this for persistence or maybe Redis? TODO: Sumedh

from backend.api.assistant.impl.workflow_agent.state import AgentState
from backend.api.assistant.impl.workflow_agent.repositories import WorkflowRepository
from backend.api.assistant.impl.workflow_agent.nodes import call_model
from backend.api.assistant.impl.workflow_agent.tools import (
    _search_entities_impl,
    _get_account_details_impl,
    _get_person_details_impl,
    _get_territory_details_impl,
    _propose_move_impl,
    _commit_move_impl,
    _get_audit_history_impl
)

from langchain_core.messages import ToolMessage
from langgraph.prebuilt import ToolNode
from langchain_openai import ChatOpenAI
from langchain_core.tools import tool
import os

logger = logging.getLogger(__name__)

# TODO: Implement more complex graph logic with tool calls and tool results handling based on business rules

def should_continue(state: AgentState) -> str:
    """Determines whether to continue the graph (call tools) or end."""
    last_message = state['messages'][-1]
    if hasattr(last_message, 'tool_calls') and last_message.tool_calls:
        logger.info("Condition: Tool call detected, routing to action node.")
        return "execute_tools"
    logger.info("Condition: No tool call detected, ending graph.")
    return END


def create_graph(repo: WorkflowRepository):
    """Creates and compiles the LangGraph StateGraph, binding tools to the repository."""
    logger.info("Creating LangGraph workflow...")

    # 1. Bind the repository to the tool implementation functions
    #    and decorate the bound functions with @tool (this is standard LangGraph practice)
    @tool
    async def search_entities(entity_type: str, query: str):
        """Search for accounts or people by name to resolve fuzzy user input to canonical IDs. Detects duplicates."""
        # Note: We use functools.partial to bind the repo to the async impl function
        bound_func = functools.partial(_search_entities_impl, repo)
        return await bound_func(entity_type=entity_type, query=query)

    @tool
    async def get_account_details(account_id: UUID):
        """Get full account record, including territory and subsidiaries/family ID, to determine current state and ask about moving the family."""
        bound_func = functools.partial(_get_account_details_impl, repo)
        return await bound_func(account_id=account_id)

    @tool
    async def get_person_details(person_id: UUID):
        """Get person record, including their assigned territories, to check for potential disambiguation."""
        bound_func = functools.partial(_get_person_details_impl, repo)
        return await bound_func(person_id=person_id)

    @tool
    async def get_territory_details(territory_id: UUID):
        """Get territory details, like its full path name, for user confirmation messages."""
        bound_func = functools.partial(_get_territory_details_impl, repo)
        return await bound_func(territory_id=territory_id)

    @tool
    async def propose_move(entity_type: str, entity_ids: List[UUID], to_territory_id: UUID, family: bool, actor_id: Optional[UUID] = None):
        """Propose a move by creating a 'move_event' record with committed=false. This stages the move for review."""
        bound_func = functools.partial(_propose_move_impl, repo)
        return await bound_func(entity_type=entity_type, entity_ids=entity_ids, to_territory_id=to_territory_id, family=family, actor_id=actor_id)

    @tool
    async def commit_move(move_id: int):
        """Commit a previously proposed move by updating its status and triggering the final action (e.g., calling Fullcast)."""
        bound_func = functools.partial(_commit_move_impl, repo)
        return await bound_func(move_id=move_id)

    @tool
    async def get_audit_history(entity_id: UUID, limit: int = 10):
        """Get the audit history for a specific entity (account or person) to check for recent moves."""
        bound_func = functools.partial(_get_audit_history_impl, repo)
        return await bound_func(entity_id=entity_id, limit=limit)

    # List of the actual tools the LLM can use
    actual_tools = [
        search_entities,
        get_account_details,
        get_person_details,
        get_territory_details,
        propose_move,
        commit_move,
        get_audit_history
    ]

    # 2. Initialize LLM and bind the created tools
    # Ensure OPENAI_API_KEY is set in your environment
    llm = ChatOpenAI(model="gpt-4o") # we are using gpt-4o for now, but we can use other models if needed
    llm_with_tools = llm.bind_tools(actual_tools) # this is very important
    logger.info(f"LLM initialized and bound to {len(actual_tools)} tools.")

    # 3. Define the graph structure
    workflow = StateGraph(AgentState)

    # Define the nodes
    # Use functools.partial to pass the bound LLM to the call_model node function
    workflow.add_node("agent", functools.partial(call_model, llm_with_tools=llm_with_tools))
    tool_node = ToolNode(actual_tools)
    workflow.add_node("action", tool_node)

    # Set the entrypoint
    workflow.set_entry_point("agent")

    # Add edges
    workflow.add_conditional_edges(
        "agent",
        should_continue,
        {
            "execute_tools": "action",
            END: END
        }
    )
    workflow.add_edge("action", "agent")

    # 4. Compile the graph
    # No checkpointer for now, add if persistence is needed (TODO: Sumedh) - we should actually use Redis for this
    memory = None
    app = workflow.compile(checkpointer=memory)
    logger.info("LangGraph workflow compiled successfully.")
    return app

# Example usage (for testing)
# if __name__ == "__main__":
#     app = create_graph()
    # Run the graph (requires async context)
    # import asyncio
    # async def run():
    #     async for event in app.astream(
    #         {"messages": [("user", "Move Disney to Julie")]},
    #         config={"configurable": {"thread_id": "test-thread"}}
    #     ):
    #         print(event)
    # asyncio.run(run()) 