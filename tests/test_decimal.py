"""DynamoDB resource reads numbers as Decimal, including nested maze coordinates."""
from decimal import Decimal
import json
from pathlib import Path
import sys
import unittest
from unittest.mock import Mock
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from cloud.aws_handler import DynamoStore, _dynamo
from cloud.codec import decode, encode
from game import Room


class DecimalTests(unittest.TestCase):
    def test_room_read_can_be_sent_and_saved_again(self):
        room = Room.new('TEST1', seed=17)
        room.join('Alpha')
        room.join('Bravo')
        room.start(0)
        raw = encode(room, ['connection-a', 'connection-b'], expires_at=1_800_007_200)
        # boto3's DynamoDB resource returns Decimal for every numeric field.
        from_dynamo = json.loads(json.dumps(raw), parse_int=Decimal, parse_float=Decimal)
        store = DynamoStore.__new__(DynamoStore)
        store.rooms = Mock()
        store.rooms.get_item.return_value = {'Item': from_dynamo}
        loaded = store.get_room(room.code)
        restored = decode(loaded)
        # A join/change re-encodes the room with json.dumps before writing.
        _dynamo(encode(restored, loaded['connections'], loaded['recentIds'], loaded['expiresAt']))
        # The same room also flows through json.dumps for a WebSocket snapshot.
        json.dumps({'type': 'state', 'state': restored.snapshot(0)})
        self.assertEqual(restored.revealed, room.revealed)

if __name__ == '__main__':
    unittest.main()
