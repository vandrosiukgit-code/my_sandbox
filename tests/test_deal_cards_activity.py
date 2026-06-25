"""Contracts for generic visual card dealing."""

import unittest

import pygame

from activities.deal_cards_activity import DealCardsActivity


class FakeResourceManager:
    @staticmethod
    def get_frames(_resource_key):
        return [pygame.Surface((10, 14), pygame.SRCALPHA)]


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

    def test_start_deals_runs_prebuilt_sequence(self):
        target_calls = []
        activity = DealCardsActivity(
            source_geometry_provider=lambda: {"center": (0, 0), "size": (1, 1)},
            target_geometry_provider=lambda player_id, hand_index: target_calls.append((player_id, hand_index))
            or {"center": (1, 1), "size": (1, 1)},
            prepare_bottom_hand=lambda _before, _incoming: None,
            land_card=lambda *_args: None,
            resource_manager=FakeResourceManager,
        )

        self.assertTrue(
            activity.start_deals(
                [{"target_activity_id": "bottom_player_hand", "card_resource_keys": ["cards.6_of_clubs"]}],
                duration=0.1,
            )
        )
        self.assertEqual(target_calls, [("bottom_player_hand", 0)])
