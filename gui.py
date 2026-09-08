import socket
import struct
import json
import threading
import pygame
import protocol
import security

print("\n==================================================")
print("[DEBUG gui.py] Starting GUI script...")
print("==================================================")

# UI & State Configurations
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600

COLOR_BG = (24, 24, 27)
COLOR_CARD = (39, 39, 42)
COLOR_BORDER = (63, 63, 70)
COLOR_TEXT = (244, 244, 245)
COLOR_TEXT_MUTED = (161, 161, 170)
COLOR_ACCENT = (99, 102, 241)
COLOR_INPUT_BG = (24, 24, 27)

MODE_LOGIN = "LOGIN"
MODE_REGISTER = "REGISTER"
STATE_AUTH = "AUTH"
STATE_LOBBY = "LOBBY"

# Global Application Variables
running = True
current_state = STATE_AUTH
auth_mode = MODE_LOGIN
status_msg = "Connecting to server..."
logged_in_user = None

sock = None
cipher = None

input_user_text = ""
input_pass_text = ""
active_input = None

# Component Hitboxes
rect_tab_login = pygame.Rect(280, 140, 100, 30)
rect_tab_reg = pygame.Rect(420, 140, 100, 30)
rect_user_input = pygame.Rect(280, 220, 240, 40)
rect_pass_input = pygame.Rect(280, 290, 240, 40)
rect_btn_submit = pygame.Rect(280, 360, 240, 45)


def listen_to_server():
    global status_msg, current_state, logged_in_user, running
    print("[DEBUG gui.py] Starting background network listener thread...")
    while running:
        try:
            opcode, payload = protocol.recv_msg(sock, cipher=cipher)
            if opcode is None:
                status_msg = "Connection lost."
                break

            data = json.loads(payload.decode('utf-8'))

            if opcode == protocol.OP_REGISTER_RESP:
                status_msg = data.get("message", "Registration response received.")
                if data.get("success"):
                    status_msg = "Account created! You can now log in."
                    
            elif opcode == protocol.OP_LOGIN_RESP or opcode == protocol.OP_AUTH_RES:
                if data.get("success"):
                    logged_in_user = data.get("user", {})
                    user_name = logged_in_user.get('username', 'Player')
                    status_msg = f"Logged in as {user_name}"
                    
                    # Transition to Lobby Screen!
                    current_state = STATE_LOBBY
                else:
                    status_msg = data.get("message", "Login failed!")

        except Exception as e:
            print(f"[DEBUG gui.py EXCEPTION] Listen error: {e}")
            status_msg = "Network connection closed."
            break


def connect_to_server(host="127.0.0.1", port=3000):
    global sock, cipher, status_msg
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.connect((host, port))

        # Perform DH Exchange
        opcode, payload = protocol.recv_msg(sock)
        if opcode != protocol.OP_DH_HANDSHAKE or not payload:
            status_msg = "Handshake Failed!"
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
        status_msg = "Server offline."


def draw_ui(screen, font_title, font_body, font_sm):
    screen.fill(COLOR_BG)

    if current_state == STATE_AUTH:
        # Render Login Card Frame
        card_rect = pygame.Rect(230, 90, 340, 380)
        pygame.draw.rect(screen, COLOR_CARD, card_rect, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_rect, 1, border_radius=12)

        color_login = COLOR_ACCENT if auth_mode == MODE_LOGIN else COLOR_TEXT_MUTED
        color_reg = COLOR_ACCENT if auth_mode == MODE_REGISTER else COLOR_TEXT_MUTED

        screen.blit(font_title.render("Sign In", True, color_login), rect_tab_login)
        screen.blit(font_title.render("Register", True, color_reg), rect_tab_reg)

        # Render Text Input Boxes
        bg_user = COLOR_BORDER if active_input == 'user' else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_user, rect_user_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_user_input, 1, border_radius=6)
        txt_u = input_user_text if input_user_text else "Username..."
        screen.blit(font_body.render(txt_u, True, COLOR_TEXT if input_user_text else COLOR_TEXT_MUTED), (rect_user_input.x + 10, rect_user_input.y + 10))

        bg_pass = COLOR_BORDER if active_input == 'pass' else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_pass, rect_pass_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_pass_input, 1, border_radius=6)
        txt_p = "•" * len(input_pass_text) if input_pass_text else "Password..."
        screen.blit(font_body.render(txt_p, True, COLOR_TEXT if input_pass_text else COLOR_TEXT_MUTED), (rect_pass_input.x + 10, rect_pass_input.y + 10))

        # Render Submission Button
        btn_text = "LOG IN" if auth_mode == MODE_LOGIN else "CREATE ACCOUNT"
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_submit, border_radius=6)
        lbl_btn = font_body.render(btn_text, True, COLOR_TEXT)
        screen.blit(lbl_btn, lbl_btn.get_rect(center=rect_btn_submit.center))

    elif current_state == STATE_LOBBY:
        # Render Game Lobby View
        username = logged_in_user.get('username', 'Player') if logged_in_user else 'Player'
        score = logged_in_user.get('score', 1000) if logged_in_user else 1000

        welcome_lbl = font_title.render(f"GAME LOBBY - Welcome {username}!", True, COLOR_ACCENT)
        stats_lbl = font_body.render(f"ELO Rating: {score} PTS", True, COLOR_TEXT)
        
        screen.blit(welcome_lbl, (50, 50))
        screen.blit(stats_lbl, (50, 100))

        # Render Matchmaking / Action Buttons
        btn_find_match = pygame.Rect(50, 180, 200, 50)
        pygame.draw.rect(screen, COLOR_ACCENT, btn_find_match, border_radius=8)
        match_lbl = font_body.render("FIND MATCH", True, COLOR_TEXT)
        screen.blit(match_lbl, match_lbl.get_rect(center=btn_find_match.center))

    # Bottom Status Bar
    lbl_status = font_sm.render(f"Status: {status_msg}", True, COLOR_TEXT_MUTED)
    screen.blit(lbl_status, (20, WINDOW_HEIGHT - 30))

    pygame.display.flip()


def main():
    global running, auth_mode, active_input, input_user_text, input_pass_text, status_msg

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Checkerboard Chase Online")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("monospace", 20, bold=True)
    font_body = pygame.font.SysFont("monospace", 15)
    font_sm = pygame.font.SysFont("monospace", 13)

    threading.Thread(target=connect_to_server, daemon=True).start()

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
                        if not sock or not cipher:
                            status_msg = "Not connected to server!"
                        else:
                            payload = json.dumps({
                                "username": input_user_text,
                                "password": input_pass_text
                            }).encode('utf-8')

                            if auth_mode == MODE_LOGIN:
                                protocol.send_msg(sock, protocol.OP_LOGIN, payload, cipher=cipher)
                                status_msg = "Logging in..."
                            else:
                                protocol.send_msg(sock, protocol.OP_REGISTER, payload, cipher=cipher)
                                status_msg = "Registering..."

            elif event.type == pygame.KEYDOWN:
                if active_input == 'user':
                    if event.key == pygame.K_BACKSPACE:
                        input_user_text = input_user_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                        input_user_text += event.unicode
                elif active_input == 'pass':
                    if event.key == pygame.K_BACKSPACE:
                        input_pass_text = input_pass_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                        input_pass_text += event.unicode

        draw_ui(screen, font_title, font_body, font_sm)

    pygame.quit()

if __name__ == "__main__":
    main()