# M.U.S.A. — Multi-User Simulation Architecture

A green CRT/WOPR browser simulation platform supporting solo and network play.

**Build 0.2 review revision: SOLO-VERIFIED-24.** Generated from branch `build-0.2`, implementation commit `aa0b142`. The full suite was rerun for this review: **24 Python tests passed**, JavaScript regressions passed, and both client syntax checks passed. Nothing has been pushed or deployed.

Live site: https://musa.jaimebsnyder.com/

Build 0.2 is a local release candidate. The existing AWS deployment remains Relay Recovery; this document does not claim that Tic-Tac-Toe is live.

## Simulations

| Selection | Behavior |
| --- | --- |
| 01 / RELAY RECOVERY | Existing two-player cooperative procedural maze. Shared fog-of-war discovery, assigned relays, joint extraction, and three-second interference delays. |
| 02 / TIC-TAC-TOE | Shows the mode-selection screen below. |
| 03 / GLOBAL THERMONUCLEAR WAR | Disabled: `ACCESS RESTRICTED // WOPR AUTHORIZATION REQUIRED`. |

### Tic-Tac-Toe modes

| Mode | Players and start | Authority | Resume and replay |
| --- | --- | --- | --- |
| 1 PLAYER / VS COMPUTER | Human X versus M.U.S.A. O. Starts immediately when created; no second browser or room join required. | Backend validates the human move, computes an optimal deterministic minimax response, and saves both moves together. No LLM or external AI service. | Existing human session restores the board; replay starts a fresh solo match immediately. |
| 2 PLAYER / NETWORK | Player 1 is X; Player 2 is O. Host starts after both join; X moves first. | Backend validates turns, occupied squares, wins, and draws and broadcasts snapshots to both clients. | Existing player tokens restore identities; host replay returns to a lobby for another match. |

Both modes use `TicTacToeRoom` in `tictactoe.py`, the same move validation and win/draw rules, and the same frontend board renderer. Three matching marks in a row, column, or diagonal win. A full board without a winner is a draw. Optimal computer play can win or draw, but cannot lose.

Network joiners enter only a room code and callsign; the room determines the simulation and mode. Solo rooms reject joins. The computer slot has no usable session token or WebSocket connection.

## AWS architecture

The existing AWS stack uses private S3 behind CloudFront with Origin Access Control, API Gateway WebSocket, Python Lambda, and two DynamoDB tables: `musa-rooms` and `musa-connections`. Route 53 supplies the custom domain and an existing us-east-1 ACM certificate supplies TLS. `infra/template.yaml` specifies Python 3.12 on arm64.

Build 0.2 reuses this infrastructure with no resource-template changes or new AWS resources. Browsers submit actions; Lambda applies authoritative rules, conditionally saves against the room version, and sends player snapshots. Solo minimax runs inside that same Lambda request.

Rooms and snapshots carry `gameType` (`maze` or `tictactoe`); stored rooms without it default to `maze`. Tic-Tac-Toe rooms and snapshots also carry `mode` (`network` or `computer`); older Tic-Tac-Toe rooms without mode default to `network`. Creating a room without a game type still creates a maze.

Room codes have five characters. Random human session tokens are stored as SHA-256 hashes in DynamoDB. Snapshots expose neither tokens nor unrevealed maze state. Shared service behavior includes token-based resume, replacement socket bindings, optimistic conflict retry, and the last 32 request IDs per player for duplicate suppression. Each solo command applies the human move and any computer response before one conditional room save; a repeated request ID does not produce additional moves. The move counter counts individual X/O placements.

Lobby and completed rooms expire after 30 minutes. Active rooms expire after two hours without a successful mutation. The service enforces expiry while DynamoDB TTL performs eventual cleanup. Heartbeats maintain the socket without extending room lifetime. Origin checks are an abuse guard rather than player authentication.

## Local development

```bash
python3 server.py --port 8000
```

Open http://localhost:8000 in one browser for computer mode or two browser profiles for network games. The local server stores rooms in memory and uses the HTTP polling client (`static/app.js`). Production builds inject the existing WebSocket URL and load `static/realtime.js`. Local in-memory rooms do not survive server restarts; AWS rooms persist in DynamoDB until expiry.

## Verified tests

```bash
python3 -m unittest discover -s tests -v
node tests/test_saved_session.cjs
node --check static/app.js
node --check static/realtime.js
git diff --check
```

The fresh run passed **24 Python test cases**: 10 original regressions, 7 network Tic-Tac-Toe cases, and 7 computer-mode cases. Coverage includes legal deterministic computer moves, win/block choices, turn rejection, terminal wins/draws, solo join rejection, persisted mode, resume/replay, duplicate-command and conflict handling, every reachable human strategy against the computer, and unchanged maze/network behavior.

JavaScript VM regressions verify mode selection, solo creation payload, hiding room join for solo mode, shared rendering, network joining, square commands, and saved-session behavior. A local HTTP smoke previously passed solo creation/moves/completion/replay, network creation/join, and default maze creation.

Browser visual/end-to-end testing remains unverified because Chromium installation failed. No live AWS gameplay verification has been performed for Build 0.2.

## Deployment gate

**Do not deploy or push without explicit approval.** See `docs/BUILD_0_2_REVIEW.md` for the current review. Deploy the backend before the frontend, including `game.py`, `tictactoe.py`, and `cloud/` in the Lambda package. Retain existing AWS resource IDs and the WebSocket endpoint.

After approval, the existing frontend publisher accepts stack outputs:

```bash
bash scripts/publish_frontend.sh <WebSocketUrl> <BucketName> <CloudFrontId>
```

It uploads the frontend, sets entrypoint metadata, and invalidates HTML, configuration, both client scripts, and CSS, then waits for completion. Verify solo play/resume/replay, network play/resume/replay, and existing maze rooms before marking this release deployed. AWS CLI and authenticated deployment access have not been established in this workspace.
