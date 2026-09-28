# M.U.S.A. — local prototype

A two-player cooperative procedural maze. This prototype uses Python's standard library and has no external packages or cloud resources.

## Run

```bash
python3 server.py
```

Open `http://localhost:8000` in two separate browsers or browser profiles. Create a room in one, then join using the five-character code in the other. The server listens on loopback only; it is not publicly reachable. To test on a separate physical device on the same trusted LAN, edit the binding in `server.py` from `127.0.0.1` to your machine's LAN address and open that address on both devices.

Run rules tests with `python3 -m unittest discover -s tests -v`.

## Rules

- Two players; the host starts and can generate a fresh maze after a win.
- LEFT and RIGHT rotate; FORWARD attempts one step. A wall blocks movement.
- The map starts almost blank. Both players reveal floor and neighboring walls collaboratively.
- Each relay is initially concealed. Either player can locate it, but only its numbered operator activates it by stepping onto it.
- Once both relays activate, both operators must occupy extraction simultaneously.
- Interference tiles delay the entering operator for three seconds; they never lock a route.

## Prototype boundary

State is held in server memory and browsers poll for updates every 850 ms. Restarting the server ends rooms. This deliberately proves the rules, hidden-data boundary, and local two-client interaction before replacing room storage and transport with DynamoDB and WebSockets. The browser is sent discovered cells and discovered landmarks only. Room credentials persist in each browser's local storage for refresh/reconnect while the local process runs.

## Serverless phase (source only)

The WebSocket/Lambda/DynamoDB implementation and proposed SAM template live in `cloud/`, `static/realtime.js`, and `infra/template.yaml`. Local mode still works as before. See [Phase 2 design and deployment review](docs/PHASE2.md) for protocol, data model, expiry, and deployment sequence. No AWS resources have been created.
