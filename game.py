"""Authoritative, dependency-free M.U.S.A. game rules and maze generation."""
from collections import deque
from dataclasses import dataclass, field
import random
import secrets
import time

SIZE = 17
DIRECTIONS = ((0, -1), (1, 0), (0, 1), (-1, 0))
LABELS = ('N', 'E', 'S', 'W')


def distances(grid, start):
    found = {start: 0}
    queue = deque([start])
    while queue:
        x, y = queue.popleft()
        for dx, dy in DIRECTIONS:
            point = (x + dx, y + dy)
            if point not in found and 0 <= point[0] < SIZE and 0 <= point[1] < SIZE and grid[point[1]][point[0]] == 0:
                found[point] = found[(x, y)] + 1
                queue.append(point)
    return found


def generate(seed=None):
    rng = random.Random(seed)
    grid = [[1] * SIZE for _ in range(SIZE)]
    start = (1, 1)
    grid[1][1] = 0
    stack = [start]
    while stack:
        x, y = stack[-1]
        options = [(x + dx * 2, y + dy * 2, dx, dy) for dx, dy in DIRECTIONS
                   if 0 < x + dx * 2 < SIZE - 1 and 0 < y + dy * 2 < SIZE - 1
                   and grid[y + dy * 2][x + dx * 2] == 1]
        if options:
            nx, ny, dx, dy = rng.choice(options)
            grid[y + dy][x + dx] = grid[ny][nx] = 0
            stack.append((nx, ny))
        else:
            stack.pop()
    # A few loops avoid excessive dead-end backtracking.
    walls = [(x, y) for y in range(2, SIZE - 2) for x in range(2, SIZE - 2)
             if grid[y][x] == 1 and ((grid[y][x-1] == grid[y][x+1] == 0) or
                                     (grid[y-1][x] == grid[y+1][x] == 0))]
    rng.shuffle(walls)
    for x, y in walls[:9]:
        grid[y][x] = 0
    from_start = distances(grid, start)
    first = max(from_start, key=from_start.get)
    from_first = distances(grid, first)
    second = max(from_first, key=from_first.get)
    from_second = distances(grid, second)
    starts = [first, second]
    candidates = [p for p in from_first if p not in starts and from_first[p] >= 4 and from_second[p] >= 4]
    relay0 = max(candidates, key=lambda p: min(from_first[p], from_second[p]))
    candidates.remove(relay0)
    from_relay0 = distances(grid, relay0)
    relay1 = max(candidates, key=lambda p: min(from_second[p], from_relay0[p]))
    candidates.remove(relay1)
    from_relay1 = distances(grid, relay1)
    exit_point = max(candidates, key=lambda p: min(from_relay0[p], from_relay1[p]))
    reserved = {*starts, relay0, relay1, exit_point}
    hazard_candidates = [p for p in candidates if p not in reserved and all(abs(p[0]-s[0])+abs(p[1]-s[1]) > 2 for s in starts)]
    hazards = set(rng.sample(hazard_candidates, min(5, len(hazard_candidates))))
    return grid, starts, [relay0, relay1], exit_point, hazards


@dataclass
class Player:
    token: str
    name: str
    pos: tuple
    facing: int = 0
    stunned_until: float = 0


@dataclass
class Room:
    code: str
    grid: list = field(default_factory=list)
    starts: list = field(default_factory=list)
    relays: list = field(default_factory=list)
    exit_point: tuple = (0, 0)
    hazards: set = field(default_factory=set)
    players: list = field(default_factory=list)
    revealed: set = field(default_factory=set)
    activated: list = field(default_factory=lambda: [False, False])
    phase: str = 'lobby'
    version: int = 0
    commands: int = 0
    started_at: float = 0
    completed_at: float = 0
    message: str = 'Awaiting second operator.'
    last_active: float = field(default_factory=time.time)

    @classmethod
    def new(cls, code, seed=None):
        grid, starts, relays, exit_point, hazards = generate(seed)
        return cls(code, grid, starts, relays, exit_point, hazards)

    def player_index(self, token):
        for i, player in enumerate(self.players):
            if secrets.compare_digest(player.token, token):
                return i
        raise ValueError('Session expired or not a member of this room.')

    def join(self, name):
        if self.phase != 'lobby' or len(self.players) >= 2:
            raise ValueError('This room is already full or in progress.')
        cleaned = ''.join(c for c in name.strip() if c.isprintable())[:18] or f'OPERATOR {len(self.players)+1}'
        index = len(self.players)
        player = Player(secrets.token_urlsafe(24), cleaned, self.starts[index])
        self.players.append(player)
        self.version += 1
        self.message = f'{cleaned} connected. ' + ('Ready to initialize.' if len(self.players) == 2 else 'Awaiting second operator.')
        return player.token

    def reveal(self, position):
        x, y = position
        for dx, dy in ((0, 0), *DIRECTIONS):
            point = (x + dx, y + dy)
            if 0 <= point[0] < SIZE and 0 <= point[1] < SIZE:
                self.revealed.add(point)

    def start(self, index):
        if index != 0 or self.phase != 'lobby' or len(self.players) != 2:
            raise ValueError('The host can start once two operators have joined.')
        self.phase = 'playing'
        self.started_at = time.time()
        for player in self.players:
            self.reveal(player.pos)
        self.version += 1
        self.message = 'Simulation live. Locate both concealed relays.'

    def command(self, index, action):
        if self.phase != 'playing':
            raise ValueError('The simulation is not active.')
        if action not in ('LEFT', 'RIGHT', 'FORWARD'):
            raise ValueError('Unknown command. Use LEFT, RIGHT, or FORWARD.')
        player = self.players[index]
        now = time.time()
        if now < player.stunned_until:
            raise ValueError(f'Interference. Controls return in {max(1, int(player.stunned_until-now+0.99))}s.')
        self.commands += 1
        if action == 'LEFT':
            player.facing = (player.facing - 1) % 4
            self.message = f'{player.name} rotated left.'
        elif action == 'RIGHT':
            player.facing = (player.facing + 1) % 4
            self.message = f'{player.name} rotated right.'
        else:
            dx, dy = DIRECTIONS[player.facing]
            point = (player.pos[0] + dx, player.pos[1] + dy)
            if not (0 <= point[0] < SIZE and 0 <= point[1] < SIZE) or self.grid[point[1]][point[0]]:
                self.message = f'{player.name}: wall ahead.'
            else:
                player.pos = point
                self.reveal(point)
                self.message = f'{player.name} advanced.'
                if point in self.relays:
                    owner = self.relays.index(point)
                    if owner == index and not self.activated[owner]:
                        self.activated[owner] = True
                        self.message = f'{player.name} activated relay {owner+1}.'
                    elif owner != index and not self.activated[owner]:
                        self.message = f'{player.name} discovered relay {owner+1}. Operator {owner+1} must activate it.'
                if point in self.hazards:
                    player.stunned_until = now + 3
                    self.message += ' Signal interference: controls delayed 3s.'
                if all(self.activated) and all(p.pos == self.exit_point for p in self.players):
                    self.phase = 'won'
                    self.completed_at = now
                    self.message = 'Both operators extracted. Simulation complete.'
        self.version += 1

    def snapshot(self, index):
        # Never serialize self.grid or unrevealed landmarks to browsers.
        visible = [[x, y, 'wall' if self.grid[y][x] else 'floor'] for x, y in sorted(self.revealed)]
        landmarks = [{'x': x, 'y': y, 'kind': 'relay', 'owner': i, 'active': self.activated[i]}
                     for i, (x, y) in enumerate(self.relays) if (x, y) in self.revealed]
        if self.exit_point in self.revealed:
            landmarks.append({'x': self.exit_point[0], 'y': self.exit_point[1], 'kind': 'exit'})
        landmarks.extend({'x': x, 'y': y, 'kind': 'hazard'} for x, y in self.hazards if (x, y) in self.revealed)
        return {'code': self.code, 'gameType': 'maze', 'phase': self.phase, 'version': self.version, 'size': SIZE,
                'you': index, 'players': [{'name': p.name, 'x': p.pos[0], 'y': p.pos[1],
                                           'facing': LABELS[p.facing], 'delay': max(0, round(p.stunned_until-time.time(), 1))}
                                          for p in self.players],
                'cells': visible, 'landmarks': landmarks, 'activated': self.activated[:],
                'commands': self.commands, 'elapsed': round((self.completed_at or time.time())-self.started_at) if self.started_at else 0,
                'message': self.message}
