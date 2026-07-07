"""Regression tests for card deal sequence orchestration."""

import unittest

import pygame

from activities.card_deal_sequence_activity import CardDealSequenceActivity


class FakeResourceManager:
    @staticmethod
    def get_frames(_resource_key):
        return [pygame.Surface((10, 14), pygame.SRCALPHA)]


class CardDealSequenceActivityTests(unittest.TestCase):
    def make_activity(self, target_calls=None, reveal_calls=None, prepare_calls=None):
        target_calls = target_calls if target_calls is not None else []
        reveal_calls = reveal_calls if reveal_calls is not None else []
        prepare_calls = prepare_calls if prepare_calls is not None else []
        return CardDealSequenceActivity(
            source_geometry_provider=lambda: {"center": (0, 0), "size": (10, 14)},
            target_geometry_provider=lambda player_id, hand_index: target_calls.append((player_id, hand_index))
            or {"center": (20, 20), "size": (10, 14)},
            prepare_hands=lambda before, incoming: prepare_calls.append((before, incoming)),
            reveal_card=lambda *args: reveal_calls.append(args),
            resource_manager=FakeResourceManager,
        )

    def finish_current_action(self, activity):
        self.assertIsNotNone(activity.current_action)
        activity.update(0)

    def test_start_sequence_starts_first_prebuilt_step(self):
        target_calls = []
        activity = self.make_activity(target_calls=target_calls)

        self.assertTrue(activity.start_sequence((("bottom_player_hand", "cards.6_of_clubs", 0),), duration=0.0))

        self.assertTrue(activity.sequence_active)
        self.assertEqual(target_calls, [("bottom_player_hand", 0)])
        self.assertEqual(len(activity.iter_generated_groups()), 1)

    def test_start_sequence_rejects_second_sequence_while_active(self):
        activity = self.make_activity()

        self.assertTrue(activity.start_sequence((("bottom_player_hand", "cards.6_of_clubs", 0),), duration=0.0))
        self.assertFalse(activity.start_sequence((("bottom_player_hand", "cards.7_of_clubs", 1),), duration=0.0))

    def test_sequence_reveals_card_and_clears_flight_group_after_last_step(self):
        reveal_calls = []
        activity = self.make_activity(reveal_calls=reveal_calls)
        activity.start_sequence((("bottom_player_hand", "cards.6_of_clubs", 0),), duration=0.0)

        self.finish_current_action(activity)

        self.assertEqual(reveal_calls, [("bottom_player_hand", "cards.6_of_clubs", 0)])
        self.assertFalse(activity.sequence_active)
        self.assertEqual(activity.iter_generated_groups(), ())

    def test_sequence_safe_point_fires_after_reveal(self):
        events = []
        activity = CardDealSequenceActivity(
            source_geometry_provider=lambda: {"center": (0, 0), "size": (10, 14)},
            target_geometry_provider=lambda _player_id, _hand_index: {"center": (20, 20), "size": (10, 14)},
            prepare_hands=lambda _before, _incoming: None,
            reveal_card=lambda *args: events.append(("reveal", args)),
            resource_manager=FakeResourceManager,
            on_safe_point=lambda safe_point, payload: events.append((safe_point, payload["player_id"], payload["hand_index"])),
        )

        activity.start_sequence((("bottom_player_hand", "cards.6_of_clubs", 0),), duration=0.0)
        self.finish_current_action(activity)

        self.assertEqual(
            events,
            [
                ("reveal", ("bottom_player_hand", "cards.6_of_clubs", 0)),
                ("deal.step.safe_point", "bottom_player_hand", 0),
            ],
        )

    def test_start_deal_prepares_hands_by_default(self):
        prepare_calls = []
        activity = self.make_activity(prepare_calls=prepare_calls)

        activity.start_deal(
            {
                "hands_before_deal": {"bottom_player_hand": ["cards.5_of_clubs"]},
                "cards_to_deal": {"bottom_player_hand": ["cards.6_of_clubs"]},
                "deal_order": ("bottom_player_hand",),
                "duration": 0.0,
            }
        )

        self.assertEqual(
            prepare_calls,
            [
                (
                    {"bottom_player_hand": ("cards.5_of_clubs",)},
                    {"bottom_player_hand": ("cards.6_of_clubs",)},
                )
            ],
        )

    def test_start_deal_skips_prepare_when_hands_are_prepared(self):
        prepare_calls = []
        activity = self.make_activity(prepare_calls=prepare_calls)

        activity.start_deal(
            {
                "hands_before_deal": {"bottom_player_hand": ["cards.5_of_clubs"]},
                "cards_to_deal": {"bottom_player_hand": ["cards.6_of_clubs"]},
                "deal_order": ("bottom_player_hand",),
                "duration": 0.0,
                "hands_prepared": True,
            }
        )

        self.assertEqual(prepare_calls, [])

    def test_start_deal_uses_round_robin_steps(self):
        target_calls = []
        activity = self.make_activity(target_calls=target_calls)
        activity.start_deal(
            {
                "hands_before_deal": {"bottom": [], "right": []},
                "cards_to_deal": {
                    "bottom": ["cards.6_of_clubs", "cards.7_of_clubs"],
                    "right": ["cards.8_of_clubs"],
                },
                "deal_order": ("bottom", "right"),
                "duration": 0.0,
                "hands_prepared": True,
            }
        )

        self.assertEqual(target_calls, [("bottom", 0)])
        self.finish_current_action(activity)
        self.assertEqual(target_calls, [("bottom", 0), ("right", 0)])
        self.finish_current_action(activity)
        self.assertEqual(target_calls, [("bottom", 0), ("right", 0), ("bottom", 1)])
