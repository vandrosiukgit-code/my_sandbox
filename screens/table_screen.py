from game_screen.game_screen import GameScreen



class TableScreen(GameScreen):
    """Первый черновой игровой экран стола."""

    SCREEN_SIZE = (1280, 720)
    BG_COLOR = (30, 30, 30)

    def __init__(self, actor_store, game_controller):
        super().__init__(
            actor_store=actor_store,
            game_controller=game_controller,
            background_color=self.BG_COLOR,
        )
        self.activate_initial_actors()
        # self.screen_zones["table"] = ActiveZone(zone_id="table", rect=())

    def activate_initial_actors(self):
        """Включить actor-ы, которые должны быть видны сразу после старта."""
        self.activate_actor("table_actor")

