"""High-level activity for one player's turn on the play area."""

from activities.base_activity import Activity


class PlayerTurnActivity(Activity):
    """Own the visual process of a player turn on the play area.

    At this stage the turn activity delegates card-slot placement to
    PlayAreaSlotsActivity. Later it can coordinate turn-level effects,
    controller commands, focus, and short actions without making the table
    screen own those details directly.
    """

    def __init__(self, play_area_slots_activity):
        super().__init__(duration=0.0)
        self.play_area_slots_activity = play_area_slots_activity

    def start(self):
        super().start()
        self.play_area_slots_activity.start()

    def update(self, dt):
        if not self.started:
            self.start()
        self.play_area_slots_activity.update(dt)

    def draw(self, screen):
        if hasattr(self.play_area_slots_activity, "draw"):
            self.play_area_slots_activity.draw(screen)

    def apply_fixture(self, fixture):
        self.play_area_slots_activity.apply_fixture(fixture)

    def is_finished(self):
        return self._finished

    def finish(self):
        self.play_area_slots_activity.finish()
        super().finish()
