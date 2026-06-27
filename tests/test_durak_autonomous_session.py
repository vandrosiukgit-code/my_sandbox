import random
import unittest

from core.durak import Card, DurakGameController, Rank, RuleBasedBotPlayer, Suit
from core.durak.state import BattlePair, BattleTable, Deck, DurakGameState, GamePhase


def card(rank, suit):
    return Card(f"{rank.value}_{suit.value}", rank, suit)


def standard_36_deck():
    return [
        card(rank, suit)
        for rank in Rank
        for suit in Suit
    ]


def shuffled_standard_36_deck(seed):
    cards = standard_36_deck()
    random.Random(seed).shuffle(cards)
    return cards


def scenario_controller(participants, cards, deck_ids=(), attacker_id="attacker", defender_id="defender"):
    controller = object.__new__(DurakGameController)
    controller.rules = controller.rules if hasattr(controller, "rules") else None
    if controller.rules is None:
        from core.durak.rules import DurakRules

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
        phase=GamePhase.DEFENDING,
    )
    return controller


class AutonomousDurakSessionTests(unittest.TestCase):
    def test_automatic_step_defends_then_completes_round_without_gui(self):
        attacker = RuleBasedBotPlayer("attacker", "Attacker", 0, hand=["9_diamonds"])
        defender = RuleBasedBotPlayer("defender", "Defender", 1, hand=["7_clubs"])
        controller = scenario_controller(
            [attacker, defender],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.NINE, Suit.DIAMONDS),
            ],
            attacker_id="attacker",
            defender_id="defender",
        )
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=1,
        )

        events = controller.play_automatic_step()

        self.assertEqual([event.type for event in events], ["card_defended"])
        self.assertEqual(controller.state.table.pairs[0].defense_card_id, "7_clubs")
        self.assertEqual(controller.state.phase, GamePhase.DEFENDING)

        events = controller.play_automatic_step()

        self.assertEqual([event.type for event in events], ["cards_discarded"])
        self.assertEqual(controller.state.table.pairs, [])
        self.assertEqual(controller.state.phase, GamePhase.FINISHED)
        self.assertEqual(controller.state.fool_id, "attacker")

    def test_automatic_step_keeps_throw_in_window_before_round_completion(self):
        attacker = RuleBasedBotPlayer("attacker", "Attacker", 0, hand=["6_spades"])
        defender = RuleBasedBotPlayer("defender", "Defender", 1, hand=["7_clubs", "8_clubs"])
        helper = RuleBasedBotPlayer("helper", "Helper", 2, hand=["9_diamonds"])
        controller = scenario_controller(
            [attacker, defender, helper],
            [
                card(Rank.SIX, Suit.CLUBS),
                card(Rank.SIX, Suit.SPADES),
                card(Rank.SEVEN, Suit.CLUBS),
                card(Rank.EIGHT, Suit.CLUBS),
                card(Rank.NINE, Suit.DIAMONDS),
            ],
            attacker_id="attacker",
            defender_id="defender",
        )
        controller.state.table = BattleTable(
            pairs=[BattlePair("6_clubs")],
            defender_initial_hand_size=2,
        )

        defense_events = controller.play_automatic_step()
        throw_in_events = controller.play_automatic_step()

        self.assertEqual([event.type for event in defense_events], ["card_defended"])
        self.assertEqual([event.type for event in throw_in_events], ["card_thrown_in"])
        self.assertEqual(
            [pair.attack_card_id for pair in controller.state.table.pairs],
            ["6_clubs", "6_spades"],
        )
        self.assertEqual(controller.state.phase, GamePhase.DEFENDING)

    def test_play_game_finishes_full_bot_session(self):
        participants = [
            RuleBasedBotPlayer("p1", "Bot 1", 0),
            RuleBasedBotPlayer("p2", "Bot 2", 1),
            RuleBasedBotPlayer("p3", "Bot 3", 2),
            RuleBasedBotPlayer("p4", "Bot 4", 3),
        ]
        controller = DurakGameController(participants, shuffled_standard_36_deck(seed=11))

        events = controller.play_game()

        self.assertTrue(events)
        self.assertEqual(controller.state.phase, GamePhase.FINISHED)
        active_with_cards = [
            player_id
            for player_id, participant in controller.state.participants.items()
            if participant.hand
        ]
        if controller.state.fool_id is None:
            self.assertEqual(active_with_cards, [])
        else:
            self.assertEqual(active_with_cards, [controller.state.fool_id])

    def test_fool_distribution_is_not_strongly_skewed_across_many_games(self):
        fool_counts = {"p1": 0, "p2": 0, "p3": 0, "p4": 0, None: 0}

        for seed in range(200):
            participants = [
                RuleBasedBotPlayer("p1", "Bot 1", 0),
                RuleBasedBotPlayer("p2", "Bot 2", 1),
                RuleBasedBotPlayer("p3", "Bot 3", 2),
                RuleBasedBotPlayer("p4", "Bot 4", 3),
            ]
            controller = DurakGameController(participants, shuffled_standard_36_deck(seed=seed))
            controller.play_game()
            fool_counts[controller.state.fool_id] += 1

        self.assertEqual(sum(fool_counts.values()), 200)
        self.assertLessEqual(fool_counts[None], 10)
        for player_id in ("p1", "p2", "p3", "p4"):
            count = fool_counts[player_id]
            self.assertGreaterEqual(count, 25)
            self.assertLessEqual(count, 75)


if __name__ == "__main__":
    unittest.main()
