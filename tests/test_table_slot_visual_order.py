"""Regression tests for visual stacking order of table slot cards."""

import unittest

import pygame

from activities.bot_turn_activity import BotTurnActivity
from activities.cards_slot_activity import CardsSlotActivityDecorator
from activities.play_area_slots_activity import PlayAreaSlotsActivity
from activities.player_turn_activity import PlayerTurnActivity


class FakeResourceManager:
    @staticmethod
    def get_frames(resource_key):
        surface = pygame.Surface((10, 14), pygame.SRCALPHA)
        surface.fill((255, 255, 255, 255))
        _ = resource_key
        return [surface]


class FakeFrame:
    def __init__(self):
        self.id = "slot_frame"
        self.local_rect = pygame.Rect(0, 0, 120, 80)
        self.content_rect = self.local_rect.copy()
        self.groups = {}

    def place_group_local(self, group, position):
        group.set_parent_frame(self)
        group.set_local_position(*position)
        self.groups[group.id] = group

    def set_group_origin(self, group_id, position):
        self.groups[group_id].set_local_position(*position)

    def remove_group(self, group_id):
        self.groups.pop(group_id, None)

    def to_screen(self, position):
        return int(round(position[0])), int(round(position[1]))

    def to_local(self, position):
        return int(round(position[0])), int(round(position[1]))

    def get_content_screen_scale(self):
        return 1.0


class TableSlotVisualOrderTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        pygame.init()

    @classmethod
    def tearDownClass(cls):
        pygame.quit()

    def make_slot_activity(self, cards=()):
        activity = CardsSlotActivityDecorator(
            FakeFrame(),
            cards=cards,
            resource_manager=FakeResourceManager,
            max_cards=2,
        )
        activity.start()
        return activity

    def test_cards_slot_activity_draw_order_keeps_first_card_under_second(self):
        activity = self.make_slot_activity(("cards.6_of_clubs", "cards.7_of_hearts"))

        draw_order = [group.card_resource_key for group in activity.iter_groups_in_draw_order()]

        self.assertEqual(draw_order, ["cards.6_of_clubs", "cards.7_of_hearts"])

    def test_play_area_slots_player_placement_keeps_first_card_under_second(self):
        central_slot = self.make_slot_activity()
        activity = PlayAreaSlotsActivity.__new__(PlayAreaSlotsActivity)
        activity.slot_transfer_actions = []
        activity.pending_slot_transfer_batches = []
        activity.pending_player_card_data = []
        activity.managed_slot_ids = ["cards_slot_frame"]
        activity.slot_activities = {"cards_slot_frame": central_slot}
        activity.prepare_central_slot_for_next_card = lambda: True
        activity.get_central_slot_activity = lambda: central_slot
        activity.has_pending_slot_transfers = lambda: False

        self.assertTrue(activity.place_player_card({"resource_key": "cards.6_of_clubs", "slot_card_index": 0}))
        self.assertTrue(activity.place_player_card({"resource_key": "cards.7_of_hearts", "slot_card_index": 1}))

        draw_order = [group.card_resource_key for group in central_slot.iter_groups_in_draw_order()]
        self.assertEqual(draw_order, ["cards.6_of_clubs", "cards.7_of_hearts"])

    def test_player_turn_final_placement_keeps_first_card_under_second(self):
        central_slot = self.make_slot_activity(("cards.6_of_clubs",))

        class PlayArea:
            started = True

            def start(self):
                return None

            def update(self, _dt):
                return None

            def finish(self):
                return None

            def place_player_card(self, card_data):
                return central_slot.place_player_card(card_data)

            def get_player_turn_target_screen_geometry(self, turn_context=None):
                return central_slot.get_player_turn_target_screen_geometry(turn_context)

            def has_pending_slot_transfers(self):
                return False

        activity = PlayerTurnActivity(PlayArea())
        activity.turn_context = {
            "resource_key": "cards.7_of_hearts",
            "card_id": "cards.7_of_hearts",
            "slot_card_index": 1,
            "target_screen_geometry": {"center": (0, 0), "size": (10, 14)},
        }

        self.assertTrue(activity.place_turn_card_in_target_slot())
        draw_order = [group.card_resource_key for group in central_slot.iter_groups_in_draw_order()]
        self.assertEqual(draw_order, ["cards.6_of_clubs", "cards.7_of_hearts"])

    def test_bot_turn_final_placement_keeps_first_card_under_second(self):
        central_slot = self.make_slot_activity(("cards.6_of_clubs",))

        class PlayArea:
            def place_player_card(self, card_data):
                return central_slot.place_player_card(card_data)

        play_area = PlayArea()
        activity = BotTurnActivity(get_activity=lambda activity_id: play_area if activity_id == "play_area_frame" else None)
        activity.remove_flight_group = lambda _group: None

        activity.land_flight_group(
            object(),
            "right_player_hand",
            object(),
            "cards_slot_frame",
            1,
            "cards.7_of_hearts",
        )

        draw_order = [group.card_resource_key for group in central_slot.iter_groups_in_draw_order()]
        self.assertEqual(draw_order, ["cards.6_of_clubs", "cards.7_of_hearts"])
