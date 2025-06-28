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
		try:
			s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
			s.connect((self.host, self.port))
			self.socket = s
			self.connected = True
			logging.info(f"Connected to Game State Server at {self.host}:{self.port}")
			return True
		except Exception as e:
			logging.error(f"Failed to connect: {e}")
			self.connected = False
			return False

	def disconnect(self):
		with self.lock:
			if self.socket:
				try:
					self.socket.close()
				except:
					pass
				self.socket = None
			self.connected = False

	def send_request(self, data):
		retries = 3
		for attempt in range(retries):
			try:
				with self.lock:
					if not self.connected:
						if not self.connect():
							time.sleep(0.1)
							continue
					payload = json.dumps(data).encode('utf-8')
					self.socket.sendall(payload)

					resp = self.socket.recv(4096)
					if not resp:
						raise ConnectionError
					return json.loads(resp.decode('utf-8'))

			except Exception as e:
				logging.error(f"Request error (attempt {attempt+1}): {e}")
				self.disconnect()
				time.sleep(0.1)
		logging.error("Max retries reached")
		return {'status':'ERROR'}

	def get_state(self):
		return self.send_request({'action':'get_state'})

	def assign_player(self):
		return self.send_request({'action':'assign_player'})

	def player_disconnected(self, pid):
		return self.send_request({'action':'player_disconnected','player_id':pid})

	def process_command(self, pid, cmd):
		return self.send_request({'action':'process_command','player_id':pid,'command':cmd})

	def update_game(self):
		return self.send_request({'action':'update'})
