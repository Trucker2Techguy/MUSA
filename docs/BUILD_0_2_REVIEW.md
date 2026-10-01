# Build 0.2 deployment review

Status: implemented locally on branch `build-0.2`; no AWS deployment and no GitHub push performed.

## Changes

- Simulation selector with Relay Recovery, Tic-Tac-Toe, and disabled Global Thermonuclear War with the requested WOPR authorization message.
- Dedicated `tictactoe.py` with backend turn, square, win, draw, and completion validation.
- `gameType` in room persistence and snapshots; absent room types decode as `maze`.
- Shared cloud service dispatches room creation, decoding, commands, and replay to the correct game. Joining derives the game from the room. Existing player identities, hashed tokens, connections, version checks, request deduplication, and broadcasts remain in use.
- Both HTTP development and WebSocket production clients render Tic-Tac-Toe while preserving the existing maze canvas renderer. Tic-Tac-Toe uses accessible square buttons and highlights winning lines.
- README describes the existing AWS architecture accurately and labels Build 0.2 as pending deployment.
- Frontend publishing invalidates both client scripts and CSS as well as existing HTML/config paths.

## Validation

- 17 Python unittest cases pass (10 existing plus 7 Tic-Tac-Toe cases).
- Maze generation/reachability, visibility, relay activation, and cooperative extraction regressions pass.
- Tic-Tac-Toe validates every winning line for both players, draws, invalid inputs, turns, occupied squares, start/session restrictions, and post-completion rejection.
- Service integration covers shared broadcasts, simulated conditional-write conflict, duplicate requests, authenticated resume for both players, stale disconnect protection, winning/draw replay, preserved connections and credentials, and legacy maze decoding.
- JavaScript VM tests pass: saved-session startup/resume/new session; selected game creation payload; room-derived Tic-Tac-Toe rendering; square command payload; draw replay; joining without a game selection payload.
- Both JavaScript syntax checks pass. `git diff --check` passes.
- Browser visual/end-to-end checks remain unverified: Playwright is installed but Chromium is absent; attempted browser downloads returned invalid/truncated archives. No live AWS gameplay tests were run.

## Production impact and release order

No AWS resource template changes, new resources, DynamoDB migrations, or room deletions are required. Maze engine behavior is unchanged except for the additive snapshot game type. Existing maze rooms without the field remain readable; default creation without a type remains a maze, allowing existing clients to continue operating.

Deploy the updated Lambda first, including `tictactoe.py`. Publishing the new frontend first would expose Tic-Tac-Toe controls to a backend that cannot handle them. Then publish the frontend and invalidate all modified asset paths. Verify existing maze resume and a full maze game, plus a two-client Tic-Tac-Toe match, draw, replay, refresh and socket reconnect before declaring the release deployed.

Rolling back Lambda to Build 0.1 after Tic-Tac-Toe rooms exist would make those rooms unreadable. A frontend-only rollback retains backend support for existing rooms. Save the prior Lambda package and frontend for a coordinated rollback, and account for active Tic-Tac-Toe rooms before reverting the backend.

AWS CLI is not installed in this environment and authenticated AWS deployment access has not been established. Approval alone does not establish access; use the existing authorized deployment environment or provide an appropriate deployment connection. Never share AWS secret keys in chat.

Deployment is explicitly gated on the user's approval. After live verification, update the README release status to describe Build 0.2 as deployed.
