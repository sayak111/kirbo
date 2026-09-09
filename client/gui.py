import socket
import struct
import json
import threading
import pygame
from lib import protocol
from lib import security

# ---------------------------------------------------------
# 1. CONSTANTS & COLOR PALETTE
# ---------------------------------------------------------
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

COLOR_BG = (24, 24, 27)
COLOR_CARD = (39, 39, 42)
COLOR_BORDER = (63, 63, 70)
COLOR_TEXT = (244, 244, 245)
COLOR_TEXT_MUTED = (161, 161, 170)
COLOR_ACCENT = (99, 102, 241)
COLOR_INPUT_BG = (24, 24, 27)
COLOR_SUCCESS = (34, 197, 94)
COLOR_GAME_BG = (2, 17, 41)  # Hex #021129

MODE_LOGIN = "LOGIN"
MODE_REGISTER = "REGISTER"
STATE_AUTH = "AUTH"
STATE_LOBBY = "LOBBY"

# ---------------------------------------------------------
# 2. GLOBAL STATE VARIABLES
# ---------------------------------------------------------
running = True
current_state = STATE_AUTH
auth_mode = MODE_LOGIN
status_msg = "Connecting to server..."

sock = None
cipher = None
user_data = {}
current_lobby_id = None
is_host = False

# Input fields
input_user_text = ""
input_pass_text = ""
input_lobby_text = ""
active_input = None  # 'user', 'pass', 'lobby', or None

# Hitboxes - Auth Screen
rect_tab_login = pygame.Rect(280, 140, 100, 30)
rect_tab_reg = pygame.Rect(420, 140, 100, 30)
rect_user_input = pygame.Rect(280, 220, 240, 40)
rect_pass_input = pygame.Rect(280, 290, 240, 40)
rect_btn_submit = pygame.Rect(280, 360, 240, 45)

# Hitboxes - Lobby Matchmaking Panel
rect_btn_create_lobby = pygame.Rect(60, 230, 280, 45)
rect_lobby_input = pygame.Rect(60, 330, 280, 40)
rect_btn_join_lobby = pygame.Rect(60, 385, 280, 45)


# ---------------------------------------------------------
# 3. NETWORK WORKER THREADS
# ---------------------------------------------------------
def listen_to_server():
    global status_msg, sock, cipher, current_state, user_data, current_lobby_id, is_host
    while running:
        try:
            res = protocol.recv_msg(sock, cipher=cipher)
            if not res or res[0] is None:
                status_msg = "Server disconnected."
                break

            opcode, payload = res[0], res[1]

            # Authentication Responses
            if opcode == protocol.OP_REGISTER_RESP:
                data = json.loads(payload.decode('utf-8'))
                status_msg = data.get("message", "Registration response received.")

            elif opcode == protocol.OP_LOGIN_RESP:
                data = json.loads(payload.decode('utf-8'))
                if data.get("success"):
                    user_data = data.get("user", {"username": input_user_text})
                    status_msg = f"Welcome, {user_data.get('username', 'Player')}!"
                    current_state = STATE_LOBBY
                else:
                    status_msg = data.get("message", "Login failed!")

            # Matchmaking & Lobby Responses
            elif opcode == protocol.OP_LOBBY_RESPONSE:
                msg = payload.decode('utf-8')
                if ":" in msg:
                    action, lid = msg.split(":", 1)
                    current_lobby_id = lid
                    is_host = (action == "CREATED")
                else:
                    current_lobby_id = msg
                    is_host = True
                status_msg = f"In Room #{current_lobby_id}"

            elif opcode == protocol.OP_CHAT_MSG:
                status_msg = f"Room Event: {payload.decode('utf-8')}"

            elif opcode == protocol.OP_ERROR:
                status_msg = f"Error: {payload.decode('utf-8')}"
            elif opcode == protocol.OP_START_GAME:
                print("[DEBUG gui.py] Received OP_START_GAME! Switching state to STATE_GAME.")
                self.state = STATE_GAME

        except Exception as e:
            status_msg = f"Network thread error: {e}"
            break


def connect_to_server(host="127.0.0.1", port=3000):
    global sock, cipher, status_msg
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))

        opcode, payload = protocol.recv_msg(sock)
        if opcode != protocol.OP_DH_HANDSHAKE or not payload:
            status_msg = "Handshake Error: Missing setup payload."
            return

        param_len = struct.unpack("!I", payload[:4])[0]
        param_bytes = payload[4 : 4 + param_len]
        server_pub_bytes = payload[4 + param_len :]

        dh_params = security.DHHandshake.load_parameters_bytes(param_bytes)
        client_dh = security.DHHandshake(parameters=dh_params)

        protocol.send_msg(sock, protocol.OP_DH_HANDSHAKE, client_dh.get_public_bytes())
        session_key = client_dh.generate_session_key(server_pub_bytes)
        cipher = security.SymmetricCipher(session_key)

        status_msg = "Connected securely!"
        threading.Thread(target=listen_to_server, daemon=True).start()

    except Exception as e:
        status_msg = f"Server offline or connection error ({e})"


# ---------------------------------------------------------
# 4. RENDERING PROCEDURES
# ---------------------------------------------------------
def draw_ui(screen, font_title, font_body, font_sm):
    screen.fill(COLOR_BG)

    if current_state == STATE_AUTH:
        # Main Auth Card Container
        card_rect = pygame.Rect(230, 90, 340, 380)
        pygame.draw.rect(screen, COLOR_CARD, card_rect, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_rect, 1, border_radius=12)

        # Tab Switching
        color_login = COLOR_ACCENT if auth_mode == MODE_LOGIN else COLOR_TEXT_MUTED
        color_reg = COLOR_ACCENT if auth_mode == MODE_REGISTER else COLOR_TEXT_MUTED
        screen.blit(font_title.render("Sign In", True, color_login), rect_tab_login)
        screen.blit(font_title.render("Register", True, color_reg), rect_tab_reg)

        # Username Input Field
        bg_user = COLOR_BORDER if active_input == 'user' else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_user, rect_user_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_user_input, 1, border_radius=6)
        txt_u = input_user_text if input_user_text else "Username..."
        screen.blit(font_body.render(txt_u, True, COLOR_TEXT if input_user_text else COLOR_TEXT_MUTED), (rect_user_input.x + 10, rect_user_input.y + 10))

        # Password Input Field
        bg_pass = COLOR_BORDER if active_input == 'pass' else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_pass, rect_pass_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_pass_input, 1, border_radius=6)
        txt_p = "•" * len(input_pass_text) if input_pass_text else "Password..."
        screen.blit(font_body.render(txt_p, True, COLOR_TEXT if input_pass_text else COLOR_TEXT_MUTED), (rect_pass_input.x + 10, rect_pass_input.y + 10))

        # Action Submit Button
        btn_text = "LOG IN" if auth_mode == MODE_LOGIN else "CREATE ACCOUNT"
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_submit, border_radius=6)
        lbl_btn = font_body.render(btn_text, True, COLOR_TEXT)
        screen.blit(lbl_btn, lbl_btn.get_rect(center=rect_btn_submit.center))

    elif current_state == STATE_LOBBY:
        username = user_data.get('username', 'Player')
        screen.blit(font_title.render(f"Welcome, {username}", True, COLOR_TEXT), (40, 40))

        # Left Card: Actions Panel
        card_left = pygame.Rect(40, 100, 320, 430)
        pygame.draw.rect(screen, COLOR_CARD, card_left, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_left, 1, border_radius=12)

        screen.blit(font_title.render("Matchmaking", True, COLOR_TEXT), (60, 120))

        # 1. Create Lobby Controls
        screen.blit(font_sm.render("Host a new game:", True, COLOR_TEXT_MUTED), (60, 205))
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_create_lobby, border_radius=6)
        lbl_create = font_body.render("+ CREATE LOBBY", True, COLOR_TEXT)
        screen.blit(lbl_create, lbl_create.get_rect(center=rect_btn_create_lobby.center))

        # 2. Join Lobby Controls
        screen.blit(font_sm.render("Or enter room code:", True, COLOR_TEXT_MUTED), (60, 305))
        bg_lobby = COLOR_BORDER if active_input == 'lobby' else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_lobby, rect_lobby_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_lobby_input, 1, border_radius=6)

        txt_l = input_lobby_text if input_lobby_text else "ROOM CODE..."
        screen.blit(font_body.render(txt_l, True, COLOR_TEXT if input_lobby_text else COLOR_TEXT_MUTED), (rect_lobby_input.x + 10, rect_lobby_input.y + 10))

        pygame.draw.rect(screen, COLOR_BORDER, rect_btn_join_lobby, border_radius=6)
        lbl_join = font_body.render("JOIN ROOM", True, COLOR_TEXT)
        screen.blit(lbl_join, lbl_join.get_rect(center=rect_btn_join_lobby.center))

        # Right Card: Active Room Panel
        card_right = pygame.Rect(390, 100, 370, 430)
        pygame.draw.rect(screen, COLOR_CARD, card_right, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_right, 1, border_radius=12)

        if not current_lobby_id:
            lbl_empty = font_body.render("No Active Room", True, COLOR_TEXT_MUTED)
            screen.blit(lbl_empty, lbl_empty.get_rect(center=card_right.center))
        else:
            screen.blit(font_title.render(f"Room #{current_lobby_id}", True, COLOR_TEXT), (420, 130))
            role_str = "You are Room Host" if is_host else "Connected as Guest"
            screen.blit(font_sm.render(role_str, True, COLOR_ACCENT), (420, 165))
            screen.blit(font_body.render("Status: Waiting for players...", True, COLOR_SUCCESS), (420, 210))

    # Bottom Status Bar
    lbl_status = font_sm.render(f"Status: {status_msg}", True, COLOR_TEXT_MUTED)
    screen.blit(lbl_status, (20, WINDOW_HEIGHT - 30))

    pygame.display.flip()


def draw_game_screen(self):
    """Renders the game state background."""
    self.screen.fill(COLOR_GAME_BG)

    # Simple indicator text to confirm transition
    canvas_lbl = self.font_main.render("--- GAME CANVAS ACTIVE ---", True, COLOR_ACCENT)
    self.screen.blit(canvas_lbl, canvas_lbl.get_rect(center=(400, 300)))


# ---------------------------------------------------------
# 5. MAIN EVENT LOOP
# ---------------------------------------------------------
def main():
    global running, auth_mode, active_input, input_user_text, input_pass_text, input_lobby_text, status_msg

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Checkerboard Chase Online")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("monospace", 20, bold=True)
    font_body = pygame.font.SysFont("monospace", 15)
    font_sm = pygame.font.SysFont("monospace", 13)

    # Launch non-blocking connection thread
    threading.Thread(target=connect_to_server, args=("127.0.0.1", 3000), daemon=True).start()

    while running:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos

                if current_state == STATE_AUTH:
                    if rect_tab_login.collidepoint(pos):
                        auth_mode = MODE_LOGIN
                    elif rect_tab_reg.collidepoint(pos):
                        auth_mode = MODE_REGISTER
                    elif rect_user_input.collidepoint(pos):
                        active_input = 'user'
                    elif rect_pass_input.collidepoint(pos):
                        active_input = 'pass'
                    else:
                        active_input = None

                    if rect_btn_submit.collidepoint(pos):
                        if sock and cipher:
                            payload = json.dumps({"username": input_user_text, "password": input_pass_text}).encode('utf-8')
                            op = protocol.OP_LOGIN if auth_mode == MODE_LOGIN else protocol.OP_REGISTER
                            protocol.send_msg(sock, op, payload, cipher=cipher)
                            status_msg = "Sending request to server..."

                elif current_state == STATE_LOBBY:
                    if rect_lobby_input.collidepoint(pos):
                        active_input = 'lobby'
                    else:
                        active_input = None

                    # Action 1: Create Lobby
                    if rect_btn_create_lobby.collidepoint(pos):
                        if sock and cipher:
                            status_msg = "Requesting new lobby..."
                            payload = json.dumps({"username": user_data.get("username", "Player")}).encode('utf-8')
                            protocol.send_msg(sock, protocol.OP_CREATE_LOBBY, payload, cipher=cipher)

                    # Action 2: Join Lobby
                    elif rect_btn_join_lobby.collidepoint(pos):
                        if sock and cipher and input_lobby_text.strip():
                            status_msg = f"Joining lobby #{input_lobby_text.strip().upper()}..."
                            protocol.send_msg(sock, protocol.OP_JOIN_LOBBY, input_lobby_text.strip().upper().encode('utf-8'), cipher=cipher)

            elif event.type == pygame.KEYDOWN:
                if active_input == 'user':
                    if event.key == pygame.K_BACKSPACE: input_user_text = input_user_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB): input_user_text += event.unicode
                elif active_input == 'pass':
                    if event.key == pygame.K_BACKSPACE: input_pass_text = input_pass_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB): input_pass_text += event.unicode
                elif active_input == 'lobby':
                    if event.key == pygame.K_BACKSPACE: input_lobby_text = input_lobby_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB): input_lobby_text += event.unicode.upper()

        draw_ui(screen, font_title, font_body, font_sm)

    pygame.quit()


if __name__ == "__main__":
    main()
