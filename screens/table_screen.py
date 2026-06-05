import json
import os

from activities import BotHandActivity
from core.resource import ResourceManager
from game_screen.game_screen import GameScreen


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "table_screen_fixture.json")


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
        self.create_frame("left_player_hand", rect=(0, 0, 260, 300))

        self.create_frame("right_player_frame", rect=(0, 0, 260, 300))
        self.create_frame("right_player_portrait", rect=(0, 0, 200, 200))

        self.create_frame("top_player_frame", rect=(0, 0, 300, 260))
        self.create_frame("top_player_portrait",  rect=(0, 0, 200, 200))

        self.create_frame("bottom_player_frame", rect=(0, 0, 300, 260))
        self.create_frame("bottom_player_portrait", rect=(0, 0, 200, 200))

        self.put_frame_in_frame("left_player_frame", "game_table", position=(0, 210))
        self.put_frame_in_frame("left_player_hand", "left_player_frame", position=(0, 0))
        self.put_frame_in_frame("left_player_portrait", "left_player_frame", position=(20, 46))

        self.put_frame_in_frame("right_player_frame", "game_table", position=(1020, 210))
        self.put_frame_in_frame("right_player_portrait", "right_player_frame", position=(20, 46))

        self.put_frame_in_frame("top_player_frame", "game_table", position=(482, 0))
        self.put_frame_in_frame("top_player_portrait", "top_player_frame", position=(58, 20))

        self.put_frame_in_frame("bottom_player_frame", "game_table", position=(475, 518))
        self.put_frame_in_frame("bottom_player_portrait", "bottom_player_frame", position=(65, 0))


        self.put_configured_group("table_group", "game_table", position=(0, 0))
        self.put_configured_group("left_player", "left_player_portrait", position=(0, 0))
        self.put_configured_group("right_player", "right_player_portrait", position=(0, 0))
        self.put_configured_group("top_player", "top_player_portrait", position=(0, 0))
        self.put_configured_group("bottom_player", "bottom_player_portrait", position=(0, 0))

        self.left_player_hand_activity = BotHandActivity(
            frame=self.get_screen_frame("left_player_hand"),
            resource_manager=ResourceManager,
            resource_key="cards.card_back",
            card_count=8,
        )
        self.add_activity(self.left_player_hand_activity)
        self.fixture_path = FIXTURE_PATH
        self._fixture_mtime = None
        self._fixture_check_elapsed = 0.0
        self._fixture_check_interval = 0.2
        self.reload_fixture_if_changed(force=True)

    def put_configured_group(self, group_id, frame_id, position=(0, 0)):
        if self.group_store is None or not self.group_store.has(group_id):
            return None
        self.activate_group(group_id)
        return self.put_group_in_frame(group_id, frame_id, position=position)

    def update(self, dt):
        self._fixture_check_elapsed += dt
        if self._fixture_check_elapsed >= self._fixture_check_interval:
            self._fixture_check_elapsed = 0.0
            self.reload_fixture_if_changed()
        super().update(dt)

    def draw(self, screen):
        """Draw table scene in explicit visual order.

        Order:
        1. table background;
        2. generated hand activity cards;
        3. player portrait groups above the hand fan;
        4. debug frame overlay.
        """
        screen.fill(self.background_color)
        self.draw_group_if_active("table_group", screen)

        for activity in self.active_activities:
            if hasattr(activity, "draw"):
                activity.draw(screen)

        for group_id in (
            "left_player",
            "right_player",
            "top_player",
            "bottom_player",
        ):
            self.draw_group_if_active(group_id, screen)

        for frame in self.iter_root_frames():
            frame.draw_debug_tree(screen)

    def draw_group_if_active(self, group_id, screen):
        if group_id in self.active_group_ids:
            self.get_group(group_id).draw(screen)

    def reload_fixture_if_changed(self, force=False):
        """Hot reload dev fixture and apply it to screen activities."""
        if not os.path.exists(self.fixture_path):
            return

        mtime = os.path.getmtime(self.fixture_path)
        if not force and self._fixture_mtime == mtime:
            return

        try:
            with open(self.fixture_path, "r", encoding="utf-8") as fixture_file:
                fixture = json.load(fixture_file)
        except json.JSONDecodeError:
            return

        self._fixture_mtime = mtime
        self.apply_fixture(fixture)
        print(f"Reloaded table fixture: {self.fixture_path}")

    def apply_fixture(self, fixture):
        """Apply dev fixture values that imitate controller visual commands."""
        activities = fixture.get("activities", {})
        hand_fixture = activities.get("left_player_hand", {})
        self.left_player_hand_activity.apply_fixture(hand_fixture)
