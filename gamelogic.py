import time

# מצבי אריחים[cite: 1]
TILE_NORMAL = 0   # רגיל[cite: 1]
TILE_WARNING = 1  # אזהרה (מהבהב לפני נפילה)[cite: 1]
TILE_EMPTY = 2    # חור/תהום[cite: 1]

class GameBoard:
    def __init__(self, rows=8, cols=8):
        self.rows = rows
        self.cols = cols
        # יצירת המטריצה הדו-ממדית (מערך של רשימות)[cite: 1]
        self.grid = [[TILE_NORMAL for _ in range(cols)] for _ in range(rows)]
        self.pending_falling_tiles = []  # רשימת אריחים שנמצאים בטיימר אזהרה[cite: 1]

    def trigger_slam(self, row, col, direction):
        """מפעיל תקיפה על שורה או עמודה לפי כיוון[cite: 1]"""
        target_tiles = []
        if direction in ("UP", "DOWN"):
            # פוגע בכל העמודה
            target_tiles = [(r, col) for r in range(self.rows) if self.grid[r][col] != TILE_EMPTY]
        elif direction in ("LEFT", "RIGHT"):
            # פוגע בכל השורה
            target_tiles = [(row, c) for c in range(self.cols) if self.grid[row][c] != TILE_EMPTY]

        now = time.time()
        for r, c in target_tiles:
            self.grid[r][c] = TILE_WARNING  # מעביר למצב אזהרה[cite: 1]
            # קובע נפילה בעוד 1.5 שניות (חלון הזדמנויות לבריחה)[cite: 1]
            self.pending_falling_tiles.append({"pos": (r, c), "fall_at": now + 1.5})

    def update_timers(self):
        """מעדכן אריחים שהטיימר שלהם פג והופך אותם ל"ריק"[cite: 1]"""
        now = time.time()
        remaining = []
        for item in self.pending_falling_tiles:
            r, c = item["pos"]
            if now >= item["fall_at"]:
                self.grid[r][c] = TILE_EMPTY  # האריח נופל![cite: 1]
            else:
                remaining.append(item)
        self.pending_falling_tiles = remaining


class GameEngine:
    def __init__(self, rows=8, cols=8):
        self.board = GameBoard(rows, cols)
        self.players = {}  # dict of player_id -> {"r": row, "c": col, "lives": 3, "is_alive": True}

    def add_player(self, player_id, start_r, start_c):
        self.players[player_id] = {"r": start_r, "c": start_c, "lives": 3, "is_alive": True}

    def move_player(self, player_id, direction):
        p = self.players.get(player_id)
        if not p or not p["is_alive"]:
            return

        new_r, new_c = p["r"], p["c"]
        if direction == "UP" and p["r"] > 0: new_r -= 1
        elif direction == "DOWN" and p["r"] < self.board.rows - 1: new_r += 1
        elif direction == "LEFT" and p["c"] > 0: new_c -= 1
        elif direction == "RIGHT" and p["c"] < self.board.cols - 1: new_c += 1

        # השרת מאמת שהמשבצת החדשה אינה תהום לפני התנועה
        if self.board.grid[new_r][new_c] != TILE_EMPTY:
            p["r"], p["c"] = new_r, new_c

    def handle_slam(self, player_id, direction):
        p = self.players.get(player_id)
        if p and p["is_alive"]:
            self.board.trigger_slam(p["r"], p["c"], direction)

    def tick(self):
        """פועם בקצב קבוע: מעדכן טיימרים ובודק התנגשויות/נפילת שחקנים[cite: 1]"""
        self.board.update_timers()

        # בדיקת התנגשויות (Authoritative Server)[cite: 1]
        for p_id, p in self.players.items():
            if not p["is_alive"]:
                continue
            
            # אם השחקן עומד על משבצת שהפכה לריקה[cite: 1]
            if self.board.grid[p["r"]][p["c"]] == TILE_EMPTY:
                p["lives"] -= 1
                if p["lives"] <= 0:
                    p["is_alive"] = False
                else:
                    # Respawn: החזרה למרכז הלוח
                    p["r"], p["c"] = self.board.rows // 2, self.board.cols // 2

    def serialize_state(self):
        """אורז את המצב למבנה קל לשליחה ברשת[cite: 1]"""
        return {
            "grid": self.board.grid,
            "players": self.players
        }