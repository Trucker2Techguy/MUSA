import copy
import unittest
from tictactoe import TicTacToeRoom, computer_square
from cloud.service import Service
from cloud.codec import encode, decode
from test_cloud import FakeStore

class ComputerTests(unittest.TestCase):
    def room(self):
        room=TicTacToeRoom.new('ABCDE','computer')
        room.join('Human')
        return room

    def test_solo_starts_without_join_and_blocks_bot_identity(self):
        room=self.room()
        self.assertEqual(room.phase,'playing')
        self.assertEqual(room.players[1].name,'M.U.S.A.')
        self.assertEqual(room.players[1].token,'')
        with self.assertRaises(ValueError): room.player_index('')
        with self.assertRaises(ValueError): room.join('Intruder')
        with self.assertRaises(ValueError): room.command(1,0)
        self.assertEqual(room.board,[None]*9)
        with self.assertRaises(ValueError): TicTacToeRoom.new('ABCDE','invalid')

    def test_computer_move_is_legal_deterministic_and_atomic(self):
        room=self.room();room.command(0,0)
        self.assertEqual(room.board.count('X'),1)
        self.assertEqual(room.board.count('O'),1)
        self.assertEqual(room.board[4],'O')
        self.assertEqual(room.turn,0)
        again=self.room();again.command(0,0)
        self.assertEqual(room.board,again.board)
        before=copy.deepcopy(room.snapshot(0))
        with self.assertRaises(ValueError): room.command(0,4)
        self.assertEqual(room.snapshot(0),before)
        board=room.board[:];square=computer_square(board)
        self.assertIsNone(board[square]);self.assertEqual(board,room.board)

    def test_computer_takes_win_and_blocks_loss(self):
        self.assertEqual(computer_square(['O','O',None,'X','X',None,None,None,'X']),2)
        self.assertEqual(computer_square(['X','X',None,None,'O',None,None,None,None]),2)
        room=self.room();room.board=['O','O',None,'X',None,None,'X',None,None]
        room.command(0,8)
        self.assertEqual(room.winner,1);self.assertEqual(room.winning_line,[0,1,2])
        self.assertEqual(room.phase,'won')
        with self.assertRaises(ValueError):room.command(0,4)

    def test_human_completion_does_not_make_extra_computer_move(self):
        room=self.room();room.board=['X','X',None,'O','O',None,None,None,None]
        room.command(0,2)
        self.assertEqual(room.winner,0);self.assertEqual(room.board.count('O'),2)
        room=self.room();room.board=['X','O','X','X','O','O','O','X',None]
        room.command(0,8)
        self.assertEqual(room.phase,'draw');self.assertEqual(room.commands,1)

    def test_every_reachable_human_strategy_computer_never_loses(self):
        outcomes=set();visited=set()
        def explore(room):
            key=tuple(room.board)
            if key in visited:return
            visited.add(key)
            if room.phase!='playing':
                self.assertNotEqual(room.winner,0)
                outcomes.add(room.phase)
                return
            self.assertEqual(room.turn,0)
            for square,cell in enumerate(room.board):
                if cell is None:
                    child=copy.deepcopy(room);child.command(0,square)
                    explore(child)
        explore(self.room())
        self.assertEqual(outcomes,{'won','draw'})
        self.assertGreater(len(visited),100)

    def test_codec_solo_roundtrip_and_legacy_network_default(self):
        room=self.room();room.command(0,0)
        self.assertEqual(decode(encode(room)).snapshot(0),room.snapshot(0))
        network=TicTacToeRoom.new('ABCDE');item=encode(network);del item['mode']
        self.assertEqual(decode(item).mode,'network')

    def test_cloud_solo_resume_duplicate_retry_replay_and_no_join(self):
        store=FakeStore();out={};service=Service(store,lambda c,m:out.setdefault(c,[]).append(m))
        service.create('a','Human','tictactoe','computer');session=out['a'][0];code=session['code']
        self.assertEqual(session['state']['phase'],'playing')
        with self.assertRaises(ValueError):service.join('b',code,'Intruder')
        store.conflicts=1;service.change('a','command',0,request_id='move')
        service.change('a','command',0,request_id='move')
        self.assertEqual(out['a'][-1]['state']['commands'],2)
        service.disconnect('a');service.resume('a2',code,session['token'])
        self.assertEqual(out['a2'][-1]['state']['board'][4],'O')
        while out['a2'][-1]['state']['phase']=='playing':
            snapshot=out['a2'][-1]['state'];square=snapshot['board'].index(None)
            service.change('a2','command',square,request_id=f'move-{snapshot["commands"]}')
        service.change('a2','replay',request_id='replay')
        self.assertEqual(out['a2'][-1]['state']['mode'],'computer')
        self.assertEqual(out['a2'][-1]['state']['phase'],'playing')
        self.assertEqual(out['a2'][-1]['state']['board'],[None]*9)
        self.assertEqual(store.rooms[code]['connections'],['a2',None])
        service.resume('a3',code,session['token'])
        self.assertEqual(out['a3'][-1]['state']['you'],0)
