# Nama file: game_state_client.py
import socket
import json
import logging
import threading
import time

class GameStateClient:
    def __init__(self, host='127.0.0.1', port=9000):
        self.host = host
        self.port = port
        self.socket = None
        self.lock = threading.Lock()
        self.connected = False
        
    def connect(self):
        """Koneksi ke game state server"""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.connect((self.host, self.port))
            self.connected = True
            logging.info(f"Connected to Game State Server at {self.host}:{self.port}")
            return True
        except Exception as e:
            logging.error(f"Failed to connect to Game State Server: {e}")
            self.connected = False
            return False
    
    def disconnect(self):
        """Disconnect dari game state server"""
        with self.lock:
            if self.socket:
                try:
                    self.socket.close()
                except:
                    pass
                self.socket = None
            self.connected = False
    
    def send_request(self, request_data):
        """Mengirim request ke game state server"""
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                with self.lock:
                    if not self.connected or not self.socket:
                        if not self.connect():
                            retry_count += 1
                            time.sleep(0.1)
                            continue
                    
                    # Send request
                    request_json = json.dumps(request_data)
                    self.socket.sendall(request_json.encode('utf-8'))
                    
                    # Receive response
                    response_data = self.socket.recv(4096)
                    if not response_data:
                        raise ConnectionError("No response from server")
                    
                    response = json.loads(response_data.decode('utf-8'))
                    return response
                    
            except Exception as e:
                logging.error(f"Error sending request (attempt {retry_count + 1}): {e}")
                self.disconnect()
                retry_count += 1
                if retry_count < max_retries:
                    time.sleep(0.1)
        
        logging.error("Failed to send request after maximum retries")
        return {'status': 'ERROR', 'message': 'Connection failed'}
    
    def get_state(self):
        """Mendapatkan state game"""
        return self.send_request({'action': 'get_state'})
    
    def assign_player(self):
        """Assign player baru"""
        return self.send_request({'action': 'assign_player'})
    
    def player_disconnected(self, player_id):
        """Notifikasi player disconnect"""
        return self.send_request({
            'action': 'player_disconnected',
            'player_id': player_id
        })
    
    def process_command(self, player_id, command):
        """Proses command dari player"""
        return self.send_request({
            'action': 'process_command',
            'player_id': player_id,
            'command': command
        })
    
    def update_game(self):
        """Update game logic"""
        return self.send_request({'action': 'update'})