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
        self.draw_groups = ("slot-draw-group",)

    def start(self):
        self.started = True

    def update(self, _dt):
        pass

    def finish(self):
        self.started = False

    def iter_generated_groups(self):
        return self.generated_groups

    def iter_groups_in_draw_order(self):
        return self.draw_groups


class FakeFlightAction:
    def __init__(self, events):
        self.events = events
        self.started = False

    def start(self):
        self.started = True
        self.events.append("action.start")


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
        self.assertEqual(activity.iter_groups_in_draw_order(), ("slot-draw-group", "flight-group"))

    def test_player_turn_removes_source_card_before_starting_flight(self):
        play_area = FakePlayAreaSlotsActivity()
        events = []

        class TestPlayerTurnActivity(PlayerTurnActivity):
            def create_player_card_action(self, turn_context):
                _ = turn_context
                return FakeFlightAction(events)

        activity = TestPlayerTurnActivity(
            play_area,
            remove_source_card=lambda _turn_context: events.append("source.remove") or True,
        )

        self.assertTrue(
            activity.start_turn(
                {
                    "resource_key": "cards.6_of_clubs",
                    "source_screen_geometry": {"center": (0, 0), "size": (10, 14)},
                    "target_screen_geometry": {"center": (20, 20), "size": (10, 14)},
                }
            )
        )
        self.assertEqual(events, ["source.remove", "action.start"])
        self.assertTrue(activity.source_card_removed)

    def test_player_turn_safe_point_fires_after_action_finish_and_slot_commit(self):
        events = []

        class PlayArea(FakePlayAreaSlotsActivity):
            def place_player_card(self, card_data):
                events.append(("slot.place", card_data["resource_key"]))
                return True

            def has_pending_slot_transfers(self):
                return False

            def get_player_turn_target_screen_geometry(self, _turn_context=None):
                return {"center": (20, 20), "size": (10, 14)}

        class FinishedFlightAction(FakeFlightAction):
            def update(self, _dt):
                self.events.append("action.update")

            def is_finished(self):
                return True

        class TestPlayerTurnActivity(PlayerTurnActivity):
            def create_player_card_action(self, turn_context):
                _ = turn_context
                return FinishedFlightAction(events)

        activity = TestPlayerTurnActivity(
            PlayArea(),
            remove_source_card=lambda _turn_context: events.append("source.remove") or True,
            on_safe_point=lambda safe_point, payload: events.append((safe_point, payload["resource_key"])),
        )

        self.assertTrue(
            activity.start_turn(
                {
                    "resource_key": "cards.6_of_clubs",
                    "card_id": "cards.6_of_clubs",
                    "source_screen_geometry": {"center": (0, 0), "size": (10, 14)},
                    "target_screen_geometry": {"center": (20, 20), "size": (10, 14)},
                }
            )
        )

        activity.update(0.0)

        self.assertEqual(
            events,
            [
                "source.remove",
                "action.start",
                "action.update",
                ("slot.place", "cards.6_of_clubs"),
                ("turn.played.safe_point", "cards.6_of_clubs"),
            ],
        )

    def test_player_turn_safe_point_waits_for_pending_slot_transfers(self):
        events = []

        class PlayArea(FakePlayAreaSlotsActivity):
            def __init__(self):
                super().__init__()
                self.pending_checks = [True, False]

            def place_player_card(self, card_data):
                events.append(("slot.place", card_data["resource_key"]))
                return True

            def has_pending_slot_transfers(self):
                if self.pending_checks:
                    return self.pending_checks.pop(0)
                return False

            def get_player_turn_target_screen_geometry(self, _turn_context=None):
                return {"center": (20, 20), "size": (10, 14)}

        class FinishedFlightAction(FakeFlightAction):
            def update(self, _dt):
                self.events.append("action.update")

            def is_finished(self):
                return True

        class TestPlayerTurnActivity(PlayerTurnActivity):
            def create_player_card_action(self, turn_context):
                _ = turn_context
                return FinishedFlightAction(events)

        activity = TestPlayerTurnActivity(
            PlayArea(),
            remove_source_card=lambda _turn_context: events.append("source.remove") or True,
            on_safe_point=lambda safe_point, payload: events.append((safe_point, payload["resource_key"])),
        )

        self.assertTrue(
            activity.start_turn(
                {
                    "resource_key": "cards.6_of_clubs",
                    "card_id": "cards.6_of_clubs",
                    "source_screen_geometry": {"center": (0, 0), "size": (10, 14)},
                    "target_screen_geometry": {"center": (20, 20), "size": (10, 14)},
                }
            )
        )

        activity.update(0.0)
        self.assertEqual(
            events,
            [
                "source.remove",
                "action.start",
                "action.update",
                ("slot.place", "cards.6_of_clubs"),
            ],
        )

        activity.update(0.0)
        self.assertEqual(events[-1], ("turn.played.safe_point", "cards.6_of_clubs"))

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
