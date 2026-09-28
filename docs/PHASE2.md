# Phase 2: serverless transport and storage

This branch is source-only. Nothing in `infra/template.yaml` has been deployed.
The known-good local server remains `python3 server.py`; `static/config.js` leaves the local HTTP client active. Python 3.12 and Node (syntax check) suffice for local tests. AWS SAM CLI is needed only for a later deployment.

## Server protocol

The deployed frontend uses `wss://<api-id>.execute-api.<region>.amazonaws.com/prod`. API Gateway selects routes using `action`. `$connect` checks the browser Origin against the site name or distribution name; `$disconnect` removes the connection if still current. Neither room codes nor Origins authenticate players. A random 24-byte token identifies each player and is returned only to that player; DynamoDB stores its SHA-256 digest.

| Action | Additional fields | Result |
| --- | --- | --- |
| `create` | `name` | `session` with room code, token, filtered state |
| `join` | `code`, `name` | `session` to joiner; new state to both |
| `resume` | `code`, `token` | replaces that player's prior connection; state to both |
| `start`, `replay` | `requestId` | versioned `state` to both |
| `command` | `command` (`LEFT`, `RIGHT`, `FORWARD`), `requestId` | versioned `state` to both |
| `snapshot` | none | filtered state to sender |
| `ping` | none | `pong` |

The initiating player's `state` includes the `requestId`; others receive the same state without it. Errors contain `type: "error"`, `error`, and the request ID if present. A client resends an unacknowledged mutation with the same ID after a delay or reconnect. The room stores the last 32 IDs **per player**, preventing a repeated command from moving twice. The client ignores older state versions. Lambda retries optimistic-lock conflicts against the latest room item. There is no full-map broadcast: `Room.snapshot` filters revealed cells and landmarks.

## Tables and expiry

`musa-rooms` has partition key `roomCode` (string), complete authoritative room state, `version`, `connections` (two current IDs), `recentIds` (two lists), and TTL `expiresAt` (epoch seconds). `musa-connections` has partition key `connectionId` (string), `roomCode`, `playerIndex`, and TTL `expiresAt`. Rooms expire after 30 minutes in the lobby, two hours without a successful game mutation, or 30 minutes after a win. Connection records expire after three hours. Each request checks the logical room expiry; DynamoDB's eventual TTL cleanup is not the enforcement mechanism. Heartbeats maintain sockets but do not extend game lifetime.

Room creation conditionally writes a new code. A room mutation conditionally replaces the room only if its stored version matches the version read. Connection bindings are written separately; a short write failure at that point may leave a temporary orphan room/slot until its TTL. Real AWS staging tests should explicitly exercise connection failures and retries before DNS is enabled.

## Infrastructure review before any deploy

`infra/template.yaml` proposes two on-demand DynamoDB tables with TTL, one Python Lambda plus scoped IAM role, a WebSocket API/stage/routes, a seven-day CloudWatch log group, a private S3 bucket with CloudFront OAC and new distribution, and optional Route 53 A/AAAA aliases. The stack's `CreateDns` parameter defaults to `false`. Supply the existing hosted-zone ID and **us-east-1** wildcard ACM ARN after checking that the certificate is issued and covers the requested hostname. The site distribution is separate from the existing portfolio distribution. The first stack deployment would still create billable resources and requires explicit approval; the DNS switch is a second reviewed update.

The S3 bucket has `DeletionPolicy: Retain` and `UpdateReplacePolicy: Retain`. `sam delete` removes the stack-managed distribution and bucket policy but **leaves the private bucket and its objects**. This prevents surprise data loss and avoids CloudFormation failing on a nonempty bucket. The deterministic bucket name will block a fresh stack using the same name until the retained bucket is deliberately emptied/deleted or imported into a new stack. Manual bucket cleanup can incur storage charges until completed.

The distribution has the `musa.jaimebsnyder.com` alias even while Route 53 records are disabled. For direct distribution-domain testing, the Lambda Origin allowlist also accepts the generated CloudFront hostname. A non-browser can forge Origin, so it is only an abuse guard. The deployment should add an AWS budget alert with the owner's desired email and threshold before publication; no email address is embedded in this source.

When deployment is authorized, the planned commands are roughly:

```bash
sam build --template-file infra/template.yaml
sam deploy --guided --capabilities CAPABILITY_NAMED_IAM
bash scripts/publish_frontend.sh '<WebSocketUrl stack output>' '<BucketName stack output>' '<CloudFrontId stack output>'
```

The stack uses `CreateDns=false` on its first deploy. The publish script sets `Cache-Control: no-store, max-age=0` on `index.html` and `config.js` and creates a CloudFront invalidation for `/`, `/index.html`, and `/config.js` after a successful upload. It exits before invalidation if an upload fails. Other static files retain the distribution's normal cache behavior. The script waits for invalidation completion before reporting success. Two real browsers must complete room creation, play, reconnect, win, and replay through the distribution domain before a second reviewed stack update sets `CreateDns=true`. Do not run these commands as part of source validation.

## Source-only checks

```bash
python3 -m unittest discover -s tests -v
python3 -m py_compile game.py server.py cloud/*.py scripts/*.py
node --check static/app.js
node --check static/realtime.js
bash -n scripts/publish_frontend.sh
```
