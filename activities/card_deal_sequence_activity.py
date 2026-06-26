"""Single visual executor for initial and mid-game card dealing snapshots."""

from actions import BotCardPlayAction
from activities.base_activity import Activity
from activities.generated_groups import GeneratedGroupRegistry


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
        self.flight_group_registry = GeneratedGroupRegistry("card_deal_sequence.flight_card")
        self.sequence_active = False

    @property
    def flight_groups(self):
        return self.flight_group_registry.iter_groups()

    @flight_groups.setter
    def flight_groups(self, groups):
        self.flight_group_registry.set_groups(groups)

    def start_deal(self, snapshot):
        if self.sequence_active:
            return False
        before, incoming, order, duration, hands_prepared = self.normalize_snapshot(snapshot)
        if not hands_prepared:
            self.prepare_hand_fans(before, incoming)
        self.pending_steps = list(self.build_steps(before, incoming, order))
        self.deal_duration = duration
        self.sequence_active = True
        if not self.started:
            self.start()
        self.start_next_step()
        return True

    def start_sequence(self, steps, duration=None):
        """Start a prebuilt deal sequence of ``(player_id, resource_key, hand_index)`` steps."""
        if self.sequence_active:
            return False
        self.pending_steps = list(self.normalize_steps(steps))
        self.deal_duration = (
            self.DEFAULT_DURATION
            if duration is None
            else max(0.0, float(duration))
        )
        self.sequence_active = True
        if not self.started:
            self.start()
        self.start_next_step()
        return True

    def prepare_hand_fans(self, hands_before_deal, cards_to_deal):
        """Build hand fans through the one screen-provided preparation contract."""
        self.prepare_hands(hands_before_deal, cards_to_deal)

    def normalize_snapshot(self, snapshot):
        if not isinstance(snapshot, dict):
            raise TypeError("deal snapshot must be a dictionary")
        before = self.normalize_cards_by_player(snapshot.get("hands_before_deal", {}))
        incoming = self.normalize_cards_by_player(snapshot.get("cards_to_deal", {}))
        order = tuple(snapshot.get("deal_order", self.DEFAULT_ORDER))
        duration = max(0.0, float(snapshot.get("duration", self.DEFAULT_DURATION)))
        hands_prepared = bool(snapshot.get("hands_prepared", False))
        return before, incoming, order, duration, hands_prepared

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
    def normalize_steps(steps):
        if not isinstance(steps, (list, tuple)):
            raise TypeError("deal steps must be a list of descriptors")
        normalized = []
        for step in steps:
            if not isinstance(step, (list, tuple)) or len(step) != 3:
                raise ValueError("each deal step must be (player_id, resource_key, hand_index)")
            player_id, resource_key, hand_index = step
            if not isinstance(player_id, str) or not player_id:
                raise ValueError("deal step requires player_id")
            if not isinstance(resource_key, str) or not resource_key:
                raise ValueError("deal step requires resource_key")
            if hand_index is not None:
                hand_index = int(hand_index)
            normalized.append((player_id, resource_key, hand_index))
        return tuple(normalized)

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
            self.finish_sequence()
            return
        self.current_step = self.pending_steps.pop(0)
        player_id, resource_key, hand_index = self.current_step
        back_resource_key, face_resource_key, flip_enabled = self.get_step_flight_visuals(
            player_id,
            resource_key,
            hand_index,
        )
        action = BotCardPlayAction(
            self.get_step_source_screen_geometry(player_id, resource_key, hand_index),
            self.target_geometry_provider(player_id, hand_index),
            back_resource_key=back_resource_key,
            face_resource_key=face_resource_key,
            duration=self.deal_duration, group_id=self.get_next_flight_group_id(),
            cleanup_group=self.remove_flight_group, resource_manager=self.resource_manager,
            flip_enabled=flip_enabled,
        )
        self.current_action = action
        self.flight_group_registry.append(action.group)
        self.on_step_started(player_id, resource_key, hand_index)
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

    def get_step_source_screen_geometry(self, _player_id, _resource_key, _hand_index):
        """Return the transient screen-space source geometry for one dealt card."""
        return self.source_geometry_provider()

    def get_step_flight_visuals(self, player_id, resource_key, _hand_index):
        """Describe the source/face resources and flip rule for one deck card."""
        return "cards.card_back", resource_key, player_id == "bottom_player_hand"

    def on_step_started(self, _player_id, _resource_key, _hand_index):
        """Allow source-specific sequences to hide a card when its flight begins."""

    def finish_sequence(self):
        """Finish one supplied dealing snapshot without ending this screen activity."""
        self.sequence_active = False

    def get_next_flight_group_id(self):
        return self.flight_group_registry.next_id()

    def remove_flight_group(self, group):
        self.flight_group_registry.remove(group)

    def iter_generated_groups(self):
        return self.flight_group_registry.iter_groups()

    def apply_fixture(self, fixture):
        """Accept the screen fixture protocol; runner starts deal snapshots explicitly."""
        _ = fixture
