"""Visual-only opening deal scenario driven by development fixtures."""

from actions import PlayerCardPlayAction
from activities.base_activity import Activity


class StartGameActivity(Activity):
    """Deal one face-down card per recipient until every hand reaches a count."""

    DEFAULT_RECIPIENT_ORDER = (
        "bottom_player_hand",
        "right_player_hand",
        "top_player_hand",
        "left_player_hand",
    )

    def __init__(
        self,
        source_geometry_provider,
        target_geometry_provider,
        reset_recipients,
        land_card,
        resource_manager,
        card_resource_key="cards.card_back",
        card_count=6,
        deal_duration=0.18,
    ):
        super().__init__(duration=0.0)
        self.source_geometry_provider = source_geometry_provider
        self.target_geometry_provider = target_geometry_provider
        self.reset_recipients = reset_recipients
        self.land_card = land_card
        self.resource_manager = resource_manager
        self.card_resource_key = card_resource_key
        self.card_count = max(0, int(card_count))
        self.deal_duration = max(0.0, float(deal_duration))
        self.recipient_order = self.DEFAULT_RECIPIENT_ORDER
        self.bottom_player_card_resource_keys = ()
        self.pending_recipients = []
        self.current_action = None
        self.current_recipient_id = None
        self.flight_groups = []
        self.flight_index = 0
        self.scenario_active = False

    def start_scenario(self, card_count=None, recipient_order=None, bottom_player_card_resource_keys=None):
        if self.scenario_active:
            return False
        if card_count is not None:
            self.card_count = max(0, int(card_count))
        if recipient_order is not None:
            self.recipient_order = self.normalize_recipient_order(recipient_order)
        if bottom_player_card_resource_keys is not None:
            self.bottom_player_card_resource_keys = self.normalize_bottom_player_cards(
                bottom_player_card_resource_keys,
                self.card_count,
            )
        if not self.started:
            self.start()
        self.reset_recipients(self.recipient_order)
        self.pending_recipients = list(
            self.build_deal_sequence(
                self.recipient_order,
                self.card_count,
                self.bottom_player_card_resource_keys,
                self.card_resource_key,
            )
        )
        self.scenario_active = True
        self.start_next_deal()
        return True

    @classmethod
    def build_recipient_sequence(cls, recipient_order, card_count):
        return tuple(recipient for _round in range(max(0, int(card_count))) for recipient in recipient_order)

    @classmethod
    def build_deal_sequence(
        cls,
        recipient_order,
        card_count,
        bottom_player_card_resource_keys,
        bot_card_resource_key,
    ):
        bottom_cards = tuple(bottom_player_card_resource_keys)
        deals = []
        for round_index in range(max(0, int(card_count))):
            for recipient_id in recipient_order:
                resource_key = bot_card_resource_key
                if recipient_id == "bottom_player_hand" and bottom_cards:
                    resource_key = bottom_cards[round_index]
                deals.append((recipient_id, resource_key))
        return tuple(deals)

    @staticmethod
    def normalize_recipient_order(recipient_order):
        if not isinstance(recipient_order, (list, tuple)) or not recipient_order:
            raise ValueError("recipient_order must contain target activity IDs")
        if not all(isinstance(activity_id, str) and activity_id for activity_id in recipient_order):
            raise ValueError("recipient_order must contain non-empty strings")
        return tuple(recipient_order)

    @staticmethod
    def normalize_bottom_player_cards(card_resource_keys, card_count):
        if not isinstance(card_resource_keys, (list, tuple)):
            raise TypeError("bottom_player_card_resource_keys must be a list of resource keys")
        if len(card_resource_keys) != card_count:
            raise ValueError("bottom_player_card_resource_keys must contain one card per deal round")
        if not all(isinstance(resource_key, str) and resource_key for resource_key in card_resource_keys):
            raise ValueError("bottom_player_card_resource_keys must contain non-empty strings")
        return tuple(card_resource_keys)

    def start_next_deal(self):
        if not self.pending_recipients:
            self.scenario_active = False
            return
        self.current_recipient_id, resource_key = self.pending_recipients.pop(0)
        source_geometry = self.source_geometry_provider()
        target_geometry = self.target_geometry_provider(self.current_recipient_id)
        if source_geometry is None or target_geometry is None:
            raise RuntimeError("StartGameActivity requires deck and recipient screen geometry")
        action = PlayerCardPlayAction(
            from_geometry=source_geometry,
            to_geometry=target_geometry,
            face_resource_key=resource_key,
            duration=self.deal_duration,
            group_id=self.get_next_flight_group_id(),
            cleanup_group=self.remove_flight_group,
            resource_manager=self.resource_manager,
        )
        self.current_action = action
        self.current_resource_key = resource_key
        self.flight_groups.append(action.group)
        action.start()

    def get_next_flight_group_id(self):
        self.flight_index += 1
        return f"start_game.flight_card.{self.flight_index}"

    def remove_flight_group(self, group):
        self.flight_groups = [flight_group for flight_group in self.flight_groups if flight_group is not group]

    def update(self, dt):
        if not self.started:
            self.start()
        if self.current_action is None:
            return
        self.current_action.update(dt)
        if not self.current_action.is_finished():
            return
        self.land_card(self.current_recipient_id, self.current_resource_key)
        self.current_action = None
        self.current_recipient_id = None
        self.current_resource_key = None
        self.start_next_deal()

    def apply_fixture(self, fixture):
        if not fixture:
            return
        if "bottom_player_card_resource_keys" in fixture:
            self.bottom_player_card_resource_keys = self.normalize_bottom_player_cards(
                fixture["bottom_player_card_resource_keys"],
                int(fixture.get("card_count", self.card_count)),
            )
        if not fixture.get("enabled", False):
            return
        self.start_scenario(
            card_count=fixture.get("card_count", self.card_count),
            recipient_order=fixture.get("recipient_order", self.recipient_order),
            bottom_player_card_resource_keys=self.bottom_player_card_resource_keys,
        )

    def iter_generated_groups(self):
        return tuple(self.flight_groups)

    def finish(self):
        if self.current_action is not None:
            self.current_action.cancel()
        self.current_action = None
        self.current_resource_key = None
        self.flight_groups = []
        self.pending_recipients = []
        self.scenario_active = False
        super().finish()
