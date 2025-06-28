import sys
import os.path
import uuid
import json
import time
import threading
from glob import glob
from datetime import datetime
from game_state_client import GameStateClient

class HttpServer:
    def __init__(self):
        self.sessions = {}
        self.types = {}
        self.types['.pdf'] = 'application/pdf'
        self.types['.jpg'] = 'image/jpeg'
        self.types['.txt'] = 'text/plain'
        self.types['.html'] = 'text/html'
        self.game_state_client = GameStateClient()
        self.lock = threading.Lock()
        
        if not self.game_state_client.connect():
            raise Exception("Failed to connect to Game State Server")

    def response(self, kode=404, message='Not Found', messagebody=bytes(), headers={}):
        tanggal = datetime.utcnow().strftime('%a, %d %b %Y %H:%M:%S GMT')
        resp = []
        resp.append("HTTP/1.1 {} {}\r\n".format(kode, message))
        resp.append("Date: {}\r\n".format(tanggal))
        resp.append("Connection: close\r\n")
        resp.append("Server: DotsAndBoxesServer/1.1\r\n")
        resp.append("Content-Length: {}\r\n".format(len(messagebody)))
        for kk in headers:
            resp.append("{}:{}\r\n".format(kk, headers[kk]))
        resp.append("\r\n")

        response_headers = ''
        for i in resp:
            response_headers = "{}{}".format(response_headers, i)
        
        if (type(messagebody) is not bytes):
            messagebody = messagebody.encode()

        response = response_headers.encode() + messagebody
        return response

    def proses(self, data):
        if "\r\n\r\n" in data:
            header_part, body_part = data.split("\r\n\r\n", 1)
        else:
            header_part = data
            body_part = ""
            
        requests = header_part.split("\r\n")
        baris = requests[0]
        all_headers = [n for n in requests[1:] if n!='']

        j = baris.split(" ")
        try:
            method=j[0].upper().strip()
            if (method=='GET'):
                object_address = j[1].strip()
                return self.http_get(object_address, all_headers)
            if (method=='POST'):
                object_address = j[1].strip()
                return self.http_post(object_address, all_headers, body_part)
            else:
                return self.response(400,'Bad Request','',{})
        except IndexError:
            return self.response(400,'Bad Request','',{})

    def get_player_id(self, headers):
        cookie_str = ''
        for header in headers:
            if header.lower().startswith('cookie:'):
                cookie_str = header.split(':', 1)[1].strip()
                break
        
        cookies = dict(item.split('=', 1) for item in cookie_str.split('; ') if '=' in item and cookie_str)
        session_id = cookies.get('session_id')
        
        with self.lock:
            if session_id and session_id in self.sessions:
                self.sessions[session_id]['last_seen'] = time.time()
                return self.sessions[session_id]['player_id']
        return None

    def http_get(self, object_address, headers):
        if object_address == '/':
            return self.response(200, 'OK', 'Dots and Boxes Game Server', dict())
        
        if object_address == '/video':
            return self.response(302, 'Found', '', dict(location='https://youtu.be/katoxpnTf04'))
        
        if object_address == '/santai':
            return self.response(200, 'OK', 'santai saja', dict())

        if object_address == '/join':
            with self.lock:
                response = self.game_state_client.assign_player()
                if response.get('status') == 'OK' and response.get('player_id'):
                    player_id = response['player_id']
                    new_session_id = str(uuid.uuid4())
                    self.sessions[new_session_id] = {
                        'player_id': player_id,
                        'last_seen': time.time()
                    }
                    body = json.dumps({'status': 'OK', 'player_id': player_id})
                    headers_resp = {
                        'Content-Type': 'application/json',
                        'Set-Cookie': 'session_id={}; Path=/'.format(new_session_id)
                    }
                    return self.response(200, 'OK', body, headers_resp)
                else:
                    return self.response(503, 'Service Unavailable', 'Game is full.')

        if object_address == '/gamestate':
            player_id = self.get_player_id(headers)
            if player_id:
                # Update game state sebelum mengembalikan state
                self.game_state_client.update_game()
                response = self.game_state_client.get_state()
                if response.get('status') == 'OK':
                    body = json.dumps({'status': 'OK', 'state': response['state']})
                    return self.response(200, 'OK', body, {'Content-Type': 'application/json'})
                else:
                    return self.response(500, 'Internal Server Error', 'Failed to get game state')
            return self.response(401, 'Unauthorized', 'No session')

        files = glob('./*')
        thedir = './'
        object_address = object_address[1:] 
        
        if thedir + object_address not in files:
            return self.response(404, 'Not Found', '', {})
        
        try:
            fp = open(thedir + object_address, 'rb')
            isi = fp.read()
            fp.close()
            
            fext = os.path.splitext(thedir + object_address)[1]
            content_type = self.types.get(fext, 'application/octet-stream')
            
            headers_resp = {}
            headers_resp['Content-type'] = content_type
            
            return self.response(200, 'OK', isi, headers_resp)
        except IOError:
            return self.response(404, 'Not Found', '', {})

    def http_post(self, object_address, headers, body):
        if object_address == '/action':
            player_id = self.get_player_id(headers)
            if not player_id:
                return self.response(401, 'Unauthorized', 'No session')
            
            try:
                if body.strip():
                    action_data = json.loads(body)
                    response = self.game_state_client.process_command(player_id, action_data)
                    if response.get('status') == 'OK':
                        return self.response(200, 'OK', json.dumps(response), {'Content-Type': 'application/json'})
                    else:
                        return self.response(500, 'Internal Server Error', json.dumps(response))
                else:
                    return self.response(400, 'Bad Request', 'Empty body')
                    
            except json.JSONDecodeError:
                return self.response(400, 'Bad Request', 'Invalid JSON')
            except Exception as e:
                return self.response(500, 'Internal Server Error', str(e))

        headers_resp = {}
        isi = "kosong"
        return self.response(200, 'OK', isi, headers_resp)

    def cleanup_sessions(self):
        with self.lock:
            current_time = time.time()
            stale_ids = [
                sid for sid, data in self.sessions.items()
                if current_time - data.get('last_seen', 0) > 5
            ]
            
            for sid in stale_ids:
                if sid in self.sessions:
                    player_id = self.sessions.pop(sid)['player_id']
                    self.game_state_client.player_disconnected(player_id)


if __name__ == "__main__":
    httpserver = HttpServer()
    d = httpserver.proses('GET testing.txt HTTP/1.0')
    print(d)
    d = httpserver.proses('GET donalbebek.jpg HTTP/1.0')
    print(d)
