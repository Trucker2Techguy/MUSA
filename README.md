# M.U.S.A. — Multi-User Simulation Arcade

M.U.S.A. is a browser-based multiplayer project built to explore server-authoritative game logic, shared state, session management, and real-time interaction between multiple clients.

The current playable simulation is a **two-player cooperative procedural maze** in which each player has incomplete information and must work with the other player to complete the mission.

The project is being developed iteratively: first proving the multiplayer game logic locally, then evolving the application toward a cloud-native AWS architecture.

---

## 🎮 Current Simulation: Cooperative Maze

Two players join the same game using a shared room code and individual player credentials.

Each player sees only the information available to them and must communicate with the other player to successfully navigate the maze.

### Objective

Players must:

1. Explore the procedurally generated maze.
2. Discover the environment through limited visibility.
3. Locate and activate their assigned relay.
4. Coordinate with the other player.
5. Reach extraction after both objectives are complete.

Neither player has complete information, making communication part of the game itself.

---

## 🧠 Multiplayer Design

M.U.S.A. uses a **server-authoritative model**.

The server owns the canonical game state while each browser acts as a client. Clients submit actions to the server and receive only the state they are authorized to see.

This approach keeps important game logic outside the browser and provides a foundation for future real-time multiplayer games.

Current functionality includes:

- Two-player room creation and joining
- Unique player credentials
- Server-authoritative movement and game state
- Procedural maze generation
- Player-specific visibility
- Collaborative map discovery
- Objective and extraction tracking
- Reconnection support
- Multi-client synchronization
- Automated testing of core game logic

---

## 🏗️ Current Architecture

The current implementation intentionally keeps the infrastructure simple while the multiplayer rules and state model are developed.

```text
Player A Browser ─┐
                  ├── HTTP API ── Game Server ── In-Memory Room State
Player B Browser ─┘
```

Clients periodically synchronize with the server while all authoritative room and game state remains server-side.

This allows the multiplayer behavior, security boundaries, and game mechanics to be validated before introducing additional cloud infrastructure.

---

## ☁️ Planned AWS Architecture

The next major iteration moves persistent game state and real-time communication to AWS.

```text
Player A ─┐
          ├── WebSocket API ── AWS Lambda ── DynamoDB
Player B ─┘
```

Planned improvements include:

- Amazon API Gateway WebSocket APIs
- AWS Lambda game/event handlers
- Amazon DynamoDB for persistent room state
- Event-driven player updates
- Reduced client polling
- Improved reconnect handling
- Multiple concurrent game rooms
- Cloud-hosted frontend deployment

The goal is to preserve the existing server-authoritative game model while replacing local state and polling with scalable managed AWS services.

---

## 🕹️ Where M.U.S.A. Is Going

The cooperative maze is the first game built on M.U.S.A., rather than the intended endpoint of the project.

A future lobby will allow players to select from multiple multiplayer games while sharing the same underlying session and communication infrastructure.

Planned or experimental game modes include:

- Cooperative Maze
- Tic-Tac-Toe
- Additional two-player games
- Terminal-style simulation experiences

The long-term goal is to separate the **multiplayer platform** from individual game logic so new games can reuse the same room, player, authentication, and state-synchronization systems.

---

## 🛠️ Engineering Goals

M.U.S.A. is primarily an engineering project disguised as a game.

The project provides a practical environment for experimenting with:

- Client/server architecture
- Distributed application state
- Server-authoritative design
- Multiplayer synchronization
- Authentication and session handling
- API design
- Hidden-information boundaries
- Procedural generation
- Automated testing
- AWS serverless architecture

---

## 🚧 Project Status

**Active development**

The cooperative maze is currently implemented using local server-side room state and client polling.

The next phases of development include:

1. Add a game-selection lobby.
2. Refactor game-specific logic behind a common multiplayer interface.
3. Add additional multiplayer game modes.
4. Replace polling with WebSocket communication.
5. Move persistent room state to DynamoDB.
6. Deploy the application using AWS serverless services.

---

## 💡 Why I Built It

M.U.S.A. started as an experiment in building a synchronized two-player game, but quickly became an opportunity to explore a larger question:

**How do you design multiplayer application state so that it can move from a simple local implementation to a scalable cloud architecture without rewriting the entire application?**

Rather than introducing cloud services immediately, the project first validates the game rules, client/server boundaries, and multiplayer state model locally.

Once those behaviors are stable, the infrastructure can evolve independently toward AWS-managed services.

---

## 📌 Repository

This repository contains the current M.U.S.A. implementation and will track the project as it evolves from a cooperative multiplayer prototype into a multi-game cloud platform.
