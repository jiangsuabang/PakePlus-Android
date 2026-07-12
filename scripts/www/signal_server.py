import asyncio
import json

try:
    import websockets
except ImportError:
    print("Installing websockets...")
    import subprocess, sys
    subprocess.check_call([sys.executable, '-m', 'pip', 'install', 'websockets'])
    import websockets

rooms = {}       # room_id -> room info dict
connections = {} # websocket -> {player_id, room_id}

async def handler(websocket):
    connections[websocket] = {'player_id': None, 'room_id': None}
    try:
        async for message in websocket:
            try:
                data = json.loads(message)
                await handle_message(websocket, data)
            except json.JSONDecodeError:
                pass
    except websockets.exceptions.ConnectionClosed:
        pass
    except Exception as e:
        print(f"Connection error: {e}")
    finally:
        cleanup(websocket)

async def handle_message(ws, msg):
    t = msg.get('type')

    if t == 'register_room':
        rid = msg['room_id']
        rooms[rid] = msg['room']
        connections[ws]['room_id'] = rid
        connections[ws]['player_id'] = msg['room']['host']
        await broadcast({'type': 'room_list', 'rooms': list(rooms.values())})

    elif t == 'list_rooms':
        await ws.send(json.dumps({'type': 'room_list', 'rooms': list(rooms.values())}))

    elif t == 'join_room':
        rid = msg['room_id']
        player = msg['player']
        if rid in rooms and len(rooms[rid]['players']) < rooms[rid]['maxPlayers']:
            existing = [p for p in rooms[rid]['players'] if p['id'] == player['id']]
            if not existing:
                rooms[rid]['players'].append(player)
            connections[ws]['room_id'] = rid
            connections[ws]['player_id'] = player['id']
            await broadcast_room(rid, {'type': 'room_update', 'room': rooms[rid]})
            await ws.send(json.dumps({'type': 'joined', 'room': rooms[rid]}))
        else:
            await ws.send(json.dumps({'type': 'join_failed', 'reason': 'Room full or not found'}))

    elif t == 'leave_room':
        rid = connections[ws].get('room_id')
        pid = msg.get('player_id', connections[ws].get('player_id'))
        if rid and rid in rooms and pid:
            rooms[rid]['players'] = [p for p in rooms[rid]['players'] if p['id'] != pid]
            connections[ws]['room_id'] = None
            connections[ws]['player_id'] = None
            await broadcast_room(rid, {'type': 'room_update', 'room': rooms[rid]})
            if not rooms[rid]['players']:
                del rooms[rid]
                await broadcast({'type': 'room_list', 'rooms': list(rooms.values())})

    elif t == 'game_start':
        rid = msg.get('room_id')
        if rid:
            await broadcast_room(rid, {
                'type': 'game_start',
                'room_id': rid,
                'start_time': msg.get('start_time'),
                'seed': msg.get('seed', 0),
            })

    elif t == 'player_state':
        # 直接转发给同房间其他玩家
        rid = connections[ws].get('room_id')
        if rid:
            await broadcast_room(rid, msg, exclude=ws)

    elif t == 'player_died':
        rid = connections[ws].get('room_id')
        if rid:
            await broadcast_room(rid, msg, exclude=ws)

    elif t == 'ping':
        await ws.send(json.dumps({'type': 'pong'}))

async def broadcast(msg):
    dead = []
    for ws in list(connections.keys()):
        if ws.readyState:
            try:
                await ws.send(json.dumps(msg))
            except:
                dead.append(ws)
        else:
            dead.append(ws)
    for ws in dead:
        cleanup(ws)

async def broadcast_room(rid, msg, exclude=None):
    dead = []
    for ws, info in list(connections.items()):
        if ws != exclude and info.get('room_id') == rid and ws.readyState:
            try:
                await ws.send(json.dumps(msg))
            except:
                dead.append(ws)
    for ws in dead:
        cleanup(ws)

def cleanup(websocket):
    info = connections.get(websocket, {})
    rid = info.get('room_id')
    pid = info.get('player_id')
    if rid and rid in rooms and pid:
        rooms[rid]['players'] = [p for p in rooms[rid]['players'] if p['id'] != pid]
        if not rooms[rid]['players'] and rid in rooms:
            del rooms[rid]
            asyncio.create_task(broadcast({'type': 'room_list', 'rooms': list(rooms.values())}))
    connections.pop(websocket, None)

async def main():
    print('=' * 50)
    print('Game Signaling Server v1.0 (Simple Relay)')
    print('ws://0.0.0.0:9091')
    print('=' * 50)
    async with websockets.serve(handler, '0.0.0.0', 9091):
        await asyncio.Future()

if __name__ == '__main__':
    asyncio.run(main())
