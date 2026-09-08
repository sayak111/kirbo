import socket
import struct
import threading
import uuid
import protocol
import security

import json
import time
import threading
from gamelogic import GameEngine

import json
import db_manager
db_manager.init_db()

class Lobby:
    def __init__(self, lobby_id: str):
        self.lobby_id = lobby_id
        self.clients = {}  # socket -> cipher[cite: 1]
        self.game_engine = GameEngine()
        self.game_running = False
        self.lock = threading.Lock()

    def start_game(self):
        self.game_running = True
        # מיקום התחלתי לשחקנים בלובי
        start_positions = [(0, 0), (7, 7), (0, 7), (7, 0)]
        for i, sock in enumerate(self.clients.keys()):
            r, c = start_positions[i % len(start_positions)]
            self.game_engine.add_player(id(sock), r, c)

        # הפעלת ה-Tick Thread הראשי של המשחק[cite: 1]
        threading.Thread(target=self.game_loop, daemon=True).start()

    def game_loop(self):
        """מנוע קצב הפעימות (Tick Rate: 20 פעימות בשנייה)[cite: 1]"""
        TICK_RATE = 1 / 20.0  # 50ms
        while self.game_running:
            start_time = time.time()

            with self.lock:
                self.game_engine.tick()  # חישוב לוגיקה[cite: 1]
                state = self.game_engine.serialize_state()  # אריזה[cite: 1]

            # שידור מצב המשחק (Broadcast)[cite: 1]
            payload = json.dumps(state).encode()
            self.broadcast(protocol.OP_GAME_STATE, payload)

            # שמירה על קצב קבוע
            elapsed = time.time() - start_time
            time.sleep(max(0, TICK_RATE - elapsed))


class Server:
    def __init__(self, host="0.0.0.0", port=3000):
        self.host = host
        self.port = port
        self.lobbies = {}
        self.lobbies_lock = threading.Lock()

    def start(self):
        server_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        server_sock.bind((self.host, self.port))
        server_sock.listen()

        print(f"[SERVER STARTED] Listening on {self.host}:{self.port}")

        while True:
            client_sock, addr = server_sock.accept()
            print(f"[NEW CONNECTION] Connected from {addr}")
            threading.Thread(target=self.handle_client, args=(client_sock,), daemon=True).start()

    def handle_client(self, client_sock):
        current_lobby = None
        cipher = None

        try:
            # --- שלב 2: Diffie-Hellman Handshake ---
            dh = security.DHHandshake()
            
            # נפרק ונארוז: [4Bytes Param Len] + [Param Bytes] + [Public Key Bytes]
            param_bytes = dh.get_parameters_bytes()
            pub_bytes = dh.get_public_bytes()
            init_payload = struct.pack("!I", len(param_bytes)) + param_bytes + pub_bytes
            
            protocol.send_msg(client_sock, protocol.OP_DH_HANDSHAKE, init_payload)
            
            opcode, client_pub_key = protocol.recv_msg(client_sock)
            if opcode != protocol.OP_DH_HANDSHAKE or not client_pub_key:
                print("[SECURITY ERROR] Handshake failed.")
                return
            
            session_key = dh.generate_session_key(client_pub_key)
            cipher = security.SymmetricCipher(session_key)
            print("[SECURITY] Encrypted session established successfully!")
                        # ----------------------------------------
            
            while True:
                opcode, payload = protocol.recv_msg(client_sock, cipher=cipher)
                if opcode is None:
                    break

                if opcode == protocol.OP_CREATE_LOBBY:
                    lobby_id = str(uuid.uuid4())[:6].upper()
                    new_lobby = Lobby(lobby_id)
                    new_lobby.add_client(client_sock, cipher)

                    with self.lobbies_lock:
                        self.lobbies[lobby_id] = new_lobby

                    current_lobby = new_lobby
                    print(f"[LOBBY CREATED] ID: {lobby_id}")
                    protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, f"CREATED:{lobby_id}".encode(), cipher=cipher)

                elif opcode == protocol.OP_JOIN_LOBBY:
                    lobby_id = payload.decode().strip()
                    with self.lobbies_lock:
                        target_lobby = self.lobbies.get(lobby_id)

                    if target_lobby:
                        target_lobby.add_client(client_sock, cipher)
                        current_lobby = target_lobby
                        print(f"[LOBBY JOIN] Client joined lobby {lobby_id}")
                        protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, f"JOINED:{lobby_id}".encode(), cipher=cipher)
                        current_lobby.broadcast(protocol.OP_CHAT_MSG, b"A new player joined (Encrypted)!", sender_socket=client_sock)
                    else:
                        protocol.send_msg(client_sock, protocol.OP_ERROR, b"Lobby not found!", cipher=cipher)

                elif opcode == protocol.OP_CHAT_MSG:
                    if current_lobby:
                        current_lobby.broadcast(protocol.OP_CHAT_MSG, payload, sender_socket=client_sock)
                # בתוך handle_client בתוך לולאת ה-Server:
                elif opcode == protocol.OP_REGISTER:
                    data = json.loads(payload.decode())
                    success, message = db_manager.register_user(data["username"], data["password"])
                    res = json.dumps({"success": success, "message": message}).encode()
                    protocol.send_msg(client_sock, protocol.OP_AUTH_RES, res, cipher=cipher)
                
                elif opcode == protocol.OP_LOGIN:
                    data = json.loads(payload.decode())
                    success, result = db_manager.authenticate_user(data["username"], data["password"])
                    if success:
                        res = json.dumps({"success": True, "user_data": result}).encode()
                    else:
                        res = json.dumps({"success": False, "message": result}).encode()
                    protocol.send_msg(client_sock, protocol.OP_AUTH_RES, res, cipher=cipher)
                
                elif opcode == protocol.OP_LEADERBOARD:
                    board = db_manager.get_leaderboard()
                    res = json.dumps(board).encode()
                    protocol.send_msg(client_sock, protocol.OP_LEADERBOARD, res, cipher=cipher)
                elif opcode == protocol.OP_PLAYER_MOVE:
                    direction = payload.decode()
                    current_lobby.game_engine.move_player(id(client_sock), direction)

                elif opcode == protocol.OP_PLAYER_SLAM:
                    direction = payload.decode()
                    current_lobby.game_engine.handle_slam(id(client_sock), direction)

        except Exception as e:
            print(f"[ERROR] Client error: {e}")
        finally:
            if current_lobby:
                current_lobby.remove_client(client_sock)
            client_sock.close()
            print("[CLIENT DISCONNECTED]")

if __name__ == "__main__":
    Server().start()