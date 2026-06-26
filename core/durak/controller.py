"""Isolated OOP controller for Durak game logic."""

from core.durak.actions import AttackAction, DefendAction, TakeCardsAction, ThrowInAction
from core.durak.cards import Card, RANK_ORDER
from core.durak.events import GameEvent
from core.durak.participants import BaseParticipant
from core.durak.rules import DurakRules
from core.durak.state import BattleTable, Deck, DurakGameState, GamePhase


class DurakGameController:
    """Domain-only Durak controller.

    This class owns the state and delegates legality checks to ``DurakRules``.
    It emits domain events, not visual commands.
    """

    def __init__(self, participants: list[BaseParticipant], cards: list[Card]):
        if len(participants) < 2:
            raise ValueError("Durak requires at least two participants")
        self.rules = DurakRules()
        self.state = self._create_initial_state(participants, cards)
        self.thrower_ids: list[str] = []

    def start_game(self) -> list[GameEvent]:
        self._deal_initial_hands()
        self._select_first_attacker()
        self.state.defender_id = self.state.next_active_player_id(self.state.attacker_id)
        self.state.phase = GamePhase.ATTACKING
        return [
            GameEvent(
                "game_started",
                {
                    "attacker_id": self.state.attacker_id,
                    "defender_id": self.state.defender_id,
                    "trump_suit": self.state.trump_suit.value,
                    "trump_card_id": self.state.trump_card_id,
                },
            )
        ]

    def apply_attack(self, action: AttackAction) -> list[GameEvent]:
        if not self.rules.can_start_attack(self.state, action):
            raise ValueError("Illegal attack")
        attacker = self.state.get_participant(action.player_id)
        defender = self.state.get_participant(self.state.defender_id)
        self.state.table = BattleTable(defender_initial_hand_size=defender.hand_size())
        for card_id in action.card_ids:
            attacker.remove_card(card_id)
            self.state.table.add_attack(card_id)
        self.state.phase = GamePhase.DEFENDING
        return [GameEvent("cards_attacked", {"player_id": action.player_id, "card_ids": list(action.card_ids)})]

    def apply_throw_in(self, action: ThrowInAction) -> list[GameEvent]:
        if not self.rules.can_throw_in(self.state, action):
            raise ValueError("Illegal throw-in")
        participant = self.state.get_participant(action.player_id)
        participant.remove_card(action.card_id)
        self.state.table.add_attack(action.card_id)
        if action.player_id not in self.thrower_ids:
            self.thrower_ids.append(action.player_id)
        return [GameEvent("card_thrown_in", {"player_id": action.player_id, "card_id": action.card_id})]

    def apply_defense(self, action: DefendAction) -> list[GameEvent]:
        if not self.rules.can_defend(self.state, action):
            raise ValueError("Illegal defense")
        defender = self.state.get_participant(action.player_id)
        defender.remove_card(action.defense_card_id)
        self.state.table.defend(action.attack_card_id, action.defense_card_id)
        events = [GameEvent("card_defended", {"player_id": action.player_id, "attack_card_id": action.attack_card_id, "defense_card_id": action.defense_card_id})]
        if self.state.table.all_defended():
            events.extend(self.resolve_successful_defense())
        return events

    def apply_take_cards(self, action: TakeCardsAction) -> list[GameEvent]:
        if not self.rules.can_take_cards(self.state, action):
            raise ValueError("Illegal take")
        defender = self.state.get_participant(action.player_id)
        card_ids = self.state.table.all_card_ids()
        defender.receive_cards(card_ids)
        self.state.table.clear()
        next_attacker_id = self.state.next_active_player_id(action.player_id)
        self._draw_cards()
        self.state.attacker_id = next_attacker_id
        self.state.defender_id = self.state.next_active_player_id(next_attacker_id)
        self.state.phase = GamePhase.ATTACKING
        self.thrower_ids.clear()
        self._update_finished_players()
        return [GameEvent("cards_taken", {"player_id": action.player_id, "card_ids": card_ids})]

    def resolve_successful_defense(self) -> list[GameEvent]:
        card_ids = self.state.table.all_card_ids()
        self.state.discard_pile.extend(card_ids)
        self.state.table.clear()
        previous_defender_id = self.state.defender_id
        self._draw_cards()
        self.state.attacker_id = previous_defender_id
        self.state.defender_id = self.state.next_active_player_id(previous_defender_id)
        self.state.phase = GamePhase.ATTACKING
        self.thrower_ids.clear()
        self._update_finished_players()
        return [GameEvent("cards_discarded", {"card_ids": card_ids})]

    def _create_initial_state(self, participants: list[BaseParticipant], cards: list[Card]) -> DurakGameState:
        if len(cards) < len(participants) * self.rules.hand_size + 1:
            raise ValueError("Not enough cards to deal initial hands and choose trump")
        cards_by_id = {card.card_id: card for card in cards}
        trump_card = cards[len(participants) * self.rules.hand_size]
        deck_ids = [card.card_id for card in cards]
        return DurakGameState(
            participants={participant.player_id: participant for participant in participants},
            turn_order=[participant.player_id for participant in participants],
            cards=cards_by_id,
            deck=Deck(deck_ids),
            trump_suit=trump_card.suit,
            trump_card_id=trump_card.card_id,
        )

    def _deal_initial_hands(self) -> None:
        for _ in range(self.rules.hand_size):
            for player_id in self.state.turn_order:
                card_id = self.state.deck.draw_one()
                if card_id is None:
                    return
                self.state.get_participant(player_id).receive_card(card_id)
        trump_card_id = self.state.deck.draw_one()
        self.state.deck.card_ids.append(trump_card_id)

    def _select_first_attacker(self) -> None:
        best_player_id = None
        best_rank = None
        for player_id in self.state.turn_order:
            participant = self.state.get_participant(player_id)
            trump_cards = [
                self.state.cards[card_id]
                for card_id in participant.hand
                if self.state.cards[card_id].suit == self.state.trump_suit
            ]
            if not trump_cards:
                continue
            lowest_trump = min(trump_cards, key=lambda card: RANK_ORDER[card.rank])
            if best_rank is None or RANK_ORDER[lowest_trump.rank] < best_rank:
                best_player_id = player_id
                best_rank = RANK_ORDER[lowest_trump.rank]
        self.state.attacker_id = best_player_id or self.state.turn_order[0]

    def _draw_cards(self) -> None:
        for player_id in self.rules.get_draw_order(self.state, self.thrower_ids):
            self.state.deck.draw_until(self.state.get_participant(player_id), self.rules.hand_size)

    def _update_finished_players(self) -> None:
        if self.state.deck.card_ids:
            return
        active_with_cards = []
        for player_id in self.state.turn_order:
            participant = self.state.get_participant(player_id)
            if participant.hand:
                active_with_cards.append(player_id)
            else:
                participant.is_active = False
        if len(active_with_cards) == 1:
            self.state.fool_id = active_with_cards[0]
            self.state.phase = GamePhase.FINISHED
