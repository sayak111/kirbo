from server.gamelogic import GameEngine


class Game:
    def __init__(self, rows=8, cols=8):
        self.engine = GameEngine(rows=rows, cols=cols)

    def add_player(self, player_id, start_r, start_c):
        self.engine.add_player(player_id, start_r, start_c)

    def move_player(self, player_id, direction):
        self.engine.move_player(player_id, direction)

    def handle_slam(self, player_id, direction):
        self.engine.handle_slam(player_id, direction)

    def tick(self):
        self.engine.tick()

    def serialize_state(self):
        return self.engine.serialize_state()
