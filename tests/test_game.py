import sys
from pathlib import Path
import unittest
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from game import Room, generate, distances

class GameTests(unittest.TestCase):
    def test_generated_objectives_are_reachable(self):
        for seed in range(150):
            grid, starts, relays, exit_point, hazards = generate(seed)
            reachable = distances(grid, starts[0])
            self.assertTrue(all(point in reachable for point in [*starts, *relays, exit_point, *hazards]))
            self.assertEqual(len(set([*starts, *relays, exit_point])), 5)

    def test_hidden_state_and_cooperative_activation(self):
        room = Room.new('TEST1', seed=17)
        tokens = [room.join('Alpha'), room.join('Bravo')]
        self.assertEqual(len(room.snapshot(0)['cells']), 0)
        with self.assertRaises(ValueError): room.start(1)
        room.start(0)
        snap = room.snapshot(0)
        self.assertNotIn('grid', snap)
        self.assertNotIn('relays', snap)
        self.assertFalse(any(p == room.relays[0] for p in [room.players[0].pos, room.players[1].pos]))
        self.assertLess(len(snap['cells']), 30)
        self.assertFalse(any(item['kind'] == 'relay' for item in snap['landmarks']))
        self.assertEqual(room.player_index(tokens[1]), 1)
        # Walking over the other player's relay discovers but cannot activate it.
        room.players[1].pos = room.relays[0]
        room.reveal(room.relays[0])
        self.assertFalse(room.activated[0])
        self.assertEqual(room.snapshot(1)['landmarks'][0]['owner'], 0)

    def test_win_requires_both_at_extraction(self):
        room = Room.new('TEST2', seed=99)
        room.join('One');room.join('Two');room.start(0)
        room.activated = [True, True]
        room.players[0].pos = room.exit_point
        room.players[1].pos = (room.exit_point[0] - 1, room.exit_point[1])
        # Use any adjacent traversable cell and face the extraction point.
        for face, (dx, dy) in enumerate(((0,-1),(1,0),(0,1),(-1,0))):
            point = (room.exit_point[0]-dx, room.exit_point[1]-dy)
            if 0 <= point[0] < 17 and 0 <= point[1] < 17 and room.grid[point[1]][point[0]] == 0:
                room.players[1].pos = point;room.players[1].facing = face;break
        room.command(1,'FORWARD')
        self.assertEqual(room.phase,'won')

if __name__ == '__main__': unittest.main()
