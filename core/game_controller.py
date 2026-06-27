"""GameController facade for the first playable Durak assembly.

The controller owns game rules and logical state through ``core.durak``.  It
emits screen-level visual commands, but does not import pygame, Activity,
Group, Frame, or screen geometry.
"""

from base import BaseGameController
from core.durak import AttackAction, BaseBotPlayer, BaseHumanPlayer, Card, DefendAction, DurakGameController
from core.durak.actions import TakeCardsAction, ThrowInAction
from core.durak.cards import RANK_ORDER, Rank, Suit
from core.durak.state import GamePhase
from core.game_state import CardState, GameState
from game_screen.events import ControllerResponse, VisualCommand


class PassiveBotPlayer(BaseBotPlayer):
    """Bot participant placeholder for the first controller-connected build."""

    def choose_action(self, state):
        if state.phase == GamePhase.ATTACKING and state.attacker_id == self.player_id:
            if not self.hand:
                return None
            return AttackAction(self.player_id, (self.hand[0],))
        if state.phase != GamePhase.DEFENDING:
            return None
        if state.defender_id == self.player_id:
            attack_card_id = next(
                (pair.attack_card_id for pair in state.table.pairs if not pair.is_defended()),
                None,
            )
            if attack_card_id is None:
                return None
            attack_card = state.cards[attack_card_id]
            for card_id in self.hand:
                defense_card = state.cards[card_id]
                trump_suit = state.trump_suit
                if attack_card.suit == defense_card.suit and RANK_ORDER[defense_card.rank] > RANK_ORDER[attack_card.rank]:
                    return DefendAction(self.player_id, attack_card_id, card_id)
                if defense_card.suit == trump_suit and attack_card.suit != trump_suit:
                    return DefendAction(self.player_id, attack_card_id, card_id)
            return TakeCardsAction(self.player_id)
        for card_id in self.hand:
            if state.cards[card_id].rank in state.table.ranks_on_table(state.cards):
                return ThrowInAction(self.player_id, card_id)
        return None


class GameController(BaseGameController):
    """Screen-facing controller backed by the isolated Durak domain model."""

    DEFAULT_FRAMES = ("deck", "bottom_hand", "top_hand", "battle_table", "discard")
    PLAYER_ORDER = ("bottom_player_hand", "right_player_hand", "top_player_hand", "left_player_hand")
    HUMAN_PLAYER_ID = "bottom_player_hand"
    BOT_CARD_RESOURCE_KEY = "cards.card_back"

    def __init__(self, initial_state=None, durak_game=None):
        self.state = initial_state or GameState(frames={frame: [] for frame in self.DEFAULT_FRAMES})
        self.clicked_group_ids = []
        self.input_events = []
        self.started = False
        self.durak_game = durak_game or self.create_default_durak_game()

    def start_game(self):
        if self.started:
            return ControllerResponse(state_view=self.get_state_view())
        self.started = True
        events = self.durak_game.start_game()
        return ControllerResponse(
            commands=(
                self.build_deck_trump_command(),
                self.build_initial_deal_command(),
                self.build_turn_prompt_command(),
            ),
            state_view={"events": events, **self.get_state_view()},
        )

    def load_fixture(self, state):
        self.state = state

    def on_group_clicked(self, group_id):
        self.clicked_group_ids.append(group_id)

    def handle_input(self, input_event):
        self.input_events.append(input_event)

        if input_event.group_id and input_event.type in ("click", "double_click"):
            self.on_group_clicked(input_event.group_id)

        selected_card = (getattr(input_event, "payload", {}) or {}).get("selected_card")
        if input_event.type != "click" or not selected_card:
            return ControllerResponse(state_view=self.get_state_view())

        command = self.apply_selected_human_card(selected_card)
        commands = (command, self.build_turn_prompt_command()) if command is not None else (self.build_turn_prompt_command(),)
        return ControllerResponse(commands=commands, state_view=self.get_state_view())

    def handle_activity_result(self, result):
        _ = result
        commands = self.continue_after_visual_step()
        return ControllerResponse(commands=tuple(commands), state_view=self.get_state_view())

    def get_state(self):
        return self.state

    def get_state_view(self):
        state = self.durak_game.state
        available_card_ids = self.get_available_human_card_ids()
        return {
            "phase": state.phase.value,
            "attacker_id": state.attacker_id,
            "defender_id": state.defender_id,
            "trump_suit": state.trump_suit.value,
            "trump_card_id": state.trump_card_id,
            "deck_count": len(state.deck.card_ids),
            "human_available_card_ids": tuple(available_card_ids),
            "human_turn_finished": not bool(available_card_ids),
            "players": {
                player_id: participant.get_public_view()
                for player_id, participant in state.participants.items()
            },
            "table": [
                {
                    "attack_card_id": pair.attack_card_id,
                    "defense_card_id": pair.defense_card_id,
                }
                for pair in state.table.pairs
            ],
        }

    def apply_selected_human_card(self, selected_card):
        card_id = self.resolve_selected_card_id(selected_card)
        if not card_id:
            return None

        state = self.durak_game.state
        player_id = self.HUMAN_PLAYER_ID
        try:
            if state.phase == GamePhase.ATTACKING and state.attacker_id == player_id:
                events = self.durak_game.apply_attack(AttackAction(player_id, (card_id,)))
                return self.build_play_card_command(selected_card, card_id, events)
            if state.phase == GamePhase.DEFENDING and state.defender_id == player_id:
                attack_card_id = self.find_first_attack_card_beaten_by(card_id)
                if attack_card_id is None:
                    return None
                events = self.durak_game.apply_defense(DefendAction(player_id, attack_card_id, card_id))
                return self.build_play_card_command(selected_card, card_id, events)
            if state.phase == GamePhase.DEFENDING and state.defender_id != player_id:
                events = self.durak_game.apply_throw_in(ThrowInAction(player_id, card_id))
                return self.build_play_card_command(selected_card, card_id, events)
        except ValueError:
            return None
        return None

    def find_first_attack_card_beaten_by(self, defense_card_id):
        state = self.durak_game.state
        for pair in state.table.pairs:
            if pair.is_defended():
                continue
            if self.durak_game.rules.can_beat(
                state.cards[pair.attack_card_id],
                state.cards[defense_card_id],
                state.trump_suit,
            ):
                return pair.attack_card_id
        return None

    @staticmethod
    def resolve_selected_card_id(selected_card):
        resource_key = selected_card.get("resource_key")
        if isinstance(resource_key, str) and resource_key.startswith("cards."):
            return resource_key
        card_id = selected_card.get("card_id")
        if isinstance(card_id, str) and card_id.startswith("cards."):
            return card_id
        return None

    def build_deck_trump_command(self):
        return VisualCommand(
            type="deck.set_trump",
            target="deck_frame",
            payload={
                "card_id": self.durak_game.state.trump_card_id,
                "resource_key": self.durak_game.state.trump_card_id,
                "suit": self.durak_game.state.trump_suit.value,
            },
            command_id="game.start.trump",
            blocking=False,
        )

    def build_initial_deal_command(self):
        return VisualCommand(
            type="deal.initial",
            target="card_deal_sequence",
            payload={
                "hands_before_deal": {player_id: () for player_id in self.PLAYER_ORDER},
                "cards_to_deal": self.build_visual_cards_by_player(),
                "deal_order": self.PLAYER_ORDER,
                "duration": 0.18,
            },
            command_id="game.start.deal",
            blocking=True,
        )

    def build_visual_cards_by_player(self):
        visual_cards = {}
        for player_id in self.PLAYER_ORDER:
            hand = tuple(self.durak_game.state.get_participant(player_id).hand)
            if player_id == self.HUMAN_PLAYER_ID:
                visual_cards[player_id] = hand
            else:
                visual_cards[player_id] = tuple(self.BOT_CARD_RESOURCE_KEY for _card_id in hand)
        return visual_cards

    def build_turn_prompt_command(self):
        available_card_ids = self.get_available_human_card_ids()
        return VisualCommand(
            type="turn.prompt",
            payload={
                "attacker_id": self.durak_game.state.attacker_id,
                "defender_id": self.durak_game.state.defender_id,
                "phase": self.durak_game.state.phase.value,
                "available_card_ids": tuple(available_card_ids),
                "turn_finished": not bool(available_card_ids),
            },
            command_id="game.turn.prompt",
            blocking=False,
        )

    def get_available_human_card_ids(self):
        state = self.durak_game.state
        participant = state.get_participant(self.HUMAN_PLAYER_ID)
        hand = tuple(participant.hand)
        if not hand:
            return ()
        if state.phase == GamePhase.ATTACKING and state.attacker_id == self.HUMAN_PLAYER_ID:
            return hand
        if state.phase != GamePhase.DEFENDING:
            return ()
        if state.defender_id == self.HUMAN_PLAYER_ID:
            return self.get_available_human_defense_card_ids()
        if not state.table.all_defended():
            return ()
        return self.get_available_human_throw_in_card_ids()

    def get_available_human_defense_card_ids(self):
        state = self.durak_game.state
        participant = state.get_participant(self.HUMAN_PLAYER_ID)
        available_card_ids = []
        for card_id in participant.hand:
            if self.find_first_attack_card_beaten_by(card_id) is not None:
                available_card_ids.append(card_id)
        return tuple(available_card_ids)

    def get_available_human_throw_in_card_ids(self):
        return self.get_available_throw_in_card_ids(self.HUMAN_PLAYER_ID)

    def get_available_throw_in_card_ids(self, player_id):
        state = self.durak_game.state
        participant = state.get_participant(player_id)
        available_card_ids = []
        for card_id in participant.hand:
            try:
                if self.durak_game.rules.can_throw_in(
                    state,
                    ThrowInAction(player_id, card_id),
                ):
                    available_card_ids.append(card_id)
            except ValueError:
                continue
        return tuple(available_card_ids)

    def build_play_card_command(self, selected_card, card_id, events):
        turn_context = dict(selected_card)
        turn_context["card_id"] = card_id
        turn_context["resource_key"] = card_id
        turn_context["events"] = [event.type for event in events]
        return VisualCommand(
            type="start_player_turn",
            payload={"turn_context": turn_context},
            command_id=f"play.{card_id}",
            blocking=True,
        )

    def continue_after_visual_step(self):
        guard = 0
        while guard < 12:
            guard += 1
            if self.durak_game.state.phase == GamePhase.FINISHED:
                return (self.build_turn_prompt_command(),)
            if self.should_wait_for_throw_in_window():
                return (self.build_turn_prompt_command(),)
            if self.is_human_waiting_for_input():
                return (self.build_turn_prompt_command(),)
            command = self.apply_next_automatic_step()
            if command is not None:
                if isinstance(command, VisualCommand) and command.type == "turn.prompt":
                    return (command,)
                return (command, self.build_turn_prompt_command())
        return (self.build_turn_prompt_command(),)

    def is_human_waiting_for_input(self):
        state = self.durak_game.state
        available_card_ids = self.get_available_human_card_ids()
        if not available_card_ids:
            return False
        if state.phase == GamePhase.ATTACKING:
            return state.attacker_id == self.HUMAN_PLAYER_ID
        if state.phase == GamePhase.DEFENDING:
            return state.defender_id == self.HUMAN_PLAYER_ID or state.defender_id != self.HUMAN_PLAYER_ID
        return False

    def apply_next_automatic_step(self):
        state = self.durak_game.state
        if state.phase == GamePhase.DEFENDING and state.defender_id == self.HUMAN_PLAYER_ID:
            self.durak_game.apply_take_cards(TakeCardsAction(self.HUMAN_PLAYER_ID))
            return None
        if state.phase == GamePhase.DEFENDING and state.table.all_defended():
            if self.any_throw_in_available():
                if self.get_available_human_throw_in_card_ids():
                    return self.build_turn_prompt_command()
                return self.apply_next_automatic_throw_in()
            self.durak_game.complete_defense()
            return None

        active_player_id = self.get_active_automatic_player_id()
        if active_player_id is None:
            return None
        participant = state.get_participant(active_player_id)
        chooser = getattr(participant, "choose_action", None)
        if not callable(chooser):
            return None
        action = chooser(state)
        if action is None:
            return None
        if isinstance(action, AttackAction):
            events = self.durak_game.apply_attack(action)
            return self.build_auto_play_card_command(active_player_id, action.card_ids[0], events)
        if isinstance(action, DefendAction):
            events = self.durak_game.apply_defense(action)
            return self.build_auto_play_card_command(active_player_id, action.defense_card_id, events)
        if isinstance(action, ThrowInAction):
            events = self.durak_game.apply_throw_in(action)
            return self.build_auto_play_card_command(active_player_id, action.card_id, events)
        if isinstance(action, TakeCardsAction):
            self.durak_game.apply_take_cards(action)
        return None

    def should_wait_for_throw_in_window(self):
        state = self.durak_game.state
        return (
            state.phase == GamePhase.DEFENDING
            and state.table.all_defended()
            and bool(self.get_available_human_throw_in_card_ids())
        )

    def any_throw_in_available(self):
        state = self.durak_game.state
        if state.phase != GamePhase.DEFENDING or not state.table.all_defended():
            return False
        for player_id, participant in state.participants.items():
            if player_id == state.defender_id or not participant.is_active:
                continue
            if self.get_available_throw_in_card_ids(player_id):
                return True
        return False

    def apply_next_automatic_throw_in(self):
        state = self.durak_game.state
        for player_id in state.turn_order:
            if player_id in (state.defender_id, self.HUMAN_PLAYER_ID):
                continue
            available_card_ids = self.get_available_throw_in_card_ids(player_id)
            if not available_card_ids:
                continue
            action = ThrowInAction(player_id, available_card_ids[0])
            events = self.durak_game.apply_throw_in(action)
            return self.build_auto_play_card_command(player_id, action.card_id, events)
        return None

    def get_active_automatic_player_id(self):
        state = self.durak_game.state
        if state.phase == GamePhase.ATTACKING:
            if state.attacker_id != self.HUMAN_PLAYER_ID:
                return state.attacker_id
            return None
        if state.phase == GamePhase.DEFENDING:
            if state.defender_id != self.HUMAN_PLAYER_ID:
                return state.defender_id
            return None
        return None

    def build_auto_play_card_command(self, player_id, card_id, events):
        return VisualCommand(
            type="start_player_turn",
            payload={
                "turn_context": {
                    "player_id": player_id,
                    "card_id": card_id,
                    "resource_key": card_id,
                    "events": [event.type for event in events],
                }
            },
            command_id=f"auto.play.{card_id}",
            blocking=True,
        )

    @classmethod
    def create_default_durak_game(cls):
        participants = [
            BaseHumanPlayer(cls.HUMAN_PLAYER_ID, "Player", 0),
            PassiveBotPlayer("right_player_hand", "Right Bot", 1),
            PassiveBotPlayer("top_player_hand", "Top Bot", 2),
            PassiveBotPlayer("left_player_hand", "Left Bot", 3),
        ]
        return DurakGameController(participants, cls.create_default_deck())

    @classmethod
    def create_default_deck(cls):
        cards = [
            Card(f"cards.{rank.value}_of_{suit.value}", rank, suit)
            for rank in Rank
            for suit in Suit
        ]
        return cls.place_card_at(cls.place_card_at(cards, "cards.6_of_hearts", 0), "cards.a_of_hearts", 24)

    @staticmethod
    def place_card_at(cards, card_id, index):
        cards = list(cards)
        current_index = next(i for i, card in enumerate(cards) if card.card_id == card_id)
        card = cards.pop(current_index)
        cards.insert(index, card)
        return cards

    @staticmethod
    def create_fixture_state():
        return GameState.from_cards(
            [
                CardState("card_6_clubs", "6", "clubs", "bottom_hand"),
                CardState("card_7_clubs", "7", "clubs", "bottom_hand"),
                CardState("card_8_clubs", "8", "clubs", "bottom_hand"),
                CardState("card_9_clubs", "9", "clubs", "bottom_hand"),
                CardState("card_10_clubs", "10", "clubs", "bottom_hand"),
                CardState("card_j_clubs", "j", "clubs", "bottom_hand"),
            ]
        )
