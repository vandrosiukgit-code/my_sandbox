"""Activity for arranging card slot frame copies inside play_area_frame."""

from activities.base_activity import Activity


class PlayAreaSlotsActivity(Activity):
    """Own placement of temporary card slot frames inside the play area.

    The fixture creates the first cards_slot_frame as a prototype. This activity
    copies that frame around play_area_frame so we can tune appearance,
    placement, and size before Controller-driven slot state exists.
    """

    def __init__(
        self,
        screen,
        play_area_frame,
        prototype_slot_frame,
        prototype_slot_activity=None,
        slot_id_prefix="cards_slot_frame",
    ):
        super().__init__(duration=0.0)
        self.screen = screen
        self.play_area_frame = play_area_frame
        self.prototype_slot_frame = prototype_slot_frame
        self.prototype_slot_activity = prototype_slot_activity
        self.slot_id_prefix = slot_id_prefix
        self.slot_count = 1
        self.columns = 1
        self.spacing = (24, 24)
        self.origin = None
        self.center = None
        self.step = (180, 180)
        self.slot_offsets = None
        self.managed_slot_ids = [self.prototype_slot_frame.id]

    def update(self, dt):
        _ = dt
        if not self.started:
            self.start()

    def apply_fixture(self, fixture):
        if not fixture:
            return

        self.slot_count = max(0, int(fixture.get("slot_count", self.slot_count)))
        self.columns = max(1, int(fixture.get("columns", self.columns)))
        self.spacing = self.normalize_pair(fixture.get("spacing", self.spacing))
        self.origin = self.normalize_optional_pair(fixture.get("origin"))
        self.center = self.normalize_optional_pair(fixture.get("center"))
        self.step = self.normalize_pair(fixture.get("step", self.step))
        self.slot_offsets = self.normalize_offsets(fixture.get("slot_offsets"))
        self.apply_layout()

    def apply_layout(self):
        self.ensure_slot_frames()

        slot_size = self.get_prototype_slot_size()

        center = self.center
        if center is None and self.origin is not None:
            center = (
                self.origin[0] + slot_size[0] // 2,
                self.origin[1] + slot_size[1] // 2,
            )
        if center is None:
            center = self.play_area_frame.content_rect.center

        for index, frame_id in enumerate(self.managed_slot_ids):
            slot_frame = self.screen.get_screen_frame(frame_id)
            offset_x, offset_y = self.get_slot_offset(index)
            x = center[0] + offset_x * self.step[0] - slot_size[0] // 2
            y = center[1] + offset_y * self.step[1] - slot_size[1] // 2
            slot_frame.set_local_rect((x, y, slot_size[0], slot_size[1]))

    def get_prototype_slot_size(self):
        if self.prototype_slot_activity is not None:
            content_rect = self.prototype_slot_activity.get_slot_content_rect()
            if content_rect.width > 0 and content_rect.height > 0:
                return content_rect.size
        return self.prototype_slot_frame.local_rect.size

    def ensure_slot_frames(self):
        target_ids = [self.get_slot_frame_id(index) for index in range(self.slot_count)]

        for frame_id in tuple(self.managed_slot_ids):
            if frame_id not in target_ids:
                self.remove_slot_frame(frame_id)

        self.managed_slot_ids = []
        for index, frame_id in enumerate(target_ids):
            if index == 0:
                slot_frame = self.prototype_slot_frame
            elif frame_id in self.screen.screen_frames:
                slot_frame = self.screen.get_screen_frame(frame_id)
            else:
                slot_frame = self.screen.create_frame(
                    frame_id,
                    rect=self.prototype_slot_frame.local_rect,
                    parent_frame_id=self.play_area_frame.id,
                )
            slot_frame.set_rect_visibility(False)
            self.managed_slot_ids.append(frame_id)

    def remove_slot_frame(self, frame_id):
        if frame_id == self.prototype_slot_frame.id:
            return
        self.play_area_frame.child_frames.pop(frame_id, None)
        self.screen.screen_frames.pop(frame_id, None)

    def get_slot_frame_id(self, index):
        if index == 0:
            return self.prototype_slot_frame.id
        return f"{self.slot_id_prefix}_{index + 1}"

    def get_slot_offset(self, index):
        if self.slot_offsets is not None and index < len(self.slot_offsets):
            return self.slot_offsets[index]
        return self.get_center_out_offset(index)

    @staticmethod
    def get_center_out_offset(index):
        if index <= 0:
            return 0, 0

        pattern = (
            (-1, 0),
            (1, 0),
            (0, -1),
            (0, 1),
            (-1, -1),
            (1, -1),
            (-1, 1),
            (1, 1),
        )
        index -= 1
        ring = index // len(pattern) + 1
        offset_x, offset_y = pattern[index % len(pattern)]
        return offset_x * ring, offset_y * ring

    @staticmethod
    def normalize_pair(value):
        if isinstance(value, dict):
            return int(round(float(value.get("x", 0)))), int(round(float(value.get("y", 0))))
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
        return tuple(cls.normalize_pair(offset) for offset in offsets)
