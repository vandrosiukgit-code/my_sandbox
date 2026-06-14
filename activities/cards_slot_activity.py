"""Cards slot decorator activity for the central play area."""

import pygame

from activities.visible_cards_hand_activity import VisibleCardsHandDecorator
from game_screen import debug_overlay


class CardsSlotActivityDecorator(VisibleCardsHandDecorator):
    """Temporary table slot decorator; Controller will provide real table cards."""

    def __init__(self, hand_activity, cards=None, resource_manager=None, max_cards=2):
        self.validate_slot_hand_activity(hand_activity)
        super().__init__(
            hand_activity,
            cards=cards,
            resource_manager=resource_manager,
            max_cards=max_cards,
        )
        self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)
        self.slot_content_scaled_local_rect = pygame.Rect(0, 0, 0, 0)
        self._last_slot_layout_signature = None
        self.card_visual_states = {}
        self.card_original_frames_by_group_id = {}

    @staticmethod
    def validate_slot_hand_activity(hand_activity):
        frame = getattr(hand_activity, "frame", None)
        if frame is None or not callable(getattr(frame, "move_group_local", None)):
            raise TypeError("CardsSlotActivityDecorator requires hand_activity.frame.move_group_local()")

    def apply_fixture(self, fixture):
        super().apply_fixture(fixture)
        card_visual_state = self.get_fixture_card_visual_state(fixture)
        if card_visual_state is not None:
            self.set_all_card_visual_states(card_visual_state)
        self.normalize_slot_content(force=True)

    def update(self, dt):
        super().update(dt)
        self.normalize_slot_content()

    def set_cards(self, cards, force=False):
        super().set_cards(cards, force=force)
        self.card_visual_states = {}
        self.card_original_frames_by_group_id = {}
        self.normalize_slot_content(force=True)

    def set_card_visual_state(self, card_index, state):
        """Set one slot card visual state without changing slot geometry."""
        group = self.get_generated_group(card_index)
        state = self.normalize_card_visual_state(state)
        self.card_visual_states[int(card_index)] = state
        self.ensure_card_original_frames(group)
        if state == "hidden":
            self.apply_transparent_card_surface(group)
        elif state == "visible":
            self.restore_card_surface(group)
        else:
            raise ValueError(f"Unsupported card visual state: {state!r}")

    def set_all_card_visual_states(self, state):
        """Set the visual state for every generated card in this slot."""
        for index, _group in enumerate(self.iter_generated_groups()):
            self.set_card_visual_state(index, state)

    def place_player_card(self, card_data):
        """Show a played player card in one existing slot card group."""
        resource_key = self.get_card_data_resource_key(card_data)
        card_index = self.get_card_data_slot_index(card_data)
        self.set_all_card_visual_states("hidden")
        self.set_card_resource(card_index, resource_key)
        self.set_card_visual_state(card_index, "visible")
        self.normalize_slot_content(force=True)

    def set_card_resource(self, card_index, resource_key):
        """Replace one slot card resource without removing its visual group."""
        index = int(card_index)
        group = self.get_generated_group(index)
        frames = self.get_resource_frames(resource_key)
        self.card_resource_keys = tuple(
            resource_key if key_index == index else key
            for key_index, key in enumerate(self.card_resource_keys)
        )
        self.card_original_frames_by_group_id[group.id] = tuple(frame.copy() for frame in frames)
        if hasattr(self.hand_activity, "group_resource_keys"):
            self.hand_activity.group_resource_keys[group.id] = resource_key
        if hasattr(self.hand_activity, "group_card_ids"):
            self.hand_activity.group_card_ids[group.id] = self.get_slot_card_id(index, resource_key)
        if hasattr(self.hand_activity, "group_base_frames"):
            self.hand_activity.group_base_frames[group.id] = tuple(frame.copy() for frame in frames)
        group.set_primary_layer_frames([frame.copy() for frame in frames], position=(0, 0))

    def get_resource_frames(self, resource_key):
        if not resource_key:
            raise ValueError("CardsSlotActivityDecorator requires card resource_key")
        if self.resource_manager is None:
            raise RuntimeError("CardsSlotActivityDecorator requires resource_manager")
        frames = self.resource_manager.get_frames(resource_key)
        if not frames:
            raise KeyError(f"Card resource has no frames: {resource_key!r}")
        return tuple(frame.copy() for frame in frames)

    def get_card_screen_state(self, card_index):
        """Return the screen rect and original visible surface for a slot card."""
        group = self.get_generated_group(card_index)
        frames = self.ensure_card_original_frames(group)
        surface = frames[0] if frames else None
        if surface is not None:
            surface = group.get_scaled_surface(surface).copy()
        return self.get_group_primary_layer_screen_rect(group), surface

    def get_card_screen_geometry(self, card_index):
        """Return screen-space center/size/angle geometry for a slot card."""
        group = self.get_generated_group(card_index)
        getter = getattr(self.hand_activity, "get_group_card_screen_geometry", None)
        if callable(getter):
            return getter(group)
        rect = self.get_group_primary_layer_screen_rect(group)
        return {
            "center": tuple(rect.center),
            "size": tuple(rect.size),
            "angle_degrees": 0.0,
        }

    def get_player_turn_target_screen_geometry(self, _turn_context=None):
        """Return the default screen-space landing geometry for player turn intent."""
        groups = tuple(self.iter_generated_groups())
        if groups:
            return self.get_card_screen_geometry(0)

        rect = self.get_slot_content_screen_rect()
        if rect.width <= 0 or rect.height <= 0:
            rect = self.hand_activity.frame.rect.copy()
        return {
            "center": tuple(rect.center),
            "size": tuple(rect.size),
            "angle_degrees": 0.0,
        }

    def get_card_resource_key_for_index(self, card_index):
        """Return the resource key used by one generated slot card."""
        return self.get_card_resource_key(int(card_index))

    @staticmethod
    def get_card_data_resource_key(card_data):
        data = card_data or {}
        return data.get("resource_key") or data.get("card_id")

    @staticmethod
    def get_card_data_slot_index(card_data):
        data = card_data or {}
        for key in ("slot_card_index", "target_card_index", "card_index"):
            if key in data:
                return int(data[key])
        return 0

    @staticmethod
    def get_slot_card_id(card_index, resource_key):
        return f"slot.card.{int(card_index)}:{resource_key}"

    def get_generated_group(self, card_index):
        groups = tuple(self.iter_generated_groups())
        index = int(card_index)
        if index < 0 or index >= len(groups):
            raise IndexError(f"Slot card index is out of range: {card_index!r}")
        return groups[index]

    def ensure_card_original_frames(self, group):
        frames = self.card_original_frames_by_group_id.get(group.id)
        if frames is None:
            frames = tuple(frame.copy() for frame in group.get_primary_layer_frames())
            self.card_original_frames_by_group_id[group.id] = frames
        return frames

    def apply_transparent_card_surface(self, group):
        frames = self.ensure_card_original_frames(group)
        if not frames:
            return
        width, height = frames[0].get_size()
        transparent_surface = pygame.Surface((width, height), pygame.SRCALPHA)
        group.set_primary_layer_frames([transparent_surface], position=(0, 0))

    def restore_card_surface(self, group):
        frames = self.ensure_card_original_frames(group)
        if frames:
            group.set_primary_layer_frames([frame.copy() for frame in frames], position=(0, 0))

    @staticmethod
    def normalize_card_visual_state(state):
        if isinstance(state, dict):
            state = state.get("state", state.get("visibility", "visible"))
        state = str(state).strip().lower()
        aliases = {
            "show": "visible",
            "shown": "visible",
            "visible": "visible",
            "card": "visible",
            "hide": "hidden",
            "hidden": "hidden",
            "empty": "hidden",
            "transparent": "hidden",
        }
        return aliases.get(state, state)

    @staticmethod
    def get_fixture_card_visual_state(fixture):
        if not fixture:
            return None
        for key in ("card_visual_state", "card_visibility"):
            if key in fixture:
                return fixture[key]
        return None

    def get_slot_content_rect(self):
        """Return visible occupied card bounds in slot frame-local coordinates."""
        return self.get_slot_content_scaled_local_rect()

    def get_slot_content_unscaled_local_rect(self):
        """Return occupied card bounds before card scale is applied."""
        return self.slot_content_local_rect.copy()

    def get_slot_content_scaled_local_rect(self):
        """Return occupied card bounds after card scale is applied."""
        return self.slot_content_scaled_local_rect.copy()

    def get_slot_content_screen_rect(self):
        """Return occupied visible card bounds in screen coordinates."""
        bounds = self.calculate_generated_groups_screen_bounds()
        if bounds is None:
            return pygame.Rect(0, 0, 0, 0)
        return bounds

    def draw_debug_overlay(self, screen):
        if not debug_overlay.should_draw_activity_rect():
            return
        rect = self.get_slot_content_screen_rect()
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(screen, (255, 232, 64), rect, 2)

    def normalize_slot_content(self, force=False):
        """Compatibility alias for older callers."""
        signature = self.get_slot_layout_signature()
        if not force and signature == self._last_slot_layout_signature:
            return
        self.move_generated_groups_to_slot_origin()
        self._last_slot_layout_signature = self.get_slot_layout_signature()

    def get_slot_layout_signature(self):
        return tuple(
            (
                group.id,
                tuple(group.local_rect),
                1.0 if group.scale_factor is None else group.scale_factor,
            )
            for group in self.iter_generated_groups()
        )

    def move_generated_groups_to_slot_origin(self):
        """Move generated groups so their local bounds start at the slot origin."""
        bounds = self.calculate_generated_groups_local_bounds()
        if bounds is None:
            self.slot_content_local_rect = pygame.Rect(0, 0, 0, 0)
            self.slot_content_scaled_local_rect = pygame.Rect(0, 0, 0, 0)
            return

        for group in self.iter_generated_groups():
            rect = group.local_rect
            self.hand_activity.frame.move_group_local(
                group,
                (rect.x - bounds.x, rect.y - bounds.y),
            )

        self.slot_content_local_rect = pygame.Rect(0, 0, bounds.width, bounds.height)
        scaled_bounds = self.calculate_generated_groups_scaled_local_bounds()
        self.slot_content_scaled_local_rect = (
            scaled_bounds.copy()
            if scaled_bounds is not None
            else pygame.Rect(0, 0, 0, 0)
        )

    def calculate_generated_groups_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = self.get_group_slot_local_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_scaled_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = self.get_group_slot_scaled_local_rect(group)
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_screen_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = group.rect
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    @staticmethod
    def get_group_slot_local_rect(group):
        return group.local_rect.copy()

    @staticmethod
    def get_group_slot_scaled_local_rect(group):
        if hasattr(group, "get_scaled_local_rect"):
            return group.get_scaled_local_rect()
        return group.local_rect.copy()

    @staticmethod
    def get_group_primary_layer_screen_rect(group):
        layer = group.get_primary_layer()
        if hasattr(group, "get_layer_rect"):
            return group.get_layer_rect(layer).copy()
        return group.rect.copy()
