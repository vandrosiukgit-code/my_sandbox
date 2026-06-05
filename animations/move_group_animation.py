"""Position animation for a single Group."""

from animations.base_animation import Animation


class MoveGroupAnimation(Animation):
    """Move a Group between two screen positions over time."""

    def __init__(self, group, to_position, duration=0.25, from_position=None):
        super().__init__(duration=duration)
        self.group = group
        self.from_position = self.normalize_position(from_position) if from_position is not None else None
        self.to_position = self.normalize_position(to_position)

    def start(self):
        super().start()
        if self.from_position is None:
            self.from_position = tuple(self.group.rect.topleft)
        self.apply(0.0)

    def apply(self, progress):
        progress = self.ease_out(progress)
        x = self.interpolate(self.from_position[0], self.to_position[0], progress)
        y = self.interpolate(self.from_position[1], self.to_position[1], progress)
        self.group.set_position(x, y)

    def finish(self):
        self.group.set_position(*self.to_position)
        super().finish()

    @staticmethod
    def normalize_position(position):
        return int(position[0]), int(position[1])

    @staticmethod
    def interpolate(start, end, progress):
        return round(start + (end - start) * progress)

    @staticmethod
    def ease_out(progress):
        progress = max(0.0, min(1.0, float(progress)))
        return 1.0 - (1.0 - progress) * (1.0 - progress)
