import socket
import threading
import struct
import json
import uuid

from lib import protocol
from lib import security
from lib import db_manager


class Lobby:
    def __init__(self, lobby_id: str):
        self.lobby_id = lobby_id
        self.clients = {}
        self.lock = threading.Lock()

    def add_client(self, client_socket, cipher):
        with self.lock:
            self.clients[client_socket] = cipher

    def remove_client(self, client_socket):
        with self.lock:
            if client_socket in self.clients:
                del self.clients[client_socket]

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
                new_lobby.add_client(client_sock, cipher)

                with LOBBIES_LOCK:
                    LOBBIES[lobby_id] = new_lobby

                current_lobby = new_lobby
                print(f"[LOBBY CREATED] ID: {lobby_id} by {client_addr}")
                res_payload = f"CREATED:{lobby_id}".encode('utf-8')
                protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, res_payload, cipher=cipher)

            elif opcode == protocol.OP_JOIN_LOBBY:
                target_id = payload.decode('utf-8').strip().upper()
                with LOBBIES_LOCK:
                    target_lobby = LOBBIES.get(target_id)

                if target_lobby:
                    target_lobby.add_client(client_sock, cipher)
                    current_lobby = target_lobby
                    print(f"[LOBBY JOIN] {client_addr} joined lobby #{target_id}")
                    res_payload = f"JOINED:{target_id}".encode('utf-8')
                    protocol.send_msg(client_sock, protocol.OP_LOBBY_RESPONSE, res_payload, cipher=cipher)
                    current_lobby.broadcast(protocol.OP_CHAT_MSG, b"A new player joined the room!", sender_socket=client_sock)
                else:
                    protocol.send_msg(client_sock, protocol.OP_ERROR, b"Lobby not found!", cipher=cipher)

            elif opcode == protocol.OP_CHAT_MSG:
                if current_lobby:
                    current_lobby.broadcast(protocol.OP_CHAT_MSG, payload, sender_socket=client_sock)

    except Exception as e:
        print(f"[ERROR] Client handling error ({client_addr}): {e}")
    finally:
        if current_lobby:
            current_lobby.remove_client(client_sock)
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
