import pygame

from client.avatar_art import make_avatar_surface


class ClientGameRenderer:
    def __init__(self, tile_size=44):
        self.tile_size = tile_size
        self.colors = {
            "bg": (2, 17, 41),
            "grid": (26, 57, 88),
            "normal": (39, 39, 42),
            "warning": (234, 179, 8),
            "empty": (16, 24, 32),
            "player": (96, 165, 250),
            "player_outline": (255, 255, 255),
            "text": (244, 244, 245),
            "muted": (161, 161, 170),
        }
        self.player_palette = [
            (96, 165, 250),
            (34, 197, 94),
            (251, 146, 60),
            (244, 114, 182),
        ]
        self.avatar_cache = {}

    def draw(self, screen, game_state, font_title, font_body, font_sm):
        screen.fill(self.colors["bg"])

        if not game_state:
            msg = font_body.render("Waiting for match state...", True, self.colors["muted"])
            screen.blit(msg, msg.get_rect(center=(400, 300)))
            return

        grid = game_state.get("grid", [])
        players = game_state.get("players", {})

        if not grid:
            msg = font_body.render("No game board available", True, self.colors["muted"])
            screen.blit(msg, msg.get_rect(center=(400, 300)))
            return

        rows = len(grid)
        cols = len(grid[0]) if rows else 0

        board_start_x = 120
        board_start_y = 80
        board_width = cols * self.tile_size
        board_height = rows * self.tile_size

        board_rect = pygame.Rect(board_start_x, board_start_y, board_width, board_height)
        pygame.draw.rect(screen, self.colors["grid"], board_rect, border_radius=8)

        for row_index, row in enumerate(grid):
            for col_index, tile in enumerate(row):
                x = board_start_x + col_index * self.tile_size
                y = board_start_y + row_index * self.tile_size
                rect = pygame.Rect(x, y, self.tile_size, self.tile_size)

                if tile == 0:
                    color = self.colors["normal"]
                elif tile == 1:
                    color = self.colors["warning"]
                else:
                    color = self.colors["empty"]

                pygame.draw.rect(screen, color, rect, border_radius=6)
                pygame.draw.rect(screen, (63, 63, 70), rect, 1, border_radius=6)

        bar_y = board_start_y - 34
        max_lives = 3

        for player_index, (player_id, player) in enumerate(players.items()):
            if not isinstance(player, dict):
                continue

            r = player.get("r", 0)
            c = player.get("c", 0)
            is_alive = player.get("is_alive", True)
            lives = player.get("lives", 0)
            player_color = player.get("color") or self.player_palette[player_index % len(self.player_palette)]

            local_x = player.get("x", c * self.tile_size + 6)
            local_y = player.get("y", r * self.tile_size + 6)
            x = board_start_x + local_x
            y = board_start_y + local_y
            size = self.tile_size - 12
            rect = pygame.Rect(x, y, size, size)

            color = player_color if is_alive else (239, 68, 68)
            avatar_rows = player.get("avatar")
            if avatar_rows:
                try:
                    cache_key = tuple(avatar_rows)
                    avatar_surface = self.avatar_cache.get(cache_key)
                    if avatar_surface is None:
                        avatar_surface = make_avatar_surface(avatar_rows, 2)
                        if avatar_surface.get_size() != rect.size:
                            avatar_surface = pygame.transform.scale(avatar_surface, rect.size)
                        self.avatar_cache[cache_key] = avatar_surface
                    screen.blit(avatar_surface, rect.topleft)
                except (TypeError, ValueError):
                    pygame.draw.ellipse(screen, color, rect)
                    pygame.draw.ellipse(screen, self.colors["player_outline"], rect, 2)
            else:
                pygame.draw.ellipse(screen, color, rect)
                pygame.draw.ellipse(screen, self.colors["player_outline"], rect, 2)

            label = font_sm.render(f"{player_id}", True, self.colors["text"])
            screen.blit(label, (x, y - 18))

            bar_rect = pygame.Rect(board_start_x, bar_y + player_index * 16, board_width, 10)
            pygame.draw.rect(screen, (63, 63, 70), bar_rect, border_radius=6)
            fill_width = max(0, min(board_width, int((lives / max_lives) * board_width)))
            pygame.draw.rect(screen, player_color if is_alive else (239, 68, 68), pygame.Rect(bar_rect.x, bar_rect.y, fill_width, bar_rect.height), border_radius=6)

            bar_label = font_sm.render(f"{player_id}", True, self.colors["text"])
            screen.blit(bar_label, (bar_rect.x, bar_rect.y - 14))

        title = font_title.render("Match in Progress", True, self.colors["text"])
        screen.blit(title, (board_start_x, 25))

        hint = font_sm.render("Server is syncing the board state", True, self.colors["muted"])
        screen.blit(hint, (board_start_x, 55))
