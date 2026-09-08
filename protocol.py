import struct

# Header Structure: 2 bytes (Unsigned Short) Opcode, 4 bytes (Unsigned Int) Length
HEADER_FORMAT = "!HI"
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# ---------------------------------------------------------
# OPCODES DEFINITIONS
# ---------------------------------------------------------
OP_DH_HANDSHAKE    = 0
OP_REGISTER        = 1
OP_REGISTER_RESP   = 2
OP_LOGIN           = 3
OP_LOGIN_RESP      = 4
OP_CREATE_LOBBY    = 5
OP_JOIN_LOBBY      = 6
OP_LOBBY_RESP      = 7
OP_CHAT_MSG        = 8
OP_ERROR           = 99

# Alias to prevent AttributeError if legacy code calls OP_AUTH_RES
OP_AUTH_RES        = OP_LOGIN_RESP


def send_msg(sock, opcode: int, payload_bytes: bytes, cipher=None):
    """Encrypts (if cipher provided) and sends header + payload over network socket."""
    if cipher and opcode != OP_DH_HANDSHAKE:
        payload_bytes = cipher.encrypt(payload_bytes)

    header = struct.pack(HEADER_FORMAT, opcode, len(payload_bytes))
    sock.sendall(header + payload_bytes)


def recv_exact(sock, length: int) -> bytes:
    """Helper to ensure exact number of bytes read from socket buffer."""
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(sock, cipher=None):
    """Reads header, retrieves payload bytes, and decrypts payload if cipher set."""
    header_bytes = recv_exact(sock, HEADER_SIZE)
    if not header_bytes:
        return None, None

    opcode, payload_len = struct.unpack(HEADER_FORMAT, header_bytes)

    payload = b""
    if payload_len > 0:
        payload = recv_exact(sock, payload_len)
        if payload is None:
            return None, None

    # Decrypt encrypted payloads (skip during initial DH exchange)
    if cipher and opcode != OP_DH_HANDSHAKE:
        try:
            payload = cipher.decrypt(payload)
        except Exception:
            return None, None

    return opcode, payload