"""Contracts for the fixture-driven opening deal sequence."""

import unittest

from activities.start_game_activity import StartGameActivity
from activities.player_hand_activity import PlayerHandActivity


class StartGameActivityTests(unittest.TestCase):
    def test_deals_one_card_to_each_recipient_before_next_round(self):
        sequence = StartGameActivity.build_recipient_sequence(("bottom", "right", "top", "left"), 2)

        self.assertEqual(sequence, ("bottom", "right", "top", "left", "bottom", "right", "top", "left"))

    def test_bottom_player_receives_fixture_face_cards_in_deal_order(self):
        sequence = StartGameActivity.build_deal_sequence(
            ("bottom_player_hand", "right_player_hand"),
            2,
            ("cards.6_of_clubs", "cards.7_of_diamonds"),
            "cards.card_back",
        )

        self.assertEqual(
            sequence,
            (
                ("bottom_player_hand", "cards.6_of_clubs"),
                ("right_player_hand", "cards.card_back"),
                ("bottom_player_hand", "cards.7_of_diamonds"),
                ("right_player_hand", "cards.card_back"),
            ),
        )

    def test_six_card_hand_is_symmetric_about_its_center_axis(self):
        positions = tuple(PlayerHandActivity.calculate_dense_slot_position(index, 6) for index in range(6))

        self.assertAlmostEqual(positions[0], -positions[1])
        self.assertAlmostEqual(positions[2], -positions[3])
        self.assertAlmostEqual(positions[4], -positions[5])
        self.assertLess(positions[0], 0)
