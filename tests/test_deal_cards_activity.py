"""Contracts for generic visual card dealing."""

import unittest

from activities.deal_cards_activity import DealCardsActivity


class DealCardsActivityTests(unittest.TestCase):
    def test_normalize_deals_preserves_target_and_card_order(self):
        deals = DealCardsActivity.normalize_deals(
            [
                {"target_activity_id": "bottom_player_hand", "card_resource_keys": ["cards.6_of_clubs"]},
                {"target_activity_id": "right_player_hand", "card_resource_keys": ["cards.7_of_hearts", "cards.8_of_spades"]},
            ]
        )

        self.assertEqual(
            deals,
            (
                ("bottom_player_hand", "cards.6_of_clubs", 0),
                ("right_player_hand", "cards.7_of_hearts", None),
                ("right_player_hand", "cards.8_of_spades", None),
            ),
        )

    def test_each_normalized_deal_contains_one_resource_key(self):
        deals = DealCardsActivity.normalize_deals(
            [{"target_activity_id": "bottom_player_hand", "card_resource_keys": ["cards.6_of_clubs"]}]
        )

        self.assertEqual(deals[0], ("bottom_player_hand", "cards.6_of_clubs", 0))
