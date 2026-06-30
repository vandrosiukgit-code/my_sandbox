"""Domain-facing contracts for autonomous Durak sessions."""

from dataclasses import dataclass, field

from core.durak.events import GameEvent


@dataclass(frozen=True)
class TablePairSnapshot:
    attack_card_id: str
    defense_card_id: str | None = None


@dataclass(frozen=True)
class PlayerSnapshot:
    player_id: str
    name: str
    seat_index: int
    hand_size: int
    is_active: bool


@dataclass(frozen=True)
class GameSnapshot:
    phase: str
    attacker_id: str | None
    defender_id: str | None
    trump_suit: str
    trump_card_id: str
    deck_count: int
    discard_count: int
    fool_id: str | None
    players: tuple[PlayerSnapshot, ...] = ()
    table_pairs: tuple[TablePairSnapshot, ...] = ()


@dataclass(frozen=True)
class DomainResult:
    events: tuple[GameEvent, ...] = ()
    snapshot: GameSnapshot | None = None
    waiting_player_id: str | None = None
    available_card_ids: tuple[str, ...] = ()
    can_take_cards: bool = False
    metadata: dict = field(default_factory=dict)
