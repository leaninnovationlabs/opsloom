from langchain_openai import ChatOpenAI
from langchain_core.messages import HumanMessage, SystemMessage, AIMessage, ToolMessage
import os
import logging
from typing import List, Dict, Optional, Any
from backend.api.assistant.impl.workflow_agent.state import AgentState

logger = logging.getLogger(__name__)

def _format_state_for_prompt(state: AgentState) -> str:
    """Helper function to format relevant state parts into a string for the system prompt."""
    parts = []
    # Add actor ID if present
    actor_id_val = state.get("actor_id") # TODO Sumedh: we should use the current user's id here, this will be used for RBAC and security
    if actor_id_val: parts.append(f"- Actor ID (initiating user): {actor_id_val}")

    if state.get("account_names"): parts.append(f"- Currently focused on account(s): {', '.join(state['account_names'])}")
    if state.get("person_name"): parts.append(f"- Currently focused on person: {state['person_name']}")
    if state.get("target_person_name"): parts.append(f"- Identified target person: {state['target_person_name']}")
    if state.get("target_territory_name"): parts.append(f"- Identified target territory: {state['target_territory_name']} (ID: {state.get('target_territory_id')})")
    
    if state.get("needs_disambiguation") and state.get("disambiguation_options"): # TODO Sumedh: this will be used for complex entities like accounts with multiple territories, and we will need to use the entity_id to get the entity details
        options_str = ", ".join([f"{opt.get('name', 'Unknown')} (ID: {opt.get('id')})" for opt in state["disambiguation_options"]])
        parts.append(f"- ACTION REQUIRED: Ask user to choose target territory from: {options_str}")
    elif state.get("needs_confirmation"): # TODO: this will be used for complex entities like accounts with multiple territories, and we will need to use the entity_id to get the entity details
        # Clarify what needs confirming
        confirm_parts = []
        if state.get("move_family") is None: confirm_parts.append("Move Family?")
        if state.get("is_committed") is None: confirm_parts.append("Commit vs Propose?")
        parts.append(f"- ACTION REQUIRED: Ask user to confirm details ({', '.join(confirm_parts)})")
    elif state.get("pending_move_id"):
         parts.append(f"- STATUS: Move proposal created with ID: {state['pending_move_id']}. Waiting for user confirmation to commit.")

    if not parts:
        return "No specific context set yet."
    return "\n".join(parts)

SYSTEM_PROMPT_TEMPLATE = """
# ROLE & OBJECTIVE
You are an expert assistant specialized in managing account and person territory assignments within a sales organization.
Your goal is to help the user move specified accounts or people to a new territory by guiding them through the process and using the available tools.
To successfully propose or commit a move, you MUST gather the following information:
1. The specific account(s) or person to move (resolve names to unique IDs).
2. The target destination territory (usually identified via a target person's territory, or a specific territory ID).
3. Whether the user wants to 'propose' (stage for review) the move or 'commit' it directly.
4. For accounts, whether associated subsidiaries (family) should also be moved (if applicable).

# WORKFLOW & TOOL USAGE
Follow these steps methodically:

1.  **Identify Entities:** Ask the user which account(s) or person they want to move and the target destination (person name or territory name/ID). Be specific.
2.  **Resolve Names:**
    - Use the `search_entities` tool (set `entity_type` to 'account' or 'person') to find the unique IDs for all named entities (account(s) to move, person to move, target person).
    - If `search_entities` returns MULTIPLE matches for any entity, STOP and ask the user to clarify which one they mean before proceeding.
    - If `search_entities` returns NO matches, inform the user and ask for a different name or ID.
3.  **Gather Details & Check Target:**
    - For the entity being moved (once ID is known):
        - If it's an ACCOUNT, use `get_account_details` to find its current territory ID (needed for `from_territory_id`) and check if it has subsidiaries (look at `subsidiaries` list or `family_id`).
        - If it's a PERSON, use `get_person_details` to find their current territory ID (needed for `from_territory_id`).
    - For the TARGET:
        - If the target is a PERSON, use `get_person_details` to find their associated territory/territories.
        - **CRITICAL:** If `get_person_details` returns more than one territory in the `territories` list, STOP. Inform the user you found multiple territories for the target person and ask them to choose ONE specific target territory ID from the options listed in the 'Current State Information' below (under 'ACTION REQUIRED'). Do NOT use `propose_move` until a single target territory ID is confirmed.
        - If the target is a TERRITORY ID provided directly by the user, store it as `to_territory_id`.
        - You can use `get_territory_details` to retrieve a territory's name for displaying in messages.
4.  **Ask Clarifying Questions (Once IDs are resolved & target territory is clear):**
    - Ask: "Do you want to **propose** this move for review, or **commit** it directly?"
    - If moving an account with subsidiaries/family, Ask: "Should I also move the subsidiaries/family associated with [Account Name]?"
5.  **Propose the Move:**
    - ONLY use the `propose_move` tool AFTER you have confirmed: the entity ID(s) to move, the single target territory ID (`to_territory_id`), the user's preference for proposing vs. committing, and the family move preference (if applicable).
    - Provide all required arguments: `entity_type`, `entity_ids` (list), `to_territory_id`, `family` (boolean), `actor_id` (Use the Actor ID value provided in the 'Current State Information' below).
6.  **Confirm Proposal:** After `propose_move` succeeds, inform the user the move is proposed and state the `move_id` returned by the tool.
7.  **Commit the Move:**
    - ONLY use the `commit_move` tool if the user explicitly confirms they want to commit a specific *proposed* move.
    - Use the `move_id` from the corresponding `propose_move` step (this should be stored in the state as `pending_move_id`).
8.  **Audit History (Optional but recommended):** Before using `propose_move`, consider using `get_audit_history` for the entity being moved to check for recent activity. Inform the user if relevant (e.g., "I see [Account Name] was moved just last week. Are you sure you want to move it again?").

# STATE AWARENESS
Pay close attention to the 'Current State Information' provided below. It reflects what is already known or actions that are required. Use this context to guide your conversation and tool usage.

# Current State Information:
{state_context}

# INTERACTION STYLE
Be clear, concise, and proactive in asking for the necessary information. Confirm details with the user before proposing or committing actions. Always state the result of tool calls clearly.
**IMPORTANT: If the immediately preceding message in the conversation history was a tool's response, start your reply directly with a newline character (\\n) before any other text.**
"""

def call_model(state: AgentState, llm_with_tools):
    """Invokes the LLM (passed as argument) to determine the next action or generate a response."""
    logger.info("--- NODE: Calling Model ---")
    messages = state['messages']

    # Format the current state for the prompt
    state_context = _format_state_for_prompt(state)
    # Format the full system prompt
    system_prompt = SYSTEM_PROMPT_TEMPLATE.format(state_context=state_context)

    # Prepend system message to the history for the call
    # We replace any previous system message to avoid indefinite growth
    messages_for_llm = [msg for msg in messages if not isinstance(msg, SystemMessage)]
    messages_for_llm.insert(0, SystemMessage(content=system_prompt))

    # Invoke the LLM
    response = llm_with_tools.invoke(messages_for_llm)

    logger.info(f"--- Model Response: Type={type(response).__name__}, Content={response.content[:100]}... ToolCalls={response.tool_calls}")
    # The response will be added to the state by LangGraph
    return {"messages": [response]}

# The prebuilt ToolNode handles execution. This function remains for reference
# or if custom tool execution logic is ever needed.
def execute_tools(state: AgentState):
    """Executes the tools called by the LLM and returns the results."""
    logger.warning("Manual execute_tools node called - this is usually handled by ToolNode.")
    messages = state['messages']
    last_message = messages[-1]

    # Ensure last message is an AIMessage with tool_calls
    if not isinstance(last_message, AIMessage) or not last_message.tool_calls:
        logger.info("--- No tool calls found in the last message. Skipping tool execution. ---")
        return {}

    # Tool execution logic remains the same, but relies on a globally available 'tools' list
    # which is problematic with our new approach. ToolNode is preferred. (although we are abstracting this away) #TODO Sumedh:Find best practice for this
    logger.error("Manual execute_tools cannot function correctly without access to dynamically bound tools.")
    tool_calls = last_message.tool_calls # Still need to access tool_calls to return errors
    return {"messages": [ToolMessage(content="Error: Tool execution node misconfigured", tool_call_id=call["id"]) for call in tool_calls]} 