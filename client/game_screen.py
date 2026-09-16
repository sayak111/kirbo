import pygame

from client.game_renderer import ClientGameRenderer

STATE_GAME = "GAME"
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
COLOR_TEXT = (244, 244, 245)
COLOR_SUCCESS = (34, 197, 94)
COLOR_TEXT_MUTED = (161, 161, 170)


def update_player(game_state, local_player_id, client, dt):
    if not game_state or not isinstance(game_state.get("players", {}), dict):
        return

    players = game_state["players"]
    if not players:
        return

    player_id = local_player_id if local_player_id in players else next(iter(players))
    player = players.get(player_id)
    grid = game_state.get("grid", [])
    if not isinstance(player, dict) or not grid:
        return

    tile_size = 44
    cols = len(grid[0])
    player.setdefault("x", float(player.get("c", 0) * tile_size + 6))
    player.setdefault("y", float(player.get("r", 0) * tile_size + 6))

    keys = pygame.key.get_pressed()
    move_x = (keys[pygame.K_RIGHT] or keys[pygame.K_d]) - (keys[pygame.K_LEFT] or keys[pygame.K_a])
    move_y = (keys[pygame.K_DOWN] or keys[pygame.K_s]) - (keys[pygame.K_UP] or keys[pygame.K_w])
    if move_x or move_y:
        speed = 170
        magnitude = (move_x ** 2 + move_y ** 2) ** 0.5
        dx = move_x / magnitude * speed * dt
        dy = move_y / magnitude * speed * dt
        player["x"] += dx
        player["y"] += dy
        if move_x > 0:
            player["facing"] = "RIGHT"
        elif move_x < 0:
            player["facing"] = "LEFT"
        elif move_y > 0:
            player["facing"] = "DOWN"
        else:
            player["facing"] = "UP"
        if client and client.connected:
            client.move_player(dx=dx, dy=dy)

    player_size = tile_size - 12
    player["x"] = max(0, min(player["x"], cols * tile_size - player_size))
    player["y"] = max(0, min(player["y"], len(grid) * tile_size - player_size))


def draw(screen, game_state, game_renderer, fonts, countdown_text, result_banner_text, result_banner_until, status_msg):
    font_title, font_body, font_sm = fonts
    game_renderer.draw(screen, game_state, font_title, font_body, font_sm)
    if countdown_text:
        overlay = font_title.render(countdown_text, True, COLOR_TEXT)
        screen.blit(overlay, overlay.get_rect(center=(WINDOW_WIDTH // 2, WINDOW_HEIGHT // 2)))

    if result_banner_text and pygame.time.get_ticks() < result_banner_until:
        banner = font_title.render(
            result_banner_text,
            True,
            COLOR_SUCCESS if result_banner_text == "YOU WON!" else COLOR_TEXT,
        )
        screen.blit(banner, banner.get_rect(center=(WINDOW_WIDTH // 2, 70)))

    status = font_sm.render(f"Status: {status_msg}", True, COLOR_TEXT_MUTED)
    screen.blit(status, (20, WINDOW_HEIGHT - 30))
    pygame.display.flip()
