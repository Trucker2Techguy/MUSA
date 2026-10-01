# Build 0.2 review — solo and network Tic-Tac-Toe

**Review revision: MAIN-MENU-VERIFIED-24.** Regenerated from current branch `build-0.2`, the solo implementation plus the verified MAIN MENU navigation change, after rerunning the complete test suite. **24 Python tests pass. Nothing pushed or deployed.**

## Verified implementation

Selecting `02 / TIC-TAC-TOE` shows:

- `1 PLAYER / VS COMPUTER`
- `2 PLAYER / NETWORK`

Solo starts immediately with human X and M.U.S.A. O. It needs one browser and no second-player join. Deterministic optimal minimax runs in `tictactoe.py` on the backend; there is no external AI service or LLM. The same room class, move validator, win/draw evaluator, snapshot format, and board renderer serve both modes.

The backend applies a legal human move and, unless the game has ended, an optimal computer response before saving the room. Conditional-write retries recompute from authoritative state; duplicate request IDs return state without applying either move again. Computer moves cannot be submitted by a human as Player 2. The virtual computer has no usable session token or socket, and solo room joining is rejected.

Solo resume restores the human identity, board, mode, and outcome. Replay preserves credentials and computer mode and starts a fresh match immediately. Network mode retains Player 1/X and Player 2/O, host initialization, authoritative turn validation, broadcasts to both clients, and lobby-based host replay.

## Main menu navigation

A global `< MAIN MENU` CRT-style control is available from maze and solo/network Tic-Tac-Toe, including active, lobby, completed, mode-selection, and saved-session screens. It hides the game, clears frontend state and saved credentials, resets selection to the normal maze entry flow, clears room-code input, stops timers, and creates a fresh WebSocket after detaching and closing the old one. HTTP operations are guarded by a session epoch so delayed replies cannot restore abandoned state or clear a newer request's busy flag. Old socket callbacks are guarded by socket identity.

No backend delete/reset/leave request is issued. The existing WebSocket disconnect path clears only the connection binding; room records and player slots remain. Ordinary resume/reconnect is preserved. Choosing MAIN MENU intentionally discards the browser's saved token; it will no longer offer that abandoned session on reload.

## Evidence from the current branch

| Requirement | Implementation |
| --- | --- |
| Mode-selection screen | `static/index.html`; mode handlers in both `static/app.js` and `static/realtime.js`. |
| Solo start with no join | `TicTacToeRoom.join` creates the computer slot and initializes immediately; solo frontend hides join controls. |
| Deterministic optimal computer | Cached `minimax` and `computer_square` in `tictactoe.py`; stable lowest-square tie break. |
| Shared rules and renderer | Both modes call `_move` and use the same board snapshots and square buttons. |
| Persisted mode | `cloud/codec.py` saves `mode`; absent mode defaults to `network`. |
| Production request dispatch | `cloud/aws_handler.py` forwards creation mode; `cloud/service.py` uses the same room/session/mutation infrastructure. |
| Resume/replay | Shared authenticated resume; mode-preserving replay in cloud service and local server. |
| Maze backward compatibility | Missing `gameType` defaults to `maze`; maze rules remain unchanged apart from additive snapshot type. |

## Fresh test results

Commands rerun for this review:

```bash
python3 -m unittest discover -s tests -v
node tests/test_saved_session.cjs
node tests/test_main_menu.cjs
node --check static/app.js
node --check static/realtime.js
git diff --check
```

| Suite | Result | Coverage |
| --- | --- | --- |
| Original Python regressions | 10 passed | Maze reachability, hidden state, cooperative objectives/extraction, cloud persistence/retry/resume/expiry, Decimal handling, mocked frontend publishing. |
| Network Tic-Tac-Toe Python tests | 7 passed | Both players and every winning line, draws, turns/occupied squares/invalid inputs, start/session validation, legacy maze decoding, broadcasts, request deduplication, conflict retry, reconnect, replay. |
| Computer-mode Python tests | 7 passed | Immediate solo start, bot identity protection, join rejection, deterministic legal moves, win/block choices, turn handling, human win/final draw termination, exhaustive reachable human strategies, codec defaults, cloud resume/replay and conflict/duplicate retry. |
| Total Python | **24 passed** | Full discovery suite; no skipped or failing cases. |
| JavaScript VM regressions | Passed | Saved-session startup/resume/new session, game/mode selection, solo payload/no join requirement/shared rendering, room-derived network game, square payload, draw replay. |
| MAIN MENU JavaScript regression suite | Passed | Both clients and all game modes; active/lobby/completed screens, pending moves and creation, stale replies and timers, fresh create flow, saved-session resume and abandonment. |
| Both JavaScript syntax checks | Passed | HTTP and WebSocket clients. |
| Diff whitespace check | Passed | No whitespace errors. |

The exhaustive solo test follows every legal human choice against the deterministic opponent and confirms the computer never loses; both computer wins and draws occur. Human-win handling is checked using a constructed board because optimal computer play cannot reach a human win.

A local HTTP API smoke previously passed solo create/move/completion/replay, network create/join, and default maze creation. Browser visual/end-to-end testing remains **unverified**: Chromium download attempts failed. No Build 0.2 live AWS gameplay tests have been run. Automated checks establish the implemented behavior within these limits, not a completed production release.

## Production impact

No AWS resource-template changes, new resources, table migrations, room deletions, or additional APIs are required. Both Tic-Tac-Toe modes reuse API Gateway WebSocket, Lambda, DynamoDB, existing codes, session tokens, and reconnect handling. Maze rooms without `gameType` remain readable. Older clients creating rooms without type still get a maze.

The selector includes the existing Relay Recovery and disabled Global Thermonuclear War entry displaying `ACCESS RESTRICTED // WOPR AUTHORIZATION REQUIRED`. The retro CRT style remains in use.

## Release gate and order

**Do not deploy or push yet. User review and explicit deployment approval are required.**

After approval and authorized AWS access:

1. Preserve the prior backend package and frontend for rollback.
2. Update the existing Lambda first, including `tictactoe.py`, `game.py`, and `cloud/`. Publishing the frontend first would expose controls the old backend cannot handle.
3. Publish the frontend to the existing S3 bucket. The publisher invalidates HTML, config, both client scripts, and CSS and waits for CloudFront completion.
4. Verify a single-browser computer game, draw/win, refresh/resume, and replay; a two-client network game and reconnect/replay; and an existing maze-room resume plus maze gameplay.
5. Mark the README deployed only after live verification succeeds.

A backend rollback to Build 0.1 cannot decode Tic-Tac-Toe rooms. A frontend-only rollback retains backend support for existing sessions. Account for active Tic-Tac-Toe rooms before reverting the backend.

AWS CLI is absent and authenticated AWS deployment access has not been established in this workspace. No deployment operation was attempted during this review.
