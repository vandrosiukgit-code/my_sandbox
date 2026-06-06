import json
import os

from activities import BotHandActivity, VisibleCardsHandDecorator
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
        self.create_frame("play_area_frame", rect=(0, 0, 1240, 680)).set_rect_visibility(False)

        self.create_frame("left_player_frame", rect=(0, 0, 260, 300))
        self.create_frame("left_player_portrait", rect=(0, 0, 200, 200))
        self.create_frame("left_player_hand", rect=(0, 0, 260, 300))

        self.create_frame("right_player_frame", rect=(0, 0, 260, 300))
        self.create_frame("right_player_portrait", rect=(0, 0, 200, 200))
        self.create_frame("right_player_hand", rect=(0, 0, 260, 300))

        self.create_frame("top_player_frame", rect=(0, 0, 300, 260))
        self.create_frame("top_player_portrait",  rect=(0, 0, 200, 200))
        self.create_frame("top_player_hand", rect=(0, 0, 300, 260))

        self.create_frame("bottom_player_frame", rect=(0, 0, 300, 260))
        self.create_frame("bottom_player_portrait", rect=(0, 0, 200, 200))
        self.create_frame("bottom_player_hand", rect=(0, 0, 300, 260))

        self.put_frame_in_frame("play_area_frame", "game_table", position=(20, 20))

        self.put_frame_in_frame("left_player_frame", "game_table", position=(0, 210))
        self.put_frame_in_frame("left_player_hand", "left_player_frame", position=(0, 0))
        self.put_frame_in_frame("left_player_portrait", "left_player_frame", position=(20, 46))

        self.put_frame_in_frame("right_player_frame", "game_table", position=(1020, 210))
        self.put_frame_in_frame("right_player_hand", "right_player_frame", position=(0, 0))
        self.put_frame_in_frame("right_player_portrait", "right_player_frame", position=(20, 46))

        self.put_frame_in_frame("top_player_frame", "game_table", position=(490, -10))
        self.put_frame_in_frame("top_player_hand", "top_player_frame", position=(0, 0))
        self.put_frame_in_frame("top_player_portrait", "top_player_frame", position=(50, 30))

        self.put_frame_in_frame("bottom_player_frame", "game_table", position=(490, 488))
        self.put_frame_in_frame("bottom_player_hand", "bottom_player_frame", position=(0, 0))
        self.put_frame_in_frame("bottom_player_portrait", "bottom_player_frame", position=(50, 30))


        self.put_configured_group("table_group", "game_table", position=(0, 0))
        self.put_configured_group("left_player", "left_player_portrait", position=(0, 0))
        self.put_configured_group("right_player", "right_player_portrait", position=(0, 0))
        self.put_configured_group("top_player", "top_player_portrait", position=(0, 0))
        self.put_configured_group("bottom_player", "bottom_player_portrait", position=(0, 0))

        self.hand_activities = {
            "left_player_hand": BotHandActivity(
                frame=self.get_screen_frame("left_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=8,
                orientation_degrees=90,
                center_offset=(20, 0),
            ),
            "right_player_hand": BotHandActivity(
                frame=self.get_screen_frame("right_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=8,
                orientation_degrees=-90,
                center_offset=(-20, 0),
            ),
            "top_player_hand": BotHandActivity(
                frame=self.get_screen_frame("top_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=8,
                orientation_degrees=180,
                center_offset=(0, 0),
            ),
            "bottom_player_hand": VisibleCardsHandDecorator(
                BotHandActivity(
                    frame=self.get_screen_frame("bottom_player_hand"),
                    resource_manager=ResourceManager,
                    card_count=0,
                    orientation_degrees=0,
                    center_offset=(0, 0),
                ),
                cards=(),
                resource_manager=ResourceManager,
            ),
        }
        for activity in self.hand_activities.values():
            self.add_activity(activity)
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
        if "gui" in fixture:
            self.apply_gui_fixture_tree(fixture["gui"])
            return

        frames = fixture.get("frames", {})
        for frame_id, frame_fixture in frames.items():
            self.apply_frame_fixture(frame_id, frame_fixture)

        groups = fixture.get("groups", {})
        for group_id, group_fixture in groups.items():
            self.apply_group_fixture(group_id, group_fixture)

        activities = fixture.get("activities", {})
        for activity_id, activity in self.hand_activities.items():
            activity.apply_fixture(activities.get(activity_id, {}))

    def apply_gui_fixture_tree(self, tree):
        """Apply a fixture shaped like the GUI frame hierarchy."""
        if not isinstance(tree, dict):
            return

        if "frame_id" in tree:
            self.apply_gui_fixture_node(tree["frame_id"], tree)
            return

        for frame_id, node in tree.items():
            self.apply_gui_fixture_node(frame_id, node)

    def apply_gui_fixture_node(self, frame_id, node):
        """Apply one frame node, then its owned groups, activity, and children."""
        if not isinstance(node, dict):
            return

        self.apply_frame_fixture(frame_id, node)

        for group_id, group_fixture in node.get("groups", {}).items():
            self.apply_group_fixture(group_id, group_fixture)

        activity_fixture = node.get("activity")
        if activity_fixture is not None and frame_id in self.hand_activities:
            self.hand_activities[frame_id].apply_fixture(activity_fixture)

        for activity_id, fixture in node.get("activities", {}).items():
            if activity_id in self.hand_activities:
                self.hand_activities[activity_id].apply_fixture(fixture)

        for child_frame_id, child_node in node.get("children", {}).items():
            self.apply_gui_fixture_node(child_frame_id, child_node)

    def apply_frame_fixture(self, frame_id, fixture):
        """Apply dev fixture values for a Frame and its descendants."""
        if not fixture or frame_id not in self.screen_frames:
            return

        frame = self.get_screen_frame(frame_id)
        if "scale_factor" in fixture:
            frame.set_scale_factor(fixture["scale_factor"])
        elif "scale" in fixture:
            frame.set_scale_factor(fixture["scale"])

        local_position = self.get_frame_fixture_local_position(frame, fixture)
        if local_position is not None:
            frame.set_local_position(*local_position)

    @staticmethod
    def get_frame_fixture_local_position(frame, fixture):
        """Resolve fixture position to local coordinates inside the parent frame."""
        if "screen_position" in fixture:
            if frame.parent_frame is None:
                return TableScreen.normalize_fixture_position(fixture["screen_position"])
            return frame.parent_frame.to_local(TableScreen.normalize_fixture_position(fixture["screen_position"]))
        for key in ("position", "local_position"):
            if key in fixture:
                return TableScreen.normalize_fixture_position(fixture[key])
        return None

    def apply_group_fixture(self, group_id, fixture):
        """Apply dev fixture values for an active configured Group."""
        if not fixture or self.group_store is None:
            return
        if not self.group_store.has(group_id):
            return

        group = self.group_store.get(group_id)
        if "scale_factor" in fixture:
            group.set_scale_factor(fixture["scale_factor"])
        elif "scale" in fixture:
            group.set_scale_factor(fixture["scale"])

        try:
            frame = self.find_frame_for_group(group_id)
        except KeyError:
            return
        local_position = self.get_group_fixture_local_position(frame, fixture)
        if local_position is None:
            return

        group.set_parent_frame(frame)
        group.set_local_position(*local_position)
        frame.group_origins[group_id] = tuple(local_position)

    @staticmethod
    def get_group_fixture_local_position(frame, fixture):
        """Resolve fixture position to local coordinates inside the current frame."""
        if "screen_position" in fixture:
            return frame.to_local(TableScreen.normalize_fixture_position(fixture["screen_position"]))
        for key in ("position", "local_position"):
            if key in fixture:
                return TableScreen.normalize_fixture_position(fixture[key])
        return None

    @staticmethod
    def normalize_fixture_position(position):
        if isinstance(position, dict):
            return (
                int(round(float(position.get("x", 0)))),
                int(round(float(position.get("y", 0)))),
            )
        return int(round(float(position[0]))), int(round(float(position[1])))
