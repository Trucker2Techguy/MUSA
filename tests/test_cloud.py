import copy
import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud.codec import encode, decode
from cloud.service import Service, Conflict
from game import Room


class FakeStore:
    def __init__(self):
        self.rooms = {}
        self.connections = {}
        self.conflicts = 0

    def get_room(self, code):
        return copy.deepcopy(self.rooms.get(code))

    def create_room(self, item):
        if item['roomCode'] in self.rooms:
            raise Conflict()
        self.rooms[item['roomCode']] = copy.deepcopy(item)

    def save_room(self, item, version):
        if self.conflicts:
            self.conflicts -= 1
            raise Conflict()
        if self.rooms[item['roomCode']]['version'] != version:
            raise Conflict()
        self.rooms[item['roomCode']] = copy.deepcopy(item)

    def bind_connection(self, connection, code, index, expires_at):
        self.connections[connection] = {'roomCode': code, 'playerIndex': index, 'expiresAt': expires_at}

    def get_connection(self, connection):
        return self.connections.get(connection)

    def remove_connection(self, connection):
        self.connections.pop(connection, None)


class CloudTests(unittest.TestCase):
    def setUp(self):
        self.store = FakeStore()
        self.out = {}
        self.now = 1_800_000_000
        self.service = Service(self.store, lambda conn, message: self.out.setdefault(conn, []).append(message),
                               lambda: self.now)
        self.service.create('a', 'Alpha')
        self.session_a = self.out['a'][0]
        self.code = self.session_a['code']

    def last(self, conn):
        return self.out[conn][-1]

    def test_codec_roundtrip_and_no_hidden_maze(self):
        original = Room.new('CODE1', seed=7)
        original.join('A');original.join('B');original.start(0)
        restored = decode(encode(original))
        self.assertEqual(restored.grid, original.grid)
        self.assertEqual(restored.revealed, original.revealed)
        snapshot = restored.snapshot(0)
        self.assertNotIn('grid', snapshot)
        self.assertNotIn('relays', snapshot)
        self.assertFalse(any(item['kind'] == 'relay' for item in snapshot['landmarks']))

    def test_two_clients_shared_state_and_idempotent_retry(self):
        self.service.join('b', self.code, 'Bravo')
        self.assertEqual(len(self.last('a')['state']['players']), 2)
        self.store.conflicts = 1
        self.service.change('a', 'start', request_id='start-1')
        self.service.change('a', 'command', 'RIGHT', request_id='cmd-1')
        self.service.change('a', 'command', 'RIGHT', request_id='cmd-1')
        self.assertEqual(self.last('b')['state']['players'][0]['facing'], 'E')
        self.assertEqual(self.last('b')['state']['commands'], 1)
        self.assertEqual(self.last('a')['state']['cells'], self.last('b')['state']['cells'])

    def test_reconnect_replaces_socket_without_late_disconnect_damage(self):
        self.service.join('b', self.code, 'Bravo')
        self.service.resume('a2', self.code, self.session_a['token'])
        self.service.disconnect('a')
        self.assertEqual(self.store.rooms[self.code]['connections'][0], 'a2')
        self.service.change('a2', 'snapshot')
        self.assertEqual(self.last('a2')['type'], 'state')
        with self.assertRaises(ValueError):
            self.service.resume('attacker', self.code, 'wrong-token')

    def test_expiry_is_enforced_before_ttl_deletes_item(self):
        self.now += 1801
        with self.assertRaisesRegex(ValueError, 'expired'):
            self.service.join('b', self.code, 'Bravo')
        self.assertIn(self.code, self.store.rooms)

    def test_replay_keeps_players_and_new_maze(self):
        self.service.join('b', self.code, 'Bravo')
        self.service.change('a', 'start', request_id='s1')
        old_grid = self.store.rooms[self.code]['grid']
        self.store.rooms[self.code]['phase'] = 'won'
        self.store.rooms[self.code]['activated'] = [True, True]
        self.service.change('a', 'replay', request_id='r1')
        new = self.store.rooms[self.code]
        self.assertEqual(new['phase'], 'lobby')
        self.assertEqual(len(new['players']), 2)
        self.assertNotEqual(new['grid'], old_grid)
        self.assertEqual(new['revealed'], [])
        self.assertEqual(new['connections'], ['a', 'b'])

if __name__ == '__main__':
    unittest.main()
