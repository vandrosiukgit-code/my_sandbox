"""Base animation primitive.

Animation changes visual group state over time: position, scale, frame index,
or another drawable property. It does not know game rules or controller state.
"""


class Animation:
    """Time-based visual primitive."""

    animated_properties = ()
    coordinate_space = None

    def __init__(self, duration=0.0, on_finish=None, max_frame_dt=None):
        self.duration = max(0.0, float(duration))
        self.max_frame_dt = None if max_frame_dt is None else max(0.0, float(max_frame_dt))
        self.on_finish = on_finish
        self.elapsed = 0.0
        self.started = False
        self._finished = False
        self.cancelled = False

    def start(self):
        self.started = True
        self._finished = False
        self.cancelled = False
        self.elapsed = 0.0

    def reset(self):
        """Return the animation to its initial not-started state."""
        self.elapsed = 0.0
        self.started = False
        self._finished = False
        self.cancelled = False

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()

        self.elapsed += self.normalize_dt(dt)
        if self.elapsed >= self.duration:
            self.finish()
            return

        self.apply(self.get_progress())

    def apply(self, progress):
        raise NotImplementedError("Animation subclasses must implement apply()")

    def finish(self):
        if self._finished:
            return
        self.apply(1.0)
        self._finished = True
        self.started = False
        self.cancelled = False
        if self.on_finish is not None:
            self.on_finish(self)

    def cancel(self):
        """Stop the animation without forcing the target final state."""
        if self._finished:
            return
        self._finished = True
        self.started = False
        self.cancelled = True

    def is_finished(self):
        return self._finished

    def get_progress(self):
        if self.duration <= 0:
            return 1.0
        return max(0.0, min(1.0, self.elapsed / self.duration))

    def normalize_dt(self, dt):
        try:
            value = float(dt)
        except (TypeError, ValueError):
            return 0.0
        value = max(0.0, value)
        if self.max_frame_dt is not None:
            value = min(value, self.max_frame_dt)
        return value


