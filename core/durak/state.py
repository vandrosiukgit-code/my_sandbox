"""State owner for the isolated Durak game model."""

from dataclasses import dataclass, field
from enum import Enum

from core.durak.cards import Card, Suit
from core.durak.participants import BaseParticipant


class GamePhase(str, Enum):
    NOT_STARTED = "not_started"
    ATTACKING = "attacking"
    DEFENDING = "defending"
    ROUND_ENDED = "round_ended"
    FINISHED = "finished"


@dataclass
class Deck:
    card_ids: list[str] = field(default_factory=list)

    def draw_one(self) -> str | None:
        if not self.card_ids:
            return None
        return self.card_ids.pop(0)

    def draw_until(self, participant: BaseParticipant, hand_size: int) -> list[str]:
        drawn = []
        while participant.hand_size() < hand_size:
            card_id = self.draw_one()
            if card_id is None:
                break
            participant.receive_card(card_id)
            drawn.append(card_id)
        return drawn


@dataclass
class BattlePair:
    attack_card_id: str
    defense_card_id: str | None = None

    def is_defended(self) -> bool:
        return self.defense_card_id is not None


@dataclass
class BattleTable:
    pairs: list[BattlePair] = field(default_factory=list)
    defender_initial_hand_size: int = 0

    def add_attack(self, card_id: str) -> None:
        self.pairs.append(BattlePair(card_id))

    def defend(self, attack_card_id: str, defense_card_id: str) -> None:
        pair = self.get_pair(attack_card_id)
        pair.defense_card_id = defense_card_id

    def get_pair(self, attack_card_id: str) -> BattlePair:
        for pair in self.pairs:
            if pair.attack_card_id == attack_card_id:
                return pair
        raise ValueError(f"Unknown attack card: {attack_card_id}")

    def all_card_ids(self) -> list[str]:
        card_ids = []
        for pair in self.pairs:
            card_ids.append(pair.attack_card_id)
            if pair.defense_card_id is not None:
                card_ids.append(pair.defense_card_id)
        return card_ids

    def ranks_on_table(self, cards: dict[str, Card]) -> set:
        return {cards[card_id].rank for card_id in self.all_card_ids()}

    def all_defended(self) -> bool:
        return bool(self.pairs) and all(pair.is_defended() for pair in self.pairs)

    def clear(self) -> None:
        self.pairs.clear()
        self.defender_initial_hand_size = 0


@dataclass
class DurakGameState:
    participants: dict[str, BaseParticipant]
    turn_order: list[str]
    cards: dict[str, Card]
    deck: Deck
    trump_suit: Suit
    trump_card_id: str
    table: BattleTable = field(default_factory=BattleTable)
    discard_pile: list[str] = field(default_factory=list)
    attacker_id: str | None = None
    defender_id: str | None = None
    phase: GamePhase = GamePhase.NOT_STARTED
    fool_id: str | None = None

    def get_participant(self, player_id: str) -> BaseParticipant:
        return self.participants[player_id]

    def active_player_ids(self) -> list[str]:
        return [
            player_id
            for player_id in self.turn_order
            if self.participants[player_id].is_active
        ]

    def next_active_player_id(self, player_id: str) -> str | None:
        active_ids = self.active_player_ids()
        if len(active_ids) <= 1:
            return None
        start = self.turn_order.index(player_id)
        for offset in range(1, len(self.turn_order) + 1):
            candidate = self.turn_order[(start + offset) % len(self.turn_order)]
            if self.participants[candidate].is_active:
                return candidate
        return None
