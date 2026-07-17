"""Short press/release pulse for the take button group."""

from actions.base_action import Action


class TakeButtonPressAction(Action):
    """Animate a quick button press without changing controller state."""

    def __init__(self, group, base_scale=1.0, pressed_scale=0.92, duration=0.12):
        self.group = group
        self.base_scale = float(base_scale)
        self.pressed_scale = float(pressed_scale)
        self.duration = max(0.0, float(duration))
        self.elapsed = 0.0
        super().__init__(group_ids=(group.id,))

    def start(self):
        super().start()
        self.elapsed = 0.0
        self.group.set_scale_factor(self.base_scale)

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()

        self.elapsed += max(0.0, float(dt or 0.0))
        if self.duration <= 0.0 or self.elapsed >= self.duration:
            self.group.set_scale_factor(self.base_scale)
            self.finish()
            return

        progress = max(0.0, min(1.0, self.elapsed / self.duration))
        if progress <= 0.5:
            phase = progress / 0.5
            scale = self.base_scale + (self.pressed_scale - self.base_scale) * phase
        else:
            phase = (progress - 0.5) / 0.5
            scale = self.pressed_scale + (self.base_scale - self.pressed_scale) * phase
        self.group.set_scale_factor(scale)

    def cancel(self):
        self.group.set_scale_factor(self.base_scale)
        super().cancel()
