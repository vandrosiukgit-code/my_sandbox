"""Activity for cards placed on one central table slot."""

import pygame

from activities.base_activity import Activity
from activities import card_visibility
from activities import normalizers
from game_screen import debug_overlay
from group import Group


class CardsSlotActivityDecorator(Activity):
    """Own table-slot card groups without depending on hand fan activities."""

    DEFAULT_MAX_CARDS = 2
    DEFAULT_REFERENCE_CARD_COUNT = 9
    DEFAULT_MAX_TOTAL_ANGLE = 160.0

    def __init__(
        self,
        frame,
        cards=None,
        resource_manager=None,
        max_cards=DEFAULT_MAX_CARDS,
        group_id_prefix=None,
        scale_factor=0.7,
        spacing=(12, 0),
        center_offset=(0, 0),
        card_layer_name="card",
        default_resource_key="cards.6_of_clubs",
        default_slot_size=(146, 144),
    ):
        super().__init__(duration=0.0)
        self.frame = self.resolve_frame(frame)
        self.resource_manager = resource_manager
        self.max_cards = self.normalize_max_cards(max_cards)
        self.group_id_prefix = group_id_prefix or f"{self.frame.id}.cards"
        self.scale_factor = self.normalize_scale_factor(scale_factor)
        self.spacing = self.normalize_pair(spacing)
        self.center_offset = self.normalize_pair(center_offset)
        self.card_layer_name = card_layer_name
        self.default_resource_key = default_resource_key
        self.default_slot_size = self.normalize_pair(default_slot_size)
        self.card_resource_keys = self.limit_cards(self.normalize_cards(cards or ()))
        self.generated_groups = []
        self.card_visual_states = {}
        self.card_original_frames_by_group_id = {}
        self.card_source_sizes_by_resource_key = {}
        self.cards_content_local_rect = pygame.Rect(0, 0, 0, 0)
        self.cards_content_scaled_local_rect = pygame.Rect(0, 0, 0, 0)
        self._last_slot_layout_signature = None

    @staticmethod
    def resolve_frame(frame):
        if hasattr(frame, "content_rect") and callable(getattr(frame, "place_group_local", None)):
            return frame
        nested_frame = getattr(frame, "frame", None)
        if nested_frame is not None:
            return CardsSlotActivityDecorator.resolve_frame(nested_frame)
        raise TypeError("CardsSlotActivityDecorator requires Frame-like object")

    def start(self):
        if self.started:
            return
        super().start()
        self.sync_visual_groups()
        self.apply_slot_layout(force=True)

    def update(self, dt):
        _ = dt
        if not self.started:
            self.start()
            return
        self.apply_slot_layout()

    def apply_fixture(self, fixture):
        if not fixture:
            return
        if "scale_factor" in fixture:
            self.scale_factor = self.normalize_scale_factor(fixture["scale_factor"])
        elif "scale" in fixture:
            self.scale_factor = self.normalize_scale_factor(fixture["scale"])
        self.spacing = self.normalize_pair(fixture.get("spacing", self.spacing))
        self.center_offset = self.normalize_pair(fixture.get("center_offset", self.center_offset))

        cards = self.get_fixture_cards(fixture)
        if cards is not None:
            self.set_cards(cards, force=True)

        card_visual_state = self.get_fixture_card_visual_state(fixture)
        if card_visual_state is not None:
            self.set_all_card_visual_states(card_visual_state)
        self.apply_slot_layout(force=True)

    def set_cards(self, cards, force=False):
        next_keys = self.limit_cards(self.normalize_cards(cards))
        if not force and next_keys == self.card_resource_keys:
            return
        self.card_resource_keys = next_keys
        self.card_visual_states = {}
        self.sync_visual_groups()
        self.apply_slot_layout(force=True)

    def place_player_card(self, card_data):
        """Append or replace a played player card in this table slot."""
        resource_key = self.get_card_data_resource_key(card_data)
        card_index = self.get_card_data_slot_index(card_data)
        if card_index is None:
            card_index = len(self.card_resource_keys)
        if self.max_cards is not None:
            card_index = min(card_index, max(0, self.max_cards - 1))
        self.ensure_card_count(card_index + 1, fill_resource_key=resource_key)
        self.set_card_resource(card_index, resource_key)
        self.set_card_visual_state(card_index, "visible")
        self.apply_slot_layout(force=True)

    def ensure_card_count(self, card_count, fill_resource_key):
        if self.max_cards is not None:
            card_count = min(card_count, self.max_cards)
        if card_count <= len(self.card_resource_keys):
            return
        cards = list(self.card_resource_keys)
        cards.extend(fill_resource_key for _index in range(card_count - len(cards)))
        self.set_cards(tuple(cards), force=True)

    def sync_visual_groups(self):
        while len(self.generated_groups) < len(self.card_resource_keys):
            self.add_generated_group(len(self.generated_groups))
        while len(self.generated_groups) > len(self.card_resource_keys):
            group = self.generated_groups.pop()
            self.frame.remove_group(group.id)
            self.card_visual_states.pop(len(self.generated_groups), None)
            self.card_original_frames_by_group_id.pop(group.id, None)

        for index, resource_key in enumerate(self.card_resource_keys):
            group = self.generated_groups[index]
            if self.get_group_resource_key(group) != resource_key:
                self.set_card_resource(index, resource_key)

    def add_generated_group(self, index):
        resource_key = self.card_resource_keys[index]
        group = Group.create_group(
            f"{self.group_id_prefix}.{index}",
            ((self.card_layer_name, resource_key),),
            resource_manager=self.resource_manager,
        )
        group.card_resource_key = resource_key
        self.card_original_frames_by_group_id[group.id] = tuple(
            frame.copy()
            for frame in group.get_primary_layer_frames()
        )
        self.generated_groups.append(group)
        self.frame.place_group_local(group, (0, 0))
        return group

    def set_card_resource(self, card_index, resource_key):
        index = int(card_index)
        group = self.get_generated_group(index)
        frames = self.get_resource_frames(resource_key)
        self.card_resource_keys = tuple(
            resource_key if key_index == index else key
            for key_index, key in enumerate(self.card_resource_keys)
        )
        group.card_resource_key = resource_key
        self.card_original_frames_by_group_id[group.id] = tuple(frame.copy() for frame in frames)
        group.set_primary_layer_frames([frame.copy() for frame in frames], position=(0, 0))

    def set_card_visual_state(self, card_index, state):
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
        for index, _group in enumerate(self.iter_generated_groups()):
            self.set_card_visual_state(index, state)

    def get_card_screen_state(self, card_index):
        group = self.get_generated_group(card_index)
        frames = self.ensure_card_original_frames(group)
        surface = frames[0] if frames else None
        if surface is not None:
            surface = group.get_scaled_surface(surface).copy()
        return self.get_group_primary_layer_screen_rect(group), surface

    def get_card_screen_geometry(self, card_index):
        group = self.get_generated_group(card_index)
        rect = self.get_group_primary_layer_screen_rect(group)
        return {
            "center": tuple(rect.center),
            "size": tuple(rect.size),
            "angle_degrees": self.get_card_angle_degrees(int(card_index)),
        }

    def get_player_turn_target_screen_geometry(self, turn_context=None):
        card_index = self.get_card_data_slot_index(turn_context)
        groups = tuple(self.iter_generated_groups())
        if card_index is not None and 0 <= card_index < len(groups):
            return self.get_card_screen_geometry(card_index)
        return self.get_next_card_screen_geometry(turn_context)

    def get_next_card_screen_geometry(self, turn_context=None):
        index = self.get_card_data_slot_index(turn_context)
        if index is None:
            index = len(self.generated_groups)
        if self.max_cards is not None:
            index = min(index, max(0, self.max_cards - 1))
        layout_count = self.get_layout_card_count()
        resource_key = self.get_card_data_resource_key(turn_context) if turn_context else self.default_resource_key
        local_size = self.get_card_source_size(resource_key)
        angle_degrees = self.get_card_angle_degrees(index, layout_count)
        rotated_size = self.get_rotated_size(local_size, angle_degrees)
        group_scale = self.get_card_group_scale_factor(rotated_size, layout_count)
        local_rect = self.get_card_local_rect(index, rotated_size, count=layout_count, scale=group_scale)
        screen_center = self.project_scaled_local_rect_center(local_rect, scale=group_scale)
        return {
            "center": tuple(screen_center),
            "size": self.local_size_to_screen_size(rotated_size, scale=group_scale),
            "angle_degrees": angle_degrees,
        }

    def screen_size_to_unscaled_local_size(self, size):
        scale = self.get_effective_screen_scale()
        if scale == 0:
            return size
        return (
            max(1, int(round(size[0] / scale))),
            max(1, int(round(size[1] / scale))),
        )

    def get_default_card_screen_size(self):
        if self.generated_groups:
            return self.generated_groups[0].rect.size
        size = self.get_default_card_local_size()
        scale = self.get_effective_screen_scale()
        return (
            max(1, int(round(size[0] * scale))),
            max(1, int(round(size[1] * scale))),
        )

    def get_default_slot_size(self):
        return self.default_slot_size

    def get_default_card_local_size(self):
        return self.get_card_source_size(self.default_resource_key)

    def get_card_source_size(self, resource_key):
        if resource_key in self.card_source_sizes_by_resource_key:
            return self.card_source_sizes_by_resource_key[resource_key]
        frames = self.get_resource_frames(resource_key) if self.resource_manager is not None else ()
        if frames:
            size = frames[0].get_size()
            self.card_source_sizes_by_resource_key[resource_key] = size
            return size
        rect = self.frame.local_rect
        size = max(1, rect.width), max(1, rect.height)
        self.card_source_sizes_by_resource_key[resource_key] = size
        return size

    def get_effective_screen_scale(self):
        frame_scale = self.frame.get_content_screen_scale() if hasattr(self.frame, "get_content_screen_scale") else 1.0
        group_scale = self.scale_factor or 1.0
        return frame_scale * group_scale

    def apply_slot_layout(self, force=False):
        signature = self.get_slot_layout_signature()
        if not force and signature == self._last_slot_layout_signature:
            return
        layout_count = self.get_layout_card_count()
        for index, group in enumerate(self.generated_groups):
            frames = self.ensure_card_original_frames(group)
            if frames:
                base_surface = frames[0]
            else:
                base_surface = group.get_primary_layer_frames()[0]
            angle_degrees = self.get_card_angle_degrees(index, layout_count)
            resource_key = self.get_card_resource_key_for_index(index)
            base_size = self.get_card_source_size(resource_key)
            rotated_size = self.get_rotated_size(base_size, angle_degrees)
            group_scale = self.get_card_group_scale_factor(rotated_size, layout_count)
            surface = self.render_card_surface(base_surface, angle_degrees)
            group.set_primary_layer_frames([surface], position=(0, 0))
            group.set_scale_factor(group_scale)
            local_rect = self.get_card_local_rect(index, rotated_size, count=layout_count, scale=group_scale)
            group.set_local_rect(local_rect)
            self.frame.set_group_origin(group.id, group.local_rect.topleft)
        self.update_cards_content_rects()
        self._last_slot_layout_signature = self.get_slot_layout_signature()

    def get_card_local_rect(self, index, size, count=None, scale=None):
        width, height = int(size[0]), int(size[1])
        count = max(1, len(self.generated_groups) if count is None else int(count))
        scale = self.scale_factor if scale is None else scale
        scale = scale or 1.0
        scaled_width = width * scale
        scaled_height = height * scale
        step_x = self.spacing[0]
        total_width = scaled_width + step_x * max(0, count - 1)
        left = self.frame.content_rect.centerx - total_width / 2 + index * step_x + self.center_offset[0]
        left += self.get_card_slot_axis_offset(index, count)
        top = self.frame.content_rect.centery - scaled_height / 2 + self.center_offset[1]
        return pygame.Rect(int(round(left)), int(round(top)), width, height)

    def project_scaled_local_rect_center(self, local_rect, scale=None):
        scale = self.scale_factor if scale is None else scale
        scale = scale or 1.0
        local_center = (
            local_rect.x + local_rect.width * scale / 2,
            local_rect.y + local_rect.height * scale / 2,
        )
        return self.frame.to_screen(local_center)

    def get_card_group_scale_factor(self, rotated_size, count=None):
        configured_scale = self.scale_factor or 1.0
        count = self.get_layout_card_count() if count is None else max(1, int(count))
        width, height = max(1, int(rotated_size[0])), max(1, int(rotated_size[1]))
        available_width = max(1, self.frame.content_rect.width - self.spacing[0] * max(0, count - 1))
        available_height = max(1, self.frame.content_rect.height)
        fit_scale = min(available_width / width, available_height / height)
        return min(configured_scale, fit_scale)

    @staticmethod
    def get_card_slot_axis_offset(index, count):
        if count != 2:
            return 0
        return -10 if int(index) == 0 else 10

    def get_layout_card_count(self):
        if self.max_cards is not None:
            return max(1, self.max_cards)
        return max(1, len(self.generated_groups))

    def get_card_angle_degrees(self, index, count=None):
        count = self.get_layout_card_count() if count is None else max(1, int(count))
        if count <= 1:
            return 0.0
        occupied_angle = self.DEFAULT_MAX_TOTAL_ANGLE / self.DEFAULT_REFERENCE_CARD_COUNT * count
        angle_step = occupied_angle / count
        return -occupied_angle / 2 + angle_step / 2 + int(index) * angle_step

    @staticmethod
    def render_card_surface(surface, angle_degrees):
        return pygame.transform.rotate(surface, -angle_degrees)

    @staticmethod
    def get_rotated_size(size, angle_degrees):
        surface = pygame.Surface(size, pygame.SRCALPHA)
        return pygame.transform.rotate(surface, -angle_degrees).get_size()

    def local_size_to_screen_size(self, size, scale=None):
        if scale is None:
            scale = self.get_effective_screen_scale()
        else:
            frame_scale = self.frame.get_content_screen_scale() if hasattr(self.frame, "get_content_screen_scale") else 1.0
            scale *= frame_scale
        return (
            max(1, int(round(size[0] * scale))),
            max(1, int(round(size[1] * scale))),
        )

    def update_cards_content_rects(self):
        local_bounds = self.calculate_generated_groups_local_bounds()
        scaled_bounds = self.calculate_generated_groups_scaled_local_bounds()
        self.cards_content_local_rect = local_bounds or pygame.Rect(0, 0, 0, 0)
        self.cards_content_scaled_local_rect = scaled_bounds or pygame.Rect(0, 0, 0, 0)

    def get_slot_content_rect(self):
        return self.get_slot_content_unscaled_local_rect()

    def get_slot_content_unscaled_local_rect(self):
        return self.frame.content_rect.copy()

    def get_slot_content_scaled_local_rect(self):
        scale = self.frame.get_content_screen_scale() if hasattr(self.frame, "get_content_screen_scale") else 1.0
        rect = self.frame.content_rect
        return pygame.Rect(
            rect.topleft,
            (
                max(0, int(round(rect.width * scale))),
                max(0, int(round(rect.height * scale))),
            ),
        )

    def get_slot_content_screen_rect(self):
        return self.get_slot_screen_rect()

    def get_slot_screen_rect(self):
        rect = self.frame.content_rect
        screen_pos = self.frame.to_screen(rect.topleft)
        scale = self.frame.get_content_screen_scale() if hasattr(self.frame, "get_content_screen_scale") else 1.0
        return pygame.Rect(
            screen_pos,
            (
                max(0, int(round(rect.width * scale))),
                max(0, int(round(rect.height * scale))),
            ),
        )

    def get_cards_content_unscaled_local_rect(self):
        return self.cards_content_local_rect.copy()

    def get_cards_content_scaled_local_rect(self):
        return self.cards_content_scaled_local_rect.copy()

    def get_cards_content_screen_rect(self):
        bounds = self.calculate_generated_groups_screen_bounds()
        if bounds is None:
            return pygame.Rect(0, 0, 0, 0)
        return bounds

    def draw_debug_overlay(self, screen):
        if not debug_overlay.should_draw_activity_rect():
            return
        rect = self.get_slot_screen_rect()
        if rect.width > 0 and rect.height > 0:
            pygame.draw.rect(screen, (255, 232, 64), rect, 2)

    def iter_generated_groups(self):
        return tuple(self.generated_groups)

    def iter_groups_in_draw_order(self):
        return tuple(self.generated_groups)

    def finish(self):
        self.clear_generated_groups()
        super().finish()

    def clear_generated_groups(self):
        for group in self.generated_groups:
            self.frame.remove_group(group.id)
        self.generated_groups = []
        self.card_visual_states = {}
        self.card_original_frames_by_group_id = {}
        self._last_slot_layout_signature = None
        self.update_cards_content_rects()

    def get_card_resource_key_for_index(self, card_index):
        return self.card_resource_keys[int(card_index)]

    def get_generated_group(self, card_index):
        index = int(card_index)
        if index < 0 or index >= len(self.generated_groups):
            raise IndexError(f"Slot card index is out of range: {card_index!r}")
        return self.generated_groups[index]

    def get_resource_frames(self, resource_key):
        if not resource_key:
            raise ValueError("CardsSlotActivityDecorator requires card resource_key")
        if self.resource_manager is None:
            raise RuntimeError("CardsSlotActivityDecorator requires resource_manager")
        frames = self.resource_manager.get_frames(resource_key)
        if not frames:
            raise KeyError(f"Card resource has no frames: {resource_key!r}")
        return tuple(frame.copy() for frame in frames)

    def ensure_card_original_frames(self, group):
        frames = self.card_original_frames_by_group_id.get(group.id)
        if frames is None:
            frames = tuple(frame.copy() for frame in group.get_primary_layer_frames())
            self.card_original_frames_by_group_id[group.id] = frames
        return frames

    def apply_transparent_card_surface(self, group):
        frames = self.ensure_card_original_frames(group)
        card_visibility.apply_transparent_primary_surface(group, frames)

    def restore_card_surface(self, group):
        frames = self.ensure_card_original_frames(group)
        card_visibility.restore_primary_frames(group, frames)

    def calculate_generated_groups_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = group.local_rect.copy()
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_scaled_local_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = group.get_scaled_local_rect() if hasattr(group, "get_scaled_local_rect") else group.local_rect
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def calculate_generated_groups_screen_bounds(self):
        bounds = None
        for group in self.iter_generated_groups():
            rect = group.rect
            bounds = rect.copy() if bounds is None else bounds.union(rect)
        return bounds

    def get_slot_layout_signature(self):
        return (
            tuple(self.card_resource_keys),
            tuple(sorted(self.card_visual_states.items())),
            self.scale_factor,
            self.spacing,
            self.center_offset,
            tuple(self.frame.local_rect),
            self.max_cards,
            tuple(
                (
                    group.id,
                    tuple(group.local_rect),
                    1.0 if group.scale_factor is None else group.scale_factor,
                )
                for group in self.generated_groups
            ),
        )

    @staticmethod
    def get_group_primary_layer_screen_rect(group):
        layer = group.get_primary_layer()
        if hasattr(group, "get_layer_rect"):
            return group.get_layer_rect(layer).copy()
        return group.rect.copy()

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
        return None

    @staticmethod
    def get_group_resource_key(group):
        return getattr(group, "card_resource_key", None)

    @staticmethod
    def get_fixture_cards(fixture):
        return normalizers.get_fixture_cards(fixture)

    @staticmethod
    def get_fixture_card_visual_state(fixture):
        if not fixture:
            return None
        for key in ("card_visual_state", "card_visibility"):
            if key in fixture:
                return fixture[key]
        return None

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
    def normalize_cards(cards):
        return normalizers.normalize_cards(cards)

    def limit_cards(self, cards):
        return normalizers.limit_cards(cards, self.max_cards)

    @staticmethod
    def normalize_max_cards(max_cards):
        return normalizers.normalize_max_cards(max_cards)

    @staticmethod
    def normalize_scale_factor(value):
        return normalizers.normalize_scale_factor(value)

    @staticmethod
    def normalize_pair(value):
        return normalizers.normalize_int_pair(value)
