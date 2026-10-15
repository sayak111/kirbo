import json
import socket
import struct
import threading
import time

from cryptography.exceptions import InvalidTag

from lib import protocol
from lib import security


class GameClient:
    def __init__(self, host="10.32.143.15", port=3000, on_event=None):
        self.host = host
        self.port = port
        self.on_event = on_event or self._default_event_handler

        self.sock = None
        self.cipher = None
        self.connected = False
        self.running = False
        self.listen_thread = None
        self.udp_socket = None
        self.udp_thread = None
        self.udp_token = None
        self.udp_sequence = 0
        self.udp_lock = threading.Lock()
        self.pending_udp_actions = {}
        self.last_move_sent = 0.0

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

    def _start_udp(self, token):
        if self.udp_token == token and self.udp_socket is not None:
            return
        self._stop_udp()
        udp_socket = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        udp_socket.settimeout(0.25)
        self.udp_socket = udp_socket
        self.udp_token = token
        self.udp_sequence = 0
        self.last_move_sent = 0.0
        self.udp_thread = threading.Thread(
            target=self._udp_listen_loop,
            args=(udp_socket, token, self.cipher),
            daemon=True,
        )
        self.udp_thread.start()
        self._send_udp({"type": "hello"})

    def _send_udp(self, message, reliable=False):
        with self.udp_lock:
            udp_socket = self.udp_socket
            token = self.udp_token
            cipher = self.cipher
            if udp_socket is None or token is None or cipher is None:
                self._emit("error", {"message": "UDP gameplay channel is not ready."})
                return None

            self.udp_sequence += 1
            sequence = self.udp_sequence
            payload = dict(message)
            payload["sequence"] = sequence
            if reliable:
                payload["action_id"] = sequence
            packet = token.encode("ascii") + b"\0" + cipher.encrypt(
                json.dumps(payload).encode("utf-8")
            )
            if reliable:
                self.pending_udp_actions[sequence] = {
                    "packet": packet,
                    "sent_at": time.monotonic(),
                    "retries": 0,
                }

        try:
            udp_socket.sendto(packet, (self.host, self.port + 1))
        except OSError as exc:
            if reliable:
                with self.udp_lock:
                    self.pending_udp_actions.pop(sequence, None)
            self._emit("error", {"message": f"UDP send failed ({exc})"})
            return None
        return sequence

    def _udp_listen_loop(self, udp_socket, token, cipher):
        while self.running and self.udp_socket is udp_socket:
            try:
                packet, _ = udp_socket.recvfrom(65507)
            except socket.timeout:
                now = time.monotonic()
                with self.udp_lock:
                    retries = [
                        (sequence, item.copy())
                        for sequence, item in self.pending_udp_actions.items()
                        if now - item["sent_at"] >= 0.3
                    ]
                for sequence, item in retries:
                    if item["retries"] >= 5:
                        with self.udp_lock:
                            self.pending_udp_actions.pop(sequence, None)
                        self._emit("error", {"message": "UDP action was not acknowledged."})
                        continue
                    try:
                        udp_socket.sendto(item["packet"], (self.host, self.port + 1))
                    except OSError as exc:
                        self._emit("error", {"message": f"UDP retry failed ({exc})"})
                        continue
                    with self.udp_lock:
                        current = self.pending_udp_actions.get(sequence)
                        if current is not None:
                            current["sent_at"] = now
                            current["retries"] += 1
                continue
            except OSError:
                break

            try:
                received_token, encrypted = packet.split(b"\0", 1)
                if received_token.decode("ascii") != token:
                    continue
                message = json.loads(cipher.decrypt(encrypted).decode("utf-8"))
            except (InvalidTag, ValueError, TypeError, UnicodeDecodeError):
                continue

            if not isinstance(message, dict):
                continue
            if message.get("type") == "ready":
                self._emit("udp_ready", {"host": self.host, "port": self.port + 1})
            elif message.get("type") == "ack":
                with self.udp_lock:
                    self.pending_udp_actions.pop(message.get("action_id"), None)
            elif message.get("type") == "game_state":
                self._emit("game_state", message.get("state", {}))

    def _stop_udp(self):
        udp_socket = self.udp_socket
        self.udp_socket = None
        self.udp_token = None
        self.pending_udp_actions.clear()
        if udp_socket is not None:
            try:
                udp_socket.close()
            except OSError:
                pass

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
                        udp_token = parts[2] if len(parts) > 2 else None
                    else:
                        self.current_lobby_id = msg
                        self.is_host = False
                        self.player_id = None
                        udp_token = None

                    if udp_token:
                        self._start_udp(udp_token)

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

                elif opcode == protocol.OP_REPLAY_LIST:
                    self._emit("replay_list", self._safe_json_load(payload))

                elif opcode == protocol.OP_REPLAY_RESPONSE:
                    self._emit("replay_response", self._safe_json_load(payload))

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

    def move_player(self, direction=None, dx=None, dy=None, action=None, facing=None, x=None, y=None):
        if not self.connected:
            raise RuntimeError("Client is not connected.")

        if action is not None:
            if action != "slam":
                raise ValueError(f"Unsupported UDP gameplay action: {action}")
            self._send_udp({"type": "slam", "facing": facing or "RIGHT"}, reliable=True)
        elif x is not None and y is not None:
            now = time.monotonic()
            if now - self.last_move_sent < 0.05:
                return
            self.last_move_sent = now
            self._send_udp({"type": "move", "x": x, "y": y, "facing": facing})
        elif direction is not None:
            self._send_udp({"type": "move", "direction": direction.upper(), "facing": facing})
        else:
            self._send_udp({
                "type": "move",
                "dx": float(dx or 0.0),
                "dy": float(dy or 0.0),
                "facing": facing,
            })

    def send_chat(self, message):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        protocol.send_msg(self.sock, protocol.OP_CHAT_MSG, message.encode("utf-8"), cipher=self.cipher)

    def request_replays(self):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        protocol.send_msg(self.sock, protocol.OP_REPLAY_LIST, b"list", cipher=self.cipher)

    def request_replay(self, replay_id):
        if not self.connected:
            raise RuntimeError("Client is not connected.")
        protocol.send_msg(self.sock, protocol.OP_REPLAY_REQUEST, str(replay_id).encode("utf-8"), cipher=self.cipher)

    def disconnect(self):
        self.running = False
        self.connected = False
        self._stop_udp()

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
