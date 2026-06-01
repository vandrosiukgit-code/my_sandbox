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

        self.create_zone("game_table", rect=(0, 0, 1280, 720))
        self.create_zone("left_player_az", rect=(0, 0, 260, 300))
        self.create_zone("left_player_portrait", rect=(0, 0, 200, 200))

        self.put_zone_in_zone("left_player_az", "game_table", position=(0, 210))
        self.put_zone_in_zone("left_player_portrait", "left_player_az", position=(20, 46))

        self.activate_actor("table_actor")
        self.activate_actor("left_player")

        self.put_actor_in_zone("table_actor", "game_table", position=(0, 0))
        self.put_actor_in_zone("left_player", "left_player_portrait", position=(0, 0))
