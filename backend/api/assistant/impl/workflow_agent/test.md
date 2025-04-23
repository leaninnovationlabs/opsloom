1. Basic Information Retrieval:
* What territory is Disney in? (Tests: search_entities -> get_account_details)
* Tell me about Bob Johnson. (Tests: search_entities -> get_person_details)
* Show me details for territory ID <T_WEST_ENT_ID> (Replace <T_WEST_ENT_ID> with the actual UUID generated in your seed script - Tests: get_territory_details)
* Does Pixar have a parent account? (Tests: search_entities -> get_account_details)

2. Starting a Move Workflow:
* Move Acme Corporation to Julie Smith. (Tests: Search Acme, Search Julie, Get Julie's territory, Ask Commit/Propose -> Propose)
* I want to transfer Bob Johnson to the West Enterprise territory. (Tests: Search Bob, Ask Commit/Propose -> Propose)
* Move Disney to Bob Johnson's territory. (Tests: Search Disney, Get Disney Details [sees family], Search Bob, Get Bob's territory, Ask Commit/Propose, Ask Family -> Propose)

3. Two-Step Commit Workflow:
* First: Propose moving Stark Industries to West Enterprise.
* (The agent should respond confirming the proposal and potentially giving a move ID like 123).
* Second: Yes, commit move 123. (Replace 123 with the actual ID given - Tests: commit_move)

4. Audit History:
* Show me the move history for account Disney. (Tests: search_entities -> get_audit_history - Note: The mock history is hardcoded in the tool for now).