"""Base animation primitive.

Animation changes visual group state over time: position, scale, frame index,
or another drawable property. It does not know game rules or controller state.
"""


class Animation:
    """Time-based visual primitive."""

    def __init__(self, duration=0.0):
        self.duration = max(0.0, float(duration))
        self.elapsed = 0.0
        self.started = False
        self._finished = False

    def start(self):
        self.started = True
        self._finished = False
        self.elapsed = 0.0

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()

        self.elapsed += dt
        self.apply(self.get_progress())

        if self.elapsed >= self.duration:
            self.finish()

    def apply(self, progress):
        _ = progress

    def finish(self):
        self._finished = True
        self.started = False

    def is_finished(self):
        return self._finished

    def get_progress(self):
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed / self.duration))


