import pygame

from client.client import GameClient
from client.game_renderer import ClientGameRenderer
from client.game_screen import draw as draw_game, update_player
from client.lobby_screen import (
    MODE_LOGIN,
    MODE_REGISTER,
    STATE_AUTH,
    STATE_LOBBY,
    draw as draw_lobby,
    rect_btn_create_lobby,
    rect_btn_join_lobby,
    rect_btn_replay,
    rect_btn_start_game,
    rect_btn_submit,
    rect_lobby_input,
    rect_pass_input,
    rect_tab_login,
    rect_tab_reg,
    rect_user_input,
)

STATE_GAME = "GAME"
STATE_REPLAY = "REPLAY"
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
local_player_id = None
countdown_text = None
countdown_until = 0
result_banner_text = None
result_banner_until = 0
input_user_text = ""
input_pass_text = ""
input_lobby_text = ""
active_input = None
replay_frames = []
replay_index = 0
replay_started_at = 0
replay_paused = False


def on_client_event(event, payload):
    global current_state, status_msg, user_data, current_lobby_id, is_host
    global game_state, local_player_id, countdown_text, countdown_until
    global result_banner_text, result_banner_until
    global replay_frames, replay_index, replay_started_at, replay_paused

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
        local_player_id = payload.get("player_id")
        status_msg = payload.get("message", f"In Room #{current_lobby_id}")
    elif event == "chat_message":
        status_msg = f"Room Event: {payload.get('message', '')}"
    elif event == "match_started":
        countdown_text = payload.get("message", "GO")
        countdown_until = pygame.time.get_ticks() + 900
        status_msg = payload.get("message", "Match starting...")
        current_state = STATE_GAME
    elif event == "match_end":
        countdown_text = None
        countdown_until = 0
        game_state = None
        current_state = STATE_LOBBY
        results = payload.get("results", []) if isinstance(payload, dict) else []
        player_result = next((item for item in results if item.get("player_id") == local_player_id), None)
        if player_result is None and user_data.get("username"):
            player_result = next(
                (item for item in results if item.get("username") == user_data["username"]),
                None,
            )
        result_banner_text = "YOU WON!" if player_result and player_result.get("won") else "YOU LOST!"
        result_banner_until = pygame.time.get_ticks() + 1600
        status_msg = payload.get("message", "Match ended.")
        if client and client.connected:
            client.request_replays()
    elif event == "game_state":
        game_state = payload
        current_state = STATE_GAME
    elif event == "replay_list":
        if payload:
            status_msg = f"{len(payload)} replay(s) available."
            client.request_replay(payload[0].get("id"))
        else:
            status_msg = "No saved replays yet."
    elif event == "replay_response":
        replay_frames = payload.get("frames", []) if isinstance(payload, dict) else []
        replay_index = 0
        replay_paused = False
        replay_started_at = pygame.time.get_ticks()
        if replay_frames:
            game_state = replay_frames[0].get("game_state")
            current_state = STATE_REPLAY
            status_msg = "Replay playing. SPACE pauses, R restarts, ESC exits."
        else:
            status_msg = "Replay has no saved frames."
    elif event == "error":
        status_msg = payload.get("message", "An error occurred.")
    elif event == "disconnected":
        status_msg = payload.get("message", "Disconnected.")


def _screen_state():
    return {
        "screen": current_state,
        "auth_mode": auth_mode,
        "status_msg": status_msg,
        "user_data": user_data,
        "current_lobby_id": current_lobby_id,
        "is_host": is_host,
        "active_input": active_input,
        "input_user_text": input_user_text,
        "input_pass_text": input_pass_text,
        "input_lobby_text": input_lobby_text,
        "result_banner_text": result_banner_text,
        "result_banner_until": result_banner_until,
    }


def _handle_mouse(pos):
    global auth_mode, active_input, status_msg

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
        active_input = "lobby" if rect_lobby_input.collidepoint(pos) else None
        if rect_btn_create_lobby.collidepoint(pos) and client.connected:
            status_msg = "Requesting new lobby..."
            client.create_lobby(user_data.get("username", "Player"))
        elif rect_btn_join_lobby.collidepoint(pos) and client.connected and input_lobby_text.strip():
            status_msg = f"Joining lobby #{input_lobby_text.strip().upper()}..."
            client.join_lobby(input_lobby_text)
        elif rect_btn_start_game.collidepoint(pos) and client.connected and is_host:
            status_msg = "Starting match..."
            client.start_match()
        elif rect_btn_replay.collidepoint(pos) and client.connected:
            status_msg = "Loading latest replay..."
            client.request_replays()


def _handle_key(event):
    global input_user_text, input_pass_text, input_lobby_text
    global current_state, active_input, game_state, status_msg
    global replay_paused, replay_index, replay_started_at

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
    elif current_state == STATE_GAME and event.key == pygame.K_SPACE:
        players = game_state.get("players", {}) if game_state else {}
        player = players.get(local_player_id) if local_player_id else None
        if not isinstance(player, dict) and players:
            player = next(iter(players.values()))
        if isinstance(player, dict):
            client.move_player(action="slam", facing=player.get("facing", "RIGHT"))
    elif current_state == STATE_REPLAY:
        if event.key == pygame.K_SPACE:
            replay_paused = not replay_paused
        elif event.key == pygame.K_r and replay_frames:
            replay_index = 0
            replay_started_at = pygame.time.get_ticks()
            game_state = replay_frames[0].get("game_state")
        elif event.key == pygame.K_ESCAPE:
            current_state = STATE_LOBBY
            status_msg = "Replay closed."


def main():
    global running, client, game_renderer, countdown_text, countdown_until
    global result_banner_text, result_banner_until, game_state
    global replay_index, replay_started_at

    pygame.init()
    screen = pygame.display.set_mode((800, 600))
    pygame.display.set_caption("Checkerboard Chase Online")
    clock = pygame.time.Clock()
    fonts = (
        pygame.font.SysFont("monospace", 20, bold=True),
        pygame.font.SysFont("monospace", 15),
        pygame.font.SysFont("monospace", 13),
    )

    game_renderer = ClientGameRenderer()
    client = GameClient(on_event=on_client_event)
    client.connect()

    while running:
        dt = clock.tick(60) / 1000.0
        now_ms = pygame.time.get_ticks()
        if countdown_text and now_ms >= countdown_until:
            countdown_text = None
            countdown_until = 0
        if result_banner_text and now_ms >= result_banner_until:
            result_banner_text = None
            result_banner_until = 0

        for event in pygame.event.get():
            if event.type == pygame.QUIT:
                running = False
                break
            if event.type == pygame.MOUSEBUTTONDOWN:
                _handle_mouse(event.pos)
            elif event.type == pygame.KEYDOWN:
                _handle_key(event)

        if current_state == STATE_GAME:
            update_player(game_state, local_player_id, client, dt)
            draw_game(screen, game_state, game_renderer, fonts, countdown_text, result_banner_text, result_banner_until, status_msg)
        elif current_state == STATE_REPLAY:
            if replay_frames and not replay_paused:
                elapsed = now_ms - replay_started_at
                while replay_index + 1 < len(replay_frames) and replay_frames[replay_index + 1].get("elapsed_ms", 0) <= elapsed:
                    replay_index += 1
                    game_state = replay_frames[replay_index].get("game_state")
            draw_game(screen, game_state, game_renderer, fonts, None, None, 0, status_msg)
        else:
            draw_lobby(screen, _screen_state(), fonts)

    pygame.quit()


if __name__ == "__main__":
    main()
