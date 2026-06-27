import unittest
from unittest.mock import Mock

from core.durak import (
    AttackAction,
    BaseHumanPlayer,
    Card,
    DefendAction,
    DurakGameController,
    Rank,
    Suit,
    TakeCardsAction,
    ThrowInAction,
)
from core.durak.rules import DurakRules
from core.durak.state import BattlePair, BattleTable, Deck, DurakGameState, GamePhase


def card(rank, suit):
    return Card(f"{rank.value}_{suit.value}", rank, suit)


def standard_test_deck():
    return [
        card(Rank.SEVEN, Suit.SPADES),
        card(Rank.SIX, Suit.HEARTS),
        card(Rank.EIGHT, Suit.CLUBS),
        card(Rank.SIX, Suit.SPADES),
        card(Rank.NINE, Suit.CLUBS),
        card(Rank.SIX, Suit.CLUBS),
        card(Rank.TEN, Suit.CLUBS),
        card(Rank.SEVEN, Suit.HEARTS),
        card(Rank.JACK, Suit.CLUBS),
        card(Rank.EIGHT, Suit.HEARTS),
        card(Rank.QUEEN, Suit.CLUBS),
        card(Rank.NINE, Suit.HEARTS),
        card(Rank.QUEEN, Suit.HEARTS),
        card(Rank.KING, Suit.CLUBS),
        card(Rank.ACE, Suit.CLUBS),
    ]


def players():
    return [
        BaseHumanPlayer("human", "Human", 0),
        BaseHumanPlayer("bot", "Bot", 1),
    ]


def scenario_controller(participants, cards, deck_ids=(), attacker_id="attacker", defender_id="defender"):
    controller = object.__new__(DurakGameController)
    controller.rules = DurakRules()
    controller.thrower_ids = []
    controller.state = DurakGameState(
        participants={participant.player_id: participant for participant in participants},
        turn_order=[participant.player_id for participant in participants],
        cards={item.card_id: item for item in cards},
        deck=Deck(list(deck_ids)),
        trump_suit=Suit.HEARTS,
        trump_card_id="trump_marker",
        attacker_id=attacker_id,
        defender_id=defender_id,
        phase=GamePhase.ATTACKING,
    )
    return controller


class DurakRulesTests(unittest.TestCase):
    def test_can_beat_same_suit_only_with_higher_rank(self):
        rules = DurakRules()

        self.assertTrue(
            rules.can_beat(
                card(Rank.NINE, Suit.CLUBS),
                card(Rank.JACK, Suit.CLUBS),
                Suit.HEARTS,
            )
        )
        self.assertFalse(
            rules.can_beat(
                card(Rank.JACK, Suit.CLUBS),
                card(Rank.NINE, Suit.CLUBS),
                Suit.HEARTS,
            )
        )

    def test_trump_beats_non_trump_and_only_higher_trump_beats_trump(self):
        rules = DurakRules()

        self.assertTrue(
            rules.can_beat(
                card(Rank.ACE, Suit.CLUBS),
                card(Rank.SIX, Suit.HEARTS),
                Suit.HEARTS,
            )
        )
        self.assertFalse(
            rules.can_beat(
                card(Rank.SEVEN, Suit.HEARTS),
                card(Rank.ACE, Suit.CLUBS),
                Suit.HEARTS,
            )
        )
        self.assertTrue(
            rules.can_beat(
                card(Rank.SEVEN, Suit.HEARTS),
                card(Rank.QUEEN, Suit.HEARTS),
                Suit.HEARTS,
            )
        )


class DurakGameControllerTests(unittest.TestCase):
    def test_start_game_deals_six_cards_and_lowest_trump_attacks_first(self):
        controller = DurakGameController(players(), standard_test_deck())

        events = controller.start_game()

        self.assertEqual(events[0].type, "game_started")
        self.assertEqual(controller.state.trump_suit, Suit.HEARTS)
        self.assertEqual(controller.state.attacker_id, "bot")
        self.assertEqual(controller.state.defender_id, "human")
        self.assertEqual(controller.state.get_participant("human").hand_size(), 6)
        self.assertEqual(controller.state.get_participant("bot").hand_size(), 6)

    def test_attack_moves_cards_from_attacker_to_battle_table(self):
        controller = DurakGameController(players(), standard_test_deck())
        controller.start_game()

        events = controller.apply_attack(AttackAction("bot", ("6_spades",)))

        self.assertEqual(events[0].type, "cards_attacked")
        self.assertFalse(controller.state.get_participant("bot").has_card("6_spades"))
        self.assertEqual(controller.state.table.pairs[0].attack_card_id, "6_spades")

    def test_defense_rejects_card_that_cannot_beat_attack(self):
        controller = DurakGameController(players(), standard_test_deck())
        controller.start_game()
        controller.apply_attack(AttackAction("bot", ("6_spades",)))

        with self.assertRaises(ValueError):
            controller.apply_defense(DefendAction("human", "6_spades", "8_clubs"))

    def test_successful_defense_discards_cards_and_defender_attacks_next(self):
        controller = DurakGameController(players(), standard_test_deck())
        controller.start_game()
        controller.apply_attack(AttackAction("bot", ("6_spades",)))

        events = controller.apply_defense(DefendAction("human", "6_spades", "7_spades"))

        self.assertEqual([event.type for event in events], ["card_defended"])
        self.assertEqual(controller.state.discard_pile, [])
        self.assertEqual(controller.state.table.pairs[0].defense_card_id, "7_spades")

        events = controller.complete_defense()

        self.assertEqual([event.type for event in events], ["cards_discarded"])
        self.assertEqual(controller.state.discard_pile, ["6_spades", "7_spades"])
        self.assertEqual(controller.state.attacker_id, "human")
        self.assertEqual(controller.state.defender_id, "bot")
        self.assertEqual(controller.state.table.pairs, [])

    def test_throw_in_requires_rank_already_on_table(self):
        controller = DurakGameController(players(), standard_test_deck())
        controller.start_game()
        controller.apply_attack(AttackAction("bot", ("6_spades",)))

        with self.assertRaises(ValueError):
            controller.apply_throw_in(ThrowInAction("bot", "7_hearts"))

        events = controller.apply_throw_in(ThrowInAction("bot", "6_clubs"))
        self.assertEqual(events[0].type, "card_thrown_in")

    def test_take_cards_gives_table_to_defender_and_skips_defender_turn(self):
        controller = DurakGameController(players(), standard_test_deck())
        controller.start_game()
        controller.apply_attack(AttackAction("bot", ("6_spades",)))

        events = controller.apply_take_cards(TakeCardsAction("human"))

        self.assertEqual(events[0].type, "cards_taken")
        self.assertTrue(controller.state.get_participant("human").has_card("6_spades"))
        self.assertEqual(controller.state.attacker_id, "bot")
        self.assertEqual(controller.state.defender_id, "human")
        self.assertEqual(controller.state.table.pairs, [])

    def test_attack_rejects_non_attacker_and_mixed_ranks_in_mocked_state(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs", "7_clubs"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.EIGHT, Suit.CLUBS),
            ],
        )

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("defender", ("8_clubs",)))

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("attacker", ("6_clubs", "7_clubs")))

    def test_attack_delegates_legality_to_rules(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.SIX, Suit.CLUBS), card(Rank.EIGHT, Suit.CLUBS)],
        )
        controller.rules = Mock(wraps=DurakRules())

        controller.apply_attack(AttackAction("attacker", ("6_clubs",)))

        controller.rules.can_start_attack.assert_called_once()

    def test_throw_in_rejects_defender_and_respects_defender_initial_hand_limit(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_spades"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["6_hearts"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SIX, Suit.SPADES),
                card(Rank.SIX, Suit.HEARTS),
            ],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=1,
        )

        with self.assertRaises(ValueError):
            controller.apply_throw_in(ThrowInAction("defender", "6_hearts"))

        with self.assertRaises(ValueError):
            controller.apply_throw_in(ThrowInAction("attacker", "6_spades"))

    def test_defense_rejects_already_defended_attack_pair(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.EIGHT, Suit.CLUBS),
            ],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=2,
        )

        with self.assertRaises(ValueError):
            controller.apply_defense(DefendAction("defender", "6_clubs", "8_clubs"))

    def test_take_cards_rejects_non_defender(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.SIX, Suit.CLUBS), card(Rank.EIGHT, Suit.CLUBS)],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=1,
        )

        with self.assertRaises(ValueError):
            controller.apply_take_cards(TakeCardsAction("attacker"))

    def test_successful_defense_draws_attacker_thrower_then_defender_in_mocked_state(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["a1", "a2", "a3", "a4", "a5"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["d1", "d2", "d3", "d4", "d5"])
        thrower = BaseHumanPlayer("thrower", "Thrower", 2, hand=["t1", "t2", "t3", "t4", "t5"])
        cards = [
            card(Rank.SIX, Suit.CLUBS),
            card(Rank.SEVEN, Suit.CLUBS),
            card(Rank.EIGHT, Suit.CLUBS),
            card(Rank.NINE, Suit.CLUBS),
            card(Rank.TEN, Suit.CLUBS),
            card(Rank.JACK, Suit.CLUBS),
            card(Rank.QUEEN, Suit.CLUBS),
            card(Rank.KING, Suit.CLUBS),
            card(Rank.ACE, Suit.CLUBS),
        ]
        controller = scenario_controller(
            [attacker, defender, thrower],
            cards,
            deck_ids=["j_clubs", "q_clubs", "k_clubs"],
        )
        controller.thrower_ids = ["thrower"]
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=2,
        )

        controller.resolve_successful_defense()

        self.assertEqual(attacker.hand[-1], "j_clubs")
        self.assertEqual(thrower.hand[-1], "q_clubs")
        self.assertEqual(defender.hand[-1], "k_clubs")
        self.assertEqual(controller.state.attacker_id, "defender")
        self.assertEqual(controller.state.defender_id, "thrower")

    def test_empty_deck_marks_last_player_with_cards_as_fool(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.SIX, Suit.CLUBS), card(Rank.SEVEN, Suit.CLUBS), card(Rank.EIGHT, Suit.CLUBS)],
            deck_ids=[],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=2,
        )

        controller.resolve_successful_defense()

        self.assertFalse(attacker.is_active)
        self.assertEqual(controller.state.fool_id, "defender")
        self.assertEqual(controller.state.phase, GamePhase.FINISHED)


if __name__ == "__main__":
    unittest.main()
