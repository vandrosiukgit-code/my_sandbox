"""Coordinate animation for card selection feedback."""

from animations.base_animation import Animation
from animations.easing import ease_out_quad, lerp_float


class CardSelectionAnimation(Animation):
    """Move and scale one card to highlight or restore it.

    This is a coordinate animation: it changes the card group's local position
    and scale factor over time, but it does not advance sprite frames.
    """

    animated_properties = ("local_position", "scale_factor")
    coordinate_space = "frame_local"

    def __init__(
        self,
        group,
        to_position,
        to_scale,
        duration=0.12,
        from_position=None,
        from_scale=None,
        on_finish=None,
    ):
        super().__init__(duration=duration, on_finish=on_finish)
        self.validate_group(group)
        self.group = group
        self.from_position = self.normalize_position(from_position) if from_position is not None else None
        self.to_position = self.normalize_position(to_position)
        self.from_scale = self.normalize_scale(from_scale, "from_scale") if from_scale is not None else None
        self.to_scale = self.normalize_scale(to_scale, "to_scale")
        self._initial_from_position = self.from_position
        self._initial_from_scale = self.from_scale
        self._explicit_from_position = from_position is not None
        self._explicit_from_scale = from_scale is not None

    def start(self):
        super().start()
        if not self._explicit_from_position:
            self.from_position = tuple(self.group.local_rect.topleft)
        if not self._explicit_from_scale:
            self.from_scale = self.get_group_scale(self.group)
        self.apply(0.0)

    def reset(self):
        super().reset()
        self.from_position = self._initial_from_position
        self.from_scale = self._initial_from_scale

    def apply(self, progress):
        progress = ease_out_quad(progress)
        x = lerp_float(self.from_position[0], self.to_position[0], progress)
        y = lerp_float(self.from_position[1], self.to_position[1], progress)
        scale = lerp_float(self.from_scale, self.to_scale, progress)

        self.group.set_scale_factor(scale)
        self.group.set_local_position(x, y)
        self.sync_frame_origin()

    def finish(self):
        super().finish()

    def sync_frame_origin(self):
        frame = getattr(self.group, "parent_frame", None)
        if frame is not None and hasattr(frame, "set_group_origin"):
            frame.set_group_origin(self.group.id, self.group.local_rect.topleft)

    @staticmethod
    def get_group_scale(group):
        return 1.0 if group.scale_factor is None else float(group.scale_factor)

    @staticmethod
    def normalize_position(position):
        if not isinstance(position, (tuple, list)) or len(position) < 2:
            raise TypeError(f"position must be a pair: {position!r}")
        return int(round(float(position[0]))), int(round(float(position[1])))

    @staticmethod
    def normalize_scale(value, name):
        scale = float(value)
        if scale <= 0:
            raise ValueError(f"{name} must be positive: {value!r}")
        return scale

    @staticmethod
    def validate_group(group):
        required = ("local_rect", "scale_factor", "set_scale_factor", "set_local_position")
        missing = [name for name in required if not hasattr(group, name)]
        if missing:
            raise TypeError(f"group is not compatible with CardSelectionAnimation: missing {missing!r}")
