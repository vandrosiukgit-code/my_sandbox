"""Visual-only opening deal scenario driven by development fixtures."""

from activities.base_activity import Activity
from activities.card_deal_sequence_activity import CardDealSequenceActivity


class StartGameActivity(Activity):
    """Build the opening six-round deal plan and delegate its execution."""

    DEFAULT_DEAL_DURATION = CardDealSequenceActivity.DEFAULT_DURATION
    DEFAULT_RECIPIENT_ORDER = ("bottom_player_hand", "right_player_hand", "top_player_hand", "left_player_hand")

    def __init__(
        self, source_geometry_provider, target_geometry_provider, reset_recipients,
        prepare_bottom_hand, land_card, resource_manager, card_resource_key="cards.card_back",
        card_count=6, deal_duration=DEFAULT_DEAL_DURATION,
    ):
        super().__init__(duration=0.0)
        self.reset_recipients = reset_recipients
        self.card_resource_key = card_resource_key
        self.card_count = max(0, int(card_count))
        self.deal_duration = max(0.0, float(deal_duration))
        self.recipient_order = self.DEFAULT_RECIPIENT_ORDER
        self.bottom_player_card_resource_keys = ()
        self.sequence = CardDealSequenceActivity(
            source_geometry_provider, target_geometry_provider, prepare_bottom_hand, land_card, resource_manager
        )

    def start_scenario(self, card_count=None, recipient_order=None, bottom_player_card_resource_keys=None):
        if self.sequence.sequence_active:
            return False
        if card_count is not None:
            self.card_count = max(0, int(card_count))
        if recipient_order is not None:
            self.recipient_order = self.normalize_recipient_order(recipient_order)
        if bottom_player_card_resource_keys is not None:
            self.bottom_player_card_resource_keys = self.normalize_bottom_player_cards(bottom_player_card_resource_keys, self.card_count)
        if not self.started:
            self.start()
        self.reset_recipients(self.recipient_order)
        return self.sequence.start_sequence(
            self.build_deal_sequence(self.recipient_order, self.card_count, self.bottom_player_card_resource_keys, self.card_resource_key),
            self.deal_duration,
        )

    @classmethod
    def build_recipient_sequence(cls, recipient_order, card_count):
        return tuple(recipient for _round in range(max(0, int(card_count))) for recipient in recipient_order)

    @classmethod
    def build_deal_sequence(cls, recipient_order, card_count, bottom_player_card_resource_keys, bot_card_resource_key):
        bottom_cards = tuple(bottom_player_card_resource_keys)
        return tuple(
            (
                recipient_id,
                bottom_cards[round_index] if recipient_id == "bottom_player_hand" and bottom_cards else bot_card_resource_key,
                round_index if recipient_id == "bottom_player_hand" and bottom_cards else None,
            )
            for round_index in range(max(0, int(card_count)))
            for recipient_id in recipient_order
        )

    @staticmethod
    def normalize_recipient_order(recipient_order):
        if not isinstance(recipient_order, (list, tuple)) or not recipient_order:
            raise ValueError("recipient_order must contain target activity IDs")
        if not all(isinstance(activity_id, str) and activity_id for activity_id in recipient_order):
            raise ValueError("recipient_order must contain non-empty strings")
        return tuple(recipient_order)

    @staticmethod
    def normalize_bottom_player_cards(card_resource_keys, card_count):
        if not isinstance(card_resource_keys, (list, tuple)) or len(card_resource_keys) != card_count:
            raise ValueError("bottom_player_card_resource_keys must contain one card per deal round")
        if not all(isinstance(resource_key, str) and resource_key for resource_key in card_resource_keys):
            raise ValueError("bottom_player_card_resource_keys must contain non-empty strings")
        return tuple(card_resource_keys)

    def update(self, dt):
        if not self.started:
            self.start()
        self.sequence.update(dt)

    def apply_fixture(self, fixture):
        if not fixture:
            return
        if "bottom_player_card_resource_keys" in fixture:
            self.bottom_player_card_resource_keys = self.normalize_bottom_player_cards(
                fixture["bottom_player_card_resource_keys"], int(fixture.get("card_count", self.card_count))
            )
        if fixture.get("enabled", False):
            self.start_scenario(fixture.get("card_count", self.card_count), fixture.get("recipient_order", self.recipient_order), self.bottom_player_card_resource_keys)

    def iter_generated_groups(self):
        return self.sequence.iter_generated_groups()

    def finish(self):
        self.sequence.finish()
        super().finish()
