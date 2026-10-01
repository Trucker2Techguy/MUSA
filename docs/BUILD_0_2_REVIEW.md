# Build 0.2 deployment review

Status: implemented locally on branch `build-0.2`; no AWS deployment and no GitHub push performed.

## Changes

- Simulation selector with Relay Recovery, Tic-Tac-Toe, and disabled Global Thermonuclear War with the requested WOPR authorization message.
- Mode selection after Tic-Tac-Toe: `1 PLAYER / VS COMPUTER` and `2 PLAYER / NETWORK`.
- Dedicated `tictactoe.py` with backend turn, square, win, draw, and completion validation.
- Solo mode starts immediately; the human is X and M.U.S.A. is O. Deterministic backend minimax chooses optimal legal moves without external services. Both modes use the same rules, snapshot format, and renderer.
- `mode` is persisted in Tic-Tac-Toe rooms/snapshots; missing mode defaults to `network`. The computer has no usable session token or socket. Room join is rejected for solo games. Human and computer moves save atomically in one service mutation, preserving duplicate suppression and conflict retry.
- Solo resume restores the human session and board. Solo replay retains the human credentials and mode and starts a fresh match immediately; network replay retains the existing lobby/start flow.
- `gameType` in room persistence and snapshots; absent room types decode as `maze`.
- Shared cloud service dispatches room creation, decoding, commands, and replay to the correct game. Joining derives the game from the room. Existing player identities, hashed tokens, connections, version checks, request deduplication, and broadcasts remain in use.
- Both HTTP development and WebSocket production clients render Tic-Tac-Toe while preserving the existing maze canvas renderer. Tic-Tac-Toe uses accessible square buttons and highlights winning lines.
- README describes the existing AWS architecture accurately and labels Build 0.2 as pending deployment.
- Frontend publishing invalidates both client scripts and CSS as well as existing HTML/config paths.

## Validation

- 24 Python unittest cases pass (10 original, 7 network Tic-Tac-Toe, and 7 computer-mode cases).
- Maze generation/reachability, visibility, relay activation, and cooperative extraction regressions pass.
- Tic-Tac-Toe validates every winning line for both players, draws, invalid inputs, turns, occupied squares, start/session restrictions, and post-completion rejection.
- Solo tests verify deterministic/legal computer moves, immediate wins, blocking losses, turn ownership, invalid moves, no extra computer move after a human win or final draw, and every reachable human strategy against the optimal opponent. Both computer wins and draws are reachable; human wins are impossible against optimal play. Rules still correctly terminate on a human winning board.
- Service integration covers shared broadcasts, simulated conditional-write conflict, duplicate requests, authenticated resume for both players, stale disconnect protection, winning/draw replay, preserved connections and credentials, and legacy maze decoding. Solo integration additionally covers conflict retries, duplicate human commands, join rejection, resume, replay, and an unbound computer slot.
- JavaScript VM tests pass: saved-session startup/resume/new session; selected game creation payload; room-derived Tic-Tac-Toe rendering; square command payload; draw replay; joining without a game selection payload; mode-selection visibility, solo creation payload, no join requirement, and the shared solo renderer.
- Real local HTTP API smoke passes: solo creation, human/computer move, completion and replay; network creation/join; default maze creation.
- Both JavaScript syntax checks pass. `git diff --check` passes.
- Browser visual/end-to-end checks remain unverified: Playwright is installed but Chromium is absent; attempted browser downloads returned invalid/truncated archives. No live AWS gameplay tests were run.

## Production impact and release order

No AWS resource template changes, new resources, DynamoDB migrations, or room deletions are required. Maze engine behavior is unchanged except for the additive snapshot game type. Existing maze rooms without the field remain readable; default creation without a type remains a maze, allowing existing clients to continue operating.

Deploy the updated Lambda first, including `tictactoe.py`. Publishing the new frontend first would expose Tic-Tac-Toe controls to a backend that cannot handle them. Then publish the frontend and invalidate all modified asset paths. Verify existing maze resume and a full maze game, plus a two-client Tic-Tac-Toe match, draw, replay, refresh and socket reconnect, and a single-browser computer game with resume and replay before declaring the release deployed.

Rolling back Lambda to Build 0.1 after Tic-Tac-Toe rooms exist would make those rooms unreadable. A frontend-only rollback retains backend support for existing rooms. Save the prior Lambda package and frontend for a coordinated rollback, and account for active Tic-Tac-Toe rooms before reverting the backend.

AWS CLI is not installed in this environment and authenticated AWS deployment access has not been established. Approval alone does not establish access; use the existing authorized deployment environment or provide an appropriate deployment connection. Never share AWS secret keys in chat.

Deployment is explicitly gated on the user's approval. After live verification, update the README release status to describe Build 0.2 as deployed.
