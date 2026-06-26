"""Rule checks for classic throw-in Durak."""

from core.durak.actions import AttackAction, DefendAction, TakeCardsAction, ThrowInAction
from core.durak.cards import Card, RANK_ORDER
from core.durak.state import DurakGameState, GamePhase


class DurakRules:
    hand_size = 6

    def can_beat(self, attack: Card, defense: Card, trump_suit) -> bool:
        if attack.suit == defense.suit:
            return RANK_ORDER[defense.rank] > RANK_ORDER[attack.rank]
        return defense.suit == trump_suit and attack.suit != trump_suit

    def can_start_attack(self, state: DurakGameState, action: AttackAction) -> bool:
        if state.phase != GamePhase.ATTACKING:
            return False
        if action.player_id != state.attacker_id:
            return False
        if not action.card_ids:
            return False
        attacker = state.get_participant(action.player_id)
        if not all(attacker.has_card(card_id) for card_id in action.card_ids):
            return False
        ranks = {state.cards[card_id].rank for card_id in action.card_ids}
        return len(ranks) == 1

    def can_throw_in(self, state: DurakGameState, action: ThrowInAction) -> bool:
        if state.phase not in (GamePhase.ATTACKING, GamePhase.DEFENDING):
            return False
        if action.player_id == state.defender_id:
            return False
        participant = state.get_participant(action.player_id)
        if not participant.has_card(action.card_id):
            return False
        if len(state.table.pairs) >= state.table.defender_initial_hand_size:
            return False
        return state.cards[action.card_id].rank in state.table.ranks_on_table(state.cards)

    def can_defend(self, state: DurakGameState, action: DefendAction) -> bool:
        if state.phase != GamePhase.DEFENDING:
            return False
        if action.player_id != state.defender_id:
            return False
        defender = state.get_participant(action.player_id)
        if not defender.has_card(action.defense_card_id):
            return False
        pair = state.table.get_pair(action.attack_card_id)
        if pair.is_defended():
            return False
        return self.can_beat(
            state.cards[pair.attack_card_id],
            state.cards[action.defense_card_id],
            state.trump_suit,
        )

    def can_take_cards(self, state: DurakGameState, action: TakeCardsAction) -> bool:
        return (
            state.phase == GamePhase.DEFENDING
            and action.player_id == state.defender_id
            and bool(state.table.pairs)
        )

    def get_draw_order(self, state: DurakGameState, thrower_ids: list[str]) -> list[str]:
        ordered = [state.attacker_id]
        for player_id in state.turn_order:
            if player_id in thrower_ids and player_id not in ordered:
                ordered.append(player_id)
        if state.defender_id not in ordered:
            ordered.append(state.defender_id)
        return [player_id for player_id in ordered if player_id is not None]
