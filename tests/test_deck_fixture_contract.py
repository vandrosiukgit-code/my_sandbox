"""Fixture contract tests for the controller-independent DeckActivity."""

import unittest
import pygame

from activities.deck_activity import DeckActivity


class DeckFixtureContractTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def test_fixture_forwards_trump_and_deals_to_public_methods(self):
        calls = []

        class FakeDeck:
            def __init__(self):
                self.deck_empty_alpha = None
                self.trump_taken_alpha = None

            def set_trump_resource_key(self, resource_key):
                calls.append(("trump", resource_key))

            def set_deck_count(self, deck_count):
                calls.append(("deck_count", deck_count))

            def deal_cards(self, deals):
                calls.append(("deals", deals))

        DeckActivity.apply_fixture(
            FakeDeck(),
            {
                "trump_resource_key": "cards.a_of_spades",
                "deck_count": 0,
                "deck_empty_alpha": 101,
                "trump_taken_alpha": 77,
                "deals": [{"target_activity_id": "bottom_player_hand", "card_resource_keys": ["cards.6_of_clubs"]}],
            },
        )

        self.assertEqual(calls[0], ("trump", "cards.a_of_spades"))
        self.assertEqual(calls[1], ("deck_count", 0))
        self.assertEqual(calls[2][0], "deals")
        self.assertEqual(calls[0][1], "cards.a_of_spades")

    def test_deal_contract_rejects_missing_recipient(self):
        with self.assertRaises(ValueError):
            DeckActivity.normalize_deal_requests([{"card_resource_keys": ["cards.6_of_clubs"]}])

    def test_empty_deck_frame_is_dimmed_and_semitransparent(self):
        frame = pygame.Surface((10, 10), pygame.SRCALPHA)
        frame.fill((255, 200, 100, 255))

        dimmed = DeckActivity.build_dimmed_frame(frame, 111)

        self.assertEqual(dimmed.get_alpha(), 111)
        self.assertNotEqual(dimmed.get_at((0, 0))[:3], frame.get_at((0, 0))[:3])

    def test_fixture_updates_transparency_settings_before_deck_state(self):
        calls = []

        class FakeDeck:
            def __init__(self):
                self.deck_empty_alpha = 120
                self.trump_taken_alpha = 120

            def set_trump_resource_key(self, _resource_key):
                return None

            def set_deck_count(self, deck_count):
                calls.append((deck_count, self.deck_empty_alpha, self.trump_taken_alpha))

            def deal_cards(self, _deals):
                return None

        fake = FakeDeck()
        DeckActivity.apply_fixture(
            fake,
            {
                "deck_empty_alpha": 88,
                "trump_taken_alpha": 66,
                "deck_count": 0,
            },
        )

        self.assertEqual(calls, [(0, 88, 66)])
