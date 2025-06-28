import socket
import threading
import json
import time
import logging
from dots_logic import DotsAndBoxesLogic

logging.basicConfig(level=logging.INFO, format='GAME_STATE_SERVER - %(levelname)s: %(message)s')

class GameStateServer:
	def __init__(self, host='127.0.0.1', port=9000):
		self.host = host
		self.port = port
		self.game_logic = DotsAndBoxesLogic()
		self.lock = threading.Lock()
		self.running = True

	def handle_request(self, data):
		try:
			req = json.loads(data.decode())
			action = req.get('action')
			with self.lock:
				if action == 'get_state':
					return json.dumps({'status':'OK','state':self.game_logic.get_state()})
				elif action == 'assign_player':
					pid = self.game_logic.assign_player()
					if pid:
						return json.dumps({'status':'OK','player_id':pid})
					else:
						return json.dumps({'status':'ERROR','message':'Game is full'})
				elif action == 'player_disconnected':
					pid = req.get('player_id')
					self.game_logic.player_disconnected(pid)
					return json.dumps({'status':'OK','state':self.game_logic.get_state()})
				elif action == 'process_command':
					pid = req.get('player_id')
					cmd = req.get('command')
					result = self.game_logic.proses_command(pid, cmd)
					return json.dumps(result)
				elif action == 'update':
					self.game_logic.update()
					return json.dumps({'status':'OK','state':self.game_logic.get_state()})
				else:
					return json.dumps({'status':'ERROR','message':'Unknown action'})
		except Exception as e:
			logging.error(f"Request error: {e}")
			return json.dumps({'status':'ERROR','message':str(e)})

	def handle_client(self, sock, addr):
		try:
			while self.running:
				data = sock.recv(4096)
				if not data: break
				resp = self.handle_request(data)
				sock.sendall(resp.encode())
		except Exception as e:
			logging.error(f"Client error {addr}: {e}")
		finally:
			sock.close()

	def update_loop(self):
		logging.info("Update loop started")
		while self.running:
			try:
				with self.lock:
					self.game_logic.update()
				time.sleep(0.1) 
			except Exception as e:
				logging.error(f"Update loop error: {e}")

	def start(self):
		s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
		s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
		s.bind((self.host, self.port))
		s.listen(10)
		logging.info(f"Game State Server running on {self.host}:{self.port}")
		
		update_thread = threading.Thread(target=self.update_loop, daemon=True)
		update_thread.start()
		
		while self.running:
			try:
				sock, addr = s.accept()
				logging.info(f"Worker connected from {addr}")
				threading.Thread(target=self.handle_client, args=(sock, addr), daemon=True).start()
			except Exception as e:
				logging.error(f"Accept error: {e}")

if __name__ == '__main__':
	server = GameStateServer()
	try:
		server.start()
	except KeyboardInterrupt:
		logging.info("Shutting down Game State Server...")
		server.running = False
