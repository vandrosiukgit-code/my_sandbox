"""Participant entities for human and bot players."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from enum import Enum
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


class BotStrategy(str, Enum):
    CAUTIOUS = "cautious"
    BALANCED = "balanced"
    PRESSURE = "pressure"
    OPPORTUNIST = "opportunist"


@dataclass(frozen=True)
class BotStrategyProfile:
    attack_group_bias: int
    attack_duplicate_bonus: int
    trump_attack_penalty: int
    high_rank_attack_penalty: int
    same_suit_defense_bonus: int
    trump_defense_penalty: int
    high_rank_defense_penalty: int
    take_margin: int
    throw_in_bonus: int
    throw_in_trump_penalty: int
    throw_in_high_rank_penalty: int


BOT_STRATEGY_PROFILES = {
    BotStrategy.CAUTIOUS: BotStrategyProfile(
        attack_group_bias=0,
        attack_duplicate_bonus=1,
        trump_attack_penalty=8,
        high_rank_attack_penalty=2,
        same_suit_defense_bonus=4,
        trump_defense_penalty=7,
        high_rank_defense_penalty=2,
        take_margin=6,
        throw_in_bonus=0,
        throw_in_trump_penalty=9,
        throw_in_high_rank_penalty=3,
    ),
    BotStrategy.BALANCED: BotStrategyProfile(
        attack_group_bias=1,
        attack_duplicate_bonus=2,
        trump_attack_penalty=6,
        high_rank_attack_penalty=1,
        same_suit_defense_bonus=5,
        trump_defense_penalty=5,
        high_rank_defense_penalty=1,
        take_margin=2,
        throw_in_bonus=2,
        throw_in_trump_penalty=6,
        throw_in_high_rank_penalty=1,
    ),
    BotStrategy.PRESSURE: BotStrategyProfile(
        attack_group_bias=4,
        attack_duplicate_bonus=5,
        trump_attack_penalty=4,
        high_rank_attack_penalty=0,
        same_suit_defense_bonus=3,
        trump_defense_penalty=4,
        high_rank_defense_penalty=0,
        take_margin=-2,
        throw_in_bonus=6,
        throw_in_trump_penalty=3,
        throw_in_high_rank_penalty=0,
    ),
    BotStrategy.OPPORTUNIST: BotStrategyProfile(
        attack_group_bias=2,
        attack_duplicate_bonus=6,
        trump_attack_penalty=5,
        high_rank_attack_penalty=1,
        same_suit_defense_bonus=6,
        trump_defense_penalty=4,
        high_rank_defense_penalty=1,
        take_margin=0,
        throw_in_bonus=4,
        throw_in_trump_penalty=5,
        throw_in_high_rank_penalty=1,
    ),
}


@dataclass
class SimpleBotPlayer(BaseBotPlayer):
    def choose_action(self, state: Any, rules: Any = None):
        return None


@dataclass
class RuleBasedBotPlayer(BaseBotPlayer):
    """Human-like bot with deterministic strategy profiles."""

    strategy: BotStrategy = BotStrategy.BALANCED

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

    @property
    def profile(self) -> BotStrategyProfile:
        return BOT_STRATEGY_PROFILES[self.strategy]

    def choose_attack_action(self, state: Any):
        attack_groups = self.build_attack_groups(state)
        if not attack_groups:
            return None
        return AttackAction(self.player_id, attack_groups[0])

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
        if not defense_card_ids:
            return TakeCardsAction(self.player_id)
        defense_card_id = min(
            defense_card_ids,
            key=lambda card_id: self.score_defense_card(state, attack_pair.attack_card_id, card_id),
        )
        if self.should_take_cards(state, attack_pair.attack_card_id, defense_card_id):
            return TakeCardsAction(self.player_id)
        return DefendAction(self.player_id, attack_pair.attack_card_id, defense_card_id)

    def choose_throw_in_action(self, state: Any, rules: Any):
        throw_in_card_ids = [
            card_id
            for card_id in self.hand
            if rules.can_throw_in(state, ThrowInAction(self.player_id, card_id))
        ]
        if not throw_in_card_ids:
            return None
        throw_in_card_id = min(
            throw_in_card_ids,
            key=lambda card_id: self.score_throw_in_card(state, card_id),
        )
        if self.should_skip_throw_in(state, throw_in_card_id):
            return None
        return ThrowInAction(self.player_id, throw_in_card_id)

    def build_attack_groups(self, state: Any) -> list[tuple[str, ...]]:
        if not self.hand:
            return []
        defender = state.get_participant(state.defender_id)
        max_group_size = max(1, min(defender.hand_size(), len(self.hand)))
        cards_by_rank = {}
        for card_id in self.hand:
            rank = state.cards[card_id].rank
            cards_by_rank.setdefault(rank, []).append(card_id)
        scored_groups = []
        for same_rank_card_ids in cards_by_rank.values():
            ordered = sorted(same_rank_card_ids, key=lambda card_id: self.score_attack_card(state, card_id))
            for size in range(1, min(len(ordered), max_group_size) + 1):
                group = tuple(ordered[:size])
                scored_groups.append((self.score_attack_group(state, group), group))
        scored_groups.sort(key=lambda item: (item[0], len(item[1]), item[1]))
        return [group for _score, group in scored_groups]

    def score_attack_group(self, state: Any, card_ids: tuple[str, ...]) -> tuple[int, int, tuple[str, ...]]:
        profile = self.profile
        total = sum(self.score_attack_card(state, card_id) for card_id in card_ids)
        rank = state.cards[card_ids[0]].rank
        duplicates = sum(1 for owned_card_id in self.hand if state.cards[owned_card_id].rank == rank)
        total -= (len(card_ids) - 1) * profile.attack_group_bias
        total -= max(0, duplicates - 1) * profile.attack_duplicate_bonus
        return total, len(card_ids), card_ids

    def score_attack_card(self, state: Any, card_id: str) -> int:
        profile = self.profile
        card = state.cards[card_id]
        score = RANK_ORDER[card.rank] * (1 + profile.high_rank_attack_penalty)
        if card.suit == state.trump_suit:
            score += profile.trump_attack_penalty
        return score

    def score_defense_card(self, state: Any, attack_card_id: str, defense_card_id: str) -> tuple[int, str]:
        profile = self.profile
        attack_card = state.cards[attack_card_id]
        defense_card = state.cards[defense_card_id]
        score = RANK_ORDER[defense_card.rank] * (1 + profile.high_rank_defense_penalty)
        if defense_card.suit == state.trump_suit and attack_card.suit != state.trump_suit:
            score += profile.trump_defense_penalty
        if defense_card.suit == attack_card.suit:
            score -= profile.same_suit_defense_bonus
        return score, defense_card_id

    def should_take_cards(self, state: Any, attack_card_id: str, defense_card_id: str) -> bool:
        profile = self.profile
        attack_card = state.cards[attack_card_id]
        defense_card = state.cards[defense_card_id]
        if not state.deck.card_ids:
            return False
        if defense_card.suit == attack_card.suit:
            return False
        if len(self.hand) <= 3:
            return False
        attack_pressure = len(state.table.pairs) * 2 + RANK_ORDER[attack_card.rank]
        defense_cost = self.score_defense_card(state, attack_card_id, defense_card_id)[0]
        if defense_card.suit == state.trump_suit and attack_card.suit != state.trump_suit:
            defense_cost += 2
        if len(self.hand) >= 6:
            defense_cost -= 1
        return defense_cost > attack_pressure + profile.take_margin

    def score_throw_in_card(self, state: Any, card_id: str) -> tuple[int, str]:
        profile = self.profile
        card = state.cards[card_id]
        score = RANK_ORDER[card.rank] * (1 + profile.throw_in_high_rank_penalty)
        score -= profile.throw_in_bonus
        if card.suit == state.trump_suit:
            score += profile.throw_in_trump_penalty
        return score, card_id

    def should_skip_throw_in(self, state: Any, card_id: str) -> bool:
        profile = self.profile
        card = state.cards[card_id]
        score = self.score_throw_in_card(state, card_id)[0]
        remaining_after_play = len(self.hand) - 1
        if not state.deck.card_ids and self.player_id != state.attacker_id:
            return True
        if self.strategy == BotStrategy.CAUTIOUS:
            return score >= 7 and remaining_after_play <= 3
        if self.strategy == BotStrategy.BALANCED:
            return card.suit == state.trump_suit and score >= 4 and remaining_after_play <= 2
        return False
