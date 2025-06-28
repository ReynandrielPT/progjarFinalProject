import json
import logging
import time
import random

DOTS = 6
COUNTDOWN_SECONDS = 5
FINISH_DELAY_SECONDS = 5

class DotsAndBoxesLogic:
    def __init__(self):
        self.players = {}
        self.player_ready = {}
        self.lines = []
        self.boxes = []
        self.winner = None
        self.current_turn = None
        self.game_state = "LOBBY"
        self.countdown_start_time = None
        self.paused_by = None
        self.game_finished_time = None
        self.board_size = DOTS
        self.reset_game()

    def reset_game(self, params=None):
        current_players = self.players.copy()
        self.lines = []
        self.boxes = []
        self.winner = None
        self.current_turn = None
        self.game_state = "LOBBY"
        self.countdown_start_time = None
        self.paused_by = None
        self.game_finished_time = None
        self.players = current_players
        self.player_ready = {pid: False for pid in self.players}
        logging.info("Game state has been reset to LOBBY.")

    def get_state(self):
        countdown = 0
        if self.game_state in ("STARTING", "RESUMING") and self.countdown_start_time:
            countdown = max(0, COUNTDOWN_SECONDS - (time.time() - self.countdown_start_time))
        elif self.game_state == "FINISHED" and self.game_finished_time:
            countdown = max(0, FINISH_DELAY_SECONDS - (time.time() - self.game_finished_time))
        return {
            'board_size': self.board_size,
            'lines': self.lines,
            'boxes': self.boxes,
            'current_turn': self.current_turn,
            'players': self.players,
            'winner': self.winner,
            'player_count': len(self.players),
            'game_state': self.game_state,
            'player_ready': self.player_ready,
            'countdown': countdown,
            'paused_by': self.paused_by
        }

    def assign_player(self):
        if 'player1' not in self.players:
            self.players['player1'] = {}
            self.player_ready['player1'] = False
            return 'player1'
        if 'player2' not in self.players:
            self.players['player2'] = {}
            self.player_ready['player2'] = False
            return 'player2'
        return None

    def player_disconnected(self, player_id):
        if player_id in self.players:
            del self.players[player_id]
            self.player_ready.pop(player_id, None)
            logging.info(f"Player {player_id} disconnected.")
            if self.game_state != "LOBBY":
                logging.info("A player disconnected during the game. Resetting to lobby.")
                self.reset_game()

    def make_move(self, params=[]):
        pid_str, line_type, row_str, col_str = params
        pid = int(pid_str)
        if self.game_state != "PLAYING" or pid != self.current_turn:
            return
        move = {'type': line_type, 'pos': (int(row_str), int(col_str))}
        if any(l['type'] == move['type'] and tuple(l['pos']) == move['pos'] for l in self.lines):
            return
        self.lines.append({'type': line_type, 'pos': move['pos'], 'owner': pid})
        if self._check_new_boxes(pid) == 0:
            self.current_turn = 2 if self.current_turn == 1 else 1
        if len(self.boxes) == (self.board_size - 1) ** 2 and self.game_state != "FINISHED":
            s1 = sum(1 for b in self.boxes if b['owner'] == 1)
            s2 = sum(1 for b in self.boxes if b['owner'] == 2)
            self.winner = 1 if s1 > s2 else 2 if s2 > s1 else 0
            self.game_state = "FINISHED"
            self.game_finished_time = time.time()

    def proses_command(self, player_id, command):
        action = command.get('action')
        if action == 'make_move':
            self.make_move([player_id.replace('player','')] + command.get('params', []))
        elif action == 'READY':
            if self.game_state == 'PAUSED' and self.paused_by != player_id:
                return {'status':'OK', 'state': self.get_state()}
            if player_id in self.player_ready:
                self.player_ready[player_id] = True
                if self.game_state == 'PAUSED' and self.paused_by == player_id:
                    self.game_state = 'RESUMING'
                    self.countdown_start_time = time.time()
        elif action == 'UNREADY':
            if self.game_state == 'PAUSED' and self.paused_by != player_id:
                return {'status':'OK', 'state': self.get_state()}
            if player_id in self.player_ready:
                self.player_ready[player_id] = False
                if self.game_state in ("STARTING", "RESUMING"):
                    self.game_state = "LOBBY" if self.paused_by is None else "PAUSED"
                    self.countdown_start_time = None
                    logging.info("Countdown cancelled.")
        elif action == 'PAUSE':
            if self.game_state == "PLAYING":
                self.game_state = "PAUSED"
                self.paused_by = player_id
                self.player_ready[player_id] = False
                logging.info(f"Game paused by {player_id}.")
            elif self.game_state == "PAUSED" and self.paused_by != player_id:
                logging.info("Both players left the paused game. Resetting to lobby.")
                self.reset_game()
        return {'status':'OK', 'state': self.get_state()}

    def update(self):
        if self.game_state == "LOBBY" and len(self.players) == 2 and all(self.player_ready.values()):
            self.game_state = "STARTING"
            self.current_turn = random.choice([1, 2])
            self.winner = None
            self.countdown_start_time = time.time()
        if self.game_state == "STARTING" and self.countdown_start_time:
            if time.time() - self.countdown_start_time >= COUNTDOWN_SECONDS:
                self.game_state = "PLAYING"
                self.countdown_start_time = None
        if self.game_state == "RESUMING" and self.countdown_start_time:
            if time.time() - self.countdown_start_time >= COUNTDOWN_SECONDS:
                self.game_state = "PLAYING"
                self.paused_by = None
                self.countdown_start_time = None
        if self.game_state == "FINISHED" and self.game_finished_time:
            if time.time() - self.game_finished_time >= FINISH_DELAY_SECONDS:
                logging.info("Game finished. Resetting to lobby automatically.")
                self.reset_game()

    def _check_new_boxes(self, player_id):
        new_boxes = 0
        all_lines = {(l['type'], tuple(l['pos'])) for l in self.lines}
        for r in range(self.board_size - 1):
            for c in range(self.board_size - 1):
                if (r, c) not in [b['pos'] for b in self.boxes] and all(
                    t in all_lines for t in [
                        ('row', (r, c)),
                        ('row', (r + 1, c)),
                        ('col', (r, c)),
                        ('col', (r, c + 1))
                    ]
                ):
                    self.boxes.append({'pos': (r, c), 'owner': player_id})
                    new_boxes += 1
        return new_boxes
