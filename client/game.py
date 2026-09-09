import pygame


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

        for player_id, player in players.items():
            if not isinstance(player, dict):
                continue

            r = player.get("r", 0)
            c = player.get("c", 0)
            is_alive = player.get("is_alive", True)
            lives = player.get("lives", 0)

            x = board_start_x + c * self.tile_size + 6
            y = board_start_y + r * self.tile_size + 6
            size = self.tile_size - 12
            rect = pygame.Rect(x, y, size, size)

            color = self.colors["player"] if is_alive else (239, 68, 68)
            pygame.draw.ellipse(screen, color, rect)
            pygame.draw.ellipse(screen, self.colors["player_outline"], rect, 2)

            label = font_sm.render(f"{player_id}", True, self.colors["text"])
            screen.blit(label, (x, y - 18))

            lives_label = font_sm.render(f"Lives: {lives}", True, self.colors["text"])
            screen.blit(lives_label, (x, y + size + 4))

        title = font_title.render("Match in Progress", True, self.colors["text"])
        screen.blit(title, (board_start_x, 25))

        hint = font_sm.render("Server is syncing the board state", True, self.colors["muted"])
        screen.blit(hint, (board_start_x, 55))
