"""Activity for arranging card slot frame copies inside play_area_frame."""

from activities.base_activity import Activity


class PlayAreaSlotsActivity(Activity):
    """Own placement of temporary card slot frames inside the play area.

    The fixture creates the first cards_slot_frame as a prototype. This activity
    copies that frame around play_area_frame so we can tune appearance,
    placement, and size before Controller-driven slot state exists.
    """

    DEFAULT_CENTER_ROW_RADIUS = 2
    DEFAULT_SIDE_ROW_RADIUS = 1
    DEFAULT_SLOT_ACTIVITY_FIXTURE = {
        "scale_factor": 0.7,
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
        self.slot_count = 1
        self.columns = 1
        self.spacing = self.DEFAULT_SPACING
        self.origin = None
        self.center = None
        self.step = None
        self.slot_offsets = None
        self.slot_activity_fixture = self.merge_slot_activity_fixture(None)
        self.managed_slot_ids = [self.prototype_slot_frame.id]
        self.slot_activities = {}
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

    def iter_generated_groups(self):
        groups = []
        for activity in self.slot_activities.values():
            if hasattr(activity, "iter_generated_groups"):
                groups.extend(activity.iter_generated_groups())
        return tuple(groups)

    def draw_debug_overlay(self, screen):
        _ = screen

    def apply_fixture(self, fixture):
        if not fixture:
            return

        self.slot_count = max(1, int(fixture.get("slot_count", self.slot_count)))
        self.columns = max(1, int(fixture.get("columns", self.columns)))
        self.spacing = self.normalize_pair(fixture.get("spacing", self.spacing))
        self.origin = self.normalize_optional_pair(fixture.get("origin"))
        self.center = self.normalize_optional_pair(fixture.get("center"))
        if "step" in fixture:
            self.step = self.normalize_optional_pair(fixture.get("step"))
        self.slot_offsets = self.normalize_offsets(fixture.get("slot_offsets"))
        self.slot_activity_fixture = self.merge_slot_activity_fixture(fixture.get("slot_activity"))
        self.apply_layout()

    def apply_layout(self):
        self.ensure_slot_frames()
        self.ensure_slot_activities()
        self.apply_slot_activity_fixtures()

        slot_size = self.get_prototype_slot_size()

        center = self.center
        if center is None and self.origin is not None:
            center = (
                self.origin[0] + slot_size[0] // 2,
                self.origin[1] + slot_size[1] // 2,
            )
        if center is None:
            center = self.get_default_layout_center()

        slot_offsets = tuple(
            self.get_slot_offset(index)
            for index in range(len(self.managed_slot_ids))
        )
        step_x, step_y = self.get_slot_step(slot_size, slot_offsets)

        for index, frame_id in enumerate(self.managed_slot_ids):
            slot_frame = self.screen.get_screen_frame(frame_id)
            offset_x, offset_y = slot_offsets[index]
            x = center[0] + offset_x * step_x - slot_size[0] // 2
            y = center[1] + offset_y * step_y - slot_size[1] // 2
            slot_frame.set_local_rect((x, y, slot_size[0], slot_size[1]))
            activity = self.slot_activities.get(frame_id)
            if activity is not None and hasattr(activity, "normalize_slot_content"):
                activity.normalize_slot_content()

        self._last_layout_signature = self.get_layout_signature()

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
            self.get_prototype_slot_size(),
            tuple(self.play_area_frame.local_rect),
            tuple(self.prototype_slot_frame.local_rect),
            self.get_player_inner_horizontal_bounds(),
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
        available_width = max(1, right - left)
        step = (available_width - slot_size[0]) / (max_offset - min_offset)
        return max(1, int(round(step)))

    def get_player_inner_horizontal_bounds(self):
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
        if isinstance(value, dict):
            return int(round(float(value.get("x", 0)))), int(round(float(value.get("y", 0))))
        if not isinstance(value, (tuple, list)) or len(value) < 2:
            raise ValueError(f"Expected pair as dict/list/tuple: {value!r}")
        return int(round(float(value[0]))), int(round(float(value[1])))

    @classmethod
    def normalize_optional_pair(cls, value):
        if value is None:
            return None
        return cls.normalize_pair(value)

    @classmethod
    def normalize_offsets(cls, offsets):
        if offsets is None:
            return None
        if not isinstance(offsets, (tuple, list)):
            raise ValueError(f"slot_offsets must be a list or tuple of pairs: {offsets!r}")
        return tuple(cls.normalize_pair(offset) for offset in offsets)
