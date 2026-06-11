"""High-level activity for one player's turn on the play area."""

from activities.base_activity import Activity


class PlayerTurnActivity(Activity):
    """Own the visual process of a player turn on the play area.

    At this stage the turn activity delegates card-slot placement to
    PlayAreaSlotsActivity. Later it can coordinate turn-level effects,
    controller commands, focus, and short actions without making the table
    screen own those details directly.
    """

    def __init__(self, play_area_slots_activity, owns_play_area_slots_activity=False):
        super().__init__(duration=0.0)
        self.validate_play_area_slots_activity(play_area_slots_activity)
        self.play_area_slots_activity = play_area_slots_activity
        self.owns_play_area_slots_activity = bool(owns_play_area_slots_activity)
        self.turn_context = None
        self.turn_active = False

    @staticmethod
    def validate_play_area_slots_activity(play_area_slots_activity):
        if play_area_slots_activity is None:
            raise ValueError("PlayerTurnActivity requires play_area_slots_activity")
        for method_name in ("start", "update", "finish"):
            if not callable(getattr(play_area_slots_activity, method_name, None)):
                raise TypeError(f"play_area_slots_activity must provide {method_name}()")

    def start(self):
        if self.started:
            return
        super().start()
        if not getattr(self.play_area_slots_activity, "started", False):
            self.play_area_slots_activity.start()

    def start_turn(self, turn_context):
        """Start one visual turn with controller-facing context."""
        if self.turn_active:
            return False
        if not self.started:
            self.start()
        self.turn_context = dict(turn_context or {})
        self.turn_active = True
        return True

    def finish_turn(self):
        """Finish the current visual turn without finishing the activity."""
        self.turn_active = False
        self.turn_context = None

    def update(self, dt):
        if not self.started:
            self.start()
            return
        self.play_area_slots_activity.update(dt)

    def draw(self, screen):
        self.draw_debug_overlay(screen)

    def draw_debug_overlay(self, screen):
        if hasattr(self.play_area_slots_activity, "draw_debug_overlay"):
            self.play_area_slots_activity.draw_debug_overlay(screen)
        elif hasattr(self.play_area_slots_activity, "draw"):
            self.play_area_slots_activity.draw(screen)

    def iter_generated_groups(self):
        if hasattr(self.play_area_slots_activity, "iter_generated_groups"):
            return tuple(self.play_area_slots_activity.iter_generated_groups())
        return ()

    def apply_fixture(self, fixture):
        if hasattr(self.play_area_slots_activity, "apply_fixture"):
            self.play_area_slots_activity.apply_fixture(fixture)

    def is_finished(self):
        return self._finished

    def finish(self):
        if self.owns_play_area_slots_activity:
            is_finished = getattr(self.play_area_slots_activity, "is_finished", None)
            if not callable(is_finished) or not is_finished():
                self.play_area_slots_activity.finish()
        self.turn_active = False
        self.turn_context = None
        super().finish()
