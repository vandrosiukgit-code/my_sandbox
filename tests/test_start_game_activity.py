"""Contracts for the fixture-driven opening deal sequence."""

import unittest

import pygame

from activities.start_game_activity import StartGameActivity
from activities.player_hand_activity import PlayerHandActivity


class FakeResourceManager:
    @staticmethod
    def get_frames(_resource_key):
        return [pygame.Surface((10, 14), pygame.SRCALPHA)]


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
                ("bottom_player_hand", "cards.6_of_clubs", 0),
                ("right_player_hand", "cards.card_back", None),
                ("bottom_player_hand", "cards.7_of_diamonds", 1),
                ("right_player_hand", "cards.card_back", None),
            ),
        )

    def test_start_scenario_runs_prebuilt_sequence(self):
        reset_calls = []
        target_calls = []

        activity = StartGameActivity(
            source_geometry_provider=lambda: {"center": (0, 0), "size": (1, 1)},
            target_geometry_provider=lambda player_id, hand_index: target_calls.append((player_id, hand_index))
            or {"center": (1, 1), "size": (1, 1)},
            reset_recipients=lambda order: reset_calls.append(tuple(order)),
            prepare_bottom_hand=lambda _before, _incoming: None,
            land_card=lambda *_args: None,
            resource_manager=FakeResourceManager,
            card_count=1,
        )

        self.assertTrue(
            activity.start_scenario(
                recipient_order=("bottom_player_hand",),
                bottom_player_card_resource_keys=("cards.6_of_clubs",),
            )
        )
        self.assertEqual(reset_calls, [("bottom_player_hand",)])
        self.assertEqual(target_calls, [("bottom_player_hand", 0)])

    def test_six_card_hand_is_symmetric_about_its_center_axis(self):
        positions = tuple(PlayerHandActivity.calculate_dense_slot_position(index, 6) for index in range(6))

        self.assertAlmostEqual(positions[0], -positions[1])
        self.assertAlmostEqual(positions[2], -positions[3])
        self.assertAlmostEqual(positions[4], -positions[5])
        self.assertGreater(positions[0], 0)

    def test_six_card_hand_has_no_gaps_between_center_and_edges(self):
        positions = sorted(
            PlayerHandActivity.calculate_dense_slot_position(index, 6)
            for index in range(6)
        )
        gaps = [right - left for left, right in zip(positions, positions[1:])]

        for gap in gaps:
            self.assertAlmostEqual(gap, 2 / 5)

    def test_first_two_cards_form_a_right_left_v(self):
        two_card_slots = tuple(PlayerHandActivity.calculate_dense_slot_position(index, 2) for index in range(2))

        self.assertEqual(two_card_slots, (1.0, -1.0))
