from game_screen.game_screen import GameScreen


class TableScreen(GameScreen):
    """Первый черновой игровой экран стола."""

    SCREEN_SIZE = (1280, 720)
    BG_COLOR = (30, 30, 30)

    def __init__(self, group_store, game_controller):
        super().__init__(
            group_store=group_store,
            game_controller=game_controller,
            background_color=self.BG_COLOR,
        )

        self.create_frame("game_table", rect=(0, 0, 1280, 720))

        self.create_frame("left_player_frame", rect=(0, 0, 260, 300))
        self.create_frame("left_player_portrait", rect=(0, 0, 200, 200))

        self.create_frame("right_player_frame", rect=(0, 0, 260, 300))
        self.create_frame("right_player_portrait", rect=(0, 0, 200, 200))

        self.create_frame("top_player_frame", rect=(0,0,300, 260))
        self.create_frame("top_player_portrait",  rect=(0, 0, 200, 200))

        self.put_frame_in_frame("left_player_frame", "game_table", position=(0, 210))
        self.put_frame_in_frame("left_player_portrait", "left_player_frame", position=(20, 46))

        self.put_frame_in_frame("right_player_frame", "game_table", position=(1020, 210))
        self.put_frame_in_frame("right_player_portrait", "right_player_frame", position=(20, 46))

        self.put_frame_in_frame("top_player_frame", "game_table", position=(482, 0))
        self.put_frame_in_frame("top_player_portrait", "top_player_frame", position=(58, 20))



        self.put_configured_group("table_group", "game_table", position=(0, 0))
        self.put_configured_group("left_player", "left_player_portrait", position=(0, 0))
        self.put_configured_group("right_player", "right_player_portrait", position=(0, 0))
        self.put_configured_group("top_player", "top_player_portrait", position=(0, 0))

    def put_configured_group(self, group_id, frame_id, position=(0, 0)):
        if self.group_store is None or not self.group_store.has(group_id):
            return None
        self.activate_group(group_id)
        return self.put_group_in_frame(group_id, frame_id, position=position)
