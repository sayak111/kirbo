import pygame

from client.client import GameClient
from client.game import ClientGameRenderer

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

MODE_LOGIN = "LOGIN"
MODE_REGISTER = "REGISTER"
STATE_AUTH = "AUTH"
STATE_LOBBY = "LOBBY"
STATE_GAME = "GAME"

running = True
current_state = STATE_AUTH
auth_mode = MODE_LOGIN
status_msg = "Connecting to server..."

user_data = {}
current_lobby_id = None
is_host = False

game_state = None
client = None
game_renderer = None

input_user_text = ""
input_pass_text = ""
input_lobby_text = ""
active_input = None

rect_tab_login = pygame.Rect(280, 140, 100, 30)
rect_tab_reg = pygame.Rect(420, 140, 100, 30)
rect_user_input = pygame.Rect(280, 220, 240, 40)
rect_pass_input = pygame.Rect(280, 290, 240, 40)
rect_btn_submit = pygame.Rect(280, 360, 240, 45)

rect_btn_create_lobby = pygame.Rect(60, 230, 280, 45)
rect_lobby_input = pygame.Rect(60, 330, 280, 40)
rect_btn_join_lobby = pygame.Rect(60, 385, 280, 45)


def on_client_event(event, payload):
    global current_state, status_msg, user_data, current_lobby_id, is_host, game_state

    if event == "connected":
        status_msg = "Connected securely!"

    elif event == "register_response":
        status_msg = payload.get("message", "Registration response received.")

    elif event == "login_response":
        data = payload or {}
        if data.get("success"):
            user_data.update(data.get("user", {"username": input_user_text}))
            status_msg = f"Welcome, {user_data.get('username', 'Player')}!"
            current_state = STATE_LOBBY
        else:
            status_msg = data.get("message", "Login failed!")

    elif event == "lobby_response":
        current_lobby_id = payload.get("lobby_id")
        is_host = payload.get("is_host", False)
        status_msg = payload.get("message", f"In Room #{current_lobby_id}")

    elif event == "chat_message":
        status_msg = f"Room Event: {payload.get('message', '')}"

    elif event == "game_state":
        game_state = payload
        current_state = STATE_GAME

    elif event == "error":
        status_msg = payload.get("message", "An error occurred.")

    elif event == "disconnected":
        status_msg = payload.get("message", "Disconnected.")


def draw_ui(screen, font_title, font_body, font_sm):
    screen.fill(COLOR_BG)

    if current_state == STATE_AUTH:
        card_rect = pygame.Rect(230, 90, 340, 380)
        pygame.draw.rect(screen, COLOR_CARD, card_rect, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_rect, 1, border_radius=12)

        color_login = COLOR_ACCENT if auth_mode == MODE_LOGIN else COLOR_TEXT_MUTED
        color_reg = COLOR_ACCENT if auth_mode == MODE_REGISTER else COLOR_TEXT_MUTED
        screen.blit(font_title.render("Sign In", True, color_login), rect_tab_login)
        screen.blit(font_title.render("Register", True, color_reg), rect_tab_reg)

        bg_user = COLOR_BORDER if active_input == "user" else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_user, rect_user_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_user_input, 1, border_radius=6)
        txt_u = input_user_text if input_user_text else "Username..."
        screen.blit(font_body.render(txt_u, True, COLOR_TEXT if input_user_text else COLOR_TEXT_MUTED), (rect_user_input.x + 10, rect_user_input.y + 10))

        bg_pass = COLOR_BORDER if active_input == "pass" else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_pass, rect_pass_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_pass_input, 1, border_radius=6)
        txt_p = "•" * len(input_pass_text) if input_pass_text else "Password..."
        screen.blit(font_body.render(txt_p, True, COLOR_TEXT if input_pass_text else COLOR_TEXT_MUTED), (rect_pass_input.x + 10, rect_pass_input.y + 10))

        btn_text = "LOG IN" if auth_mode == MODE_LOGIN else "CREATE ACCOUNT"
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_submit, border_radius=6)
        lbl_btn = font_body.render(btn_text, True, COLOR_TEXT)
        screen.blit(lbl_btn, lbl_btn.get_rect(center=rect_btn_submit.center))

    elif current_state == STATE_LOBBY:
        username = user_data.get('username', 'Player')
        screen.blit(font_title.render(f"Welcome, {username}", True, COLOR_TEXT), (40, 40))

        card_left = pygame.Rect(40, 100, 320, 430)
        pygame.draw.rect(screen, COLOR_CARD, card_left, border_radius=12)
        pygame.draw.rect(screen, COLOR_BORDER, card_left, 1, border_radius=12)

        screen.blit(font_title.render("Matchmaking", True, COLOR_TEXT), (60, 120))

        screen.blit(font_sm.render("Host a new game:", True, COLOR_TEXT_MUTED), (60, 205))
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_create_lobby, border_radius=6)
        lbl_create = font_body.render("+ CREATE LOBBY", True, COLOR_TEXT)
        screen.blit(lbl_create, lbl_create.get_rect(center=rect_btn_create_lobby.center))

        screen.blit(font_sm.render("Or enter room code:", True, COLOR_TEXT_MUTED), (60, 305))
        bg_lobby = COLOR_BORDER if active_input == "lobby" else COLOR_INPUT_BG
        pygame.draw.rect(screen, bg_lobby, rect_lobby_input, border_radius=6)
        pygame.draw.rect(screen, COLOR_BORDER, rect_lobby_input, 1, border_radius=6)
        txt_l = input_lobby_text if input_lobby_text else "ROOM CODE..."
        screen.blit(font_body.render(txt_l, True, COLOR_TEXT if input_lobby_text else COLOR_TEXT_MUTED), (rect_lobby_input.x + 10, rect_lobby_input.y + 10))

        pygame.draw.rect(screen, COLOR_BORDER, rect_btn_join_lobby, border_radius=6)
        lbl_join = font_body.render("JOIN ROOM", True, COLOR_TEXT)
        screen.blit(lbl_join, lbl_join.get_rect(center=rect_btn_join_lobby.center))

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

    elif current_state == STATE_GAME:
        game_renderer.draw(screen, game_state, font_title, font_body, font_sm)

    lbl_status = font_sm.render(f"Status: {status_msg}", True, COLOR_TEXT_MUTED)
    screen.blit(lbl_status, (20, WINDOW_HEIGHT - 30))

    pygame.display.flip()


def main():
    global running, auth_mode, active_input, input_user_text, input_pass_text, input_lobby_text, status_msg
    global client, game_renderer

    pygame.init()
    screen = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
    pygame.display.set_caption("Checkerboard Chase Online")
    clock = pygame.time.Clock()

    font_title = pygame.font.SysFont("monospace", 20, bold=True)
    font_body = pygame.font.SysFont("monospace", 15)
    font_sm = pygame.font.SysFont("monospace", 13)

    game_renderer = ClientGameRenderer()
    client = GameClient(on_event=on_client_event)
    client.connect()

    while running:
        clock.tick(60)

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break

            elif event.type == pygame.MOUSEBUTTONDOWN:
                pos = event.pos

                if current_state == STATE_AUTH:
                    if rect_tab_login.collidepoint(pos):
                        auth_mode = MODE_LOGIN
                    elif rect_tab_reg.collidepoint(pos):
                        auth_mode = MODE_REGISTER
                    elif rect_user_input.collidepoint(pos):
                        active_input = "user"
                    elif rect_pass_input.collidepoint(pos):
                        active_input = "pass"
                    else:
                        active_input = None

                    if rect_btn_submit.collidepoint(pos) and client.connected:
                        status_msg = "Sending request to server..."
                        if auth_mode == MODE_LOGIN:
                            client.login(input_user_text, input_pass_text)
                        else:
                            client.register(input_user_text, input_pass_text)

                elif current_state == STATE_LOBBY:
                    if rect_lobby_input.collidepoint(pos):
                        active_input = "lobby"
                    else:
                        active_input = None

                    if rect_btn_create_lobby.collidepoint(pos) and client.connected:
                        status_msg = "Requesting new lobby..."
                        client.create_lobby(user_data.get("username", "Player"))

                    elif rect_btn_join_lobby.collidepoint(pos) and client.connected and input_lobby_text.strip():
                        status_msg = f"Joining lobby #{input_lobby_text.strip().upper()}..."
                        client.join_lobby(input_lobby_text)

            elif event.type == pygame.KEYDOWN:
                if current_state == STATE_AUTH:
                    if active_input == "user":
                        if event.key == pygame.K_BACKSPACE:
                            input_user_text = input_user_text[:-1]
                        elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                            input_user_text += event.unicode
                    elif active_input == "pass":
                        if event.key == pygame.K_BACKSPACE:
                            input_pass_text = input_pass_text[:-1]
                        elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                            input_pass_text += event.unicode
                elif current_state == STATE_LOBBY and active_input == "lobby":
                    if event.key == pygame.K_BACKSPACE:
                        input_lobby_text = input_lobby_text[:-1]
                    elif event.key not in (pygame.K_RETURN, pygame.K_TAB):
                        input_lobby_text += event.unicode.upper()

        draw_ui(screen, font_title, font_body, font_sm)

    pygame.quit()


if __name__ == "__main__":
    main()
