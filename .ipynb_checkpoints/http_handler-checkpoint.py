import sys
import os.path
import uuid
import json
import time
import threading
from datetime import datetime
from game_state_client import GameStateClient

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.game_state_client = GameStateClient()
        self.lock = threading.Lock()
        
        # Pastikan koneksi ke game state server
        if not self.game_state_client.connect():
            raise Exception("Failed to connect to Game State Server")

    def response(self, kode=404, message='Not Found', messagebody=b"", headers={}):
        tanggal = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        resp = [
            f"HTTP/1.1 {kode} {message}",
            f"Date: {tanggal}",
            "Server: DotsAndBoxesServer/1.1",
            "Connection: close",
            f"Content-Length: {len(messagebody)}",
        ]
        for kk, vv in headers.items():
            resp.append(f"{kk}: {vv}")
        
        response_str = "\r\n".join(resp) + "\r\n\r\n"
        
        if not isinstance(messagebody, bytes):
            messagebody = messagebody.encode()

        return response_str.encode() + messagebody

    def proses(self, data):
        try:
            header_part, body = data.split("\r\n\r\n", 1)
            request_lines = header_part.split("\r\n")
            request_line = request_lines[0]
            
            all_headers = {line.split(': ', 1)[0].lower(): line.split(': ', 1)[1] for line in request_lines[1:] if ': ' in line}
            method, object_address, _ = request_line.split(" ", 2)

            if method == 'GET':
                return self.http_get(object_address, all_headers)
            elif method == 'POST':
                return self.http_post(object_address, all_headers, body)
            else:
                return self.response(400, 'Bad Request', b'Unsupported method')
        except ValueError:
            return self.response(400, 'Bad Request', b'Malformed request')
        except Exception as e:
            return self.response(500, 'Internal Server Error', str(e).encode())

    def get_player_id(self, headers):
        cookie_str = headers.get('cookie', '')
        cookies = dict(item.split('=', 1) for item in cookie_str.split('; ') if '=' in item)
        session_id = cookies.get('session_id')
        
        with self.lock:
            if session_id and session_id in self.sessions:
                self.sessions[session_id]['last_seen'] = time.time()
                return self.sessions[session_id]['player_id']
        return None

    def http_get(self, object_address, headers):
        if object_address == '/join':
            with self.lock:
                # Request assign player dari game state server
                response = self.game_state_client.assign_player()
                if response.get('status') == 'OK' and response.get('player_id'):
                    player_id = response['player_id']
                    new_session_id = str(uuid.uuid4())
                    self.sessions[new_session_id] = {
                        'player_id': player_id, 
                        'last_seen': time.time()
                    }
                    body = json.dumps({'status': 'OK', 'player_id': player_id})
                    return self.response(200, 'OK', body.encode(), {
                        'Content-Type': 'application/json', 
                        'Set-Cookie': f'session_id={new_session_id}; Path=/'
                    })
                else:
                    return self.response(503, 'Service Unavailable', b'Game is full.')
        
        elif object_address == '/gamestate':
            player_id = self.get_player_id(headers)
            if player_id:
                # Get state dari game state server
                response = self.game_state_client.get_state()
                if response.get('status') == 'OK':
                    body = json.dumps({'status': 'OK', 'state': response['state']})
                    return self.response(200, 'OK', body, {'Content-Type': 'application/json'})
                else:
                    return self.response(500, 'Internal Server Error', b'Failed to get game state')
            return self.response(401, 'Unauthorized', b'No session')
        return self.response(404, 'Not Found', b'')

    def http_post(self, object_address, headers, body):
        player_id = self.get_player_id(headers)
        if not player_id:
            return self.response(401, 'Unauthorized', b'No session')
        
        if object_address == '/action':
            try:
                command = json.loads(body)
                # Process command via game state server
                response = self.game_state_client.process_command(player_id, command)
                if response.get('status') == 'OK':
                    return self.response(200, 'OK', json.dumps(response), {'Content-Type': 'application/json'})
                else:
                    return self.response(500, 'Internal Server Error', json.dumps(response), {'Content-Type': 'application/json'})
            except (json.JSONDecodeError, KeyError):
                return self.response(400, 'Bad Request', b'Invalid JSON Body')
        return self.response(404, 'Not Found', b'')
    
    def cleanup_sessions(self):
        """Cleanup expired sessions"""
        with self.lock:
            current_time = time.time()
            stale_ids = [
                sid for sid, data in self.sessions.items() 
                if current_time - data.get('last_seen', 0) > 5
            ]
            
            for sid in stale_ids:
                if sid in self.sessions:
                    player_id = self.sessions.pop(sid)['player_id']
                    # Notify game state server about disconnection
                    self.game_state_client.player_disconnected(player_id)