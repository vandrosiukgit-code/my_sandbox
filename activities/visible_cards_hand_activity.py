"""Visible-card decorator for player hand fan activities."""

from activities.base_activity import Activity


class VisibleCardsHandDecorator(Activity):
    """Decorate a hand fan activity with visible card resources.

    The wrapped activity owns fan geometry and generated groups. This decorator
    owns the player-facing card list and gives the wrapped activity one resource
    key per generated card slot.
    """

    def __init__(
        self,
        hand_activity,
        cards=None,
        resource_manager=None,
        max_cards=None,
        owns_hand_activity=True,
    ):
        super().__init__(duration=0.0)
        self.hand_activity = hand_activity
        self.resource_manager = resource_manager
        self.max_cards = self.normalize_max_cards(max_cards)
        self.owns_hand_activity = bool(owns_hand_activity)
        self.card_resource_keys = self.limit_cards(self.normalize_cards(cards or ()))
        self.hand_activity.card_resource_provider = self.get_card_resource_key
        self.hand_activity.card_layer_name = "card"
        self.hand_activity.card_count = len(self.card_resource_keys)

    def start(self):
        if self.started:
            return
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
        next_keys = self.limit_cards(self.normalize_cards(cards))
        if next_keys == self.card_resource_keys:
            return

        self.hand_activity.clear_generated_groups()
        self.card_resource_keys = next_keys
        self.hand_activity.card_count = len(self.card_resource_keys)
        if getattr(self.hand_activity, "started", False):
            self.hand_activity.sync_visual_groups()
            self.hand_activity.apply_fan_layout()

    def get_card_resource_key(self, index):
        try:
            return self.card_resource_keys[index]
        except IndexError as error:
            raise RuntimeError("VisibleCardsHandDecorator card index is out of range") from error

    def is_finished(self):
        return self._finished or self.hand_activity.is_finished()

    def finish(self):
        if self.owns_hand_activity:
            self.hand_activity.finish()
        super().finish()

    def get_card_selection_context(self, group):
        """Return controller-facing selection data for a wrapped hand group."""
        if not hasattr(self.hand_activity, "get_card_selection_context"):
            return None
        context = self.hand_activity.get_card_selection_context(group)
        if context is None:
            return None
        hand_index = context.get("hand_index")
        if hand_index is not None and 0 <= hand_index < len(self.card_resource_keys):
            resource_key = self.card_resource_keys[hand_index]
            context = dict(context)
            context["card_id"] = resource_key
            context["resource_key"] = resource_key
        return context

    def get_fixture_cards(self, fixture):
        for key in ("cards", "card_resource_keys", "resource_keys"):
            if key in fixture:
                return fixture[key]
        if fixture.get("cards_from_manifest"):
            return self.get_manifest_card_keys(fixture)
        return None

    def get_manifest_card_keys(self, fixture):
        """Temporary GUI debug source; Controller must provide real hand cards."""
        if self.resource_manager is None:
            return ()

        resource_keys = tuple(
            key
            for key in self.resource_manager.get_runtime_cache()
            if key.startswith("cards.") and key != "cards.card_back"
        )
        start, stop = self.get_fixture_slice_bounds(fixture)
        return resource_keys[start:stop]

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

    def limit_cards(self, cards):
        if self.max_cards is None:
            return tuple(cards)
        return tuple(cards)[: self.max_cards]

    @staticmethod
    def normalize_max_cards(max_cards):
        if max_cards is None:
            return None
        value = int(max_cards)
        if value < 0:
            raise ValueError(f"max_cards must be non-negative: {max_cards!r}")
        return value

    @staticmethod
    def normalize_slice(card_slice):
        if isinstance(card_slice, dict):
            start = card_slice.get("start", 0)
            stop = card_slice.get("stop", card_slice.get("end"))
        else:
            values = tuple(card_slice)
            start = values[0] if len(values) >= 1 else 0
            stop = values[1] if len(values) >= 2 else None
        start = 0 if start is None else int(start)
        stop = None if stop is None else int(stop)
        return start, stop

    @classmethod
    def get_fixture_slice_bounds(cls, fixture):
        card_slice = fixture.get("card_slice", fixture.get("cards_slice"))
        if card_slice is None:
            start, stop = 0, None
        else:
            start, stop = cls.normalize_slice(card_slice)

        if "card_count" in fixture:
            count = max(0, int(fixture["card_count"]))
            stop = start + count
        return start, stop
