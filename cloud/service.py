"""Connection-oriented game service; dependencies are injected for offline tests."""
import hashlib
import secrets
import time
from game import Room
from .codec import encode, decode

ALPHABET = 'ABCDEFGHJKLMNPQRSTUVWXYZ23456789'


class Conflict(Exception):
    pass


class Service:
    def __init__(self, store, send, clock=time.time):
        self.store, self.send, self.clock = store, send, clock

    def _expiry(self, room, now):
        if room.phase == 'lobby':
            return int(now + 1800)
        if room.phase == 'won':
            return int(now + 1800)
        return int(now + 7200)

    def _room(self, code):
        item = self.store.get_room(code)
        if not item or item['expiresAt'] <= self.clock():
            raise ValueError('Room expired or not found.')
        return item

    def _publish(self, item, acknowledgement=None):
        room = decode(item)
        for i, connection in enumerate(item['connections']):
            if connection:
                try:
                    self.send(connection, {'type': 'state', 'state': room.snapshot(i),
                                           **({'requestId': acknowledgement[1]} if acknowledgement and acknowledgement[0] == connection else {})})
                except Gone:
                    self.store.remove_connection(connection)
                    # The next mutation or resume replaces this stale binding.

    def _bind(self, connection, code, index, old=None):
        # A short-lived reverse lookup for $disconnect. A replaced socket is harmless.
        self.store.bind_connection(connection, code, index, int(self.clock() + 3 * 3600))
        if old and old != connection:
            self.store.remove_connection(old)

    def create(self, connection, name):
        if self.store.get_connection(connection):
            raise ValueError('Connection already belongs to a room.')
        for _ in range(8):
            code = ''.join(secrets.choice(ALPHABET) for _ in range(5))
            room = Room.new(code)
            token = room.join(name)
            room.players[0].token = hashlib.sha256(token.encode()).hexdigest()
            item = encode(room, [connection, None], expires_at=self._expiry(room, self.clock()))
            try:
                self.store.create_room(item)
            except Conflict:
                continue
            self._bind(connection, code, 0)
            self.send(connection, {'type': 'session', 'code': code, 'token': token, 'state': room.snapshot(0)})
            return
        raise ValueError('Unable to allocate room. Try again.')

    def join(self, connection, code, name):
        if self.store.get_connection(connection):
            raise ValueError('Connection already belongs to a room.')
        code = code.strip().upper()
        for _ in range(8):
            item = self._room(code)
            room = decode(item)
            token = room.join(name)
            room.players[1].token = hashlib.sha256(token.encode()).hexdigest()
            updated = encode(room, [item['connections'][0], connection], item['recentIds'], self._expiry(room, self.clock()))
            try:
                self.store.save_room(updated, item['version'])
                break
            except Conflict:
                continue
        else:
            raise ValueError('Room is busy. Try again.')
        self._bind(connection, code, 1)
        self.send(connection, {'type': 'session', 'code': code, 'token': token, 'state': room.snapshot(1)})
        self._publish(updated)

    def resume(self, connection, code, token):
        code = code.strip().upper()
        existing = self.store.get_connection(connection)
        if existing and existing['roomCode'] != code:
            raise ValueError('Connection already belongs to another room.')
        digest = hashlib.sha256(token.encode()).hexdigest()
        for _ in range(8):
            item = self._room(code)
            room = decode(item)
            index = next((i for i, p in enumerate(room.players) if secrets.compare_digest(p.token, digest)), None)
            if index is None:
                raise ValueError('Session expired or not a member of this room.')
            old = item['connections'][index]
            connections = item['connections'][:]
            connections[index] = connection
            room.version += 1
            updated = encode(room, connections, item['recentIds'], item['expiresAt'])
            try:
                self.store.save_room(updated, item['version'])
                break
            except Conflict:
                continue
        else:
            raise ValueError('Room is busy. Try again.')
        self._bind(connection, code, index, old)
        self._publish(updated)

    def change(self, connection, action, command=None, request_id=None):
        binding = self.store.get_connection(connection)
        if not binding:
            raise ValueError('Connection not bound to a room. Reconnect.')
        code, index = binding['roomCode'], int(binding['playerIndex'])
        if action != 'snapshot' and (not isinstance(request_id, str) or not 1 <= len(request_id) <= 80):
            raise ValueError('Missing request ID.')
        for _ in range(12):
            item = self._room(code)
            if item['connections'][index] != connection:
                raise ValueError('Connection replaced. Reconnect.')
            room = decode(item)
            if action == 'snapshot':
                self.send(connection, {'type': 'state', 'state': room.snapshot(index)})
                return
            if request_id in item['recentIds'][index]:
                self.send(connection, {'type': 'state', 'state': room.snapshot(index), 'requestId': request_id})
                return
            if action == 'start':
                room.start(index)
            elif action == 'command':
                room.command(index, command)
            elif action == 'replay':
                if index != 0 or room.phase != 'won':
                    raise ValueError('Host can generate a new maze after a win.')
                old_players = room.players
                room = Room.new(code)
                room.players = old_players
                for i, player in enumerate(room.players):
                    player.pos, player.facing, player.stunned_until = room.starts[i], 0, 0
                room.version = item['version'] + 1
                room.message = 'New simulation ready. Host may initialize.'
            else:
                raise ValueError('Unknown action.')
            recent = [ids[:] for ids in item['recentIds']]
            recent[index] = (recent[index] + [request_id])[-32:]
            room.last_active = self.clock()
            updated = encode(room, item['connections'], recent, self._expiry(room, room.last_active))
            try:
                self.store.save_room(updated, item['version'])
                break
            except Conflict:
                continue
        else:
            raise ValueError('Room is busy. Try again.')
        self._publish(updated, (connection, request_id))

    def disconnect(self, connection):
        binding = self.store.get_connection(connection)
        if not binding:
            return
        self.store.remove_connection(connection)
        for _ in range(8):
            item = self.store.get_room(binding['roomCode'])
            if not item:
                return
            index = int(binding['playerIndex'])
            if item['connections'][index] != connection:
                return
            room = decode(item)
            room.version += 1
            connections = item['connections'][:]
            connections[index] = None
            updated = encode(room, connections, item['recentIds'], item['expiresAt'])
            try:
                self.store.save_room(updated, item['version'])
                self._publish(updated)
                return
            except Conflict:
                continue


class Gone(Exception):
    pass
