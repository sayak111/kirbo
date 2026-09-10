import time

PLAYER_COLORS = [
    (96, 165, 250),
    (34, 197, 94),
    (251, 146, 60),
    (244, 114, 182),
]

# Tile states
TILE_NORMAL = 0
TILE_WARNING = 1
TILE_EMPTY = 2


class GameBoard:
    def __init__(self, rows=8, cols=8):
        self.rows = rows
        self.cols = cols
        self.grid = [[TILE_NORMAL for _ in range(cols)] for _ in range(rows)]
        self.pending_falling_tiles = []

    def trigger_slam(self, row, col, direction):
        """Apply a slam effect to a row or column based on direction."""
        target_tiles = []
        if direction in ("UP", "DOWN"):
            target_tiles = [(r, col) for r in range(self.rows) if self.grid[r][col] != TILE_EMPTY]
        elif direction in ("LEFT", "RIGHT"):
            target_tiles = [(row, c) for c in range(self.cols) if self.grid[row][c] != TILE_EMPTY]

        now = time.time()
        for r, c in target_tiles:
            self.grid[r][c] = TILE_WARNING
            self.pending_falling_tiles.append({"pos": (r, c), "fall_at": now + 1.5})

    def update_timers(self):
        """Update tiles whose timer has expired and turn them into empty tiles."""
        now = time.time()
        remaining = []
        for item in self.pending_falling_tiles:
            r, c = item["pos"]
            if now >= item["fall_at"]:
                self.grid[r][c] = TILE_EMPTY
            else:
                remaining.append(item)
        self.pending_falling_tiles = remaining


class GameEngine:
    def __init__(self, rows=8, cols=8):
        self.board = GameBoard(rows, cols)
        self.players = {}
        self.spawn_points = []

        for row in (0, self.board.rows - 1):
            for col in (0, self.board.cols - 1):
                if (row, col) not in self.spawn_points:
                    self.spawn_points.append((row, col))

        self.spawn_points = self.spawn_points[:4]

    def add_player(self, player_id, start_r, start_c):
        color_index = len(self.players) % len(PLAYER_COLORS)
        start_x = start_c * 44 + 6
        start_y = start_r * 44 + 6
        self.players[player_id] = {
            "r": start_r,
            "c": start_c,
            "x": float(start_x),
            "y": float(start_y),
            "lives": 3,
            "is_alive": True,
            "color": PLAYER_COLORS[color_index],
        }

    def remove_player(self, player_id):
        self.players.pop(player_id, None)

    def move_player(self, player_id, direction=None, dx=None, dy=None):
        p = self.players.get(player_id)
        if not p or not p["is_alive"]:
            return

        step = 12
        x = p.get("x", float(p["c"] * 44 + 6))
        y = p.get("y", float(p["r"] * 44 + 6))

        if direction is not None:
            if direction == "UP":
                y -= step
            elif direction == "DOWN":
                y += step
            elif direction == "LEFT":
                x -= step
            elif direction == "RIGHT":
                x += step
        else:
            x += float(dx or 0.0)
            y += float(dy or 0.0)

        max_x = (self.board.cols * 44) - 32
        max_y = (self.board.rows * 44) - 32

        p["x"] = max(0, min(x, max_x))
        p["y"] = max(0, min(y, max_y))
        p["r"] = int(p["y"] // 44)
        p["c"] = int(p["x"] // 44)

    def handle_slam(self, player_id, direction):
        p = self.players.get(player_id)
        if p and p["is_alive"]:
            self.board.trigger_slam(p["r"], p["c"], direction)

    def tick(self):
        """Runs on a fixed tick: update timers and check collisions / player falls."""
        self.board.update_timers()

        for p_id, p in self.players.items():
            if not p["is_alive"]:
                continue

            if self.board.grid[p["r"]][p["c"]] == TILE_EMPTY:
                p["lives"] -= 1
                if p["lives"] <= 0:
                    p["is_alive"] = False
                else:
                    p["r"], p["c"] = self.board.rows // 2, self.board.cols // 2
                    p["x"] = float(p["c"] * 44 + 6)
                    p["y"] = float(p["r"] * 44 + 6)

    def serialize_state(self):
        """Pack the current state into a small network-friendly structure."""
        return {
            "grid": self.board.grid,
            "players": self.players,
        }


class Game:
    def __init__(self, rows=8, cols=8):
        self.engine = GameEngine(rows=rows, cols=cols)

    def add_player(self, player_id, start_r, start_c):
        self.engine.add_player(player_id, start_r, start_c)

    def remove_player(self, player_id):
        self.engine.remove_player(player_id)

    def move_player(self, player_id, direction=None, dx=None, dy=None):
        self.engine.move_player(player_id, direction=direction, dx=dx, dy=dy)

    def handle_slam(self, player_id, direction):
        self.engine.handle_slam(player_id, direction)

    def tick(self):
        self.engine.tick()

    def serialize_state(self):
        return self.engine.serialize_state()
