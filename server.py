"""Local-only prototype server. Run: python3 server.py"""
from http.server import ThreadingHTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from threading import RLock
from urllib.parse import urlparse, parse_qs
import json
import secrets
import time

from game import Room
from tictactoe import TicTacToeRoom

ROOT = Path(__file__).parent / 'static'
ROOMS = {}
LOCK = RLock()
ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def send_json(self, status, data):
        body = json.dumps(data).encode()
        self.send_response(status)
        self.send_header('Content-Type', 'application/json; charset=utf-8')
        self.send_header('Cache-Control', 'no-store')
        self.send_header('Content-Length', str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def request_json(self):
        length = int(self.headers.get('Content-Length', 0))
        if length > 4096:
            raise ValueError('Request too large.')
        return json.loads(self.rfile.read(length) or b'{}')

    def room(self, code, token):
        room = ROOMS.get(str(code).upper())
        if not room:
            raise ValueError('Room not found.')
        index = room.player_index(str(token))
        room.last_active = time.time()
        return room, index

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == '/api/state':
            try:
                params = parse_qs(url.query)
                with LOCK:
                    room, index = self.room(params.get('code', [''])[0], params.get('token', [''])[0])
                    self.send_json(200, room.snapshot(index))
            except (ValueError, IndexError) as exc:
                self.send_json(400, {'error': str(exc)})
            return
        if url.path.startswith('/api/'):
            self.send_json(404, {'error': 'Unknown endpoint.'})
            return
        super().do_GET()

    def do_POST(self):
        try:
            data = self.request_json()
            with LOCK:
                if self.path == '/api/create':
                    code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
                    while code in ROOMS:
                        code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
                    game_type = data.get('gameType', 'maze')
                    if game_type not in ('maze', 'tictactoe'):
                        raise ValueError('Unknown simulation.')
                    room = ROOMS[code] = TicTacToeRoom.new(code) if game_type == 'tictactoe' else Room.new(code)
                    token = room.join(str(data.get('name', '')))
                    result = {'token': token, 'state': room.snapshot(0)}
                elif self.path == '/api/join':
                    room = ROOMS.get(str(data.get('code', '')).strip().upper())
                    if not room:
                        raise ValueError('Room not found. Check the code.')
                    token = room.join(str(data.get('name', '')))
                    result = {'token': token, 'state': room.snapshot(1)}
                elif self.path in ('/api/start', '/api/command', '/api/replay'):
                    room, index = self.room(data.get('code'), data.get('token'))
                    if self.path == '/api/start':
                        room.start(index)
                    elif self.path == '/api/command':
                        room.command(index, data.get('action') if isinstance(room, TicTacToeRoom) else str(data.get('action', '')).upper())
                    else:
                        if index != 0 or room.phase not in ('won', 'draw'):
                            raise ValueError('Host can generate a new maze after a win.')
                        replacement = TicTacToeRoom.new(room.code) if isinstance(room, TicTacToeRoom) else Room.new(room.code)
                        replacement.players = room.players
                        if isinstance(replacement, Room):
                            for i, player in enumerate(replacement.players):
                                player.pos = replacement.starts[i]
                                player.facing = 0
                                player.stunned_until = 0
                        replacement.version = room.version + 1
                        replacement.message = 'New simulation ready. Host may initialize.'
                        ROOMS[room.code] = room = replacement
                    result = {'state': room.snapshot(index)}
                else:
                    self.send_json(404, {'error': 'Unknown endpoint.'})
                    return
                self.send_json(200, result)
        except (ValueError, TypeError, json.JSONDecodeError) as exc:
            self.send_json(400, {'error': str(exc)})


def serve(port=8000):
    server = ThreadingHTTPServer(('127.0.0.1', port), Handler)
    print(f'M.U.S.A. local prototype: http://localhost:{port}', flush=True)
    server.serve_forever()


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser()
    parser.add_argument('--port', type=int, default=8000)
    serve(parser.parse_args().port)
