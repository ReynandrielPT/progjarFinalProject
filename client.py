import pygame
import sys
import socket
import logging
import json
import math
import time
import threading
import queue

logging.basicConfig(level=logging.INFO, format='CLIENT - %(levelname)s: %(message)s')
pygame.init()

WIDTH, HEIGHT = 640, 640
DOTS = 6
MARGIN = 50
SPACING = (WIDTH - 2 * MARGIN) / (DOTS - 1)
SERVER_ADDRESS = ("172.16.16.101", 8000)

BG_COLOR, DOT_COLOR, LINE_COLOR = (15, 23, 42), (203, 213, 225), (51, 65, 85)
PLAYER_COLORS = {1: (250, 100, 100), 2: (100, 150, 250)}; BOX_COLORS = {1: (250, 100, 100, 100), 2: (100, 150, 250, 100)}
WHITE, GREY, GREEN_ACCENT, RED_ACCENT = (240, 240, 240), (128, 128, 128), (0, 255, 150), (255, 50, 100)
DOT_RADIUS, LINE_WIDTH = 10, 5
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("Dots & Boxes")
clock = pygame.time.Clock()

class ClientInterface:
    def __init__(self):
        self.cookie = None

    def send_command(self, method, path, body=None):
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            sock.settimeout(10.0)
            sock.connect(SERVER_ADDRESS)
            
            body_str = json.dumps(body) if body else ""
            
            headers = [
                f"{method} {path} HTTP/1.1",
                f"Host: {SERVER_ADDRESS[0]}:{SERVER_ADDRESS[1]}",
                "Connection: close", "Accept: application/json",
                "User-Agent: ManualSocketClient/1.2"
            ]
            if self.cookie: headers.append(f"Cookie: {self.cookie}")
            if body_str:
                headers.append("Content-Type: application/json")
                headers.append(f"Content-Length: {len(body_str)}")

            request = "\r\n".join(headers) + "\r\n\r\n" + body_str
            sock.sendall(request.encode('utf-8'))

            response_bytes = b""
            while True:
                try:
                    chunk = sock.recv(4096)
                    if not chunk: break
                    response_bytes += chunk
                except socket.timeout: break
            
            if not response_bytes: return None
            
            header_part, body_part = response_bytes.split(b'\r\n\r\n', 1)
            
            for line in header_part.decode('utf-8', errors='ignore').split('\r\n'):
                if 'set-cookie:' in line.lower():
                    self.cookie = line.split(':', 1)[1].strip().split(';')[0]
            
            if body_part:
                return json.loads(body_part.decode('utf-8'))
            return {"status": "OK"}
        except Exception as e:
            logging.error(f"Error di send_command: {e}")
            return None
        finally:
            sock.close()

    def join(self): return self.send_command('GET', '/join')
    def get_state(self): return self.send_command('GET', '/gamestate')
    def send_action(self, action, params=[]):
        return self.send_command('POST', '/action', {'action': action, 'params': params})

class ConnectionManager:
    def __init__(self):
        self.lock = threading.Lock()
        self.latest_state = None
        self.action_queue = queue.Queue()
        self.my_id = None
        self.is_connected = False
        self.running = True
        self.client_interface = ClientInterface()

    def network_loop(self):
        response = self.client_interface.join()
        if response and response.get('player_id'):
            with self.lock:
                self.is_connected = True
                self.my_id = int(response['player_id'].replace('player', ''))
            logging.info(f"Bergabung sebagai {response['player_id']}")
        else:
            logging.error(f"Gagal bergabung. Respons: {response}")
            self.running = False
            return

        while self.running:
            try:
                action_data = self.action_queue.get(timeout=0.2)
                response = self.client_interface.send_action(action_data['action'], action_data.get('params', []))
            except queue.Empty:
                response = self.client_interface.get_state()
            
            if response and response.get('status') == 'OK' and 'state' in response:
                with self.lock:
                    self.latest_state = response.get('state')
            elif response:
                logging.warning(f"Server error atau respons tidak lengkap: {response}")
            time.sleep(0.1)

def get_line_rects():
    lines = []
    for r in range(DOTS):
        for c in range(DOTS - 1): lines.append({'type': 'row', 'pos': (r, c), 'rect': pygame.Rect(MARGIN + c * SPACING + DOT_RADIUS, MARGIN + r * SPACING - LINE_WIDTH // 2, SPACING - DOT_RADIUS * 2, LINE_WIDTH)})
    for r in range(DOTS - 1):
        for c in range(DOTS): lines.append({'type': 'col', 'pos': (r, c), 'rect': pygame.Rect(MARGIN + c * SPACING - LINE_WIDTH // 2, MARGIN + r * SPACING + DOT_RADIUS, LINE_WIDTH, SPACING - DOT_RADIUS * 2)})
    return lines

def draw_lobby_view(screen, state, my_id):
    font_title=pygame.font.SysFont("consolas", 60); font_main=pygame.font.SysFont("consolas", 30)
    screen.fill(BG_COLOR); title = font_title.render("Dots & Boxes", True, WHITE); screen.blit(title, (WIDTH / 2 - title.get_width() / 2, 80))
    countdown_text = None
    if state['game_state'] == "STARTING": countdown_text = f"Starting in {math.ceil(state['countdown'])}..."
    elif state['game_state'] == "RESUMING": countdown_text = f"Resuming in {math.ceil(state['countdown'])}..."
    if countdown_text: render_countdown = font_main.render(countdown_text, True, WHITE); screen.blit(render_countdown, (WIDTH / 2 - render_countdown.get_width() / 2, 180))
    
    all_players_joined = len(state['players']) >= 2
    
    if not all_players_joined and state['game_state'] == 'LOBBY':
        wait_text = font_main.render("Waiting for Player 2...", True, WHITE); screen.blit(wait_text, (WIDTH / 2 - wait_text.get_width() / 2, 250))
    else:
        for i, p_id_str in enumerate(['player1', 'player2']):
            if p_id_str in state['players']:
                y_pos = 250 + i * 100; is_ready = state['player_ready'].get(p_id_str, False)
                color = GREEN_ACCENT if is_ready else RED_ACCENT; text = f"Player {i+1}: {'READY' if is_ready else 'NOT READY'}"
                if my_id == (i + 1): text += " (You)"
                render = font_main.render(text, True, color); screen.blit(render, (WIDTH / 2 - render.get_width() / 2, y_pos))

    if all_players_joined:
        my_player_str = f'player{my_id}'; am_i_ready = state['player_ready'].get(my_player_str, False)
        action_msg = "Press [R] to UNREADY" if am_i_ready else "Press [R] to GET READY"
        render = font_main.render(action_msg, True, WHITE); screen.blit(render, (WIDTH / 2 - render.get_width() / 2, 500))

def draw_game_view(screen, state, my_id):
    font_main=pygame.font.SysFont("consolas",24); font_score=pygame.font.SysFont("consolas",40); font_pause=pygame.font.SysFont("consolas",50)
    screen.fill(BG_COLOR)
    for box in state['boxes']: r,c,owner=box['pos'][0],box['pos'][1],box['owner']; s=pygame.Surface((SPACING,SPACING),pygame.SRCALPHA);s.fill(BOX_COLORS[owner]);screen.blit(s,(MARGIN+c*SPACING,MARGIN+r*SPACING))
    for line in state['lines']:
        for lr in get_line_rects():
            if lr['type']==line['type'] and tuple(lr['pos'])==tuple(line['pos']): pygame.draw.rect(screen,PLAYER_COLORS.get(line['owner'],LINE_COLOR),lr['rect']);break
    for r in range(DOTS):
        for c in range(DOTS): pygame.draw.circle(screen,DOT_COLOR,(MARGIN+c*SPACING,MARGIN+r*SPACING),DOT_RADIUS)
    s1=sum(1 for b in state['boxes'] if b['owner']==1);s2=sum(1 for b in state['boxes'] if b['owner']==2)
    p1s=font_score.render(f"P1: {s1}",True,PLAYER_COLORS[1]);screen.blit(p1s,(20,10));p2s=font_score.render(f"P2: {s2}",True,PLAYER_COLORS[2]);screen.blit(p2s,(WIDTH-p2s.get_width()-20,10))
    is_my_turn = state.get('current_turn')==my_id; turn_text = "YOUR TURN" if is_my_turn else f"Player {state['current_turn']}'s Turn"; turn_color=PLAYER_COLORS[my_id] if is_my_turn else GREY
    turn_render=font_main.render(turn_text,True,turn_color);screen.blit(turn_render,(WIDTH/2-turn_render.get_width()/2,20))
    overlay_text_bottom = None
    if state.get('game_state') == "PAUSED":
        paused_by_id=int(state['paused_by'].replace('player',''));
        if my_id != paused_by_id:
            pause_render = font_pause.render("GAME PAUSED", True, WHITE); screen.blit(pause_render, (WIDTH / 2 - pause_render.get_width()/2, HEIGHT / 2 - pause_render.get_height()/2 - 30))
            overlay_text_bottom = "Press [ESC] to return to menu"
    elif state.get('game_state') == "RESUMING":
        paused_by_id=int(state['paused_by'].replace('player',''));
        if my_id != paused_by_id:
            countdown_text = f"Resuming in {math.ceil(state['countdown'])}..."; countdown_render = font_pause.render(countdown_text, True, WHITE)
            screen.blit(countdown_render, (WIDTH / 2 - countdown_render.get_width() / 2, HEIGHT / 2 - countdown_render.get_height() / 2))
    if overlay_text_bottom: back_text_render = font_main.render(overlay_text_bottom, True, WHITE); screen.blit(back_text_render, (WIDTH/2 - back_text_render.get_width()/2, HEIGHT - 50))

def draw_finished_view(screen, state):
    font_winner=pygame.font.SysFont("consolas",70); font_countdown=pygame.font.SysFont("consolas",30); screen.fill(BG_COLOR)
    winner_id = state.get('winner'); win_text = "GAME TIED!" if winner_id == 0 else f"PLAYER {winner_id} WINS!"
    render_winner = font_winner.render(win_text, True, WHITE); screen.blit(render_winner, (WIDTH / 2 - render_winner.get_width() / 2, HEIGHT / 2 - render_winner.get_height() / 2 - 30))
    countdown_text=f"Returning to lobby in {math.ceil(state['countdown'])}..."; render_countdown = font_countdown.render(countdown_text, True, GREY)
    screen.blit(render_countdown, (WIDTH/2 - render_countdown.get_width()/2, HEIGHT / 2 + 50))

def main():
    conn = ConnectionManager()
    threading.Thread(target=conn.network_loop, daemon=True).start()
    line_rects = get_line_rects()
    while conn.running:
        clock.tick(60)
        for event in pygame.event.get():
            if event.type == pygame.QUIT: conn.running = False
            with conn.lock: is_ready_for_input = conn.is_connected and conn.latest_state is not None
            if is_ready_for_input:
                current_state=conn.latest_state; my_id=conn.my_id
                server_game_state = current_state.get('game_state'); my_player_str=f'player{my_id}'

                all_players_joined = len(current_state['players']) >= 2
                
                if event.type == pygame.KEYDOWN:
                    if event.key == pygame.K_r and server_game_state in ["LOBBY","STARTING","PAUSED","RESUMING"] and all_players_joined:
                        is_currently_ready = current_state['player_ready'].get(my_player_str, False)
                        conn.action_queue.put({'action': 'UNREADY' if is_currently_ready else 'READY'})
                    elif event.key == pygame.K_ESCAPE and server_game_state in ["PLAYING", "PAUSED"]:
                        conn.action_queue.put({'action': 'PAUSE'})
                if event.type == pygame.MOUSEBUTTONDOWN and server_game_state == "PLAYING" and current_state.get('current_turn') == my_id:
                    if conn.action_queue.empty():
                        for line in line_rects:
                            if line['rect'].collidepoint(event.pos):
                                if not any(l['type']==line['type'] and tuple(l['pos'])==tuple(line['pos']) for l in current_state['lines']):
                                    conn.action_queue.put({'action':'make_move', 'params':[line['type'], line['pos'][0], line['pos'][1]]})
                                    break
        with conn.lock: current_state, my_id, is_connected = conn.latest_state, conn.my_id, conn.is_connected
        if not is_connected or not current_state:
            screen.fill(BG_COLOR); font = pygame.font.SysFont("consolas", 40)
            text = font.render("Connecting...", True, WHITE)
            screen.blit(text, (WIDTH / 2 - text.get_width() / 2, HEIGHT / 2 - text.get_height() / 2))
        else:
            server_game_state = current_state.get('game_state'); my_player_str = f'player{my_id}'
            am_i_in_lobby_view = (server_game_state in ["LOBBY","STARTING"] or ((server_game_state in ["PAUSED","RESUMING"]) and current_state.get('paused_by') == my_player_str))
            if am_i_in_lobby_view: draw_lobby_view(screen, current_state, my_id)
            elif server_game_state == "FINISHED": draw_finished_view(screen, current_state)
            else: draw_game_view(screen, current_state, my_id)
        pygame.display.flip()
    pygame.quit()
    sys.exit()

if __name__ == "__main__":
    main()
