import json
import os

import pygame

from activities import (
    BotHandActivity,
    CardSelectionActivity,
    CardsSlotActivityDecorator,
    CardDealSequenceActivity,
    DeckActivity,
    DiscardTableActivity,
    PlayerHandActivity,
    PlayerTurnActivity,
    PlayAreaSlotsActivity,
    TakeTableActivity,
    VisibleCardsHandDecorator,
)
from core.resource import ResourceManager
from game_screen import debug_overlay
from game_screen.events import ActivityResult, ControllerResponse
from game_screen.game_screen import GameScreen
import screen_layout_config


PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "table_screen_fixture.json")
PLAY_AREA_FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "play_area_fixture.json")
DEBUG_OVERLAY_FIXTURE_PATH = os.path.join(PROJECT_DIR, "fixtures", "debug_overlay_fixture.json")


class TableScreen(GameScreen):
    """Первый черновой игровой экран стола."""

    SCREEN_SIZE = (1280, 720)
    BG_COLOR = (30, 30, 30)
    PLAY_AREA_INSET = 20
    SIDE_PLAYER_FRAME_SIZE = (260, 300)
    CENTER_PLAYER_FRAME_SIZE = (300, 260)
    PORTRAIT_FRAME_SIZE = (200, 200)
    DECK_FRAME_SIZE = (160, 160)
    DECK_FRAME_POSITION = (1071, PLAY_AREA_INSET)
    CARD_SLOT_FRAME_SIZE_RATIO = (0.72, 0.53)
    SIDE_HAND_SLOT_GUTTER = 80
    BOTTOM_PLAYER_HAND_PROBE_ENABLED = False
    BOTTOM_PLAYER_HAND_PROBE_COLOR = (255, 0, 0)
    BOTTOM_PLAYER_HAND_PROBE_BOTTOM_OFFSET = 50
    BOTTOM_PLAYER_HAND_ANCHOR_SLOT_FRAME_IDS = (
        "cards_slot_frame",
        "cards_slot_frame_2",
        "cards_slot_frame_3",
        "cards_slot_frame_4",
        "cards_slot_frame_5",
        "cards_slot_frame_6",
        "cards_slot_frame_7",
    )
    SCREEN_ID = "table_screen"
    FOREGROUND_GROUP_IDS = (
        "left_player",
        "right_player",
        "top_player",
        "bottom_player",
    )

    def __init__(self, group_store, game_controller):
        super().__init__(
            group_store=group_store,
            game_controller=game_controller,
            background_color=self.BG_COLOR,
        )

        self.create_frame("game_table", rect=(0, 0, 1280, 720))
        self.create_frame("play_area_frame", rect=self.rect_from_size(self.calculate_play_area_size())).set_rect_visibility(False)
        self.create_frame("cards_slot_frame", rect=self.rect_from_size(self.calculate_card_slot_frame_size())).set_rect_visibility(False)
        self.create_frame("deck_frame", rect=self.rect_from_size(self.DECK_FRAME_SIZE)).set_rect_visibility(False)

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
        self.layout_deck_frame()

        self.place_configured_groups_from_layout()

        cards_slot_activity = self.create_cards_slot_activity(self.get_screen_frame("cards_slot_frame"))
        deck_activity = DeckActivity(
            frame=self.get_screen_frame("deck_frame"),
            resource_manager=ResourceManager,
        )
        play_area_slots_activity = PlayAreaSlotsActivity(
            screen=self,
            play_area_frame=self.get_screen_frame("play_area_frame"),
            prototype_slot_frame=self.get_screen_frame("cards_slot_frame"),
            prototype_slot_activity=cards_slot_activity,
            slot_activity_factory=self.create_cards_slot_activity,
        )
        player_turn_activity = PlayerTurnActivity(
            play_area_slots_activity,
            freeze_slot_layout=self.freeze_play_area_slot_layout,
            release_slot_layout=self.release_play_area_slot_layout,
            remove_source_card=self.remove_hand_card,
            on_safe_point=self.handle_bottom_player_hand_safe_point,
        )
        card_deal_sequence_activity = CardDealSequenceActivity(
            source_geometry_provider=deck_activity.get_deal_source_screen_geometry,
            target_geometry_provider=self.get_start_game_target_screen_geometry,
            prepare_hands=self.prepare_card_deal_hands,
            reveal_card=self.reveal_card_deal,
            resource_manager=ResourceManager,
            on_safe_point=self.handle_bottom_player_hand_safe_point,
        )
        bottom_player_hand_activity = CardSelectionActivity(
            VisibleCardsHandDecorator(
                PlayerHandActivity(
                    frame=self.get_screen_frame("bottom_player_hand"),
                    resource_manager=ResourceManager,
                    card_count=0,
                    scale_factor=0.85,
                    orientation_degrees=0,
                    center_offset=(0, 0),
                    max_card_angle=60,
                    sector_angle_extra=30,
                    debug_fan_rect=True,
                    debug_fan_rect_color=(255, 128, 64),
                ),
                cards=(),
                resource_manager=ResourceManager,
            ),
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
            "deck_frame": deck_activity,
            "card_deal_sequence": card_deal_sequence_activity,
        }
        self._play_area_slot_layout_lock_depth = 0
        self._locked_play_area_slot_horizontal_local_bounds = None
        for activity_id, activity in activity_map.items():
            self.register_named_activity(activity_id, activity)
            self.add_activity(activity)
        self.fixture_paths = (FIXTURE_PATH, PLAY_AREA_FIXTURE_PATH, DEBUG_OVERLAY_FIXTURE_PATH)
        self._fixture_mtimes = {}
        self._fixture_check_elapsed = 0.0
        self._fixture_check_interval = 0.2
        self.controller_game_started = False
        self.controller_owned_visual_state = False
        self._bottom_player_hand_fan_area_signature = None
        self._bottom_player_hand_layout_lock_depth = 0
        self._bottom_player_hand_layout_release_pending = False
        self._bottom_player_hand_turn_rebuild_pending = False
        self._activity_result_watchers = []
        self.reload_fixture_if_changed(force=True)

    def start(self):
        super().start()
        self.start_controller_game()

    def start_controller_game(self):
        if self.controller_game_started or self.game_controller is None:
            return
        starter = getattr(self.game_controller, "start_game", None)
        if not callable(starter):
            return
        commands = self.get_controller_response_commands(starter())
        if commands:
            self.controller_owned_visual_state = True
        self.dispatch_visual_commands(commands)
        self.controller_game_started = True

    def create_cards_slot_activity(self, frame, index=0):
        _ = index
        return CardsSlotActivityDecorator(
            frame,
            resource_manager=ResourceManager,
            group_id_prefix=f"{frame.id}.cards",
        )

    def ensure_play_area_slot_frame(self, frame_id, prototype_frame):
        """Create or return a play-area slot frame owned by this screen."""
        if frame_id == prototype_frame.id:
            slot_frame = prototype_frame
        elif self.has_screen_frame(frame_id):
            slot_frame = self.get_screen_frame(frame_id)
        else:
            slot_frame = self.create_frame(
                frame_id,
                rect=prototype_frame.local_rect,
                parent_frame_id="play_area_frame",
            )
        slot_frame.set_rect_visibility(False)
        return slot_frame

    def ensure_play_area_slot_activity(self, frame_id, slot_frame, index):
        """Create or return a screen-owned slot activity for a play-area frame."""
        activity = self.get_named_activity(frame_id)
        if activity is not None:
            return activity
        activity = self.create_cards_slot_activity(slot_frame, index)
        self.register_named_activity(frame_id, activity)
        self.add_activity(activity)
        return activity

    def remove_play_area_slot_activity(self, frame_id, finish=True):
        """Remove a screen-owned slot activity by frame ID."""
        return self.unregister_named_activity(frame_id, finish=finish)

    def remove_play_area_slot_frame(self, frame_id, prototype_frame_id="cards_slot_frame"):
        """Remove a non-prototype play-area slot frame."""
        if frame_id == prototype_frame_id:
            return None
        return self.remove_screen_frame(frame_id)

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

    def layout_deck_frame(self):
        self.put_frame_in_frame(
            "deck_frame",
            "game_table",
            position=self.DECK_FRAME_POSITION,
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

    def get_play_area_slot_horizontal_local_bounds(self, play_area_frame):
        """Return frame-local horizontal bounds reserved for table card slots."""
        if self._locked_play_area_slot_horizontal_local_bounds is not None:
            return self._locked_play_area_slot_horizontal_local_bounds

        return self.calculate_play_area_slot_horizontal_local_bounds(play_area_frame)

    def freeze_play_area_slot_layout(self):
        """Keep slot geometry stable while a visual turn changes hand occupancy."""
        if self._play_area_slot_layout_lock_depth == 0:
            play_area_frame = self.get_screen_frame("play_area_frame")
            self._locked_play_area_slot_horizontal_local_bounds = (
                self.calculate_play_area_slot_horizontal_local_bounds(play_area_frame)
            )
        self._play_area_slot_layout_lock_depth += 1

    def release_play_area_slot_layout(self):
        """Allow slot geometry to reflect the settled visual hand layout."""
        if self._play_area_slot_layout_lock_depth <= 0:
            return
        self._play_area_slot_layout_lock_depth -= 1
        if self._play_area_slot_layout_lock_depth == 0:
            self._locked_play_area_slot_horizontal_local_bounds = None

    def calculate_play_area_slot_horizontal_local_bounds(self, play_area_frame):
        """Calculate stable frame-local slot bounds from fixed side anchors."""
        left_frame_rect = self.get_frame_screen_rect("left_player_frame")
        right_frame_rect = self.get_frame_screen_rect("right_player_frame")
        left_screen_x = left_frame_rect.right + self.SIDE_HAND_SLOT_GUTTER
        right_screen_x = right_frame_rect.left - self.SIDE_HAND_SLOT_GUTTER
        left_local_x = play_area_frame.to_local((left_screen_x, 0))[0]
        right_local_x = play_area_frame.to_local((right_screen_x, 0))[0]
        content_rect = play_area_frame.content_rect
        if left_local_x >= right_local_x:
            return None
        return (
            max(content_rect.left, left_local_x),
            min(content_rect.right, right_local_x),
        )

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

    def get_configured_group_placements(self):
        return screen_layout_config.get_screen_group_placements(self.SCREEN_ID)

    def place_configured_groups_from_layout(self):
        for group_id, placement in self.get_configured_group_placements().items():
            if not isinstance(placement, dict):
                continue
            frame_id = placement.get("frame_id")
            if not frame_id or not self.has_screen_frame(frame_id):
                continue
            position = placement.get("position", (0, 0))
            self.put_configured_group(group_id, frame_id, position=self.normalize_fixture_position(position))

    def update(self, dt):
        self._fixture_check_elapsed += dt
        if self._fixture_check_elapsed >= self._fixture_check_interval:
            self._fixture_check_elapsed = 0.0
            self.reload_fixture_if_changed()
        self.configure_bottom_player_hand_fan_area()
        super().update(dt)
        self.rebuild_bottom_player_hand_if_ready()
        self.forward_activity_completion_results()
        self.forward_completed_turn_results()
        self.release_pending_bottom_player_hand_layout()

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

        self.draw_activity_generated_groups(screen)

        for activity in self.iter_active_activities():
            if hasattr(activity, "draw_debug_overlay"):
                activity.draw_debug_overlay(screen)
            elif hasattr(activity, "draw"):
                activity.draw(screen)

        for group_id in self.iter_midground_group_ids():
            self.draw_group_if_active(group_id, screen)

        for group_id in self.FOREGROUND_GROUP_IDS:
            self.draw_group_if_active(group_id, screen)

        self.draw_bottom_player_hand_probe(screen)

        for frame in self.iter_root_frames():
            frame.draw_debug_tree(screen)

    def draw_group_if_active(self, group_id, screen):
        if self.is_group_active(group_id):
            self.get_group(group_id).draw(screen)

    def draw_activity_generated_groups(self, screen):
        for group in self.iter_activity_generated_groups():
            group.draw(screen)

    def iter_midground_group_ids(self):
        excluded = {"table_group", *self.FOREGROUND_GROUP_IDS}
        return tuple(group_id for group_id in self.active_group_ids if group_id not in excluded)

    def iter_activity_generated_groups(self):
        seen_group_ids = set()
        groups = []
        for activity in self.iter_active_activities():
            if self.should_hide_activity_generated_groups(activity):
                continue
            group_iterator = getattr(activity, "iter_groups_in_draw_order", None)
            if not callable(group_iterator):
                group_iterator = getattr(activity, "iter_generated_groups", None)
            if not callable(group_iterator):
                continue
            for group in group_iterator():
                if group.id in seen_group_ids:
                    continue
                seen_group_ids.add(group.id)
                groups.append(group)
        return tuple(groups)

    def should_hide_activity_generated_groups(self, activity):
        if not self.BOTTOM_PLAYER_HAND_PROBE_ENABLED:
            return False
        return activity is self.get_named_activity("bottom_player_hand")

    def draw_bottom_player_hand_probe(self, screen):
        if not self.BOTTOM_PLAYER_HAND_PROBE_ENABLED:
            return
        probe_rect = self.calculate_bottom_player_hand_available_screen_rect()
        if probe_rect.width <= 0 or probe_rect.height <= 0:
            return
        pygame.draw.rect(screen, self.BOTTOM_PLAYER_HAND_PROBE_COLOR, probe_rect)

    def calculate_bottom_player_hand_available_screen_rect(self):
        """Return the legacy interactive screen-space corridor for the bottom hand.

        This is the authoritative layout input for the bottom player's fan.
        It may depend only on stable frame geometry:
        - bottom player hand frame;
        - bottom player portrait frame;
        - legacy anchor slot frames that shape the original corridor.

        Dynamic hand occupancy, generated card groups, and extra slot frames
        outside that anchor set must not change this rect.
        """
        hand_frame = self.get_screen_frame("bottom_player_hand")
        hand_rect = hand_frame.rect.copy()
        side_slot_bounds = self.calculate_side_play_area_slot_screen_bounds()
        if side_slot_bounds is None:
            return hand_rect

        left, side_slot_bottom, right = side_slot_bounds
        central_slot_bottom = self.calculate_central_play_area_slots_bottom()
        top = central_slot_bottom if central_slot_bottom is not None else side_slot_bottom
        width = max(0, right - left)
        center_x = self.get_screen_frame("bottom_player_portrait").rect.centerx
        return pygame.Rect(
            int(round(center_x - width / 2)),
            top,
            width,
            max(
                0,
                self.get_screen_frame("bottom_player_portrait").rect.centery
                + self.BOTTOM_PLAYER_HAND_PROBE_BOTTOM_OFFSET
                - top,
            ),
        )

    def configure_bottom_player_hand_fan_area(self):
        activity = self.find_nested_activity_with_method(
            self.get_named_activity("bottom_player_hand"),
            "set_fan_area_local_rect",
        )
        if activity is None:
            return
        if self._bottom_player_hand_layout_lock_depth > 0:
            return
        signature = self.get_bottom_player_hand_fan_area_signature()
        if signature == self._bottom_player_hand_fan_area_signature:
            return
        screen_rect = self.calculate_bottom_player_hand_available_screen_rect()
        local_rect = self.screen_rect_to_frame_local_rect(
            screen_rect,
            self.get_screen_frame("bottom_player_hand"),
        )
        activity.set_fan_area_local_rect(local_rect)
        self._bottom_player_hand_fan_area_signature = signature

    def freeze_bottom_player_hand_layout(self):
        self._bottom_player_hand_layout_lock_depth += 1
        return self._bottom_player_hand_layout_lock_depth

    def request_bottom_player_hand_layout_release(self):
        if self._bottom_player_hand_layout_lock_depth <= 0:
            return False
        self._bottom_player_hand_layout_release_pending = True
        return True

    def release_pending_bottom_player_hand_layout(self):
        if not self._bottom_player_hand_layout_release_pending:
            return False
        if self.has_blocking_visual_activity():
            return False
        self._bottom_player_hand_layout_lock_depth = 0
        self._bottom_player_hand_layout_release_pending = False
        self._bottom_player_hand_fan_area_signature = None
        self.configure_bottom_player_hand_fan_area()
        return True

    def get_bottom_player_hand_fan_area_signature(self):
        """Return stable inputs that are allowed to relayout the bottom fan."""
        return (
            tuple(self.get_frame_screen_rect("bottom_player_hand")),
            tuple(self.get_frame_screen_rect("bottom_player_portrait")),
            tuple(tuple(rect) for rect in self.get_bottom_hand_anchor_slot_frame_screen_rects()),
        )

    @staticmethod
    def find_nested_activity_with_method(activity, method_name):
        while activity is not None:
            if callable(getattr(activity, method_name, None)):
                return activity
            activity = getattr(activity, "hand_activity", None)
        return None

    @staticmethod
    def screen_rect_to_frame_local_rect(screen_rect, frame):
        left, top = frame.to_local(screen_rect.topleft)
        right, bottom = frame.to_local(screen_rect.bottomright)
        return pygame.Rect(left, top, max(0, right - left), max(0, bottom - top))

    def calculate_lower_play_area_slot_screen_bounds(self):
        return self.calculate_side_play_area_slot_screen_bounds()

    def calculate_side_play_area_slot_screen_bounds(self):
        slot_rects = self.get_bottom_hand_anchor_slot_frame_screen_rects()
        if not slot_rects:
            return None

        hand_center_x = self.get_screen_frame("bottom_player_hand").rect.centerx
        left_slots = [rect for rect in slot_rects if rect.centerx < hand_center_x]
        right_slots = [rect for rect in slot_rects if rect.centerx > hand_center_x]
        if not left_slots or not right_slots:
            return None

        left_boundary_slot = min(left_slots, key=lambda rect: rect.centerx)
        right_boundary_slot = max(right_slots, key=lambda rect: rect.centerx)
        return (
            left_boundary_slot.right,
            max(left_boundary_slot.bottom, right_boundary_slot.bottom),
            right_boundary_slot.left,
        )

    def calculate_central_play_area_slots_bottom(self):
        slot_rects = self.get_bottom_hand_anchor_slot_frame_screen_rects()
        if len(slot_rects) < 3:
            return None

        play_area_center_x = self.get_screen_frame("play_area_frame").rect.centerx
        central_slots = sorted(
            slot_rects,
            key=lambda rect: abs(rect.centerx - play_area_center_x),
        )[:3]
        return max(rect.bottom for rect in central_slots)

    def calculate_play_area_slot_screen_bounds(self):
        slot_rects = self.get_play_area_slot_frame_screen_rects()
        if not slot_rects:
            return None
        return slot_rects[0].unionall(slot_rects[1:])

    def get_play_area_slot_screen_rects(self):
        """Compatibility alias for stable slot Frame rects."""
        return self.get_play_area_slot_frame_screen_rects()

    def get_play_area_slot_frame_screen_rects(self):
        """Return stable screen-space rects for play-area slot Frames."""
        return [
            self.get_frame_screen_rect(activity_id)
            for activity_id, _activity in self.iter_named_activities()
            if self.is_play_area_slot_frame_id(activity_id) and self.has_screen_frame(activity_id)
        ]

    def get_bottom_hand_anchor_slot_frame_screen_rects(self):
        """Return only the slot frames that define the legacy bottom-hand corridor."""
        return [
            self.get_frame_screen_rect(frame_id)
            for frame_id in self.BOTTOM_PLAYER_HAND_ANCHOR_SLOT_FRAME_IDS
            if self.has_screen_frame(frame_id)
        ]

    def get_play_area_slot_content_screen_rects(self):
        """Return dynamic card bounds inside play-area slots for debug/inspection only."""
        rects = []
        for activity_id, activity in self.iter_named_activities():
            if not self.is_play_area_slot_frame_id(activity_id):
                continue
            if not hasattr(activity, "get_cards_content_screen_rect"):
                continue
            rects.append(activity.get_cards_content_screen_rect())
        return rects

    @staticmethod
    def is_play_area_slot_frame_id(frame_id):
        return frame_id == "cards_slot_frame" or frame_id.startswith("cards_slot_frame_")

    def dispatch_visual_command(self, command):
        """Handle table-specific visual commands after controller decisions."""
        command_type = self.get_command_value(command, "type")
        if command_type == "start_player_turn":
            payload = self.get_command_value(command, "payload", {}) or {}
            return self.start_player_turn_from_command(payload.get("turn_context", {}), command)
        if command_type == "deck.set_trump":
            payload = self.get_command_value(command, "payload", {}) or {}
            return self.set_deck_trump_from_command(payload)
        if command_type == "deal.initial":
            payload = self.get_command_value(command, "payload", {}) or {}
            return self.start_initial_deal_from_command(payload, command)
        if command_type == "table.take":
            payload = self.get_command_value(command, "payload", {}) or {}
            return self.start_take_table_from_command(payload, command)
        if command_type == "table.discard":
            payload = self.get_command_value(command, "payload", {}) or {}
            return self.start_discard_table_from_command(payload, command)
        if command_type == "turn.prompt":
            payload = self.get_command_value(command, "payload", {}) or {}
            self.last_turn_prompt = dict(payload)
            return None
        return super().dispatch_visual_command(command)

    def dispatch_visual_commands(self, visual_commands):
        for command in visual_commands or ():
            self.dispatch_visual_command(command)

    def set_deck_trump_from_command(self, payload):
        deck_activity = self.get_named_activity("deck_frame")
        setter = getattr(deck_activity, "set_trump_resource_key", None)
        deck_count_setter = getattr(deck_activity, "set_deck_count", None)
        resource_key = (payload or {}).get("resource_key")
        if callable(setter) and resource_key:
            setter(resource_key)
        deck_count = (payload or {}).get("deck_count")
        if callable(deck_count_setter) and deck_count is not None:
            return deck_count_setter(deck_count)
        return None

    def sync_deck_activity_from_state_view(self, state_view):
        if not isinstance(state_view, dict):
            return None
        deck_count = state_view.get("deck_count")
        if deck_count is None:
            return None
        deck_activity = self.get_named_activity("deck_frame")
        setter = getattr(deck_activity, "set_deck_count", None)
        if callable(setter):
            return setter(deck_count)
        return None

    def get_controller_response_commands(self, response):
        commands = GameScreen.get_controller_response_commands(response)
        state_view = getattr(response, "state_view", None) if isinstance(response, ControllerResponse) else None
        self.sync_deck_activity_from_state_view(state_view)
        return commands

    def start_initial_deal_from_command(self, payload, command=None):
        activity = self.get_named_activity("card_deal_sequence")
        starter = getattr(activity, "start_deal", None)
        if not callable(starter):
            return None
        started = starter(payload or {})
        if started:
            self.register_activity_result_watcher(
                activity=activity,
                result=ActivityResult(
                    type="deal.completed",
                    source="card_deal_sequence",
                    command_id=getattr(command, "command_id", None),
                ),
                completion_check=lambda watched_activity: (
                    not getattr(watched_activity, "sequence_active", False)
                    and getattr(watched_activity, "current_action", None) is None
                ),
            )
        return started

    def get_current_table_cards(self):
        result = []
        slots = self.get_play_area_slots_activity().slot_activities
        for slot_id, slot in slots.items():
            for index, key in enumerate(slot.card_resource_keys):
                result.append(
                    {
                        "slot_id": slot_id,
                        "resource_key": key,
                        "geometry": slot.get_card_screen_geometry(index),
                    }
                )
        return result

    def set_current_table_cards(self, table_slots):
        self.clear_play_area_slot_cards()
        slots = self.get_play_area_slots_activity().slot_activities
        for slot_id, cards in (table_slots or {}).items():
            if slot_id in slots:
                slots[slot_id].set_cards(cards, force=True)

    def remove_current_table_card(self, card):
        slots = self.get_play_area_slots_activity().slot_activities
        slot = slots[card["slot_id"]]
        cards = list(slot.card_resource_keys)
        if card["resource_key"] in cards:
            cards.remove(card["resource_key"])
        slot.set_cards(cards, force=True)

    def register_activity_result_watcher(self, activity, result, completion_check=None):
        if activity is None:
            return
        if not hasattr(self, "_activity_result_watchers"):
            self._activity_result_watchers = []
        if completion_check is None:
            completion_check = lambda watched_activity: callable(getattr(watched_activity, "is_finished", None)) and watched_activity.is_finished()
        self._activity_result_watchers.append(
            {
                "activity": activity,
                "result": result,
                "completion_check": completion_check,
            }
        )

    def forward_activity_completion_results(self):
        pending_watchers = []
        completed_results = []
        for watcher in self._activity_result_watchers:
            activity = watcher["activity"]
            completion_check = watcher["completion_check"]
            try:
                completed = bool(completion_check(activity))
            except Exception:
                completed = False
            if completed:
                completed_results.append(watcher["result"])
            else:
                pending_watchers.append(watcher)
        self._activity_result_watchers = pending_watchers
        for result in completed_results:
            if result.type in {"table.take.completed", "table.discard.completed", "deal.completed"}:
                self.request_bottom_player_hand_layout_release()
            commands = self.forward_activity_result_to_controller(result)
            self.dispatch_visual_commands(commands)

    def start_take_table_from_command(self, payload, command=None):
        defender_id = payload.get("defender_id")
        table_slots = payload.get("table_slots", {})
        cards_before = tuple(payload.get("cards_before", ()))
        self.set_current_table_cards(table_slots)
        activity = TakeTableActivity(
            self.get_current_table_cards,
            self.set_current_table_cards,
            self.remove_current_table_card,
            self.prepare_card_deal_hands,
            self.get_start_game_target_screen_geometry,
            self.reveal_card_deal,
            self.clear_play_area_slot_cards,
            ResourceManager,
            0.26,
            on_safe_point=self.handle_bottom_player_hand_safe_point,
        )
        self.add_activity(activity)
        started = activity.start_take_plan(
            (
                {
                    "defender_id": defender_id,
                    "cards_before": cards_before,
                    "table_slots": table_slots,
                },
            ),
            0.0,
        )
        if started:
            self.register_activity_result_watcher(
                activity=activity,
                result=ActivityResult(
                    type="table.take.completed",
                    source="take_table",
                    command_id=getattr(command, "command_id", None),
                ),
            )
        return started

    def start_discard_table_from_command(self, payload, command=None):
        table_slots = payload.get("table_slots", {})
        self.set_current_table_cards(table_slots)
        activity = DiscardTableActivity(
            self.get_current_table_cards,
            self.set_current_table_cards,
            self.remove_current_table_card,
            self.clear_play_area_slot_cards,
            ResourceManager,
            0.5,
            45,
        )
        self.add_activity(activity)
        started = activity.start_discard(table_slots, 0.0)
        if started:
            self.register_activity_result_watcher(
                activity=activity,
                result=ActivityResult(
                    type="table.discard.completed",
                    source="discard_table",
                    command_id=getattr(command, "command_id", None),
                ),
            )
        return started

    def has_blocking_visual_activity(self):
        for activity in self.iter_active_activities():
            if getattr(activity, "turn_active", False):
                return True
            if getattr(activity, "sequence_active", False):
                return True
            if getattr(activity, "plan_active", False):
                return True
            if getattr(activity, "slot_layout_release_pending", False):
                return True
            current_action = getattr(activity, "current_action", None)
            if current_action is not None:
                return True
            animations = getattr(activity, "animations", None)
            if animations and any(not animation.is_finished() for animation in animations):
                return True
        return False

    def get_start_game_target_screen_geometry(self, target_activity_id, hand_index=None):
        if hand_index is not None:
            projected = self.find_nested_activity_with_method(
                self.get_named_activity(target_activity_id),
                "get_projected_card_screen_geometry",
            )
            if projected is not None:
                return projected.get_projected_card_screen_geometry(hand_index)
            hand = self.find_nested_activity_with_method(
                self.get_named_activity(target_activity_id),
                "get_prepared_card_screen_geometry",
            )
            if hand is not None:
                return hand.get_prepared_card_screen_geometry(hand_index)
        frame = self.get_screen_frame(target_activity_id)
        deck_activity = self.get_named_activity("deck_frame")
        source_geometry = deck_activity.get_deal_source_screen_geometry()
        return {"center": frame.rect.center, "size": source_geometry["size"]}

    def prepare_card_deal_hands(self, hands_before_deal, cards_to_deal):
        for player_id in set(hands_before_deal) | set(cards_to_deal):
            before = tuple(hands_before_deal.get(player_id, ()))
            incoming = tuple(cards_to_deal.get(player_id, ()))
            if player_id == "bottom_player_hand":
                hand = self.find_nested_activity_with_method(
                    self.get_named_activity(player_id),
                    "prepare_incremental_cards",
                )
                if hand is not None:
                    hand.prepare_incremental_cards(before, incoming)
                    continue
            hand = self.find_nested_activity_with_method(self.get_named_activity(player_id), "prepare_cards")
            if hand is None:
                raise RuntimeError(f"{player_id} does not support prepared cards")
            hand.prepare_cards((*before, *incoming), revealed_count=len(before))

    def reveal_card_deal(self, player_id, resource_key, hand_index):
        if player_id == "bottom_player_hand":
            hand = self.find_nested_activity_with_method(
                self.get_named_activity(player_id),
                "append_revealed_card",
            )
            if hand is not None:
                return hand.append_revealed_card(resource_key)
        hand = self.find_nested_activity_with_method(self.get_named_activity(player_id), "reveal_card")
        if hand is None:
            raise RuntimeError(f"{player_id} does not support card reveal")
        hand.reveal_card(hand_index)

    def get_play_area_slots_activity(self):
        activity = self.get_named_activity("play_area_frame")
        return getattr(activity, "play_area_slots_activity", activity)

    def remove_hand_card(self, turn_context):
        """Remove the visual source card from the hand that owns the current turn."""
        group_id = (turn_context or {}).get("group_id")
        player_id = (turn_context or {}).get("player_id") or (turn_context or {}).get("frame_id")
        if not group_id or not player_id:
            return False
        hand_activity = self.get_named_activity(player_id)
        extractor = getattr(hand_activity, "extract_card_by_group_id", None)
        remover = getattr(hand_activity, "remove_card_by_group_id", None)
        if player_id == "bottom_player_hand" and callable(extractor):
            removed = bool(extractor(group_id))
        else:
            removed = bool(remover(group_id)) if callable(remover) else False
        if removed and player_id == "bottom_player_hand":
            self.freeze_bottom_player_hand_layout()
            self._bottom_player_hand_turn_rebuild_pending = True
        return removed

    def rebuild_bottom_player_hand_after_turn(self):
        hand_activity = self.get_named_activity("bottom_player_hand")
        rebuilder = getattr(hand_activity, "rebuild_layout", None)
        rebuilt = bool(rebuilder()) if callable(rebuilder) else False
        if rebuilt:
            self._bottom_player_hand_turn_rebuild_pending = False
        return rebuilt

    def handle_bottom_player_hand_safe_point(self, safe_point, payload=None):
        payload = payload or {}
        player_id = payload.get("player_id")
        if safe_point == "turn.played.safe_point":
            return self.rebuild_bottom_player_hand_after_turn()
        if safe_point == "deal.step.safe_point" and player_id == "bottom_player_hand":
            hand_activity = self.get_named_activity("bottom_player_hand")
            has_pending = getattr(hand_activity, "has_pending_layout_rebuild", None)
            if callable(has_pending) and has_pending():
                return self.rebuild_bottom_player_hand_after_turn()
            return False
        if safe_point == "table.take.safe_point" and player_id == "bottom_player_hand":
            return self.rebuild_bottom_player_hand_after_turn()
        return False

    def rebuild_bottom_player_hand_if_ready(self):
        hand_activity = self.get_named_activity("bottom_player_hand")
        has_pending = getattr(hand_activity, "has_pending_layout_rebuild", None)
        if not self._bottom_player_hand_turn_rebuild_pending and (
            not callable(has_pending) or not has_pending()
        ):
            return False
        turn_activity = self.get_named_activity("play_area_frame")
        if turn_activity is not None:
            if getattr(turn_activity, "turn_active", False):
                return False
            if getattr(turn_activity, "current_action", None) is not None:
                return False
            if getattr(turn_activity, "slot_layout_release_pending", False):
                return False
        return self.rebuild_bottom_player_hand_after_turn()

    def remove_bottom_player_hand_card(self, turn_context):
        """Remove the landed card from the lower hand's visual-only groups."""
        group_id = (turn_context or {}).get("group_id")
        if not group_id:
            return False
        hand_activity = self.get_named_activity("bottom_player_hand")
        remover = getattr(hand_activity, "remove_card_by_group_id", None)
        return bool(remover(group_id)) if callable(remover) else False

    def clear_play_area_slot_cards(self):
        activity = self.get_play_area_slots_activity()
        clearer = getattr(activity, "clear_slot_cards", None)
        if callable(clearer):
            clearer()

    def get_play_area_slot_ids_by_position(self):
        slot_ids = [
            activity_id
            for activity_id, _activity in self.iter_named_activities()
            if self.is_play_area_slot_frame_id(activity_id) and self.has_screen_frame(activity_id)
        ]
        return tuple(
            sorted(
                slot_ids,
                key=lambda slot_id: (
                    self.get_screen_frame(slot_id).rect.centery,
                    self.get_screen_frame(slot_id).rect.centerx,
                ),
            )
        )

    def start_player_turn_from_command(self, turn_context, command=None):
        activity = self.get_named_activity("play_area_frame")
        if activity is None:
            return None
        turn_context = self.resolve_turn_context(turn_context or {})
        if getattr(command, "command_id", None):
            turn_context["command_id"] = command.command_id
        if hasattr(activity, "start_turn"):
            return activity.start_turn(turn_context)
        return activity.start()

    def resolve_turn_context(self, turn_context):
        context = dict(turn_context or {})
        if context.get("source_screen_geometry") and context.get("group_id"):
            return context
        player_id = context.get("player_id")
        card_id = context.get("card_id") or context.get("resource_key")
        if not player_id or not card_id:
            return context
        hand_activity = self.find_nested_activity_with_method(
            self.get_named_activity(player_id),
            "get_card_selection_context",
        )
        if hand_activity is None:
            return context
        geometry_owner = self.find_nested_activity_with_method(
            self.get_named_activity(player_id),
            "get_group_card_screen_geometry",
        )
        if geometry_owner is None or not hasattr(hand_activity, "iter_generated_groups"):
            return context
        generated_groups = tuple(hand_activity.iter_generated_groups())
        for group in generated_groups:
            card_context = hand_activity.get_card_selection_context(group)
            if not card_context:
                continue
            if card_context.get("card_id") != card_id and card_context.get("resource_key") != card_id:
                continue
            context.update(card_context)
            context["source_screen_geometry"] = geometry_owner.get_group_card_screen_geometry(group)
            return context
        if generated_groups:
            fallback_group = generated_groups[-1]
            fallback_context = hand_activity.get_card_selection_context(fallback_group) or {}
            context.update(fallback_context)
            context["card_id"] = card_id
            context["resource_key"] = card_id
            context["source_screen_geometry"] = geometry_owner.get_group_card_screen_geometry(fallback_group)
        return context

    def forward_completed_turn_results(self):
        activity = self.get_named_activity("play_area_frame")
        consumer = getattr(activity, "consume_completed_turn_context", None)
        if not callable(consumer):
            return
        completed_context = consumer()
        if not completed_context:
            return
        self.rebuild_bottom_player_hand_after_turn()
        commands = self.forward_activity_result_to_controller(
            ActivityResult(
                type="turn.completed",
                source="play_area_frame",
                command_id=completed_context.get("command_id"),
                payload={"turn_context": completed_context},
            )
        )
        self.dispatch_visual_commands(commands)

    def reload_fixture_if_changed(self, force=False):
        """Hot reload dev fixture and apply it to screen activities."""
        if self.controller_owned_visual_state and not force:
            return
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
        if "debug" in fixture:
            debug_overlay.configure(fixture["debug"])

        if "card_counts" in fixture:
            self.apply_card_counts_fixture(fixture["card_counts"])

        if "gui" in fixture:
            self.apply_gui_fixture_tree(fixture["gui"])

        frames = fixture.get("frames", {})
        for frame_id, frame_fixture in frames.items():
            self.apply_frame_fixture(frame_id, frame_fixture)

        groups = fixture.get("groups", {})
        for group_id, group_fixture in groups.items():
            self.apply_group_fixture(group_id, group_fixture)

        activities = fixture.get("activities", {})
        for activity_id, activity in self.iter_named_activities():
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
