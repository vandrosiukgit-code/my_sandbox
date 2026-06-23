"""Single visual executor for initial and mid-game card dealing snapshots."""

from actions import PlayerCardPlayAction
from activities.base_activity import Activity


class CardDealSequenceActivity(Activity):
    DEFAULT_DURATION = 0.26
    DEFAULT_ORDER = ("bottom_player_hand", "right_player_hand", "top_player_hand", "left_player_hand")

    def __init__(self, source_geometry_provider, target_geometry_provider, prepare_hands, reveal_card, resource_manager):
        super().__init__(duration=0.0)
        self.source_geometry_provider = source_geometry_provider
        self.target_geometry_provider = target_geometry_provider
        self.prepare_hands = prepare_hands
        self.reveal_card = reveal_card
        self.resource_manager = resource_manager
        self.pending_steps = []
        self.current_action = None
        self.current_step = None
        self.flight_groups = []
        self.flight_index = 0
        self.sequence_active = False

    def start_deal(self, snapshot):
        if self.sequence_active:
            return False
        before, incoming, order, duration = self.normalize_snapshot(snapshot)
        self.prepare_hands(before, incoming)
        self.pending_steps = list(self.build_steps(before, incoming, order))
        self.deal_duration = duration
        self.sequence_active = True
        if not self.started:
            self.start()
        self.start_next_step()
        return True

    def normalize_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            raise TypeError("deal snapshot must be a dictionary")
        before = self.normalize_cards_by_player(snapshot.get("hands_before_deal", {}))
        incoming = self.normalize_cards_by_player(snapshot.get("cards_to_deal", {}))
        order = tuple(snapshot.get("deal_order", self.DEFAULT_ORDER))
        duration = max(0.0, float(snapshot.get("duration", self.DEFAULT_DURATION)))
        return before, incoming, order, duration

    @staticmethod
    def normalize_cards_by_player(value):
        if not isinstance(value, dict):
            raise TypeError("card snapshot must map player IDs to card keys")
        result = {}
        for player_id, keys in value.items():
            if not isinstance(player_id, str) or not isinstance(keys, (list, tuple)):
                raise ValueError("each player requires a list of resource keys")
            result[player_id] = tuple(keys)
        return result

    @staticmethod
    def build_steps(before, incoming, order):
        offsets = {player_id: len(before.get(player_id, ())) for player_id in incoming}
        positions = {player_id: 0 for player_id in incoming}
        steps = []
        while any(positions[player_id] < len(incoming[player_id]) for player_id in incoming):
            for player_id in order:
                cards = incoming.get(player_id, ())
                index = positions.get(player_id, 0)
                if index >= len(cards):
                    continue
                steps.append((player_id, cards[index], offsets[player_id] + index))
                positions[player_id] = index + 1
        return tuple(steps)

    def start_next_step(self):
        if not self.pending_steps:
            self.sequence_active = False
            return
        self.current_step = self.pending_steps.pop(0)
        player_id, _resource_key, hand_index = self.current_step
        action = PlayerCardPlayAction(
            self.source_geometry_provider(), self.target_geometry_provider(player_id, hand_index),
            "cards.card_back", duration=self.deal_duration, group_id=self.get_next_flight_group_id(),
            cleanup_group=self.remove_flight_group, resource_manager=self.resource_manager,
        )
        self.current_action = action
        self.flight_groups.append(action.group)
        action.start()

    def update(self, dt):
        if self.current_action is None:
            return
        self.current_action.update(dt)
        if self.current_action.is_finished():
            self.reveal_card(*self.current_step)
            self.current_action = None
            self.current_step = None
            self.start_next_step()

    def get_next_flight_group_id(self):
        self.flight_index += 1
        return f"card_deal_sequence.flight_card.{self.flight_index}"

    def remove_flight_group(self, group):
        self.flight_groups = [item for item in self.flight_groups if item is not group]

    def iter_generated_groups(self):
        return tuple(self.flight_groups)

    def apply_fixture(self, fixture):
        """Accept the screen fixture protocol; runner starts deal snapshots explicitly."""
        _ = fixture
