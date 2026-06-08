"""Coordinate animation for card selection feedback."""

from animations.base_animation import Animation


class CardSelectionAnimation(Animation):
    """Move and scale one card to highlight or restore it.

    This is a coordinate animation: it changes the card group's local position
    and scale factor over time, but it does not advance sprite frames.
    """

    def __init__(
        self,
        group,
        to_position,
        to_scale,
        duration=0.12,
        from_position=None,
        from_scale=None,
    ):
        super().__init__(duration=duration)
        self.group = group
        self.from_position = self.normalize_position(from_position) if from_position is not None else None
        self.to_position = self.normalize_position(to_position)
        self.from_scale = float(from_scale) if from_scale is not None else None
        self.to_scale = float(to_scale)

    def start(self):
        super().start()
        if self.from_position is None:
            self.from_position = tuple(self.group.local_rect.topleft)
        if self.from_scale is None:
            self.from_scale = self.get_group_scale(self.group)
        self.apply(0.0)

    def apply(self, progress):
        progress = self.ease_out(progress)
        x = self.interpolate(self.from_position[0], self.to_position[0], progress)
        y = self.interpolate(self.from_position[1], self.to_position[1], progress)
        scale = self.interpolate(self.from_scale, self.to_scale, progress)

        self.group.set_scale_factor(scale)
        self.group.set_local_position(x, y)

    def finish(self):
        self.group.set_scale_factor(self.to_scale)
        self.group.set_local_position(*self.to_position)
        super().finish()

    @staticmethod
    def get_group_scale(group):
        return 1.0 if group.scale_factor is None else float(group.scale_factor)

    @staticmethod
    def normalize_position(position):
        return int(round(float(position[0]))), int(round(float(position[1])))

    @staticmethod
    def interpolate(start, end, progress):
        return start + (end - start) * progress

    @staticmethod
    def ease_out(progress):
        progress = max(0.0, min(1.0, float(progress)))
        return 1.0 - (1.0 - progress) * (1.0 - progress)
