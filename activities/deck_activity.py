"""Long-lived visual activity for a face-down table deck."""

from activities.base_activity import Activity
from group import Group


class DeckActivity(Activity):
    """Own one visual-only card-back group in an assigned deck Frame."""

    def __init__(
        self,
        frame,
        resource_manager,
        resource_key="cards.card_back",
        group_id=None,
    ):
        super().__init__(duration=0.0)
        self.frame = frame
        self.resource_manager = resource_manager
        self.resource_key = resource_key
        self.group_id = group_id or f"{frame.id}.card_back"
        self.deck_group = None

    def start(self):
        if self.started:
            return
        super().start()
        self.deck_group = Group.create_group(
            self.group_id,
            (("card_back", self.resource_key),),
            resource_manager=self.resource_manager,
        )
        self.frame.place_group_local(self.deck_group, (0, 0))

    def update(self, dt):
        _ = dt
        if not self.started:
            self.start()

    def apply_fixture(self, fixture):
        """Accept the screen fixture protocol; the static deck has no options yet."""
        _ = fixture

    def iter_generated_groups(self):
        if self.deck_group is None:
            return ()
        return (self.deck_group,)

    def finish(self):
        if self.deck_group is not None:
            self.frame.remove_group(self.deck_group.id)
            self.deck_group = None
        super().finish()
