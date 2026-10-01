import unittest
from tictactoe import TicTacToeRoom, LINES
from cloud.codec import encode, decode
from cloud.service import Service
from cloud.aws_handler import _dynamo, _native
from test_cloud import FakeStore
from game import Room

class TicTacToeTests(unittest.TestCase):
    def room(self):
        room = TicTacToeRoom.new('ABCDE')
        room.join('A'); room.join('B'); room.start(0)
        return room

    def test_turns_occupied_squares_and_invalid_inputs_do_not_mutate(self):
        room = self.room()
        for player, square in [(1,0),(0,-1),(0,9),(0,True),(0,'0'),(0,None),(0,{})]:
            with self.assertRaises(ValueError): room.command(player,square)
        self.assertEqual(room.commands,0)
        room.command(0,0)
        with self.assertRaises(ValueError): room.command(1,0)
        self.assertEqual(room.board,['X']+[None]*8)

    def test_all_winning_lines_for_both_players(self):
        for winner in (0,1):
            for line in LINES:
                room = self.room()
                room.board = [None]*9
                room.board[line[0]] = room.board[line[1]] = ('X','O')[winner]
                room.turn = winner
                room.command(winner,line[2])
                self.assertEqual(room.winner,winner)
                self.assertEqual(room.winning_line,list(line))
                self.assertEqual(room.phase,'won')
                with self.assertRaises(ValueError): room.command(1-winner,8)

    def test_draw_and_roundtrip(self):
        room = self.room()
        for i,square in enumerate([0,1,2,4,3,5,7,6,8]): room.command(i%2,square)
        self.assertEqual(room.phase,'draw')
        self.assertIsNone(room.winner)
        self.assertEqual(decode(_native(_dynamo(encode(room)))).snapshot(0),room.snapshot(0))

    def test_start_join_and_session_validation(self):
        room=TicTacToeRoom.new('ABCDE')
        with self.assertRaises(ValueError): room.start(0)
        token=room.join('A');room.join('B')
        self.assertEqual(room.player_index(token),0)
        with self.assertRaises(ValueError): room.start(1)
        with self.assertRaises(ValueError): room.join('C')
        with self.assertRaises(ValueError): room.player_index('wrong')

    def test_legacy_maze_without_type(self):
        item=encode(Room.new('ABCDE',seed=1));del item['gameType']
        self.assertEqual(decode(item).snapshot(0)['gameType'],'maze')

    def test_service_broadcast_retry_resume_and_replay(self):
        store=FakeStore();out={}
        service=Service(store,lambda c,m:out.setdefault(c,[]).append(m))
        with self.assertRaises(ValueError): service.create('a','A','war')
        service.create('a','A','tictactoe');session=out['a'][0];code=session['code']
        service.join('b',code,'B');token_b=out['b'][0]['token']
        self.assertEqual(out['b'][-1]['state']['gameType'],'tictactoe')
        service.change('a','start',request_id='start')
        store.conflicts=1
        service.change('a','command',0,request_id='move')
        service.change('a','command',0,request_id='move')
        self.assertEqual(out['b'][-1]['state']['commands'],1)
        service.disconnect('b');service.resume('b2',code,token_b)
        self.assertEqual(out['b2'][-1]['state']['board'][0],'X')
        service.resume('a2',code,session['token']);service.disconnect('a')
        for c,square in [('b2',3),('a2',1),('b2',4),('a2',2)]:
            service.change(c,'command',square,request_id=f'{c}-{square}')
        self.assertEqual(out['b2'][-1]['state']['winner'],0)
        with self.assertRaises(ValueError): service.change('b2','replay',request_id='bad')
        service.change('a2','replay',request_id='replay')
        self.assertEqual(out['b2'][-1]['state']['board'],[None]*9)
        self.assertEqual(store.rooms[code]['connections'],['a2','b2'])
        service.resume('b3',code,token_b)
        self.assertEqual(out['b3'][-1]['state']['phase'],'lobby')

    def test_draw_replay(self):
        store=FakeStore();out={};service=Service(store,lambda c,m:out.setdefault(c,[]).append(m))
        service.create('a','A','tictactoe');code=out['a'][0]['code'];service.join('b',code,'B')
        service.change('a','start',request_id='s')
        for i,square in enumerate([0,1,2,4,3,5,7,6,8]):service.change(('a','b')[i%2],'command',square,request_id=str(i))
        self.assertEqual(store.rooms[code]['phase'],'draw')
        service.change('a','replay',request_id='r');self.assertEqual(store.rooms[code]['phase'],'lobby')
