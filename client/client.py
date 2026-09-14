import json
import socket
import struct
import threading

from lib import protocol
from lib import security


class GameClient:
    def __init__(self, host="127.0.0.1", port=3000, on_event=None):
        self.host = host
        self.port = port
        self.on_event = on_event or self._default_event_handler

        self.sock = None
        self.cipher = None
        self.connected = False
        self.running = False
        self.listen_thread = None

        self.user_data = {}
        self.current_lobby_id = None
        self.is_host = False
        self.player_id = None

    def _default_event_handler(self, event, payload):
        print(f"[client:{event}] {payload}")

    def _emit(self, event, payload=None):
        try:
            self.on_event(event, payload)
        except Exception as exc:
            print(f"[client:callback_error] {exc}")

    def connect(self):
        if self.connected:
            return True

        try:
            self.sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.sock.connect((self.host, self.port))
            self.running = True

            opcode, init_payload = protocol.recv_msg(self.sock)
            if opcode != protocol.OP_DH_HANDSHAKE or not init_payload:
                self._emit("error", {"message": "Handshake Error: Missing setup payload."})
                self.disconnect()
                return False

            param_len = struct.unpack("!I", init_payload[:4])[0]
            param_bytes = init_payload[4 : 4 + param_len]
            server_pub_bytes = init_payload[4 + param_len :]

            server_params = security.DHHandshake.load_parameters_bytes(param_bytes)
            dh = security.DHHandshake(parameters=server_params)

            protocol.send_msg(self.sock, protocol.OP_DH_HANDSHAKE, dh.get_public_bytes())
            session_key = dh.generate_session_key(server_pub_bytes)
            self.cipher = security.SymmetricCipher(session_key)

            self.connected = True
            self.listen_thread = threading.Thread(target=self._listen_loop, daemon=True)
            self.listen_thread.start()
            self._emit("connected", {"host": self.host, "port": self.port})
            return True

        except Exception as exc:
            self._emit("error", {"message": f"Server offline or connection error ({exc})"})
            self.disconnect()
            return False

    def _listen_loop(self):
        while self.running:
            try:
                res = protocol.recv_msg(self.sock, cipher=self.cipher)
                if not res or res[0] is None:
                    self._emit("disconnected", {"message": "Server disconnected."})
                    break

                opcode, payload = res

                if opcode == protocol.OP_REGISTER_RESP:
                    data = self._safe_json_load(payload)
                    self._emit("register_response", data)

                elif opcode == protocol.OP_LOGIN_RESP:
                    data = self._safe_json_load(payload)
                    if data.get("success"):
                        self.user_data = data.get("user", {"username": "Player"})
                        self._emit("login_response", {"success": True, "user": self.user_data})
                    else:
                        self._emit("login_response", {"success": False, "message": data.get("message", "Login failed!")})

                elif opcode == protocol.OP_LOBBY_RESPONSE:
                    msg = payload.decode("utf-8", errors="ignore")
                    if ":" in msg:
                        action, remainder = msg.split(":", 1)
                        parts = remainder.split(":")
                        self.current_lobby_id = parts[0]
                        self.is_host = action == "CREATED"
                        self.player_id = parts[1] if len(parts) > 1 else None
                    else:
                        self.current_lobby_id = msg
                        self.is_host = False
                        self.player_id = None

                    self._emit("lobby_response", {
                        "lobby_id": self.current_lobby_id,
                        "is_host": self.is_host,
                        "player_id": self.player_id,
                        "message": msg,
                    })

                elif opcode == protocol.OP_CHAT_MSG:
                    self._emit("chat_message", {"message": payload.decode("utf-8", errors="ignore")})

                elif opcode == protocol.OP_MATCH_START:
                    self._emit("match_started", {"message": payload.decode("utf-8", errors="ignore")})

                elif opcode == protocol.OP_MATCH_END:
                    data = self._safe_json_load(payload)
                    self._emit("match_end", data)

                elif opcode == protocol.OP_GAME_STATE:
                    try:
                        data = json.loads(payload.decode("utf-8"))
                    except Exception:
                        data = {"message": payload.decode("utf-8", errors="ignore")}
                    self._emit("game_state", data)

                elif opcode == protocol.OP_ERROR:
                    self._emit("error", {"message": payload.decode("utf-8", errors="ignore")})

                else:
                    self._emit("raw_message", {"opcode": opcode, "payload": payload})

            except Exception as exc:
                self._emit("error", {"message": f"Network thread error: {exc}"})
                break

        self.disconnect()

    def _safe_json_load(self, payload):
        try:
            return json.loads(payload.decode("utf-8"))
        except Exception:
            return {"message": payload.decode("utf-8", errors="ignore")}

    def register(self, username, password):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        protocol.send_msg(self.sock, protocol.OP_REGISTER, payload, cipher=self.cipher)

    def login(self, username, password):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        payload = json.dumps({"username": username, "password": password}).encode("utf-8")
        protocol.send_msg(self.sock, protocol.OP_LOGIN, payload, cipher=self.cipher)

    def create_lobby(self, username=None):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        payload = json.dumps({"username": username or self.user_data.get("username", "Player")}).encode("utf-8")
        protocol.send_msg(self.sock, protocol.OP_CREATE_LOBBY, payload, cipher=self.cipher)

    def join_lobby(self, lobby_id):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        payload = lobby_id.strip().upper().encode("utf-8")
        protocol.send_msg(self.sock, protocol.OP_JOIN_LOBBY, payload, cipher=self.cipher)

    def start_match(self):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        protocol.send_msg(self.sock, protocol.OP_START_MATCH, b"start", cipher=self.cipher)

    def move_player(self, direction=None, dx=None, dy=None, action=None, facing=None):
        if not self.connected:
            raise RuntimeError("Client is not connected.")

        if action is not None:
            payload = json.dumps({
                "action": action,
                "facing": facing or "RIGHT",
            }).encode("utf-8")
        elif direction is not None:
            payload = direction.encode("utf-8")
        else:
            payload = json.dumps({
                "dx": float(dx or 0.0),
                "dy": float(dy or 0.0),
            }).encode("utf-8")

        protocol.send_msg(self.sock, protocol.OP_MOVE_PLAYER, payload, cipher=self.cipher)

    def send_chat(self, message):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        protocol.send_msg(self.sock, protocol.OP_CHAT_MSG, message.encode("utf-8"), cipher=self.cipher)

    def disconnect(self):
        self.running = False
        self.connected = False

        if self.sock is not None:
            try:
                self.sock.shutdown(socket.SHUT_RDWR)
            except Exception:
                pass
            finally:
                self.sock.close()
                self.sock = None

        self.cipher = None
        self._emit("disconnected", {"message": "Connection closed."})


if __name__ == "__main__":
    def on_event(event, payload):
        print(f"Event: {event} | Payload: {payload}")

    client = GameClient(on_event=on_event)
    if client.connect():
        print("Connected. Use GameClient methods to register/login/create lobby/join lobby/send chat.")
