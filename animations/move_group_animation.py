"""Position animation for a single Group."""

from animations.base_animation import Animation
from animations.easing import ease_out_quad, lerp_int


class MoveGroupAnimation(Animation):
    """Move a Group between two screen positions over time."""

    animated_properties = ("screen_position",)
    coordinate_space = "screen"

    def __init__(self, group, to_position, duration=0.25, from_position=None, frame=None, on_finish=None):
        super().__init__(duration=duration, on_finish=on_finish)
        self.validate_group(group)
        self.group = group
        self.frame = frame
        self.from_position = self.normalize_position(from_position) if from_position is not None else None
        self.to_position = self.normalize_position(to_position)
        self._initial_from_position = self.from_position
        self._explicit_from_position = from_position is not None

    def start(self):
        super().start()
        if not self._explicit_from_position:
            self.from_position = tuple(self.group.rect.topleft)
        self.apply(0.0)

    def reset(self):
        super().reset()
        self.from_position = self._initial_from_position

    def apply(self, progress):
        progress = ease_out_quad(progress)
        x = lerp_int(self.from_position[0], self.to_position[0], progress)
        y = lerp_int(self.from_position[1], self.to_position[1], progress)
        self.group.set_position(x, y)
        self.sync_frame_origin()

    def finish(self):
        super().finish()

    def sync_frame_origin(self):
        frame = self.frame or getattr(self.group, "parent_frame", None)
        if frame is not None and hasattr(frame, "set_group_origin"):
            frame.set_group_origin(self.group.id, self.group.local_rect.topleft)

    @staticmethod
    def normalize_position(position):
        if not isinstance(position, (tuple, list)) or len(position) < 2:
            raise TypeError(f"position must be a pair: {position!r}")
        return int(round(float(position[0]))), int(round(float(position[1])))

    @staticmethod
    def validate_group(group):
        required = ("id", "rect", "local_rect", "set_position")
        missing = [name for name in required if not hasattr(group, name)]
        if missing:
            raise TypeError(f"group is not compatible with MoveGroupAnimation: missing {missing!r}")
