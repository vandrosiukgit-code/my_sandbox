"""Slot transfer behavior before extracting batch action helpers."""

import unittest

from activities.play_area_slots_activity import PlayAreaSlotsActivity


class FakeSlotActivity:
    def __init__(self, cards=()):
        self.card_resource_keys = tuple(cards)
        self.max_cards = 2
        self.set_cards_calls = []

    def set_cards(self, cards, force=False):
        self.card_resource_keys = tuple(cards)
        self.set_cards_calls.append((tuple(cards), force))

    def get_card_screen_geometry(self, index):
        return {"center": (10 + index, 20), "size": (10, 14), "angle_degrees": 0.0}

    def get_next_card_screen_geometry(self, context=None):
        index = (context or {}).get("slot_card_index", len(self.card_resource_keys))
        return {"center": (30 + index, 40), "size": (10, 14), "angle_degrees": 0.0}


class FakeAction:
    def __init__(self):
        self.cancelled = False

    def cancel(self):
        self.cancelled = True


class PlayAreaSlotsTransferTests(unittest.TestCase):
    def make_activity(self):
        activity = PlayAreaSlotsActivity.__new__(PlayAreaSlotsActivity)
        activity.slot_transfer_actions = []
        activity.pending_slot_transfer_batches = []
        activity.pending_player_card_data = []
        activity.next_overflow_direction = -1
        return activity

    def test_build_slot_cards_transfer_specs_creates_specs_and_clears_source(self):
        activity = self.make_activity()
        source = FakeSlotActivity(("cards.6_of_clubs", "cards.7_of_clubs"))
        target = FakeSlotActivity(())

        specs = activity.build_slot_cards_transfer_specs(source, target)

        self.assertEqual([spec["resource_key"] for spec in specs], ["cards.6_of_clubs", "cards.7_of_clubs"])
        self.assertEqual([spec["target_index"] for spec in specs], [0, 1])
        self.assertEqual(source.card_resource_keys, ())
        self.assertEqual(source.set_cards_calls[-1], ((), True))

    def test_queue_slot_transfer_batch_defers_when_actions_are_running(self):
        activity = self.make_activity()
        activity.slot_transfer_actions = [FakeAction()]

        activity.queue_slot_transfer_batch(({"resource_key": "cards.6_of_clubs"},))

        self.assertEqual(len(activity.pending_slot_transfer_batches), 1)

    def test_has_pending_slot_transfers_checks_actions_and_batches(self):
        activity = self.make_activity()
        self.assertFalse(activity.has_pending_slot_transfers())

        activity.pending_slot_transfer_batches.append(({"resource_key": "cards.6_of_clubs"},))
        self.assertTrue(activity.has_pending_slot_transfers())

        activity.pending_slot_transfer_batches = []
        activity.slot_transfer_actions = [FakeAction()]
        self.assertTrue(activity.has_pending_slot_transfers())

    def test_land_slot_transfer_card_extends_target_to_index(self):
        activity = self.make_activity()
        target = FakeSlotActivity(("cards.6_of_clubs",))

        activity.land_slot_transfer_card(target, 2, "cards.8_of_clubs")

        self.assertEqual(
            target.card_resource_keys,
            ("cards.6_of_clubs", "cards.8_of_clubs", "cards.8_of_clubs"),
        )

    def test_clear_slot_cards_clears_slots_actions_batches_and_pending_cards(self):
        activity = self.make_activity()
        first = FakeSlotActivity(("cards.6_of_clubs",))
        second = FakeSlotActivity(("cards.7_of_clubs",))
        running_action = FakeAction()
        activity.slot_activities = {"first": first, "second": second}
        activity.slot_transfer_actions = [running_action]
        activity.pending_slot_transfer_batches = [({"resource_key": "cards.8_of_clubs"},)]
        activity.pending_player_card_data = [{"resource_key": "cards.9_of_clubs"}]

        activity.clear_slot_cards()

        self.assertEqual(first.card_resource_keys, ())
        self.assertEqual(second.card_resource_keys, ())
        self.assertTrue(running_action.cancelled)
        self.assertEqual(activity.slot_transfer_actions, [])
        self.assertEqual(activity.pending_slot_transfer_batches, [])
        self.assertEqual(activity.pending_player_card_data, [])
        self.assertEqual(activity.next_overflow_direction, 1)

    def test_resolve_slot_local_rect_prefers_explicit_override(self):
        activity = self.make_activity()
        activity.slot_local_rects = {"cards_slot_frame_8": (24, 512, 138, 136)}

        rect = activity.resolve_slot_local_rect(
            "cards_slot_frame_8",
            (138, 136),
            (640, 360),
            (143, 148),
            (-2, 1),
        )

        self.assertEqual(rect, (24, 512, 138, 136))

    def test_apply_fixture_merges_slot_local_rect_overrides(self):
        activity = self.make_activity()
        activity.slot_count = activity.DEFAULT_SLOT_COUNT
        activity.columns = 1
        activity.spacing = activity.DEFAULT_SPACING
        activity.origin = None
        activity.center = None
        activity.step = None
        activity.slot_offsets = None
        activity.slot_local_rects = {"cards_slot_frame": (1, 2, 3, 4)}
        activity.slot_activity_fixture = dict(activity.DEFAULT_SLOT_ACTIVITY_FIXTURE)
        activity.apply_layout = lambda: None

        activity.apply_fixture(
            {
                "slot_local_rects": {
                    "cards_slot_frame_8": [24, 512, 138, 136],
                },
            }
        )

        self.assertEqual(
            activity.slot_local_rects,
            {
                "cards_slot_frame": (1, 2, 3, 4),
                "cards_slot_frame_8": (24, 512, 138, 136),
            },
        )
