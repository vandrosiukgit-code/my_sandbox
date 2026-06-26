"""Generated visual group lifecycle contracts for activities."""

import unittest

import pygame

from activities.card_deal_sequence_activity import CardDealSequenceActivity
from activities.discard_table_activity import DiscardTableActivity
from activities.player_turn_activity import PlayerTurnActivity


class FakeResourceManager:
    @staticmethod
    def get_frames(_resource_key):
        return [pygame.Surface((10, 14), pygame.SRCALPHA)]


class FakePlayAreaSlotsActivity:
    def __init__(self):
        self.started = False
        self.generated_groups = ("slot-group",)

    def start(self):
        self.started = True

    def update(self, _dt):
        pass

    def finish(self):
        self.started = False

    def iter_generated_groups(self):
        return self.generated_groups


class GeneratedGroupLifecycleTests(unittest.TestCase):
    def test_card_deal_sequence_exposes_and_cleans_flight_group(self):
        activity = CardDealSequenceActivity(
            source_geometry_provider=lambda: {"center": (0, 0), "size": (10, 14)},
            target_geometry_provider=lambda _player_id, _hand_index: {"center": (20, 20), "size": (10, 14)},
            prepare_hands=lambda _before, _incoming: None,
            reveal_card=lambda *_args: None,
            resource_manager=FakeResourceManager,
        )

        activity.start_sequence((("bottom_player_hand", "cards.6_of_clubs", 0),), duration=0.0)
        groups = activity.iter_generated_groups()

        self.assertEqual(len(groups), 1)
        self.assertTrue(groups[0].id.startswith("card_deal_sequence.flight_card."))

        activity.update(0)

        self.assertEqual(activity.iter_generated_groups(), ())

    def test_player_turn_combines_flight_and_play_area_groups(self):
        play_area = FakePlayAreaSlotsActivity()
        activity = PlayerTurnActivity(play_area)
        activity.flight_groups = ["flight-group"]

        self.assertEqual(activity.iter_generated_groups(), ("flight-group", "slot-group"))

    def test_discard_table_exposes_groups_during_fade_and_clears_on_finish(self):
        table_cards = [
            {
                "resource_key": "cards.6_of_clubs",
                "geometry": {"center": (10, 10), "size": (10, 14), "angle_degrees": 0.0},
            }
        ]
        removed_cards = []
        activity = DiscardTableActivity(
            get_table_cards=lambda: tuple(table_cards),
            set_table_cards=lambda _slots: None,
            remove_table_card=lambda card: removed_cards.append(card),
            clear_table=lambda: table_cards.clear(),
            resource_manager=FakeResourceManager,
            duration=0.0,
        )

        self.assertTrue(activity.start_discard({"slot": ["cards.6_of_clubs"]}))

        self.assertEqual(len(activity.iter_generated_groups()), 1)
        self.assertEqual(removed_cards[0]["resource_key"], "cards.6_of_clubs")

        activity.update(0)

        self.assertEqual(activity.iter_generated_groups(), ())
        self.assertEqual(table_cards, [])
