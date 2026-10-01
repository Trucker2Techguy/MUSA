"""Server-authoritative Tic-Tac-Toe rules, independent of maze generation."""
from dataclasses import dataclass, field
from functools import lru_cache
import secrets
import time
from game import Player

LINES = ((0,1,2),(3,4,5),(6,7,8),(0,3,6),(1,4,7),(2,5,8),(0,4,8),(2,4,6))


@lru_cache(maxsize=19683)
def minimax(board, mark):
    """Score from O's perspective; stable square order breaks equal-score ties."""
    for line in LINES:
        if board[line[0]] is not None and all(board[i] == board[line[0]] for i in line):
            return (1 + board.count(None)) * (1 if board[line[0]] == 'O' else -1)
    scores = []
    for i, cell in enumerate(board):
        if cell is None:
            next_board = board[:i] + (mark,) + board[i+1:]
            scores.append(minimax(next_board, 'X' if mark == 'O' else 'O'))
    return (max(scores) if mark == 'O' else min(scores)) if scores else 0


def computer_square(board):
    """Return an optimal legal O move without changing the supplied board."""
    choices = [(minimax(tuple(board[:i] + ['O'] + board[i+1:]), 'X'), i)
               for i, cell in enumerate(board) if cell is None]
    if not choices:
        raise ValueError('No legal computer move.')
    return max(choices, key=lambda choice: (choice[0], -choice[1]))[1]

@dataclass
class TicTacToeRoom:
    code: str
    players: list = field(default_factory=list)
    board: list = field(default_factory=lambda: [None] * 9)
    turn: int = 0
    winner: object = None
    winning_line: list = field(default_factory=list)
    mode: str = 'network'
    phase: str = 'lobby'
    version: int = 0
    commands: int = 0
    started_at: float = 0
    completed_at: float = 0
    message: str = 'Awaiting second operator.'
    last_active: float = field(default_factory=time.time)
    game_type = 'tictactoe'

    @classmethod
    def new(cls, code, mode='network'):
        if mode not in ('network', 'computer'):
            raise ValueError('Unknown Tic-Tac-Toe mode.')
        return cls(code, mode=mode)

    def player_index(self, token):
        for i, player in enumerate(self.players):
            if player.token and secrets.compare_digest(player.token, token):
                return i
        raise ValueError('Session expired or not a member of this room.')

    def join(self, name):
        if self.phase != 'lobby' or len(self.players) >= (1 if self.mode == 'computer' else 2):
            raise ValueError('This room is already full or in progress.')
        cleaned = ''.join(c for c in name.strip() if c.isprintable())[:18] or f'OPERATOR {len(self.players)+1}'
        player = Player(secrets.token_urlsafe(24), cleaned, (0, 0))
        self.players.append(player)
        self.version += 1
        self.message = 'Ready to initialize.' if len(self.players) == 2 else 'Awaiting second operator.'
        if self.mode == 'computer':
            self.players.append(Player('', 'M.U.S.A.', (0, 0)))
            self.start(0)
        return player.token

    def start(self, index):
        if index != 0 or self.phase != 'lobby' or len(self.players) != 2:
            raise ValueError('The host can start once two operators have joined.')
        self.phase = 'playing'
        self.started_at = time.time()
        self.version += 1
        self.message = 'Player 1 (X) to move.'

    def command(self, index, square):
        if self.mode == 'computer' and index != 0:
            raise ValueError('Computer moves are controlled by the server.')
        self._move(index, square)
        if self.mode == 'computer' and self.phase == 'playing':
            self._move(1, computer_square(self.board))

    def _move(self, index, square):
        if self.phase != 'playing':
            raise ValueError('The simulation is not active.')
        if index != self.turn:
            raise ValueError('Wait for your turn.')
        if type(square) is not int or not 0 <= square < 9:
            raise ValueError('Choose a square from 0 to 8.')
        if self.board[square] is not None:
            raise ValueError('Square already occupied.')
        mark = ('X', 'O')[index]
        self.board[square] = mark
        self.commands += 1
        self.version += 1
        line = next((line for line in LINES if all(self.board[i] == mark for i in line)), None)
        if line:
            self.winner = index
            self.winning_line = list(line)
            self.phase = 'won'
            self.message = f'Player {index+1} ({mark}) wins.'
        elif all(cell is not None for cell in self.board):
            self.phase = 'draw'
            self.message = 'Draw. The only winning move… is to play again.'
        else:
            self.turn = 1 - index
            self.message = f'Player {self.turn+1} ({("X", "O")[self.turn]}) to move.'
        if self.phase != 'playing':
            self.completed_at = time.time()

    def snapshot(self, index):
        return {'code': self.code, 'gameType': self.game_type, 'mode': self.mode, 'phase': self.phase,
                'version': self.version, 'you': index, 'board': self.board[:],
                'turn': self.turn, 'winner': self.winner, 'winningLine': self.winning_line[:],
                'players': [{'name': p.name, 'mark': ('X','O')[i]} for i,p in enumerate(self.players)],
                'commands': self.commands, 'elapsed': round((self.completed_at or time.time())-self.started_at) if self.started_at else 0,
                'message': self.message}
