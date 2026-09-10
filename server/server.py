import json
import socket
import threading
import struct
import time
import uuid

from lib import db_manager
from lib import protocol
from lib import security
from server.game import Game


class Lobby:
    def __init__(self, lobby_id: str):
        self.lobby_id = lobby_id
        self.clients = {}
        self.lock = threading.Lock()
        self.game = None
        self.match_started = False
        self.match_thread = None
        self.client_ids = {}
        self.host_socket = None

    def add_client(self, client_socket, cipher):
        with self.lock:
            if client_socket in self.clients:
                return True
            if len(self.clients) >= 4:
                return False
            self.clients[client_socket] = cipher

            if client_socket not in self.client_ids:
                for player_num in range(1, 5):
                    player_id = f"p{player_num}"
                    if player_id not in self.client_ids.values():
                        self.client_ids[client_socket] = player_id
                        break

            if self.host_socket is None:
                self.host_socket = client_socket
            return True

    def remove_client(self, client_socket):
        with self.lock:
            if client_socket in self.clients:
                del self.clients[client_socket]

            player_id = self.client_ids.pop(client_socket, None)
            if player_id and self.game is not None:
                self.game.remove_player(player_id)

            if self.host_socket == client_socket and self.clients:
                self.host_socket = next(iter(self.clients.keys()))
            elif self.host_socket == client_socket:
                self.host_socket = None

    def _ensure_game(self):
        if self.game is None:
            self.game = Game()

    def _assign_players(self):
        self._ensure_game()
        ordered_clients = list(self.clients.keys())[:4]
        corners = self.game.engine.spawn_points[:len(ordered_clients)]

        for idx, client_socket in enumerate(ordered_clients):
            player_id = self.client_ids.get(client_socket, f"p{idx + 1}")
            self.client_ids[client_socket] = player_id
            start_r, start_c = corners[idx]
            self.game.add_player(player_id, start_r, start_c)

    def can_start(self, client_socket):
        with self.lock:
            return (
                self.host_socket == client_socket
                and not self.match_started
                and len(self.clients) >= 2
            )

    def request_start(self, client_socket):
        if not self.can_start(client_socket):
            return False

        self.start_match()
        return True

    def start_match(self):
        if self.match_started:
            return True

        if len(self.clients) < 2:
            return False

        self._assign_players()
        self.match_started = True

        self.countdown_thread = threading.Thread(target=self._run_countdown, daemon=True)
        self.countdown_thread.start()
        return True

    def _run_countdown(self):
        for value in (3, 2, 1, "GO"):
            self.broadcast_match_start(str(value))
            time.sleep(1)

        self.match_thread = threading.Thread(target=self._run_match_loop, daemon=True)
        self.match_thread.start()
        self.broadcast_game_state()

    def _run_match_loop(self):
        while self.clients:
            if self.game is not None:
                self.game.tick()
                self.broadcast_game_state()
            time.sleep(0.5)

    def broadcast_match_start(self, payload_text="Match started!"):
        payload = payload_text.encode("utf-8")
        with self.lock:
            for client, cipher in list(self.clients.items()):
                try:
                    protocol.send_msg(client, protocol.OP_MATCH_START, payload, cipher=cipher)
                except Exception:
                    self.remove_client(client)

    def broadcast_game_state(self):
        if self.game is None:
            return

        payload = json.dumps(self.game.serialize_state()).encode('utf-8')
        with self.lock:
            for client, cipher in list(self.clients.items()):
                try:
                    protocol.send_msg(client, protocol.OP_GAME_STATE, payload, cipher=cipher)
                except Exception:
                    self.remove_client(client)

    def broadcast(self, opcode: int, payload_bytes: bytes, sender_socket=None):
        with self.lock:
            for client, cipher in list(self.clients.items()):
                if client != sender_socket:
                    try:
                        protocol.send_msg(client, opcode, payload_bytes, cipher=cipher)
                    except Exception:
                        self.remove_client(client)


LOBBIES = {}
LOBBIES_LOCK = threading.Lock()


def handle_client(client_sock, client_addr, server_dh_params):
    print(f"[NEW CONNECTION] Connected from {client_addr}")
    cipher = None
    current_lobby = None

    try:
        dh_session = security.DHHandshake(parameters=server_dh_params)
        param_bytes = dh_session.get_parameters_bytes()
        pub_bytes = dh_session.get_public_bytes()

        init_payload = struct.pack("!I", len(param_bytes)) + param_bytes + pub_bytes
        protocol.send_msg(client_sock, protocol.OP_DH_HANDSHAKE, init_payload)

        opcode, client_pub_bytes = protocol.recv_msg(client_sock)
        if opcode != protocol.OP_DH_HANDSHAKE or not client_pub_bytes:
            print(f"[SECURITY ERROR] Handshake failed with {client_addr}")
            client_sock.close()
            return

        session_key = dh_session.generate_session_key(client_pub_bytes)
        cipher = security.SymmetricCipher(session_key)
        print(f"[SECURITY] Encrypted session established with {client_addr}")

        while True:
            opcode, payload = protocol.recv_msg(client_sock, cipher=cipher)
            if opcode is None:
                print(f"[CLIENT DISCONNECTED] {client_addr}")
                break

            if opcode == protocol.OP_REGISTER:
                try:
                    data = json.loads(payload.decode('utf-8'))
                except Exception:
                    data = {}
                username = data.get("username", "").strip()
                password = data.get("password", "").strip()

                success, msg = db_manager.register_user(username, password)
                res_payload = json.dumps({"success": success, "message": msg}).encode('utf-8')
                protocol.send_msg(client_sock, protocol.OP_REGISTER_RESP, res_payload, cipher=cipher)

            elif opcode == protocol.OP_LOGIN:
                try:
                    data = json.loads(payload.decode('utf-8'))
                except Exception:
                    data = {}
                username = data.get("username", "").strip()
                password = data.get("password", "").strip()

                success, user_info_or_msg = db_manager.authenticate_user(username, password)
                if success:
                    res_payload = json.dumps({
                        "success": True,
                        "message": "Login successful!",
                        "user": user_info_or_msg
                    }).encode('utf-8')
                else:
                    res_payload = json.dumps({
                        "success": False,
                        "message": str(user_info_or_msg)
                    }).encode('utf-8')

                protocol.send_msg(client_sock, protocol.OP_LOGIN_RESP, res_payload, cipher=cipher)

            elif opcode == protocol.OP_CREATE_LOBBY:
                lobby_id = str(uuid.uuid4())[:6].upper()
                new_lobby = Lobby(lobby_id)
                if not new_lobby.add_client(client_sock, cipher):
                    protocol.send_msg(client_sock, protocol.OP_ERROR, b"Lobby is full!", cipher=cipher)
                    client_sock.close()
                    return

                with LOBBIES_LOCK:
                    LOBBIES[lobby_id] = new_lobby

                current_lobby = new_lobby
                print(f"[LOBBY CREATED] ID: {lobby_id} by {client_addr}")
                player_id = new_lobby.client_ids.get(client_sock, "p1")
                res_payload = f"CREATED:{lobby_id}:{player_id}".encode('utf-8')
                protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, res_payload, cipher=cipher)

            elif opcode == protocol.OP_JOIN_LOBBY:
                target_id = payload.decode('utf-8').strip().upper()
                with LOBBIES_LOCK:
                    target_lobby = LOBBIES.get(target_id)

                if target_lobby:
                    if not target_lobby.add_client(client_sock, cipher):
                        protocol.send_msg(client_sock, protocol.OP_ERROR, b"Lobby is full!", cipher=cipher)
                        continue

                    current_lobby = target_lobby
                    print(f"[LOBBY JOIN] {client_addr} joined lobby #{target_id}")
                    player_id = target_lobby.client_ids.get(client_sock, "p1")
                    res_payload = f"JOINED:{target_id}:{player_id}".encode('utf-8')
                    protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, res_payload, cipher=cipher)
                    current_lobby.broadcast(protocol.OP_CHAT_MSG, b"A new player joined the room!", sender_socket=client_sock)
                else:
                    protocol.send_msg(client_sock, protocol.OP_ERROR, b"Lobby not found!", cipher=cipher)

            elif opcode == protocol.OP_START_MATCH:
                if not current_lobby:
                    protocol.send_msg(client_sock, protocol.OP_ERROR, b"You are not in a lobby.", cipher=cipher)
                    continue

                if not current_lobby.request_start(client_sock):
                    protocol.send_msg(
                        client_sock,
                        protocol.OP_ERROR,
                        b"At least 2 players are required before the host can start the game.",
                        cipher=cipher
                    )

            elif opcode == protocol.OP_MOVE_PLAYER:
                if not current_lobby or not current_lobby.game:
                    continue

                player_id = current_lobby.client_ids.get(client_sock)
                if not player_id:
                    continue

                try:
                    data = json.loads(payload.decode("utf-8", errors="ignore"))
                    current_lobby.game.move_player(player_id, dx=data.get("dx", 0.0), dy=data.get("dy", 0.0))
                except Exception:
                    direction = payload.decode("utf-8", errors="ignore").upper()
                    current_lobby.game.move_player(player_id, direction=direction)

                current_lobby.broadcast_game_state()

            elif opcode == protocol.OP_CHAT_MSG:
                if current_lobby:
                    current_lobby.broadcast(protocol.OP_CHAT_MSG, payload, sender_socket=client_sock)

    except Exception as e:
        print(f"[ERROR] Client handling error ({client_addr}): {e}")
    finally:
        if current_lobby:
            current_lobby.remove_client(client_sock)
            if not current_lobby.clients:
                with LOBBIES_LOCK:
                    LOBBIES.pop(current_lobby.lobby_id, None)
        client_sock.close()


def main():
    db_manager.init_db()

    print("[SERVER] Initializing Diffie-Hellman parameters...")
    dh_master = security.DHHandshake()
    server_dh_params = dh_master.parameters
    print("[SERVER] DH Parameters ready. Starting server socket...")

    HOST = "0.0.0.0"
    PORT = 3000

    server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server_sock.bind((HOST, PORT))
    server_sock.listen(5)

    print(f"[SERVER STARTED] Listening on {HOST}:{PORT}")

    while True:
        client_sock, client_addr = server_sock.accept()
        t = threading.Thread(
            target=handle_client,
            args=(client_sock, client_addr, server_dh_params),
            daemon=True
        )
        t.start()


if __name__ == "__main__":
    main()
