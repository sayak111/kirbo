import pygame

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

rect_tab_login = pygame.Rect(280, 140, 100, 30)
rect_tab_reg = pygame.Rect(420, 140, 100, 30)
rect_user_input = pygame.Rect(280, 220, 240, 40)
rect_pass_input = pygame.Rect(280, 290, 240, 40)
rect_btn_submit = pygame.Rect(280, 360, 240, 45)
rect_btn_create_lobby = pygame.Rect(60, 230, 280, 45)
rect_lobby_input = pygame.Rect(60, 330, 280, 40)
rect_btn_join_lobby = pygame.Rect(60, 385, 280, 45)
rect_btn_start_game = pygame.Rect(420, 245, 230, 45)


def draw(screen, state, fonts):
    font_title, font_body, font_sm = fonts
    screen.fill(COLOR_BG)
    if state["screen"] == STATE_AUTH:
        _draw_auth(screen, state, font_title, font_body)
    else:
        _draw_lobby(screen, state, font_title, font_body, font_sm)

    if state["result_banner_text"] and pygame.time.get_ticks() < state["result_banner_until"]:
        banner = font_title.render(
            state["result_banner_text"],
            True,
            COLOR_SUCCESS if state["result_banner_text"] == "YOU WON!" else COLOR_TEXT,
        )
        screen.blit(banner, banner.get_rect(center=(WINDOW_WIDTH // 2, 70)))

    status = font_sm.render(f"Status: {state['status_msg']}", True, COLOR_TEXT_MUTED)
    screen.blit(status, (20, WINDOW_HEIGHT - 30))
    pygame.display.flip()


def _draw_auth(screen, state, font_title, font_body):
    card_rect = pygame.Rect(230, 90, 340, 380)
    pygame.draw.rect(screen, COLOR_CARD, card_rect, border_radius=12)
    pygame.draw.rect(screen, COLOR_BORDER, card_rect, 1, border_radius=12)

    login_color = COLOR_ACCENT if state["auth_mode"] == MODE_LOGIN else COLOR_TEXT_MUTED
    register_color = COLOR_ACCENT if state["auth_mode"] == MODE_REGISTER else COLOR_TEXT_MUTED
    screen.blit(font_title.render("Sign In", True, login_color), rect_tab_login)
    screen.blit(font_title.render("Register", True, register_color), rect_tab_reg)

    user_active = state["active_input"] == "user"
    pygame.draw.rect(screen, COLOR_BORDER if user_active else COLOR_INPUT_BG, rect_user_input, border_radius=6)
    pygame.draw.rect(screen, COLOR_BORDER, rect_user_input, 1, border_radius=6)
    username = state["input_user_text"] or "Username..."
    screen.blit(font_body.render(username, True, COLOR_TEXT if state["input_user_text"] else COLOR_TEXT_MUTED), (290, 230))

    pass_active = state["active_input"] == "pass"
    pygame.draw.rect(screen, COLOR_BORDER if pass_active else COLOR_INPUT_BG, rect_pass_input, border_radius=6)
    pygame.draw.rect(screen, COLOR_BORDER, rect_pass_input, 1, border_radius=6)
    password = "*" * len(state["input_pass_text"]) if state["input_pass_text"] else "Password..."
    screen.blit(font_body.render(password, True, COLOR_TEXT if state["input_pass_text"] else COLOR_TEXT_MUTED), (290, 300))

    button_text = "LOG IN" if state["auth_mode"] == MODE_LOGIN else "CREATE ACCOUNT"
    pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_submit, border_radius=6)
    label = font_body.render(button_text, True, COLOR_TEXT)
    screen.blit(label, label.get_rect(center=rect_btn_submit.center))


def _draw_lobby(screen, state, font_title, font_body, font_sm):
    user_data = state["user_data"]
    username = user_data.get("username", "Player")
    screen.blit(font_title.render(f"Welcome, {username}", True, COLOR_TEXT), (40, 40))

    card_left = pygame.Rect(40, 100, 320, 430)
    pygame.draw.rect(screen, COLOR_CARD, card_left, border_radius=12)
    pygame.draw.rect(screen, COLOR_BORDER, card_left, 1, border_radius=12)
    screen.blit(font_title.render("Matchmaking", True, COLOR_TEXT), (60, 120))

    screen.blit(font_sm.render("Your Stats", True, COLOR_TEXT_MUTED), (60, 158))
    screen.blit(font_sm.render(f"Score: {user_data.get('score', 0)}", True, COLOR_TEXT), (60, 180))
    screen.blit(font_sm.render(f"Wins: {user_data.get('wins', 0)}", True, COLOR_TEXT), (160, 180))
    screen.blit(font_sm.render(f"Losses: {user_data.get('losses', 0)}", True, COLOR_TEXT), (245, 180))

    screen.blit(font_sm.render("Host a new game:", True, COLOR_TEXT_MUTED), (60, 205))
    pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_create_lobby, border_radius=6)
    label = font_body.render("+ CREATE LOBBY", True, COLOR_TEXT)
    screen.blit(label, label.get_rect(center=rect_btn_create_lobby.center))

    screen.blit(font_sm.render("Or enter room code:", True, COLOR_TEXT_MUTED), (60, 305))
    lobby_active = state["active_input"] == "lobby"
    pygame.draw.rect(screen, COLOR_BORDER if lobby_active else COLOR_INPUT_BG, rect_lobby_input, border_radius=6)
    pygame.draw.rect(screen, COLOR_BORDER, rect_lobby_input, 1, border_radius=6)
    room_code = state["input_lobby_text"] or "ROOM CODE..."
    screen.blit(font_body.render(room_code, True, COLOR_TEXT if state["input_lobby_text"] else COLOR_TEXT_MUTED), (70, 340))

    pygame.draw.rect(screen, COLOR_BORDER, rect_btn_join_lobby, border_radius=6)
    label = font_body.render("JOIN ROOM", True, COLOR_TEXT)
    screen.blit(label, label.get_rect(center=rect_btn_join_lobby.center))

    card_right = pygame.Rect(390, 100, 370, 430)
    pygame.draw.rect(screen, COLOR_CARD, card_right, border_radius=12)
    pygame.draw.rect(screen, COLOR_BORDER, card_right, 1, border_radius=12)
    if not state["current_lobby_id"]:
        label = font_body.render("No Active Room", True, COLOR_TEXT_MUTED)
        screen.blit(label, label.get_rect(center=card_right.center))
        return

    screen.blit(font_title.render(f"Room #{state['current_lobby_id']}", True, COLOR_TEXT), (420, 130))
    role = "You are Room Host" if state["is_host"] else "Connected as Guest"
    screen.blit(font_sm.render(role, True, COLOR_ACCENT), (420, 165))
    screen.blit(font_body.render("Status: Waiting for players...", True, COLOR_SUCCESS), (420, 210))
    if state["is_host"]:
        pygame.draw.rect(screen, COLOR_ACCENT, rect_btn_start_game, border_radius=6)
        label = font_body.render("START GAME", True, COLOR_TEXT)
        screen.blit(label, label.get_rect(center=rect_btn_start_game.center))
