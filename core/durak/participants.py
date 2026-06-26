"""Participant entities for human and bot players."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from typing import Any


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
    def choose_action(self, state: Any):
        """Return a domain action for the current state."""


@dataclass
class SimpleBotPlayer(BaseBotPlayer):
    def choose_action(self, state: Any):
        return None
