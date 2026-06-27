"""Participant entities for human and bot players."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any

from core.durak.actions import AttackAction, DefendAction, TakeCardsAction, ThrowInAction
from core.durak.cards import RANK_ORDER


@dataclass
class BaseParticipant(ABC):
    player_id: str
    name: str
    seat_index: int
    hand: list[str] = field(default_factory=list)
    is_active: bool = True

    def receive_card(self, card_id: str) -> None:
        self.hand.append(card_id)

    def receive_cards(self, card_ids: list[str]) -> None:
        self.hand.extend(card_ids)

    def remove_card(self, card_id: str) -> None:
        self.hand.remove(card_id)

    def has_card(self, card_id: str) -> bool:
        return card_id in self.hand

    def hand_size(self) -> int:
        return len(self.hand)

    def get_public_view(self) -> dict[str, Any]:
        return {
            "player_id": self.player_id,
            "name": self.name,
            "seat_index": self.seat_index,
            "hand_size": len(self.hand),
            "is_active": self.is_active,
        }


@dataclass
class BaseHumanPlayer(BaseParticipant):
    selected_card_ids: list[str] = field(default_factory=list)

    def clear_selection(self) -> None:
        self.selected_card_ids.clear()


@dataclass
class BaseBotPlayer(BaseParticipant):
    @abstractmethod
    def choose_action(self, state: Any, rules: Any = None):
        """Return a domain action for the current state."""


@dataclass
class SimpleBotPlayer(BaseBotPlayer):
    def choose_action(self, state: Any, rules: Any = None):
        return None


@dataclass
class RuleBasedBotPlayer(BaseBotPlayer):
    """Deterministic bot that chooses the lowest legal card for each step."""

    def choose_action(self, state: Any, rules: Any = None):
        if rules is None:
            return None
        phase_value = getattr(state.phase, "value", state.phase)
        if phase_value == "attacking" and state.attacker_id == self.player_id:
            return self.choose_attack_action(state)
        if phase_value != "defending":
            return None
        if state.defender_id == self.player_id:
            return self.choose_defense_action(state, rules)
        return self.choose_throw_in_action(state, rules)

    def choose_attack_action(self, state: Any):
        card_id = self.choose_lowest_card_id(state, self.hand)
        if card_id is None:
            return None
        return AttackAction(self.player_id, (card_id,))

    def choose_defense_action(self, state: Any, rules: Any):
        attack_pair = next((pair for pair in state.table.pairs if not pair.is_defended()), None)
        if attack_pair is None:
            return None
        attack_card = state.cards[attack_pair.attack_card_id]
        defense_card_ids = [
            card_id
            for card_id in self.hand
            if rules.can_beat(attack_card, state.cards[card_id], state.trump_suit)
        ]
        defense_card_id = self.choose_lowest_card_id(state, defense_card_ids)
        if defense_card_id is None:
            return TakeCardsAction(self.player_id)
        return DefendAction(self.player_id, attack_pair.attack_card_id, defense_card_id)

    def choose_throw_in_action(self, state: Any, rules: Any):
        throw_in_card_ids = [
            card_id
            for card_id in self.hand
            if rules.can_throw_in(state, ThrowInAction(self.player_id, card_id))
        ]
        throw_in_card_id = self.choose_lowest_card_id(state, throw_in_card_ids)
        if throw_in_card_id is None:
            return None
        return ThrowInAction(self.player_id, throw_in_card_id)

    @staticmethod
    def choose_lowest_card_id(state: Any, card_ids):
        if not card_ids:
            return None
        return min(
            card_ids,
            key=lambda card_id: (
                int(state.cards[card_id].suit == state.trump_suit),
                RANK_ORDER[state.cards[card_id].rank],
                card_id,
            ),
        )
