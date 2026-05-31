from game_screen.game_screen import GameScreen
from game_screen.active_zone import ActiveZone


class TableScreen(GameScreen):
    SCREEN_SIZE = (1280, 720)
    BG_COLOR = (30, 30, 30)

    def __init__(self, actor_store, game_controller):
        super().__init__(
            actor_store=actor_store,
            game_controller=game_controller,
            background_color=self.BG_COLOR,
        )
        # self.screen_zones["table"] = ActiveZone(zone_id="table", rect=())

