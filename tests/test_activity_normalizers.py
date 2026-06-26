"""Current normalization behavior used by activity fixtures."""

import unittest

from activities.bot_hand_activity import BotHandActivity
from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.play_area_slots_activity import PlayAreaSlotsActivity
from activities.visible_cards_hand_activity import VisibleCardsHandDecorator


class ActivityNormalizerTests(unittest.TestCase):
    def test_normalize_pair_accepts_tuple_list_and_dict(self):
        self.assertEqual(CardsSlotActivityDecorator.normalize_pair((1.2, 2.8)), (1, 3))
        self.assertEqual(BotHandActivity.normalize_pair([3.4, 4.4]), (3.4, 4.4))
        self.assertEqual(PlayAreaSlotsActivity.normalize_pair({"x": 5.6, "y": 6.4}), (6, 6))

    def test_normalize_pair_rejects_invalid_values(self):
        with self.assertRaises(TypeError):
            CardsSlotActivityDecorator.normalize_pair("1,2")

    def test_normalize_scale_factor_accepts_none_and_positive_values(self):
        self.assertIsNone(CardsSlotActivityDecorator.normalize_scale_factor(None))
        self.assertEqual(CardsSlotActivityDecorator.normalize_scale_factor("0.5"), 0.5)

    def test_normalize_scale_factor_rejects_zero_and_negative_values(self):
        for value in (0, -1):
            with self.subTest(value=value):
                with self.assertRaises(ValueError):
                    CardsSlotActivityDecorator.normalize_scale_factor(value)

    def test_normalize_cards_preserves_current_string_and_none_behavior(self):
        self.assertEqual(CardsSlotActivityDecorator.normalize_cards(None), ())
        self.assertEqual(CardsSlotActivityDecorator.normalize_cards("cards.a_of_spades"), ("cards.a_of_spades",))
        self.assertEqual(
            VisibleCardsHandDecorator.normalize_cards(["cards.a_of_spades", {"key": "cards.k_of_spades"}]),
            ("cards.a_of_spades", "cards.k_of_spades"),
        )
        with self.assertRaises(TypeError):
            VisibleCardsHandDecorator.normalize_cards(["cards.a_of_spades", 12])

    def test_normalize_max_cards(self):
        self.assertIsNone(CardsSlotActivityDecorator.normalize_max_cards(None))
        self.assertEqual(CardsSlotActivityDecorator.normalize_max_cards("-3"), 0)
        self.assertEqual(VisibleCardsHandDecorator.normalize_max_cards("4"), 4)

    def test_get_fixture_cards_accepts_all_current_aliases(self):
        for key in ("cards", "card_resource_keys", "resource_keys"):
            with self.subTest(key=key):
                self.assertEqual(
                    CardsSlotActivityDecorator.get_fixture_cards({key: ["cards.6_of_clubs"]}),
                    ["cards.6_of_clubs"],
                )

    def test_normalize_card_visual_state_aliases(self):
        aliases = {
            "show": "visible",
            "shown": "visible",
            "card": "visible",
            "hide": "hidden",
            "empty": "hidden",
            "transparent": "hidden",
        }
        for value, expected in aliases.items():
            with self.subTest(value=value):
                self.assertEqual(CardsSlotActivityDecorator.normalize_card_visual_state(value), expected)
