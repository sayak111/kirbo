import struct

HEADER_FORMAT = "!HI"  # Opcode (2 bytes), Length (4 bytes)
HEADER_SIZE = struct.calcsize(HEADER_FORMAT)

# Opcodes
OP_DH_HANDSHAKE = 0  # חילוף מפתחות
OP_CREATE_LOBBY = 1
OP_JOIN_LOBBY = 2
OP_LOBBY_RESPONSE = 3
OP_CHAT_MSG = 4
# user controll
OP_REGISTER     = 5
OP_LOGIN        = 6
OP_LEADERBOARD  = 7
OP_AUTH_RES     = 8
# Opcodes קיימים: OP_DH_HANDSHAKE=0, OP_CREATE_LOBBY=1, OP_JOIN_LOBBY=2...
OP_PLAYER_MOVE  = 10  # הלקוח שולח בקשת תנועה (Up/Down/Left/Right)
OP_PLAYER_SLAM  = 11  # הלקוח שולח בקשת תקיפה (Direction)
OP_GAME_STATE   = 20  # השרת משדר את מצב הלוח והשחקנים לכולם
OP_START_GAME   = 21  # השרת מודיע על תחילת משחק
OP_ERROR = 99


def send_msg(sock, opcode: int, payload_bytes: bytes, cipher=None):
    """שליחת הודעה. אם נקבע cipher (הצפנה), ה-Payload מוצפן לפני השליחה"""
    if cipher and opcode != OP_DH_HANDSHAKE:
        payload_bytes = cipher.encrypt(payload_bytes)

    header = struct.pack(HEADER_FORMAT, opcode, len(payload_bytes))
    sock.sendall(header + payload_bytes)


def recv_exact(sock, length: int) -> bytes:
    buf = b""
    while len(buf) < length:
        chunk = sock.recv(length - len(buf))
        if not chunk:
            return None
        buf += chunk
    return buf


def recv_msg(sock, cipher=None):
    """קריאת הודעה. אם נקבע cipher, ה-Payload מפעונח אוטומטית"""
    header_bytes = recv_exact(sock, HEADER_SIZE)
    if not header_bytes:
        return None, None

    opcode, payload_len = struct.unpack(HEADER_FORMAT, header_bytes)

    payload = b""
    if payload_len > 0:
        payload = recv_exact(sock, payload_len)
        if payload is None:
            return None, None

    # פענוח המידע במידה וההצפנה פעילה וזהו אינו שלב ה-Handshake
    if cipher and opcode != OP_DH_HANDSHAKE:
        try:
            payload = cipher.decrypt(payload)
        except Exception:
            return None, None  # כישלון בפענוח (ניסיון הזרקה/חבלה)

    return opcode, payload