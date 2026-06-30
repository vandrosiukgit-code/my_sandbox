"""Activity for arranging card slot frame copies inside play_area_frame."""

from actions import SlotCardHoverFlightAction
from activities.base_activity import Activity
from activities import normalizers


class PlayAreaSlotsActivity(Activity):
    """Own placement of temporary card slot frames inside the play area.

    The fixture creates the first cards_slot_frame as a prototype. This activity
    copies that frame around play_area_frame so we can tune appearance,
    placement, and size before Controller-driven slot state exists.
    """

    DEFAULT_CENTER_ROW_RADIUS = 2
    DEFAULT_SIDE_ROW_RADIUS = 1
    DEFAULT_SLOT_COUNT = 7
    CENTER_ROW_SLOT_GAP_LOCAL_PIXELS = 5
    OVERFLOW_LANE_OFFSETS = {
        -1: ((-1, 0), (-2, 0), (-2, -1)),
        1: ((1, 0), (2, 0), (2, -1)),
    }
    DEFAULT_SLOT_ACTIVITY_FIXTURE = {
        "scale_factor": 0.95,
        "radius": 80,
        "center_offset": (0, 0),
    }
    DEFAULT_SPACING = (12, 12)

    def __init__(
        self,
        screen,
        play_area_frame,
        prototype_slot_frame,
        prototype_slot_activity=None,
        slot_activity_factory=None,
        slot_id_prefix="cards_slot_frame",
    ):
        super().__init__(duration=0.0)
        self.screen = screen
        self.play_area_frame = play_area_frame
        self.prototype_slot_frame = prototype_slot_frame
        self.prototype_slot_activity = prototype_slot_activity
        self.slot_activity_factory = slot_activity_factory
        self.slot_id_prefix = slot_id_prefix
        self.slot_count = self.DEFAULT_SLOT_COUNT
        self.columns = 1
        self.spacing = self.DEFAULT_SPACING
        self.origin = None
        self.center = None
        self.step = None
        self.slot_offsets = None
        self.slot_local_rects = {}
        self.slot_activity_fixture = self.merge_slot_activity_fixture(None)
        self.managed_slot_ids = [self.prototype_slot_frame.id]
        self.slot_activities = {}
        self.next_overflow_direction = 1
        self.slot_transfer_actions = []
        self.pending_slot_transfer_batches = []
        self.pending_player_card_data = []
        self.next_transfer_group_index = 0
        self._last_layout_signature = None
        self.validate_screen_slot_owner(screen)
        if self.prototype_slot_activity is not None:
            self.slot_activities[self.prototype_slot_frame.id] = self.prototype_slot_activity

    @staticmethod
    def validate_screen_slot_owner(screen):
        required_methods = (
            "ensure_play_area_slot_frame",
            "ensure_play_area_slot_activity",
            "remove_play_area_slot_activity",
            "remove_play_area_slot_frame",
        )
        missing_methods = [
            method_name
            for method_name in required_methods
            if not callable(getattr(screen, method_name, None))
        ]
        if missing_methods:
            missing = ", ".join(missing_methods)
            raise TypeError(f"PlayAreaSlotsActivity requires screen slot owner API: {missing}")

    def start(self):
        if self.started:
            return
        super().start()
        self.apply_layout()

    def update(self, dt):
        _ = dt
        if not self.started:
            self.start()
            return

        layout_signature = self.get_layout_signature()
        if layout_signature != self._last_layout_signature:
            self.apply_layout()
        self.update_slot_transfer_actions(dt)

    def iter_generated_groups(self):
        groups = []
        for activity in self.slot_activities.values():
            if hasattr(activity, "iter_generated_groups"):
                groups.extend(activity.iter_generated_groups())
        for action in self.slot_transfer_actions:
            group = getattr(action, "group", None)
            if group is not None:
                groups.append(group)
        return tuple(groups)

    def iter_groups_in_draw_order(self):
        groups = []
        for activity in self.slot_activities.values():
            group_iterator = getattr(activity, "iter_groups_in_draw_order", None)
            if not callable(group_iterator):
                group_iterator = getattr(activity, "iter_generated_groups", None)
            if callable(group_iterator):
                groups.extend(group_iterator())
        for action in self.slot_transfer_actions:
            group = getattr(action, "group", None)
            if group is not None:
                groups.append(group)
        return tuple(groups)

    def draw_debug_overlay(self, screen):
        _ = screen

    def apply_fixture(self, fixture):
        if not fixture:
            return

        self.slot_count = max(self.DEFAULT_SLOT_COUNT, int(fixture.get("slot_count", self.slot_count)))
        self.columns = max(1, int(fixture.get("columns", self.columns)))
        self.spacing = self.normalize_pair(fixture.get("spacing", self.spacing))
        self.origin = self.normalize_optional_pair(fixture.get("origin"))
        self.center = self.normalize_optional_pair(fixture.get("center"))
        if "step" in fixture:
            self.step = self.normalize_optional_pair(fixture.get("step"))
        self.slot_offsets = self.normalize_offsets(fixture.get("slot_offsets"))
        if "slot_local_rects" in fixture:
            # Fixture patches may override one slot at a time during geometry
            # diagnostics, so preserve existing explicit rects unless replaced.
            merged_slot_local_rects = dict(self.slot_local_rects)
            merged_slot_local_rects.update(
                self.normalize_slot_local_rects(fixture.get("slot_local_rects"))
            )
            self.slot_local_rects = merged_slot_local_rects
        self.slot_activity_fixture = self.merge_slot_activity_fixture(fixture.get("slot_activity"))
        self.apply_layout()

    def apply_layout(self):
        self.ensure_slot_frames()
        self.ensure_slot_activities()
        self.apply_slot_activity_fixtures()

        slot_offsets = tuple(
            self.get_slot_offset(index)
            for index in range(len(self.managed_slot_ids))
        )
        slot_size = self.get_layout_slot_size(slot_offsets)

        center = self.center
        if center is None and self.origin is not None:
            center = (
                self.origin[0] + slot_size[0] // 2,
                self.origin[1] + slot_size[1] // 2,
            )
        if center is None:
            center = self.get_default_layout_center()

        step_x, step_y = self.get_slot_step(slot_size, slot_offsets)
        for index, frame_id in enumerate(self.managed_slot_ids):
            slot_frame = self.screen.get_screen_frame(frame_id)
            offset_x, offset_y = slot_offsets[index]
            slot_frame.set_local_rect(
                self.resolve_slot_local_rect(
                    frame_id,
                    slot_size,
                    center,
                    (step_x, step_y),
                    (offset_x, offset_y),
                )
            )
            activity = self.slot_activities.get(frame_id)
            if activity is not None and hasattr(activity, "normalize_slot_content"):
                activity.normalize_slot_content()

        self._last_layout_signature = self.get_layout_signature()

    def get_layout_slot_size(self, slot_offsets):
        """Size central-row slots to fit between the current bot fan bounds."""
        prototype_width, prototype_height = self.get_prototype_slot_size()
        horizontal_bounds = self.get_player_inner_horizontal_bounds()
        if horizontal_bounds is None:
            return prototype_width, prototype_height

        central_offsets = {offset_x for offset_x, offset_y in slot_offsets if offset_y == 0}
        central_count = len(central_offsets)
        if central_count <= 1:
            return prototype_width, prototype_height
        left, right = horizontal_bounds
        gap_total = self.CENTER_ROW_SLOT_GAP_LOCAL_PIXELS * (central_count - 1)
        width = max(1, (right - left - gap_total) // central_count)
        height = max(1, int(round(width * prototype_height / max(1, prototype_width))))
        return width, height

    @classmethod
    def merge_slot_activity_fixture(cls, fixture):
        merged = dict(cls.DEFAULT_SLOT_ACTIVITY_FIXTURE)
        if fixture:
            merged.update(fixture)
        return merged

    def get_layout_signature(self):
        return (
            self.slot_count,
            self.columns,
            self.spacing,
            self.origin,
            self.center,
            self.step,
            self.slot_offsets,
            self.freeze_mapping(self.slot_local_rects),
            self.get_layout_slot_size(
                tuple(self.get_slot_offset(index) for index in range(self.slot_count))
            ),
            tuple(self.play_area_frame.local_rect),
            tuple(self.prototype_slot_frame.local_rect),
            self.get_player_inner_horizontal_bounds(),
            self.CENTER_ROW_SLOT_GAP_LOCAL_PIXELS,
            self.freeze_mapping(self.slot_activity_fixture),
        )

    @classmethod
    def freeze_mapping(cls, value):
        if isinstance(value, dict):
            return tuple(sorted((key, cls.freeze_mapping(item)) for key, item in value.items()))
        if isinstance(value, (list, tuple)):
            return tuple(cls.freeze_mapping(item) for item in value)
        return value

    def get_default_layout_center(self):
        center_x, center_y = self.play_area_frame.content_rect.center
        horizontal_bounds = self.get_player_inner_horizontal_bounds()
        if horizontal_bounds is not None:
            left, right = horizontal_bounds
            center_x = int(round((left + right) / 2))
        return center_x, center_y

    def get_slot_step(self, slot_size, slot_offsets=None):
        """Return distance between slot centers in play-area local coordinates."""
        if self.step is not None:
            return self.step
        slot_offsets = slot_offsets or ()
        return (
            self.calculate_horizontal_slot_step(slot_size, slot_offsets),
            int(slot_size[1] + self.spacing[1]),
        )

    def calculate_horizontal_slot_step(self, slot_size, slot_offsets):
        horizontal_bounds = self.get_player_inner_horizontal_bounds()
        if horizontal_bounds is None:
            return int(slot_size[0] + self.spacing[0])

        min_offset, max_offset = self.get_horizontal_offset_span(slot_offsets)
        if min_offset == max_offset:
            return int(slot_size[0] + self.spacing[0])

        left, right = horizontal_bounds
        central_count = len({offset_x for offset_x, offset_y in slot_offsets if offset_y == 0})
        if central_count > 1:
            return slot_size[0] + self.CENTER_ROW_SLOT_GAP_LOCAL_PIXELS
        available_width = max(1, right - left)
        step = (available_width - slot_size[0]) / (max_offset - min_offset)
        return max(1, int(round(step)))

    def get_player_inner_horizontal_bounds(self):
        getter = getattr(self.screen, "get_play_area_slot_horizontal_local_bounds", None)
        if callable(getter):
            return getter(self.play_area_frame)

        left_rect = self.get_player_frame_screen_rect("left_player_frame")
        right_rect = self.get_player_frame_screen_rect("right_player_frame")
        if left_rect is None or right_rect is None:
            return None

        left_inner_x = self.play_area_frame.to_local((left_rect.right, 0))[0]
        right_inner_x = self.play_area_frame.to_local((right_rect.left, 0))[0]
        if left_inner_x >= right_inner_x:
            return None

        content_rect = self.play_area_frame.content_rect
        return (
            max(content_rect.left, left_inner_x),
            min(content_rect.right, right_inner_x),
        )

    def get_player_frame_screen_rect(self, frame_id):
        try:
            if hasattr(self.screen, "get_frame_screen_rect"):
                return self.screen.get_frame_screen_rect(frame_id)
            return self.screen.get_screen_frame(frame_id).rect.copy()
        except KeyError:
            return None

    @staticmethod
    def get_horizontal_offset_span(slot_offsets):
        if not slot_offsets:
            return 0, 0
        x_offsets = [offset[0] for offset in slot_offsets]
        return min(x_offsets), max(x_offsets)

    def get_prototype_slot_size(self):
        if self.prototype_slot_activity is not None:
            getter = getattr(self.prototype_slot_activity, "get_default_slot_size", None)
            if callable(getter):
                size = getter()
                if size[0] > 0 and size[1] > 0:
                    return size
            content_rect = self.prototype_slot_activity.get_slot_content_rect()
            if content_rect.width > 0 and content_rect.height > 0:
                return content_rect.size
        return self.prototype_slot_frame.local_rect.size

    def resolve_slot_local_rect(self, frame_id, slot_size, center, step, offset):
        explicit_rect = self.slot_local_rects.get(frame_id)
        if explicit_rect is not None:
            return explicit_rect
        step_x, step_y = step
        offset_x, offset_y = offset
        x = center[0] + offset_x * step_x - slot_size[0] // 2
        y = center[1] + offset_y * step_y - slot_size[1] // 2
        return x, y, slot_size[0], slot_size[1]

    def ensure_slot_frames(self):
        target_ids = [self.get_slot_frame_id(index) for index in range(self.slot_count)]

        for frame_id in tuple(self.managed_slot_ids):
            if frame_id not in target_ids:
                self.remove_slot_activity(frame_id)
                self.remove_slot_frame(frame_id)

        self.managed_slot_ids = []
        for index, frame_id in enumerate(target_ids):
            slot_frame = self.ensure_slot_frame(frame_id, index)
            slot_frame.set_rect_visibility(False)
            self.managed_slot_ids.append(frame_id)

    def ensure_slot_frame(self, frame_id, index):
        """Request a screen-owned slot frame."""
        _ = index
        return self.screen.ensure_play_area_slot_frame(frame_id, self.prototype_slot_frame)

    def ensure_slot_activities(self):
        """Keep one CardsSlotActivity alive for each managed slot frame."""
        for index, frame_id in enumerate(self.managed_slot_ids):
            if frame_id in self.slot_activities:
                continue
            if self.slot_activity_factory is None:
                continue

            slot_frame = self.screen.get_screen_frame(frame_id)
            activity = self.ensure_slot_activity(frame_id, slot_frame, index)
            self.slot_activities[frame_id] = activity

    def ensure_slot_activity(self, frame_id, slot_frame, index):
        """Request a screen-owned slot activity."""
        return self.screen.ensure_play_area_slot_activity(frame_id, slot_frame, index)

    def apply_slot_activity_fixtures(self):
        """Apply shared slot contents to every CardsSlotActivity in the play area."""
        if not self.slot_activity_fixture:
            return
        for activity in self.slot_activities.values():
            if hasattr(activity, "apply_fixture"):
                activity.apply_fixture(self.slot_activity_fixture)

    def get_player_turn_target_screen_geometry(self, turn_context=None):
        """Return target geometry for the next player card in the central slot."""
        if not self.prepare_central_slot_for_next_card():
            return None
        central_activity = self.get_central_slot_activity()
        if central_activity is None:
            return None
        getter = getattr(central_activity, "get_player_turn_target_screen_geometry", None)
        if not callable(getter):
            return None
        return getter(turn_context)

    def place_player_card(self, card_data):
        """Place a player card into the central slot after overflow routing."""
        if self.has_pending_slot_transfers():
            self.pending_player_card_data.append(card_data)
            return True
        if not self.prepare_central_slot_for_next_card():
            return False
        central_activity = self.get_central_slot_activity()
        if central_activity is None:
            return False
        placer = getattr(central_activity, "place_player_card", None)
        if callable(placer):
            placer(card_data)
            return True
        return False

    def prepare_central_slot_for_next_card(self):
        central_activity = self.get_central_slot_activity()
        if central_activity is None:
            return False
        if self.get_slot_card_count(central_activity) < self.get_slot_max_cards(central_activity):
            return True
        return self.schedule_central_pair_overflow(central_activity)

    def get_central_slot_activity(self):
        if not self.managed_slot_ids:
            return None
        return self.slot_activities.get(self.managed_slot_ids[0])

    def schedule_central_pair_overflow(self, central_activity):
        """Move a filled central pair through an alternating slot cascade."""
        directions = (self.next_overflow_direction, -self.next_overflow_direction)
        for direction in directions:
            path = self.get_overflow_path(direction)
            if not path:
                continue
            specs = self.build_overflow_path_specs(path)
            specs.extend(self.build_slot_cards_transfer_specs(central_activity, path[0]))
            self.queue_slot_transfer_batch(specs)
            self.next_overflow_direction = -direction
            return True
        return False

    def get_overflow_path(self, direction):
        side_activities = self.get_side_slot_activities(direction)
        for index, activity in enumerate(side_activities):
            if self.get_slot_card_count(activity) == 0:
                return side_activities[: index + 1]
        return ()

    def get_side_slot_activities(self, direction):
        lane_offsets = self.OVERFLOW_LANE_OFFSETS.get(int(direction))
        if lane_offsets is None:
            return ()
        activities_by_offset = {}
        for index, frame_id in enumerate(self.managed_slot_ids):
            offset = self.get_slot_offset(index)
            activity = self.slot_activities.get(frame_id)
            if activity is not None:
                activities_by_offset[offset] = activity
        if any(offset not in activities_by_offset for offset in lane_offsets):
            return ()
        return tuple(activities_by_offset[offset] for offset in lane_offsets)

    def build_overflow_path_specs(self, path):
        specs = []
        for source_activity, target_activity in reversed(tuple(zip(path, path[1:]))):
            specs.extend(self.build_slot_cards_transfer_specs(source_activity, target_activity))
        return specs

    @staticmethod
    def get_slot_card_count(activity):
        return len(getattr(activity, "card_resource_keys", ()))

    @staticmethod
    def get_slot_max_cards(activity):
        max_cards = getattr(activity, "max_cards", None)
        if max_cards is None:
            return 2
        return max(1, int(max_cards))

    @staticmethod
    def move_slot_cards(source_activity, target_activity):
        cards = tuple(getattr(source_activity, "card_resource_keys", ()))
        if not cards:
            return
        target_activity.set_cards(cards, force=True)
        source_activity.set_cards((), force=True)

    def schedule_slot_cards_transfer(self, source_activity, target_activity):
        specs = self.build_slot_cards_transfer_specs(source_activity, target_activity)
        if not specs:
            return False
        self.queue_slot_transfer_batch(specs)
        return True

    def build_slot_cards_transfer_specs(self, source_activity, target_activity):
        cards = tuple(getattr(source_activity, "card_resource_keys", ()))
        if not cards:
            return []
        specs = []
        for index, resource_key in enumerate(cards):
            from_geometry = source_activity.get_card_screen_geometry(index)
            to_geometry = target_activity.get_next_card_screen_geometry(
                {
                    "resource_key": resource_key,
                    "slot_card_index": index,
                }
            )
            specs.append(
                {
                    "resource_key": resource_key,
                    "from_geometry": from_geometry,
                    "to_geometry": to_geometry,
                    "target_activity": target_activity,
                    "target_index": index,
                }
            )
        source_activity.set_cards((), force=True)
        return specs

    def queue_slot_transfer_batch(self, specs):
        if not specs:
            return
        self.pending_slot_transfer_batches.append(tuple(specs))
        self.start_next_slot_transfer_action()

    def start_next_slot_transfer_action(self):
        if self.slot_transfer_actions or not self.pending_slot_transfer_batches:
            return
        specs = self.pending_slot_transfer_batches.pop(0)
        for spec in specs:
            resource_key = spec["resource_key"]
            target_activity = spec["target_activity"]
            target_index = spec["target_index"]
            action = SlotCardHoverFlightAction(
                from_geometry=spec["from_geometry"],
                to_geometry=spec["to_geometry"],
                face_resource_key=resource_key,
                group_id=self.get_next_transfer_group_id(),
                cleanup_group=self.remove_slot_transfer_group,
                land_card=lambda activity=target_activity, index=target_index, key=resource_key: (
                    self.land_slot_transfer_card(activity, index, key)
                ),
            )
            self.slot_transfer_actions.append(action)
            action.start()

    def update_slot_transfer_actions(self, dt):
        running = []
        for action in self.slot_transfer_actions:
            action.update(dt)
            if not action.is_finished():
                running.append(action)
        self.slot_transfer_actions = running
        self.start_next_slot_transfer_action()
        self.start_next_pending_player_card()

    def has_pending_slot_transfers(self):
        return bool(self.slot_transfer_actions or self.pending_slot_transfer_batches)

    def start_next_pending_player_card(self):
        if self.has_pending_slot_transfers() or not self.pending_player_card_data:
            return
        card_data = self.pending_player_card_data.pop(0)
        self.place_player_card(card_data)

    def land_slot_transfer_card(self, target_activity, target_index, resource_key):
        cards = list(getattr(target_activity, "card_resource_keys", ()))
        while len(cards) <= target_index:
            cards.append(resource_key)
        cards[target_index] = resource_key
        target_activity.set_cards(tuple(cards), force=True)

    def remove_slot_transfer_group(self, group):
        _ = group

    def get_next_transfer_group_id(self):
        self.next_transfer_group_index += 1
        return f"slot_card_hover.flight_card.{self.next_transfer_group_index}"

    def clear_slot_cards(self):
        """Clear all visual card state from managed slot activities."""
        for activity in self.slot_activities.values():
            setter = getattr(activity, "set_cards", None)
            if callable(setter):
                setter((), force=True)
        self.next_overflow_direction = 1
        for action in self.slot_transfer_actions:
            if hasattr(action, "cancel"):
                action.cancel()
        self.slot_transfer_actions = []
        self.pending_slot_transfer_batches = []
        self.pending_player_card_data = []

    def remove_slot_activity(self, frame_id):
        """Stop and unregister the CardsSlotActivity owned by a removed slot."""
        activity = self.slot_activities.get(frame_id)
        if activity is None or activity is self.prototype_slot_activity:
            return

        self.slot_activities.pop(frame_id, None)
        self.screen.remove_play_area_slot_activity(frame_id, finish=True)

    def remove_slot_frame(self, frame_id):
        if frame_id == self.prototype_slot_frame.id:
            return
        self.screen.remove_play_area_slot_frame(frame_id, self.prototype_slot_frame.id)

    def get_slot_frame_id(self, index):
        if index == 0:
            return self.prototype_slot_frame.id
        return f"{self.slot_id_prefix}_{index + 1}"

    def get_slot_offset(self, index):
        """Return layout offset for a slot by creation order.

        Slot positions are generated from the center outward. The fixture can
        still override offsets for debugging, but the default layout is derived.
        """
        if self.slot_offsets is not None and index < len(self.slot_offsets):
            return self.slot_offsets[index]
        return self.get_default_slot_offset(index)

    def get_default_slot_offset(self, index):
        if self.columns <= 1:
            return self.generate_default_slot_offsets(index + 1)[index]

        column = index % self.columns
        row = index // self.columns
        return column - (self.columns - 1) / 2, row

    @classmethod
    def generate_default_slot_offsets(cls, count):
        offsets = []
        for x in cls.iter_center_out_axis(cls.DEFAULT_CENTER_ROW_RADIUS):
            offsets.append((x, 0))
            if len(offsets) >= count:
                return tuple(offsets)

        side_x = cls.DEFAULT_CENTER_ROW_RADIUS
        while len(offsets) < count:
            for y in cls.iter_center_out_axis(cls.DEFAULT_SIDE_ROW_RADIUS):
                if y == 0:
                    continue
                for x in (-side_x, side_x):
                    offsets.append((x, y))
                    if len(offsets) >= count:
                        return tuple(offsets)
            side_x += 1
        return tuple(offsets)

    @staticmethod
    def iter_center_out_axis(radius):
        yield 0
        for distance in range(1, int(radius) + 1):
            yield -distance
            yield distance

    @staticmethod
    def normalize_pair(value):
        return normalizers.normalize_int_pair(value, error_type=ValueError)

    @classmethod
    def normalize_optional_pair(cls, value):
        return normalizers.normalize_optional_pair(value, cls.normalize_pair)

    @classmethod
    def normalize_offsets(cls, offsets):
        return normalizers.normalize_offsets(offsets, cls.normalize_pair)

    @classmethod
    def normalize_slot_local_rects(cls, mapping):
        if mapping is None:
            return {}
        if not isinstance(mapping, dict):
            raise TypeError("slot_local_rects must be a mapping of frame_id to rect")
        normalized = {}
        for frame_id, rect in mapping.items():
            if not isinstance(frame_id, str) or not frame_id:
                raise TypeError("slot_local_rects keys must be non-empty frame_id strings")
            normalized[frame_id] = cls.normalize_rect(rect)
        return normalized

    @classmethod
    def normalize_rect(cls, value):
        if isinstance(value, dict):
            x = value.get("x")
            y = value.get("y")
            width = value.get("width")
            height = value.get("height")
            return (
                int(round(x)),
                int(round(y)),
                int(round(width)),
                int(round(height)),
            )
        if isinstance(value, (list, tuple)) and len(value) == 4:
            return tuple(int(round(item)) for item in value)
        raise TypeError("slot rect must be a 4-item sequence or mapping with x/y/width/height")
