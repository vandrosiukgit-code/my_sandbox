"""Decorators for player hand activities."""

from activities.base_activity import Activity


class VisibleCardsHandDecorator(Activity):
    """Decorate a hand fan activity with visible card resources.

    The wrapped activity owns fan geometry and generated groups. This decorator
    owns the player-facing card list and gives the wrapped activity one resource
    key per generated card slot.
    """

    def __init__(self, hand_activity, cards=None):
        super().__init__(duration=0.0)
        self.hand_activity = hand_activity
        self.card_resource_keys = self.normalize_cards(cards or ())
        self.hand_activity.card_resource_provider = self.get_card_resource_key
        self.hand_activity.card_layer_name = "card"
        self.hand_activity.card_count = len(self.card_resource_keys)

    def start(self):
        super().start()
        self.hand_activity.start()

    def update(self, dt):
        self.hand_activity.update(dt)

    def draw(self, screen):
        self.hand_activity.draw(screen)

    def apply_fixture(self, fixture):
        """Apply visible-card fixture fields and delegate geometry to the hand."""
        if not fixture:
            return

        cards = self.get_fixture_cards(fixture)
        if cards is not None:
            self.set_cards(cards)

        decorated_fixture = dict(fixture)
        decorated_fixture["card_count"] = len(self.card_resource_keys)
        decorated_fixture.pop("resource_key", None)
        self.hand_activity.apply_fixture(decorated_fixture)

    def set_cards(self, cards):
        """Replace visible cards and force generated groups to use new resources."""
        next_keys = self.normalize_cards(cards)
        if next_keys == self.card_resource_keys:
            return

        self.hand_activity.clear_generated_groups()
        self.card_resource_keys = next_keys
        self.hand_activity.card_count = len(self.card_resource_keys)

    def get_card_resource_key(self, index):
        try:
            return self.card_resource_keys[index]
        except IndexError as error:
            raise RuntimeError("VisibleCardsHandDecorator card index is out of range") from error

    def is_finished(self):
        return self.hand_activity.is_finished()

    def finish(self):
        self.hand_activity.finish()
        super().finish()

    @staticmethod
    def get_fixture_cards(fixture):
        for key in ("cards", "card_resource_keys", "resource_keys"):
            if key in fixture:
                return fixture[key]
        return None

    @staticmethod
    def normalize_cards(cards):
        normalized = []
        for card in cards or ():
            if isinstance(card, str):
                normalized.append(card)
            elif isinstance(card, dict):
                resource_key = card.get("resource_key") or card.get("key")
                if resource_key:
                    normalized.append(str(resource_key))
        return tuple(normalized)
