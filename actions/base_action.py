"""Base visual action.

An Action owns a short visual script and delegates frame-by-frame changes to
Animation objects. It is started by an Frame after GameController has
already accepted the game intent and returned a visual command.
"""


class Action:
    """Composable visual script executed by an Frame."""

    def __init__(self, group_ids=None, animations=None):
        self.group_ids = tuple(group_ids or ())
        self.animations = list(animations or ())
        self.started = False
        self._finished = False

    def start(self):
        self.started = True
        self._finished = False
        for animation in self.animations:
            if hasattr(animation, "start"):
                animation.start()

    def update(self, dt):
        if self._finished:
            return
        if not self.started:
            self.start()

        running = []
        for animation in self.animations:
            animation.update(dt)
            if not self._is_finished(animation):
                running.append(animation)
        self.animations = running

        if not self.animations:
            self.finish()

    def finish(self):
        self._finished = True
        self.started = False

    def is_finished(self):
        return self._finished

    @staticmethod
    def _is_finished(item):
        is_finished = getattr(item, "is_finished", False)
        if callable(is_finished):
            return is_finished()
        return bool(is_finished)


