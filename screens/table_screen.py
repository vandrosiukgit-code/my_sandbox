import json
import os

from activities import (
    BotHandActivity,
    CardSelectionActivity,
    CardsSlotActivityDecorator,
    PlayerHandActivity,
    PlayerTurnActivity,
    PlayAreaSlotsActivity,
    VisibleCardsHandDecorator,
)
from core.resource import ResourceManager
from game_screen.game_screen import GameScreen


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "table_screen_fixture.json")
PLAY_AREA_FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "play_area_fixture.json")


class TableScreen(GameScreen):
    """Первый черновой игровой экран стола."""

    SCREEN_SIZE = (1280, 720)
    BG_COLOR = (30, 30, 30)
    PLAY_AREA_INSET = 20
    SIDE_PLAYER_FRAME_SIZE = (260, 300)
    CENTER_PLAYER_FRAME_SIZE = (300, 260)
    PORTRAIT_FRAME_SIZE = (200, 200)
    CARD_SLOT_FRAME_SIZE_RATIO = (0.72, 0.53)

    def __init__(self, group_store, game_controller):
        super().__init__(
            group_store=group_store,
            game_controller=game_controller,
            background_color=self.BG_COLOR,
        )

        self.create_frame("game_table", rect=(0, 0, 1280, 720))
        self.create_frame("play_area_frame", rect=self.rect_from_size(self.calculate_play_area_size())).set_rect_visibility(False)
        self.create_frame("cards_slot_frame", rect=self.rect_from_size(self.calculate_card_slot_frame_size())).set_rect_visibility(False)

        self.create_frame("left_player_frame", rect=self.rect_from_size(self.SIDE_PLAYER_FRAME_SIZE))
        self.create_frame("left_player_portrait", rect=self.rect_from_size(self.PORTRAIT_FRAME_SIZE))
        self.create_frame("left_player_hand", rect=self.rect_from_size(self.SIDE_PLAYER_FRAME_SIZE))

        self.create_frame("right_player_frame", rect=self.rect_from_size(self.SIDE_PLAYER_FRAME_SIZE))
        self.create_frame("right_player_portrait", rect=self.rect_from_size(self.PORTRAIT_FRAME_SIZE))
        self.create_frame("right_player_hand", rect=self.rect_from_size(self.SIDE_PLAYER_FRAME_SIZE))

        self.create_frame("top_player_frame", rect=self.rect_from_size(self.CENTER_PLAYER_FRAME_SIZE))
        self.create_frame("top_player_portrait", rect=self.rect_from_size(self.PORTRAIT_FRAME_SIZE))
        self.create_frame("top_player_hand", rect=self.rect_from_size(self.CENTER_PLAYER_FRAME_SIZE))

        self.create_frame("bottom_player_frame", rect=self.rect_from_size(self.CENTER_PLAYER_FRAME_SIZE))
        self.create_frame("bottom_player_portrait", rect=self.rect_from_size(self.PORTRAIT_FRAME_SIZE))
        self.create_frame("bottom_player_hand", rect=self.rect_from_size(self.CENTER_PLAYER_FRAME_SIZE))

        self.layout_play_area_frames()

        self.layout_player_frames()

        self.put_configured_group("table_group", "game_table", position=(0, 0))
        self.put_configured_group("left_player", "left_player_portrait", position=(0, 0))
        self.put_configured_group("right_player", "right_player_portrait", position=(0, 0))
        self.put_configured_group("top_player", "top_player_portrait", position=(0, 0))
        self.put_configured_group("bottom_player", "bottom_player_portrait", position=(0, 0))

        cards_slot_activity = self.create_cards_slot_activity(self.get_screen_frame("cards_slot_frame"))
        play_area_slots_activity = PlayAreaSlotsActivity(
            screen=self,
            play_area_frame=self.get_screen_frame("play_area_frame"),
            prototype_slot_frame=self.get_screen_frame("cards_slot_frame"),
            prototype_slot_activity=cards_slot_activity,
            slot_activity_factory=self.create_cards_slot_activity,
        )
        player_turn_activity = PlayerTurnActivity(play_area_slots_activity)
        bottom_player_hand_activity = CardSelectionActivity(
            VisibleCardsHandDecorator(
                PlayerHandActivity(
                    frame=self.get_screen_frame("bottom_player_hand"),
                    resource_manager=ResourceManager,
                    card_count=0,
                    scale_factor=0.7,
                    orientation_degrees=0,
                    center_offset=(-5, -20),
                    max_card_angle=60,
                ),
                cards=(),
                resource_manager=ResourceManager,
            ),
            player_turn_activity=player_turn_activity,
            owns_hand_activity=True,
        )

        activity_map = {
            "left_player_hand": BotHandActivity(
                frame=self.get_screen_frame("left_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=9,
                scale_factor=0.7,
                radius=80,
                orientation_degrees=90,
                center_offset=(-30, 0),
                debug_fan_rect=True,
                debug_fan_rect_color=(255, 232, 64),
            ),
            "right_player_hand": BotHandActivity(
                frame=self.get_screen_frame("right_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=9,
                scale_factor=0.7,
                radius=80,
                orientation_degrees=-90,
                center_offset=(18, 0),
                debug_fan_rect=True,
                debug_fan_rect_color=(64, 200, 255),
            ),
            "top_player_hand": BotHandActivity(
                frame=self.get_screen_frame("top_player_hand"),
                resource_manager=ResourceManager,
                resource_key="cards.card_back",
                card_count=9,
                scale_factor=0.7,
                radius=80,
                orientation_degrees=180,
                center_offset=(0, -30),
            ),
            "bottom_player_hand": bottom_player_hand_activity,
            "play_area_frame": player_turn_activity,
            "cards_slot_frame": cards_slot_activity,
        }
        self.hand_activities = {}
        for activity_id, activity in activity_map.items():
            self.register_named_activity(activity_id, activity)
            self.add_activity(activity)
        self.fixture_paths = (FIXTURE_PATH, PLAY_AREA_FIXTURE_PATH)
        self._fixture_mtimes = {}
        self._fixture_check_elapsed = 0.0
        self._fixture_check_interval = 0.2
        self.reload_fixture_if_changed(force=True)

    def create_cards_slot_activity(self, frame, index=0):
        _ = index
        return CardsSlotActivityDecorator(
            BotHandActivity(
                frame=frame,
                resource_manager=ResourceManager,
                card_count=0,
                group_id_prefix=f"{frame.id}.cards",
                orientation_degrees=0,
                center_offset=(0, 0),
            ),
            cards=(),
            resource_manager=ResourceManager,
        )

    def layout_play_area_frames(self):
        play_area_size = self.calculate_play_area_size()
        card_slot_size = self.calculate_card_slot_frame_size()
        self.put_frame_in_frame(
            "play_area_frame",
            "game_table",
            position=(self.PLAY_AREA_INSET, self.PLAY_AREA_INSET),
        )
        self.put_frame_in_frame(
            "cards_slot_frame",
            "play_area_frame",
            position=self.center_child(play_area_size, card_slot_size),
        )

    def calculate_play_area_size(self):
        inset = self.PLAY_AREA_INSET * 2
        return (
            max(1, self.SCREEN_SIZE[0] - inset),
            max(1, self.SCREEN_SIZE[1] - inset),
        )

    def calculate_card_slot_frame_size(self):
        play_area_width, play_area_height = self.calculate_play_area_size()
        width_ratio, height_ratio = self.CARD_SLOT_FRAME_SIZE_RATIO
        return (
            max(1, int(round(play_area_width * width_ratio))),
            max(1, int(round(play_area_height * height_ratio))),
        )

    def layout_player_frames(self):
        """Place all player zones from anchors and frame sizes."""
        self.layout_player_frame("left", self.SIDE_PLAYER_FRAME_SIZE)
        self.layout_player_frame("right", self.SIDE_PLAYER_FRAME_SIZE)
        self.layout_player_frame("top", self.CENTER_PLAYER_FRAME_SIZE)
        self.layout_player_frame("bottom", self.CENTER_PLAYER_FRAME_SIZE)

    def layout_player_frame(self, player_id, frame_size):
        player_frame_id = f"{player_id}_player_frame"
        hand_frame_id = f"{player_id}_player_hand"
        portrait_frame_id = f"{player_id}_player_portrait"
        player_frame_position = self.calculate_player_frame_position(player_id, frame_size)

        self.put_frame_in_frame(
            player_frame_id,
            "game_table",
            position=player_frame_position,
        )
        self.put_frame_in_frame(hand_frame_id, player_frame_id, position=(0, 0))
        self.put_frame_in_frame(
            portrait_frame_id,
            player_frame_id,
            position=self.calculate_player_portrait_position(
                player_id,
                frame_size,
                player_frame_position,
            ),
        )

    def calculate_player_frame_position(self, player_id, frame_size):
        screen_width, screen_height = self.SCREEN_SIZE
        frame_width, frame_height = frame_size

        if player_id == "left":
            return 0, self.center_axis(screen_height, frame_height)
        if player_id == "right":
            return screen_width - frame_width, self.center_axis(screen_height, frame_height)
        if player_id == "top":
            return self.center_axis(screen_width, frame_width), 0
        if player_id == "bottom":
            return self.center_axis(screen_width, frame_width), screen_height - frame_height

        raise ValueError(f"Unknown player layout anchor: {player_id}")

    def calculate_player_portrait_position(self, player_id, frame_size, frame_position):
        """Place portrait so its outer edge touches the play-area border."""
        portrait_x, portrait_y = self.center_child(frame_size, self.PORTRAIT_FRAME_SIZE)
        play_area_left, play_area_top, play_area_right, play_area_bottom = self.calculate_play_area_bounds()
        frame_x, frame_y = frame_position
        portrait_width, portrait_height = self.PORTRAIT_FRAME_SIZE

        if player_id == "left":
            portrait_x = play_area_left - frame_x
        elif player_id == "right":
            portrait_x = play_area_right - frame_x - portrait_width
        elif player_id == "top":
            portrait_y = play_area_top - frame_y
        elif player_id == "bottom":
            portrait_y = play_area_bottom - frame_y - portrait_height
        else:
            raise ValueError(f"Unknown player portrait anchor: {player_id}")

        return int(round(portrait_x)), int(round(portrait_y))

    def calculate_play_area_bounds(self):
        play_area_width, play_area_height = self.calculate_play_area_size()
        left = self.PLAY_AREA_INSET
        top = self.PLAY_AREA_INSET
        return left, top, left + play_area_width, top + play_area_height

    @staticmethod
    def center_child(parent_size, child_size):
        return (
            TableScreen.center_axis(parent_size[0], child_size[0]),
            TableScreen.center_axis(parent_size[1], child_size[1]),
        )

    @staticmethod
    def center_axis(parent_size, child_size):
        return int(round((parent_size - child_size) / 2))

    @staticmethod
    def rect_from_size(size):
        return 0, 0, int(size[0]), int(size[1])

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
        changed_paths = []
        existing_paths = []
        for fixture_path in self.fixture_paths:
            if not os.path.exists(fixture_path):
                continue

            existing_paths.append(fixture_path)
            mtime = os.path.getmtime(fixture_path)
            if force or self._fixture_mtimes.get(fixture_path) != mtime:
                changed_paths.append(fixture_path)

        if not changed_paths:
            return

        for fixture_path in existing_paths:
            fixture = self.load_fixture_file(fixture_path)
            if fixture is None:
                continue

            self._fixture_mtimes[fixture_path] = os.path.getmtime(fixture_path)
            self.apply_fixture(fixture)
            print(f"Reloaded table fixture: {fixture_path}")

    @staticmethod
    def load_fixture_file(fixture_path):
        try:
            with open(fixture_path, "r", encoding="utf-8") as fixture_file:
                return json.load(fixture_file)
        except json.JSONDecodeError:
            return None

    def apply_fixture(self, fixture):
        """Apply dev fixture values that imitate controller visual commands."""
        if "card_counts" in fixture:
            self.apply_card_counts_fixture(fixture["card_counts"])
            return

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

    def apply_card_counts_fixture(self, card_counts):
        """Apply the compact table fixture: only visible hand sizes stay public."""
        if not isinstance(card_counts, dict):
            return

        for activity_id, card_count in card_counts.items():
            activity = self.get_named_activity(activity_id)
            if activity is None:
                continue

            activity_fixture = {"card_count": card_count}
            if activity_id == "bottom_player_hand":
                activity_fixture["cards_from_manifest"] = True

            activity.apply_fixture(activity_fixture)

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

        for child_frame_id, child_node in node.get("children", {}).items():
            self.apply_gui_fixture_node(child_frame_id, child_node)

        activity_fixture = node.get("activity")
        activity = self.get_named_activity(frame_id)
        if activity_fixture is not None and activity is not None:
            activity.apply_fixture(activity_fixture)

        for activity_id, fixture in node.get("activities", {}).items():
            activity = self.get_named_activity(activity_id)
            if activity is not None:
                activity.apply_fixture(fixture)

    def apply_frame_fixture(self, frame_id, fixture):
        """Apply dev fixture values for a Frame and its descendants."""
        if not fixture or not self.has_screen_frame(frame_id):
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

        frame.place_group_local(group, local_position)

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
