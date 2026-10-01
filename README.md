# M.U.S.A. — Multi-User Simulation Architecture

A two-player browser simulation platform with a green CRT/WOPR interface.

Live site: https://musa.jaimebsnyder.com/

**Release status:** Build 0.2 is prepared for review, pending deployment approval. The live deployment remains Build 0.1 (Relay Recovery). Do not interpret the new game below as deployed yet.

## Simulations

- **01 / Relay Recovery:** existing cooperative procedural maze. Both players share fog-of-war discovery, activate their assigned relays, and reach extraction together. Interference delays movement for three seconds.
- **02 / Tic-Tac-Toe (Build 0.2):** competitive play. Player 1 is X; Player 2 is O. X starts. The backend validates turns and squares and determines wins and draws. The host can create another match after completion.
- **03 / Global Thermonuclear War:** disabled; `ACCESS RESTRICTED // WOPR AUTHORIZATION REQUIRED`.

The creator selects the simulation. A joining player needs only the room code and automatically receives the room's game type. Resume uses the existing saved player credentials for either game.

## Deployed AWS architecture

The existing deployment uses a private S3 frontend bucket behind CloudFront with Origin Access Control, an API Gateway WebSocket API, a Python Lambda handler, and two DynamoDB tables (`musa-rooms` and `musa-connections`). Route 53 provides the custom domain; an existing us-east-1 ACM certificate supplies TLS. The template uses Python 3.12 on arm64. Build 0.2 requires no new AWS resources or template changes.

Browsers send actions over WebSocket. Lambda loads authoritative room state, applies game rules, conditionally saves against the room version, and broadcasts player snapshots. Rooms use five-character codes. Random player session tokens are stored as SHA-256 hashes in DynamoDB; snapshots never expose tokens or the hidden maze. Origin validation is an abuse guard, not player authentication.

Rooms and snapshots carry `gameType` (`maze` or `tictactoe`). Missing stored room types default to `maze`, preserving existing rooms. Maze rules stay in `game.py`; Tic-Tac-Toe rules live in `tictactoe.py`. The codec selects the matching room implementation. Both games share session binding, optimistic concurrency, retries, and the last 32 request IDs per player for duplicate suppression.

Lobby and completed rooms expire after 30 minutes; active rooms expire after two hours without a successful mutation. DynamoDB TTL performs eventual cleanup, while the service enforces expiry immediately. Disconnects preserve player slots for authenticated resume. Heartbeats maintain the socket without extending room lifetime.

## Local development

```bash
python3 server.py --port 8000
```

Open http://localhost:8000 in two browser profiles. `static/config.js` selects the local HTTP polling client by default. Production builds inject the existing WebSocket endpoint and use `static/realtime.js`. The local server stores rooms in memory and is a development tool, not the production backend.

## Validation

```bash
python3 -m unittest discover -s tests -v
node tests/test_saved_session.cjs
node --check static/app.js
node --check static/realtime.js
```

Tests cover maze reachability and hidden state, cooperative extraction, persistence, legacy rooms, Tic-Tac-Toe wins/draws/input validation, duplicate commands, conflict retry, broadcasts, token resume, replay, and frontend publishing with a mocked AWS CLI.

## Release procedure

Deployment requires explicit approval. Review `docs/BUILD_0_2_REVIEW.md` first. Update the existing Lambda before publishing the frontend. Include `game.py`, `tictactoe.py`, and `cloud/` in the Lambda package. Retain the current WebSocket URL and AWS resource identities.

After approval, publish using the existing stack outputs:

```bash
bash scripts/publish_frontend.sh <WebSocketUrl> <BucketName> <CloudFrontId>
```

This builds the frontend, uploads it, sets entrypoint cache metadata, and invalidates HTML, configuration, both clients, and CSS before waiting for invalidation completion. Verify both games with two live clients, including reconnect and legacy maze resume. Update release status above only after live verification succeeds.
