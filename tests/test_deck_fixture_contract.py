"""Fixture contract tests for the controller-independent DeckActivity."""

import unittest

from activities.deck_activity import DeckActivity


class DeckFixtureContractTests(unittest.TestCase):
    def test_fixture_forwards_trump_and_deals_to_public_methods(self):
        calls = []

        class FakeDeck:
            def set_trump_resource_key(self, resource_key):
                calls.append(("trump", resource_key))

            def deal_cards(self, deals):
                calls.append(("deals", deals))

        DeckActivity.apply_fixture(
            FakeDeck(),
            {
                "trump_resource_key": "cards.a_of_spades",
                "deals": [{"target_activity_id": "bottom_player_hand", "card_resource_keys": ["cards.6_of_clubs"]}],
            },
        )

        self.assertEqual(calls[0], ("trump", "cards.a_of_spades"))
        self.assertEqual(calls[1][0], "deals")

    def test_deal_contract_rejects_missing_recipient(self):
        with self.assertRaises(ValueError):
            DeckActivity.normalize_deal_requests([{"card_resource_keys": ["cards.6_of_clubs"]}])
