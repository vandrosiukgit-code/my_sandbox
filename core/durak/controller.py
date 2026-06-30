"""Isolated OOP controller for Durak game logic."""

from core.durak.actions import AttackAction, DefendAction, TakeCardsAction, ThrowInAction
from core.durak.cards import Card, RANK_ORDER
from core.durak.contracts import DomainResult, GameSnapshot, PlayerSnapshot, TablePairSnapshot
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

    def build_snapshot(self) -> GameSnapshot:
        return GameSnapshot(
            phase=self.state.phase.value,
            attacker_id=self.state.attacker_id,
            defender_id=self.state.defender_id,
            trump_suit=self.state.trump_suit.value,
            trump_card_id=self.state.trump_card_id,
            deck_count=len(self.state.deck.card_ids),
            discard_count=len(self.state.discard_pile),
            fool_id=self.state.fool_id,
            players=tuple(
                PlayerSnapshot(
                    player_id=participant.player_id,
                    name=participant.name,
                    seat_index=participant.seat_index,
                    hand_size=participant.hand_size(),
                    is_active=participant.is_active,
                )
                for participant in self.state.participants.values()
            ),
            table_pairs=tuple(
                TablePairSnapshot(
                    attack_card_id=pair.attack_card_id,
                    defense_card_id=pair.defense_card_id,
                )
                for pair in self.state.table.pairs
            ),
        )

    def get_available_card_ids_for_player(self, player_id: str) -> tuple[str, ...]:
        participant = self.state.get_participant(player_id)
        if not participant.hand:
            return ()
        if self.state.phase == GamePhase.ATTACKING and self.state.attacker_id == player_id:
            return self.get_available_attack_card_ids(player_id)
        if self.state.phase != GamePhase.DEFENDING:
            return ()
        if self.state.defender_id == player_id:
            return tuple(defense_card_id for _attack_card_id, defense_card_id in self.get_available_defense_pairs(player_id))
        if not self.state.table.all_defended():
            return ()
        return self.get_available_throw_in_card_ids(player_id)

    def can_player_take_cards(self, player_id: str) -> bool:
        return bool(self.rules.can_take_cards(self.state, TakeCardsAction(player_id)))

    def get_waiting_player_id(self, player_ids) -> str | None:
        for player_id in player_ids or ():
            if self.get_available_card_ids_for_player(player_id):
                return player_id
            if self.state.phase == GamePhase.DEFENDING and self.state.defender_id == player_id and self.can_player_take_cards(player_id):
                return player_id
        return None

    def build_result(self, events=(), waiting_player_ids=()) -> DomainResult:
        waiting_player_id = self.get_waiting_player_id(tuple(waiting_player_ids or ()))
        available_card_ids = ()
        can_take_cards = False
        if waiting_player_id is not None:
            available_card_ids = self.get_available_card_ids_for_player(waiting_player_id)
            can_take_cards = self.can_player_take_cards(waiting_player_id)
        return DomainResult(
            events=tuple(events or ()),
            snapshot=self.build_snapshot(),
            waiting_player_id=waiting_player_id,
            available_card_ids=tuple(available_card_ids),
            can_take_cards=bool(can_take_cards),
        )

    def submit_action(self, action, waiting_player_ids=()) -> DomainResult:
        if isinstance(action, AttackAction):
            events = self.apply_attack(action)
        elif isinstance(action, DefendAction):
            events = self.apply_defense(action)
        elif isinstance(action, ThrowInAction):
            events = self.apply_throw_in(action)
        elif isinstance(action, TakeCardsAction):
            events = self.apply_take_cards(action)
        else:
            raise TypeError(f"Unsupported domain action: {type(action)!r}")
        return self.build_result(events, waiting_player_ids=waiting_player_ids)

    def advance_to_next_checkpoint(self, waiting_player_ids=(), max_steps: int = 64) -> DomainResult:
        for _ in range(max_steps):
            result = self.build_result(waiting_player_ids=waiting_player_ids)
            if result.waiting_player_id is not None or self.state.phase == GamePhase.FINISHED:
                return result
            step_events = self.play_automatic_step()
            if step_events:
                return self.build_result(step_events, waiting_player_ids=waiting_player_ids)
        raise RuntimeError(f"Failed to reach next checkpoint within {max_steps} steps")

    def get_unanswered_attack_card_ids(self) -> list[str]:
        return [
            pair.attack_card_id
            for pair in self.state.table.pairs
            if not pair.is_defended()
        ]

    def get_available_attack_card_ids(self, player_id: str) -> tuple[str, ...]:
        if self.state.phase != GamePhase.ATTACKING or self.state.attacker_id != player_id:
            return ()
        return tuple(self.state.get_participant(player_id).hand)

    def get_available_defense_pairs(self, player_id: str) -> tuple[tuple[str, str], ...]:
        if self.state.phase != GamePhase.DEFENDING or self.state.defender_id != player_id:
            return ()
        participant = self.state.get_participant(player_id)
        available_pairs = []
        for attack_card_id in self.get_unanswered_attack_card_ids():
            attack_card = self.state.cards[attack_card_id]
            for defense_card_id in participant.hand:
                defense_card = self.state.cards[defense_card_id]
                if self.rules.can_beat(attack_card, defense_card, self.state.trump_suit):
                    available_pairs.append((attack_card_id, defense_card_id))
        return tuple(available_pairs)

    def get_available_throw_in_card_ids(self, player_id: str) -> tuple[str, ...]:
        participant = self.state.get_participant(player_id)
        available_card_ids = []
        for card_id in participant.hand:
            if self.rules.can_throw_in(self.state, ThrowInAction(player_id, card_id)):
                available_card_ids.append(card_id)
        return tuple(available_card_ids)

    def can_complete_defense(self) -> bool:
        return self.state.phase == GamePhase.DEFENDING and self.state.table.all_defended()

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
        return [
            GameEvent(
                "card_defended",
                {
                    "player_id": action.player_id,
                    "attack_card_id": action.attack_card_id,
                    "defense_card_id": action.defense_card_id,
                },
            )
        ]

    def complete_defense(self) -> list[GameEvent]:
        if not self.can_complete_defense():
            raise ValueError("Cannot complete defense while table is not fully defended")
        return self.resolve_successful_defense()

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

    def choose_participant_action(self, player_id: str):
        participant = self.state.get_participant(player_id)
        chooser = getattr(participant, "choose_action", None)
        if not callable(chooser):
            return None
        try:
            return chooser(self.state, self.rules)
        except TypeError:
            return chooser(self.state)

    def get_throw_in_turn_order(self) -> list[str]:
        if self.state.attacker_id is None:
            return []
        ordered = []
        start_index = self.state.turn_order.index(self.state.attacker_id)
        for offset in range(len(self.state.turn_order)):
            player_id = self.state.turn_order[(start_index + offset) % len(self.state.turn_order)]
            participant = self.state.participants[player_id]
            if not participant.is_active or player_id == self.state.defender_id:
                continue
            ordered.append(player_id)
        return ordered

    def get_active_player_ids_with_cards(self) -> list[str]:
        return [
            player_id
            for player_id in self.state.turn_order
            if self.state.participants[player_id].is_active and self.state.participants[player_id].hand
        ]

    def next_active_player_with_cards(self, player_id: str | None) -> str | None:
        active_ids = self.get_active_player_ids_with_cards()
        if not active_ids:
            return None
        if player_id not in self.state.turn_order:
            return active_ids[0]
        start = self.state.turn_order.index(player_id)
        for offset in range(1, len(self.state.turn_order) + 1):
            candidate = self.state.turn_order[(start + offset) % len(self.state.turn_order)]
            participant = self.state.participants[candidate]
            if participant.is_active and participant.hand:
                return candidate
        return None

    def normalize_turn_owners(self) -> None:
        active_with_cards = self.get_active_player_ids_with_cards()
        if not active_with_cards:
            self.state.phase = GamePhase.FINISHED
            return
        if len(active_with_cards) == 1 and not self.state.deck.card_ids and not self.state.table.pairs:
            for player_id, participant in self.state.participants.items():
                participant.is_active = player_id in active_with_cards
            self.state.fool_id = active_with_cards[0]
            self.state.phase = GamePhase.FINISHED
            return
        if self.state.phase == GamePhase.ATTACKING:
            if self.state.attacker_id not in active_with_cards:
                self.state.attacker_id = active_with_cards[0]
            self.state.defender_id = self.next_active_player_with_cards(self.state.attacker_id)

    def play_automatic_step(self) -> list[GameEvent]:
        if self.state.phase == GamePhase.NOT_STARTED:
            return self.start_game()
        self.normalize_turn_owners()
        if self.state.phase == GamePhase.FINISHED:
            return []
        if self.state.phase == GamePhase.ATTACKING:
            if self.state.attacker_id is None:
                raise RuntimeError("Attacking phase requires attacker_id")
            action = self.choose_participant_action(self.state.attacker_id)
            if not isinstance(action, AttackAction):
                raise RuntimeError(f"Attacker {self.state.attacker_id!r} did not provide AttackAction")
            return self.apply_attack(action)

        if self.get_unanswered_attack_card_ids():
            if self.state.defender_id is None:
                raise RuntimeError("Defending phase requires defender_id")
            action = self.choose_participant_action(self.state.defender_id)
            if isinstance(action, DefendAction):
                return self.apply_defense(action)
            if isinstance(action, TakeCardsAction):
                return self.apply_take_cards(action)
            if self.get_available_defense_pairs(self.state.defender_id):
                raise RuntimeError(f"Defender {self.state.defender_id!r} has legal defense but returned {action!r}")
            return self.apply_take_cards(TakeCardsAction(self.state.defender_id))

        if self.state.table.all_defended():
            for player_id in self.get_throw_in_turn_order():
                action = self.choose_participant_action(player_id)
                if isinstance(action, ThrowInAction) and self.rules.can_throw_in(self.state, action):
                    return self.apply_throw_in(action)
            return self.complete_defense()

        return []

    def play_game(self, max_steps: int = 2048) -> list[GameEvent]:
        events: list[GameEvent] = []
        for _ in range(max_steps):
            if self.state.phase == GamePhase.FINISHED:
                return events
            step_events = self.play_automatic_step()
            if not step_events and self.state.phase != GamePhase.FINISHED:
                raise RuntimeError("Automatic game stalled without reaching FINISHED phase")
            events.extend(step_events)
        raise RuntimeError(f"Automatic game exceeded step limit: {max_steps}")

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
