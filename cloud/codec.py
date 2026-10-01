"""Store authoritative room state as DynamoDB-safe JSON primitives."""
from game import Player, Room
from tictactoe import TicTacToeRoom


def encode(room, connections=None, recent_ids=None, expires_at=None):
    if isinstance(room, TicTacToeRoom):
        item = {key: getattr(room, attr) for key, attr in (
            ('board','board'), ('turn','turn'), ('winner','winner'), ('winningLine','winning_line'),
            ('phase','phase'), ('version','version'), ('commands','commands'),
            ('startedAt','started_at'), ('completedAt','completed_at'), ('message','message'), ('lastActive','last_active'))}
        item.update(roomCode=room.code, gameType='tictactoe', mode=room.mode,
                    players=[{'tokenHash': p.token, 'name': p.name} for p in room.players],
                    connections=list(connections or [None,None]), recentIds=list(recent_ids or [[],[]]),
                    expiresAt=int(expires_at or 0))
        return item
    return {'gameType': 'maze',
        'roomCode': room.code, 'grid': room.grid, 'starts': [list(p) for p in room.starts],
        'relays': [list(p) for p in room.relays], 'exitPoint': list(room.exit_point),
        'hazards': [list(p) for p in sorted(room.hazards)],
        'players': [{'tokenHash': p.token, 'name': p.name, 'pos': list(p.pos),
                     'facing': p.facing, 'stunnedUntil': p.stunned_until} for p in room.players],
        'revealed': [list(p) for p in sorted(room.revealed)], 'activated': room.activated[:],
        'phase': room.phase, 'version': room.version, 'commands': room.commands,
        'startedAt': room.started_at, 'completedAt': room.completed_at,
        'message': room.message, 'lastActive': room.last_active,
        'connections': list(connections or [None, None]),
        'recentIds': list(recent_ids or [[], []]), 'expiresAt': int(expires_at or 0),
    }


def decode(item):
    if item.get('gameType', 'maze') == 'tictactoe':
        room = TicTacToeRoom.new(item['roomCode'], item.get('mode', 'network'))
        for key, attr in (('board','board'), ('turn','turn'), ('winner','winner'), ('winningLine','winning_line'),
                          ('phase','phase'), ('version','version'), ('commands','commands'),
                          ('startedAt','started_at'), ('completedAt','completed_at'), ('message','message'), ('lastActive','last_active')):
            setattr(room, attr, item[key])
        room.players = [Player(p['tokenHash'], p['name'], (0,0)) for p in item['players']]
        return room
    if item.get('gameType', 'maze') != 'maze':
        raise ValueError('Unknown simulation.')
    return Room(
        code=item['roomCode'], grid=item['grid'], starts=[tuple(p) for p in item['starts']],
        relays=[tuple(p) for p in item['relays']], exit_point=tuple(item['exitPoint']),
        hazards={tuple(p) for p in item['hazards']},
        players=[Player(p['tokenHash'], p['name'], tuple(p['pos']), int(p['facing']),
                        float(p['stunnedUntil'])) for p in item['players']],
        revealed={tuple(p) for p in item['revealed']}, activated=item['activated'][:],
        phase=item['phase'], version=int(item['version']), commands=int(item['commands']),
        started_at=float(item['startedAt']), completed_at=float(item['completedAt']),
        message=item['message'], last_active=float(item['lastActive']),
    )
