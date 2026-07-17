import unittest

from core.durak import (
    AttackAction,
    BaseHumanPlayer,
    Card,
    DefendAction,
    DurakGameController,
    Rank,
    Suit,
    ThrowInAction,
    TakeCardsAction,
)
from core.durak.rules import DurakRules
from core.durak.state import BattlePair, BattleTable, Deck, DurakGameState, GamePhase


def card(rank, suit):
    return Card(f"{rank.value}_{suit.value}", rank, suit)


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


class DurakControllerEdgeCaseTests(unittest.TestCase):
    def test_constructor_rejects_too_few_players(self):
        with self.assertRaises(ValueError):
            DurakGameController([BaseHumanPlayer("solo", "Solo", 0)], [])

    def test_constructor_rejects_deck_without_initial_hands_and_trump(self):
        with self.assertRaises(ValueError):
            DurakGameController(
                [BaseHumanPlayer("a", "A", 0), BaseHumanPlayer("b", "B", 1)],
                [card(Rank.SIX, Suit.CLUBS)],
            )

    def test_attack_allows_multiple_cards_with_same_rank(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs", "6_spades"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs", "9_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SIX, Suit.SPADES),
                card(Rank.EIGHT, Suit.CLUBS),
                card(Rank.NINE, Suit.CLUBS),
            ],
        )

        controller.apply_attack(AttackAction("attacker", ("6_clubs", "6_spades")))

        self.assertEqual(
            [pair.attack_card_id for pair in controller.state.table.pairs],
            ["6_clubs", "6_spades"],
        )
        self.assertEqual(attacker.hand, [])

    def test_attack_rejects_duplicate_card_without_partial_mutation(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs", "9_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.EIGHT, Suit.CLUBS),
                card(Rank.NINE, Suit.CLUBS),
            ],
        )

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("attacker", ("6_clubs", "6_clubs")))

        self.assertEqual(attacker.hand, ["6_clubs"])
        self.assertEqual(controller.state.table.pairs, [])

    def test_initial_attack_cannot_exceed_defender_hand_size(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs", "6_spades"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SIX, Suit.SPADES),
                card(Rank.EIGHT, Suit.CLUBS),
            ],
        )

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("attacker", ("6_clubs", "6_spades")))

        self.assertEqual(attacker.hand, ["6_clubs", "6_spades"])
        self.assertEqual(controller.state.table.pairs, [])

    def test_attack_rejects_empty_selection_and_card_not_in_hand(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["6_clubs"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.SIX, Suit.CLUBS), card(Rank.EIGHT, Suit.CLUBS)],
        )

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("attacker", ()))

        with self.assertRaises(ValueError):
            controller.apply_attack(AttackAction("attacker", ("8_clubs",)))

    def test_defense_allows_trump_against_non_trump(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["6_hearts"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.ACE, Suit.CLUBS), card(Rank.SIX, Suit.HEARTS)],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("a_clubs")],
            defender_initial_hand_size=1,
        )

        events = controller.apply_defense(DefendAction("defender", "a_clubs", "6_hearts"))

        self.assertEqual([event.type for event in events], ["card_defended"])

        complete_events = controller.complete_defense()

        self.assertEqual([event.type for event in complete_events], ["cards_discarded"])

    def test_defense_rejects_non_trump_against_trump(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["a_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [card(Rank.SEVEN, Suit.HEARTS), card(Rank.ACE, Suit.CLUBS)],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("7_hearts")],
            defender_initial_hand_size=1,
        )

        with self.assertRaises(ValueError):
            controller.apply_defense(DefendAction("defender", "7_hearts", "a_clubs"))

    def test_throw_in_allows_rank_from_defense_card_already_on_table(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["7_spades"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=[])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.SEVEN, Suit.SPADES),
            ],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=2,
        )

        controller.apply_throw_in(ThrowInAction("attacker", "7_spades"))

        self.assertEqual(controller.state.table.pairs[-1].attack_card_id, "7_spades")

    def test_successful_defense_draws_only_remaining_cards_when_deck_is_short(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=["a1", "a2", "a3", "a4", "a5"])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["d1", "d2", "d3", "d4", "d5"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.JACK, Suit.CLUBS),
            ],
            deck_ids=["j_clubs"],
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=2,
        )

        controller.resolve_successful_defense()

        self.assertEqual(attacker.hand[-1], "j_clubs")
        self.assertEqual(defender.hand, ["d1", "d2", "d3", "d4", "d5"])
        self.assertEqual(controller.state.deck.card_ids, [])

    def test_three_player_take_makes_next_after_defender_attack(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["8_clubs"])
        next_player = BaseHumanPlayer("next", "Next", 2, hand=["9_clubs"])
        controller = scenario_controller(
            [attacker, defender, next_player],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.EIGHT, Suit.CLUBS),
                card(Rank.NINE, Suit.CLUBS),
            ],
            attacker_id="attacker",
            defender_id="defender",
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=1,
        )

        controller.apply_take_cards(TakeCardsAction("defender"))

        self.assertEqual(controller.state.attacker_id, "next")
        self.assertEqual(controller.state.defender_id, "defender")

    def test_three_player_successful_defense_makes_defender_attack_next_player(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=["7_clubs", "8_spades"])
        next_player = BaseHumanPlayer("next", "Next", 2, hand=["9_clubs"])
        controller = scenario_controller(
            [attacker, defender, next_player],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.EIGHT, Suit.SPADES),
                card(Rank.NINE, Suit.CLUBS),
            ],
            attacker_id="attacker",
            defender_id="defender",
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=1,
        )

        controller.apply_defense(DefendAction("defender", "6_clubs", "7_clubs"))
        controller.complete_defense()

        self.assertEqual(controller.state.attacker_id, "defender")
        self.assertEqual(controller.state.defender_id, "next")

    def test_successful_defense_skips_players_who_left_the_game(self):
        attacker = BaseHumanPlayer("attacker", "Attacker", 0, hand=[])
        defender = BaseHumanPlayer("defender", "Defender", 1, hand=[])
        next_player = BaseHumanPlayer("next", "Next", 2, hand=["9_clubs"])
        last_player = BaseHumanPlayer("last", "Last", 3, hand=["10_clubs"])
        controller = scenario_controller(
            [attacker, defender, next_player, last_player],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.NINE, Suit.CLUBS),
                card(Rank.TEN, Suit.CLUBS),
            ],
            attacker_id="attacker",
            defender_id="defender",
        )
        controller.state.phase = GamePhase.DEFENDING
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs", "7_clubs")],
            defender_initial_hand_size=1,
        )

        controller.resolve_successful_defense()

        self.assertEqual(controller.state.attacker_id, "next")
        self.assertEqual(controller.state.defender_id, "last")
        self.assertFalse(attacker.is_active)
        self.assertFalse(defender.is_active)

    def test_draw_order_starts_at_attacker_and_wraps_clockwise(self):
        players = [
            BaseHumanPlayer("p1", "P1", 0),
            BaseHumanPlayer("p2", "P2", 1),
            BaseHumanPlayer("p3", "P3", 2),
            BaseHumanPlayer("p4", "P4", 3),
        ]
        controller = scenario_controller(
            players,
            [],
            attacker_id="p2",
            defender_id="p3",
        )

        self.assertEqual(
            controller.rules.get_draw_order(controller.state, ["p1", "p4"]),
            ["p2", "p4", "p1", "p3"],
        )


if __name__ == "__main__":
    unittest.main()
