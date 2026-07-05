"""GameController facade for the first playable Durak assembly.

The controller owns game rules and logical state through ``core.durak``.  It
emits screen-level visual commands, but does not import pygame, Activity,
Group, Frame, or screen geometry.
"""

import random

from base import BaseGameController
from core.durak import AttackAction, BaseHumanPlayer, Card, DefendAction, DurakGameController, Rank, RuleBasedBotPlayer, Suit
from core.durak.actions import ThrowInAction
from core.durak.state import GamePhase
from core.game_state import CardState, GameState
from game_screen.events import ControllerResponse, VisualCommand


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
        self._last_snapshot = self.durak_game.build_snapshot()
        self._pending_visual_commands = []
        self.moves_count = 0

    def get_waiting_player_ids(self):
        return (self.HUMAN_PLAYER_ID,)

    def queue_visual_commands(self, commands):
        self._pending_visual_commands.extend(tuple(commands or ()))

    def flush_pending_visual_commands(self):
        if not self._pending_visual_commands:
            return ()
        commands = []
        while self._pending_visual_commands:
            command = self._pending_visual_commands.pop(0)
            commands.append(command)
            if getattr(command, "blocking", True):
                break
        return tuple(commands)

    def start_game(self):
        if self.started:
            return ControllerResponse(state_view=self.get_state_view())
        self.started = True
        self.moves_count = 0
        result = self.durak_game.build_result(self.durak_game.start_game(), waiting_player_ids=self.get_waiting_player_ids())
        self._last_snapshot = result.snapshot
        return ControllerResponse(
            commands=(
                self.build_deck_trump_command(),
                self.build_initial_deal_command(),
            ),
            state_view={"events": result.events, **self.get_state_view(result)},
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

        result, command = self.apply_selected_human_card(selected_card)
        self.record_moves_from_events(result.events)
        self._last_snapshot = result.snapshot
        commands = (command,) if command is not None else (self.build_turn_prompt_command(result),)
        return ControllerResponse(commands=commands, state_view=self.get_state_view())

    def handle_activity_result(self, result):
        if getattr(result, "status", "completed") != "completed":
            return ControllerResponse(commands=(self.build_turn_prompt_command(),), state_view=self.get_state_view())
        queued_commands = self.flush_pending_visual_commands()
        if queued_commands:
            return ControllerResponse(commands=queued_commands, state_view=self.get_state_view())
        previous_snapshot = self._last_snapshot
        domain_result = self.durak_game.advance_to_next_checkpoint(waiting_player_ids=self.get_waiting_player_ids())
        self.record_moves_from_events(domain_result.events)
        commands = self.build_commands_from_domain_result(domain_result, previous_snapshot)
        self._last_snapshot = domain_result.snapshot
        return ControllerResponse(commands=tuple(commands), state_view=self.get_state_view(domain_result))

    def get_state(self):
        return self.state

    def get_state_view(self, domain_result=None):
        snapshot = (domain_result.snapshot if domain_result is not None else self.durak_game.build_snapshot())
        available_card_ids = (
            tuple(domain_result.available_card_ids)
            if domain_result is not None and domain_result.waiting_player_id == self.HUMAN_PLAYER_ID
            else self.durak_game.get_available_card_ids_for_player(self.HUMAN_PLAYER_ID)
        )
        return {
            "phase": snapshot.phase,
            "attacker_id": snapshot.attacker_id,
            "defender_id": snapshot.defender_id,
            "trump_suit": snapshot.trump_suit,
            "trump_card_id": snapshot.trump_card_id,
            "deck_count": snapshot.deck_count,
            "human_available_card_ids": tuple(available_card_ids),
            "human_turn_finished": not bool(available_card_ids),
            "players": {
                player.player_id: {
                    "player_id": player.player_id,
                    "name": player.name,
                    "seat_index": player.seat_index,
                    "hand_size": player.hand_size,
                    "is_active": player.is_active,
                }
                for player in snapshot.players
            },
            "table": [
                {
                    "attack_card_id": pair.attack_card_id,
                    "defense_card_id": pair.defense_card_id,
                }
                for pair in snapshot.table_pairs
            ],
        }

    def get_end_game_stats(self):
        snapshot = self.durak_game.build_snapshot()
        loser_id = snapshot.fool_id
        winners = tuple(player for player in snapshot.players if player.player_id != loser_id)
        loser = next((player for player in snapshot.players if player.player_id == loser_id), None)
        return {
            "moves_count": self.moves_count,
            "winner": ", ".join(player.name for player in winners) if winners else "Unknown",
            "loser": loser.name if loser is not None else "Unknown",
            "winner_ids": tuple(player.player_id for player in winners),
            "loser_id": loser_id,
            "phase": snapshot.phase,
        }

    def record_moves_from_events(self, events):
        self.moves_count += sum(
            1
            for event in events or ()
            if event.type in ("cards_attacked", "card_defended", "card_thrown_in")
        )

    def apply_selected_human_card(self, selected_card):
        card_id = self.resolve_selected_card_id(selected_card)
        if not card_id:
            return self.durak_game.build_result(waiting_player_ids=self.get_waiting_player_ids()), None

        state = self.durak_game.state
        player_id = self.HUMAN_PLAYER_ID
        try:
            if state.phase == GamePhase.ATTACKING and state.attacker_id == player_id:
                result = self.durak_game.submit_action(AttackAction(player_id, (card_id,)), waiting_player_ids=self.get_waiting_player_ids())
                return result, self.build_play_card_command(selected_card, card_id, result.events)
            if state.phase == GamePhase.DEFENDING and state.defender_id == player_id:
                attack_card_id = self.find_first_attack_card_beaten_by(card_id)
                if attack_card_id is None:
                    return self.durak_game.build_result(waiting_player_ids=self.get_waiting_player_ids()), None
                result = self.durak_game.submit_action(
                    DefendAction(player_id, attack_card_id, card_id),
                    waiting_player_ids=self.get_waiting_player_ids(),
                )
                return result, self.build_play_card_command(selected_card, card_id, result.events)
            if state.phase == GamePhase.DEFENDING and state.defender_id != player_id and state.table.all_defended():
                result = self.durak_game.submit_action(ThrowInAction(player_id, card_id), waiting_player_ids=self.get_waiting_player_ids())
                return result, self.build_play_card_command(selected_card, card_id, result.events)
        except ValueError:
            return self.durak_game.build_result(waiting_player_ids=self.get_waiting_player_ids()), None
        return self.durak_game.build_result(waiting_player_ids=self.get_waiting_player_ids()), None

    def find_first_attack_card_beaten_by(self, defense_card_id):
        for attack_card_id, candidate_defense_card_id in self.durak_game.get_available_defense_pairs(self.HUMAN_PLAYER_ID):
            if candidate_defense_card_id == defense_card_id:
                return attack_card_id
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
                "deck_count": len(self.durak_game.state.deck.card_ids),
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

    def build_turn_prompt_command(self, domain_result=None):
        if domain_result is None:
            domain_result = self.durak_game.build_result(waiting_player_ids=self.get_waiting_player_ids())
        available_card_ids = (
            tuple(domain_result.available_card_ids)
            if domain_result.waiting_player_id == self.HUMAN_PLAYER_ID
            else ()
        )
        return VisualCommand(
            type="turn.prompt",
            payload={
                "attacker_id": domain_result.snapshot.attacker_id,
                "defender_id": domain_result.snapshot.defender_id,
                "phase": domain_result.snapshot.phase,
                "available_card_ids": tuple(available_card_ids),
                "turn_finished": not bool(available_card_ids),
                "can_take_cards": bool(domain_result.can_take_cards),
            },
            command_id="game.turn.prompt",
            blocking=False,
        )

    def get_available_human_card_ids(self):
        return tuple(self.durak_game.get_available_card_ids_for_player(self.HUMAN_PLAYER_ID))

    def get_available_human_defense_card_ids(self):
        return tuple(
            defense_card_id
            for _attack_card_id, defense_card_id in self.durak_game.get_available_defense_pairs(self.HUMAN_PLAYER_ID)
        )

    def get_available_human_throw_in_card_ids(self):
        return tuple(self.durak_game.get_available_throw_in_card_ids(self.HUMAN_PLAYER_ID))

    def get_available_throw_in_card_ids(self, player_id):
        return tuple(self.durak_game.get_available_throw_in_card_ids(player_id))

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

    def build_auto_command_from_event(self, event):
        if event.type == "cards_attacked":
            card_ids = tuple(event.payload.get("card_ids", ()))
            if card_ids:
                return self.build_auto_play_card_command(event.payload["player_id"], card_ids[0], (event,))
        if event.type == "card_defended":
            return self.build_auto_play_card_command(
                event.payload["player_id"],
                event.payload["defense_card_id"],
                (event,),
            )
        if event.type == "card_thrown_in":
            return self.build_auto_play_card_command(
                event.payload["player_id"],
                event.payload["card_id"],
                (event,),
            )
        return None

    def build_table_slots_payload(self, snapshot):
        table_slots = {}
        for index, pair in enumerate(snapshot.table_pairs):
            slot_id = "cards_slot_frame" if index == 0 else f"cards_slot_frame_{index}"
            cards = [pair.attack_card_id]
            if pair.defense_card_id is not None:
                cards.append(pair.defense_card_id)
            table_slots[slot_id] = tuple(cards)
        return table_slots

    def build_visual_hand_prefix(self, player_id, count):
        count = max(0, int(count))
        if player_id == self.HUMAN_PLAYER_ID:
            hand = tuple(self.durak_game.state.get_participant(player_id).hand)
            return hand[:count]
        return tuple(self.BOT_CARD_RESOURCE_KEY for _ in range(count))

    def build_follow_up_deal_command(self, previous_snapshot, current_snapshot, baseline_hand_sizes=None):
        previous_players = {player.player_id: player for player in previous_snapshot.players}
        current_players = {player.player_id: player for player in current_snapshot.players}
        baseline_hand_sizes = dict(baseline_hand_sizes or {})
        hands_before_deal = {}
        cards_to_deal = {}
        deal_order = []
        for player_id in self.PLAYER_ORDER:
            previous_hand_size = baseline_hand_sizes.get(
                player_id,
                previous_players.get(player_id).hand_size if player_id in previous_players else 0,
            )
            current_hand_size = current_players.get(player_id).hand_size if player_id in current_players else 0
            if current_hand_size <= previous_hand_size:
                continue
            current_visual_hand = self.build_visual_hand_prefix(player_id, current_hand_size)
            hands_before_deal[player_id] = current_visual_hand[:previous_hand_size]
            cards_to_deal[player_id] = current_visual_hand[previous_hand_size:current_hand_size]
            deal_order.append(player_id)
        if not cards_to_deal:
            return None
        return VisualCommand(
            type="deal.initial",
            target="card_deal_sequence",
            payload={
                "hands_before_deal": hands_before_deal,
                "cards_to_deal": cards_to_deal,
                "deal_order": tuple(deal_order),
                "duration": 0.18,
            },
            command_id="game.followup.deal",
            blocking=True,
        )

    def build_commands_from_domain_result(self, domain_result, previous_snapshot=None):
        commands = []
        previous_snapshot = previous_snapshot or self._last_snapshot
        for event in domain_result.events:
            command = self.build_auto_command_from_event(event)
            if command is not None:
                commands.append(command)
                break
            if event.type == "cards_discarded":
                discard_command = VisualCommand(
                    type="table.discard",
                    payload={"table_slots": self.build_table_slots_payload(previous_snapshot)},
                    command_id="game.table.discard",
                    blocking=True,
                )
                commands.append(discard_command)
                deal_command = self.build_follow_up_deal_command(previous_snapshot, domain_result.snapshot)
                if deal_command is not None:
                    self.queue_visual_commands((deal_command,))
                break
            if event.type == "cards_taken":
                defender_id = event.payload["player_id"]
                previous_players = {player.player_id: player for player in previous_snapshot.players}
                previous_hand_size = previous_players.get(defender_id).hand_size if defender_id in previous_players else 0
                taken_cards_count = len(event.payload.get("card_ids", ()))
                take_command = VisualCommand(
                    type="table.take",
                    payload={
                        "defender_id": defender_id,
                        "cards_before": self.build_visual_hand_prefix(defender_id, previous_hand_size),
                        "table_slots": self.build_table_slots_payload(previous_snapshot),
                    },
                    command_id="game.table.take",
                    blocking=True,
                )
                commands.append(take_command)
                baseline_hand_sizes = {
                    defender_id: previous_hand_size + taken_cards_count,
                }
                deal_command = self.build_follow_up_deal_command(
                    previous_snapshot,
                    domain_result.snapshot,
                    baseline_hand_sizes=baseline_hand_sizes,
                )
                if deal_command is not None:
                    self.queue_visual_commands((deal_command,))
                break
        if not commands:
            commands.append(self.build_turn_prompt_command(domain_result))
        return tuple(commands)

    @classmethod
    def create_default_durak_game(cls):
        participants = [
            BaseHumanPlayer(cls.HUMAN_PLAYER_ID, "Player", 0),
            RuleBasedBotPlayer("right_player_hand", "Right Bot", 1),
            RuleBasedBotPlayer("top_player_hand", "Top Bot", 2),
            RuleBasedBotPlayer("left_player_hand", "Left Bot", 3),
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

    @classmethod
    def create_shuffled_deck(cls, rng=None):
        cards = [
            Card(f"cards.{rank.value}_of_{suit.value}", rank, suit)
            for rank in Rank
            for suit in Suit
        ]
        shuffler = rng if rng is not None else random.SystemRandom()
        shuffler.shuffle(cards)
        return cards

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
