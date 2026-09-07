import socket
import struct
import threading
import uuid
import protocol
import security

class Lobby:
    def __init__(self, lobby_id: str):
        self.lobby_id = lobby_id
        self.clients = {}  # dict of socket -> cipher
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

        except Exception as e:
            print(f"[ERROR] Client error: {e}")
        finally:
            if current_lobby:
                current_lobby.remove_client(client_sock)
            client_sock.close()
            print("[CLIENT DISCONNECTED]")

if __name__ == "__main__":
    Server().start()