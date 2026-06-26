"""Player intents accepted by the isolated Durak controller."""

from dataclasses import dataclass


@dataclass(frozen=True)
class AttackAction:
    player_id: str
    card_ids: tuple[str, ...]


@dataclass(frozen=True)
class ThrowInAction:
    player_id: str
    card_id: str


@dataclass(frozen=True)
class DefendAction:
    player_id: str
    attack_card_id: str
    defense_card_id: str


@dataclass(frozen=True)
class TakeCardsAction:
    player_id: str
