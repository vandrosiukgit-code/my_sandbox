"""Fixture-driven visual scenario for a generic card refill plan."""

from activities.base_activity import Activity
from activities.card_deal_sequence_activity import CardDealSequenceActivity


class DealCardsActivity(Activity):
    """Build a refill plan and delegate all flights to a child sequence."""

    DEFAULT_DURATION = CardDealSequenceActivity.DEFAULT_DURATION

    def __init__(self, source_geometry_provider, target_geometry_provider, prepare_bottom_hand, land_card, resource_manager):
        super().__init__(duration=0.0)
        self.sequence = CardDealSequenceActivity(
            source_geometry_provider,
            target_geometry_provider,
            prepare_bottom_hand,
            land_card,
            resource_manager,
        )

    def start_deals(self, deals, duration=None):
        return self.sequence.start_sequence(self.normalize_deals(deals), duration)

    @staticmethod
    def normalize_deals(deals):
        if not isinstance(deals, (list, tuple)):
            raise TypeError("deals must be a list of descriptors")
        normalized = []
        bottom_hand_index = 0
        for deal in deals:
            if not isinstance(deal, dict):
                raise TypeError("each deal must be a dictionary")
            target_activity_id = deal.get("target_activity_id")
            card_resource_keys = deal.get("card_resource_keys", deal.get("cards"))
            if not isinstance(target_activity_id, str) or not target_activity_id:
                raise ValueError("deal requires target_activity_id")
            if not isinstance(card_resource_keys, (list, tuple)):
                raise ValueError("deal requires card_resource_keys")
            for resource_key in card_resource_keys:
                if not isinstance(resource_key, str) or not resource_key:
                    raise ValueError("card_resource_keys must contain non-empty strings")
                hand_index = None
                if target_activity_id == "bottom_player_hand":
                    hand_index = bottom_hand_index
                    bottom_hand_index += 1
                normalized.append((target_activity_id, resource_key, hand_index))
        return tuple(normalized)

    def update(self, dt):
        if not self.started:
            self.start()
        self.sequence.update(dt)

    def apply_fixture(self, fixture):
        if fixture and fixture.get("enabled", False):
            self.start_deals(fixture.get("deals", ()), fixture.get("duration"))

    def iter_generated_groups(self):
        return self.sequence.iter_generated_groups()

    def finish(self):
        self.sequence.finish()
        super().finish()
