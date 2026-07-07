"""Visual table-take scenario built on the standard card-dealing sequence."""

from activities.card_deal_sequence_activity import CardDealSequenceActivity


class TakeTableActivity(CardDealSequenceActivity):
    """Move table cards into one or more prepared hands using the deal sequence."""

    def __init__(
        self,
        get_table_cards,
        set_table_cards,
        remove_table_card,
        prepare_hands,
        target_geometry_provider,
        reveal_card,
        clear_table,
        resource_manager,
        duration=0.26,
        on_safe_point=None,
    ):
        super().__init__(
            source_geometry_provider=lambda: None,
            target_geometry_provider=target_geometry_provider,
            prepare_hands=prepare_hands,
            reveal_card=reveal_card,
            resource_manager=resource_manager,
            on_safe_point=on_safe_point,
        )
        self.get_table_cards = get_table_cards
        self.set_table_cards = set_table_cards
        self.remove_table_card = remove_table_card
        self.clear_table = clear_table
        self.duration = duration
        self.take_plan = ()
        self.take_index = 0
        self.initial_delay_seconds = 0.0
        self.delay_elapsed = 0.0
        self.plan_active = False
        self.table_cards = ()
        self.source_geometry_by_hand_index = {}
        self.source_resource_key_by_hand_index = {}
        self.source_card_by_hand_index = {}

    def start_take_plan(self, takes, initial_delay_seconds=0.0):
        self.take_plan = tuple(takes)
        self.take_index = 0
        self.initial_delay_seconds = max(0.0, float(initial_delay_seconds))
        self.delay_elapsed = 0.0
        self.plan_active = bool(self.take_plan)
        if not self.plan_active:
            self.finish()
            return False
        self.prepare_all_hand_fans()
        self.prepare_current_table()
        if self.initial_delay_seconds <= 0:
            self.start_current_take()
        return True

    def update(self, dt):
        if not self.plan_active:
            return
        if not self.sequence_active:
            self.delay_elapsed += dt
            if self.delay_elapsed < self.initial_delay_seconds:
                return
            self.initial_delay_seconds = 0.0
            self.start_current_take()
        super().update(dt)

    def prepare_current_table(self):
        command = self.take_plan[self.take_index]
        self.set_table_cards(command.get("table_slots", {}))

    def prepare_all_hand_fans(self):
        hands_before_deal = {}
        cards_to_deal = {}
        for command in self.take_plan:
            defender_id = command["defender_id"]
            hands_before_deal[defender_id] = tuple(command.get("cards_before", ()))
            cards_to_deal[defender_id] = tuple(
                self.get_hand_resource_key(defender_id, resource_key)
                for cards in command.get("table_slots", {}).values()
                for resource_key in cards
            )
        self.prepare_hand_fans(hands_before_deal, cards_to_deal)

    def start_current_take(self):
        command = self.take_plan[self.take_index]
        self.table_cards = tuple(self.get_table_cards())
        defender_id = command["defender_id"]
        cards_before = tuple(command.get("cards_before", ()))
        incoming = tuple(
            self.get_hand_resource_key(defender_id, card["resource_key"])
            for card in self.table_cards
        )
        offset = len(cards_before)
        self.source_geometry_by_hand_index = {
            offset + index: card["geometry"]
            for index, card in enumerate(self.table_cards)
        }
        self.source_resource_key_by_hand_index = {
            offset + index: card["resource_key"]
            for index, card in enumerate(self.table_cards)
        }
        self.source_card_by_hand_index = {
            offset + index: card
            for index, card in enumerate(self.table_cards)
        }
        self.start_deal(
            {
                "hands_before_deal": {defender_id: cards_before},
                "cards_to_deal": {defender_id: incoming},
                "deal_order": (defender_id,),
                "duration": self.duration,
                "hands_prepared": True,
            }
        )

    def get_step_source_screen_geometry(self, _player_id, _resource_key, hand_index):
        return self.source_geometry_by_hand_index[hand_index]

    def get_step_flight_visuals(self, _player_id, resource_key, _hand_index):
        source_resource_key = self.source_resource_key_by_hand_index[_hand_index]
        is_bottom_player = _player_id == "bottom_player_hand"
        return source_resource_key, resource_key, not is_bottom_player

    def on_step_started(self, _player_id, _resource_key, hand_index):
        self.remove_table_card(self.source_card_by_hand_index[hand_index])

    @staticmethod
    def get_hand_resource_key(defender_id, table_resource_key):
        if defender_id == "bottom_player_hand":
            return table_resource_key
        return "cards.card_back"

    def finish_sequence(self):
        super().finish_sequence()
        self.clear_table()
        self.take_index += 1
        if self.take_index >= len(self.take_plan):
            self.plan_active = False
            self.finish()
            return
        self.prepare_current_table()
        self.start_current_take()
